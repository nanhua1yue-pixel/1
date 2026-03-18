"""
数据同步脚本 - 从旺店通拉取库存/销售数据，识别滞销品
设置为定时任务（宝塔面板计划任务，建议每天凌晨2点执行）

使用方式:
    cd /www/wwwroot/purchase-decision
    source venv/bin/activate && source .env
    python scripts/sync_data.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from backend.app import create_app
from backend.models.database import db
from backend.models.slow_moving import SlowMovingSKU
from backend.models.inventory import SKUDetail, InventorySnapshot
from backend.utils.wdt_client import wdt_client


def sync_stock_data(app):
    """同步库存数据"""
    print(f"[{datetime.now()}] 开始同步库存数据...")

    with app.app_context():
        try:
            all_stock = wdt_client.fetch_all_pages(wdt_client.get_stock_query)
            print(f"  获取到 {len(all_stock)} 条库存记录")

            for item in all_stock:
                sku_code = item.get('spec_no') or item.get('goods_no', '')
                if not sku_code:
                    continue

                sku = SKUDetail.query.filter_by(sku_code=sku_code).first()
                if not sku:
                    sku = SKUDetail(sku_code=sku_code)
                    db.session.add(sku)

                sku.goods_name = item.get('goods_name', '')
                sku.spec_name = item.get('spec_name', '')
                sku.current_stock = int(item.get('stock_num', 0))
                sku.cost_price = float(item.get('cost_price', 0))
                sku.stock_amount = sku.current_stock * float(sku.cost_price or 0)
                sku.warehouse = item.get('warehouse_name', '')
                sku.wdt_goods_id = str(item.get('goods_id', ''))
                sku.synced_at = datetime.now()

            db.session.commit()
            print(f"  库存数据同步完成")

        except Exception as e:
            print(f"  库存同步失败: {e}")
            db.session.rollback()


def sync_sales_data(app):
    """同步销售数据（近90天）"""
    print(f"[{datetime.now()}] 开始同步销售数据...")

    with app.app_context():
        try:
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            start_30d = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            start_60d = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
            start_90d = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')

            # 获取销售统计
            sales_data = wdt_client.fetch_all_pages(
                wdt_client.get_sales_stats,
                start_time=start_30d,
                end_time=end_time,
            )
            print(f"  获取到 {len(sales_data)} 条销售记录")

            for item in sales_data:
                sku_code = item.get('spec_no') or item.get('goods_no', '')
                if not sku_code:
                    continue

                sku = SKUDetail.query.filter_by(sku_code=sku_code).first()
                if sku:
                    sku.sales_30d = int(item.get('sell_num', 0))
                    sku.avg_daily_sales = sku.sales_30d / 30.0
                    if sku.avg_daily_sales > 0:
                        sku.turnover_days = sku.current_stock / sku.avg_daily_sales
                        sku.stock_months = sku.turnover_days / 30.0

            db.session.commit()
            print(f"  销售数据同步完成")

        except Exception as e:
            print(f"  销售同步失败: {e}")
            db.session.rollback()


def identify_slow_moving(app):
    """识别滞销品（月销<10）并写入滞销品表"""
    print(f"[{datetime.now()}] 开始识别滞销品...")

    with app.app_context():
        current_period = datetime.now().strftime('%Y-%m')

        # 查找月销<10的SKU
        slow_skus = SKUDetail.query.filter(
            SKUDetail.sales_30d < 10,
            SKUDetail.current_stock > 0,
        ).all()

        new_count = 0
        for sku in slow_skus:
            # 排除近2个月新品和库存为0的
            if sku.is_new:
                continue

            existing = SlowMovingSKU.query.filter_by(
                sku_code=sku.sku_code, period=current_period
            ).first()

            if not existing:
                # 确定滞销类型
                if sku.sales_30d == 0:
                    slow_type = 'zero_sale'
                elif sku.sales_30d < 5:
                    slow_type = 'very_slow'
                else:
                    slow_type = 'slow'

                slow_item = SlowMovingSKU(
                    sku_code=sku.sku_code,
                    goods_name=sku.goods_name,
                    spec_name=sku.spec_name,
                    category=sku.category,
                    supplier=sku.supplier,
                    current_stock=sku.current_stock,
                    stock_amount=sku.stock_amount,
                    cost_price=sku.cost_price,
                    monthly_sales_30d=sku.sales_30d,
                    monthly_sales_60d=sku.sales_60d,
                    monthly_sales_90d=sku.sales_90d,
                    stock_days=int(sku.turnover_days or 0),
                    slow_type=slow_type,
                    status='pending',
                    period=current_period,
                    wdt_goods_id=sku.wdt_goods_id,
                    synced_at=datetime.now(),
                )
                db.session.add(slow_item)
                new_count += 1
            else:
                # 更新库存和销售数据
                existing.current_stock = sku.current_stock
                existing.stock_amount = sku.stock_amount
                existing.monthly_sales_30d = sku.sales_30d
                existing.synced_at = datetime.now()

        db.session.commit()
        total = SlowMovingSKU.query.filter_by(period=current_period).count()
        print(f"  识别完成: 新增{new_count}个滞销品，当期总计{total}个")


def create_snapshot(app):
    """创建库存快照"""
    print(f"[{datetime.now()}] 创建库存快照...")

    with app.app_context():
        today = datetime.now().date()

        # 判断快照类型
        snapshot_type = 'daily'
        if today.day == 1:
            snapshot_type = 'month_start'
        elif today.day >= 28:
            # 月末
            next_month = today.replace(day=28) + timedelta(days=4)
            if next_month.month != today.month:
                snapshot_type = 'month_end'

        total_sku = SKUDetail.query.count()
        total_amount = db.session.query(db.func.sum(SKUDetail.stock_amount)).scalar() or 0
        slow_lt10 = SKUDetail.query.filter(SKUDetail.sales_30d < 10, SKUDetail.current_stock > 0).count()
        slow_lt300_amount = db.session.query(
            db.func.sum(SKUDetail.stock_amount)
        ).filter(SKUDetail.sales_30d < 300, SKUDetail.current_stock > 0).scalar() or 0
        high_turnover = SKUDetail.query.filter(SKUDetail.stock_months > 2).count()

        snapshot = InventorySnapshot(
            snapshot_date=today,
            snapshot_type=snapshot_type,
            total_sku_count=total_sku,
            total_stock_amount=total_amount,
            slow_sku_count_lt10=slow_lt10,
            slow_inventory_amount_lt300=slow_lt300_amount,
            high_turnover_sku_count=high_turnover,
        )
        db.session.add(snapshot)
        db.session.commit()
        print(f"  快照创建完成: {snapshot_type}")


if __name__ == '__main__':
    app = create_app()

    print("=" * 50)
    print("采购补货决策系统 - 数据同步")
    print("=" * 50)

    sync_stock_data(app)
    sync_sales_data(app)
    identify_slow_moving(app)
    create_snapshot(app)

    print(f"\n[{datetime.now()}] 全部同步完成！")
