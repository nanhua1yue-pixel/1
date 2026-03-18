"""
库存与销售数据模型 - 从旺店通同步
"""
from .database import db, BaseModel


class InventorySnapshot(BaseModel):
    """库存快照 - 每日/月初月末"""
    __tablename__ = 'inventory_snapshot'

    snapshot_date = db.Column(db.Date, nullable=False, index=True, comment='快照日期')
    snapshot_type = db.Column(db.String(20), default='daily',
                              comment='快照类型: daily/month_start/month_end')

    total_sku_count = db.Column(db.Integer, default=0, comment='总SKU数')
    total_stock_amount = db.Column(db.Numeric(14, 2), default=0, comment='库存总金额(元)')
    total_stock_qty = db.Column(db.Integer, default=0, comment='库存总数量')

    # 周转相关
    avg_turnover_days = db.Column(db.Numeric(6, 1), comment='平均库存周转天数(加权)')
    turnover_days_gt1000 = db.Column(db.Numeric(6, 1), comment='月销>1000的周转天数')
    turnover_days_lt1000 = db.Column(db.Numeric(6, 1), comment='月销<1000的周转天数')
    n_index = db.Column(db.Numeric(4, 2), comment='N指数')

    # 高周转SKU (库存>2个月)
    high_turnover_sku_count = db.Column(db.Integer, default=0, comment='高周转SKU数(库存>2月)')

    # 滞销统计
    slow_sku_count_lt10 = db.Column(db.Integer, default=0, comment='月销<10的SKU数')
    slow_sku_count_lt5 = db.Column(db.Integer, default=0, comment='月销<5的SKU数')
    slow_sku_count_zero = db.Column(db.Integer, default=0, comment='0销量SKU数')
    slow_inventory_amount_lt300 = db.Column(db.Numeric(14, 2), default=0, comment='月销<300链接库存金额')

    # 缺货统计
    stockout_sku_count = db.Column(db.Integer, default=0, comment='缺货SKU数')
    no_chain_rate = db.Column(db.Numeric(5, 4), comment='无链路占比')

    def to_dict(self):
        return {
            'id': self.id,
            'snapshot_date': self.snapshot_date.isoformat() if self.snapshot_date else None,
            'snapshot_type': self.snapshot_type,
            'total_sku_count': self.total_sku_count,
            'total_stock_amount': float(self.total_stock_amount or 0),
            'avg_turnover_days': float(self.avg_turnover_days or 0),
            'n_index': float(self.n_index or 0),
            'high_turnover_sku_count': self.high_turnover_sku_count,
            'slow_sku_count_lt10': self.slow_sku_count_lt10,
            'slow_inventory_amount_lt300': float(self.slow_inventory_amount_lt300 or 0),
            'stockout_sku_count': self.stockout_sku_count,
        }


class SKUDetail(BaseModel):
    """SKU明细数据 - 从旺店通同步"""
    __tablename__ = 'sku_detail'

    sku_code = db.Column(db.String(100), nullable=False, index=True, comment='SKU编码')
    goods_name = db.Column(db.String(500), comment='商品名称')
    spec_name = db.Column(db.String(500), comment='规格名称')
    category = db.Column(db.String(200), comment='品类')
    supplier = db.Column(db.String(200), comment='供应商')
    cost_price = db.Column(db.Numeric(10, 2), default=0, comment='成本价')

    # 库存
    current_stock = db.Column(db.Integer, default=0, comment='当前库存')
    stock_amount = db.Column(db.Numeric(12, 2), default=0, comment='库存金额')
    warehouse = db.Column(db.String(100), comment='仓库')

    # 销售
    sales_30d = db.Column(db.Integer, default=0, comment='近30天销量')
    sales_60d = db.Column(db.Integer, default=0, comment='近60天销量')
    sales_90d = db.Column(db.Integer, default=0, comment='近90天销量')
    avg_daily_sales = db.Column(db.Numeric(8, 2), default=0, comment='日均销量')

    # 周转
    turnover_days = db.Column(db.Numeric(8, 1), default=0, comment='周转天数')
    stock_months = db.Column(db.Numeric(6, 1), default=0, comment='可售月数')

    # 供应链
    lead_time = db.Column(db.Integer, default=0, comment='采购周期(天)')
    last_purchase_date = db.Column(db.Date, comment='最近采购日期')
    last_sale_date = db.Column(db.Date, comment='最近销售日期')

    # 状态标签
    is_new = db.Column(db.Boolean, default=False, comment='是否新品(近2月)')
    is_top150 = db.Column(db.Boolean, default=False, comment='是否TOP150政策品')
    is_top20 = db.Column(db.Boolean, default=False, comment='是否TOP20')
    has_chain = db.Column(db.Boolean, default=True, comment='是否有链路')

    # 同步
    synced_at = db.Column(db.DateTime, comment='最近同步时间')
    wdt_goods_id = db.Column(db.String(100), comment='旺店通商品ID')

    __table_args__ = (
        db.Index('idx_sku_sales', 'sales_30d'),
        db.Index('idx_sku_turnover', 'turnover_days'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'sku_code': self.sku_code,
            'goods_name': self.goods_name,
            'spec_name': self.spec_name,
            'category': self.category,
            'supplier': self.supplier,
            'current_stock': self.current_stock,
            'stock_amount': float(self.stock_amount or 0),
            'sales_30d': self.sales_30d,
            'turnover_days': float(self.turnover_days or 0),
            'is_top20': self.is_top20,
            'has_chain': self.has_chain,
        }


class PurchaseOrder(BaseModel):
    """采购订单记录 - 用于执行力考核"""
    __tablename__ = 'purchase_order'

    order_no = db.Column(db.String(100), unique=True, nullable=False, comment='采购单号')
    supplier = db.Column(db.String(200), comment='供应商')
    order_date = db.Column(db.Date, comment='下单日期')
    expected_date = db.Column(db.Date, comment='约定到货日期')
    actual_date = db.Column(db.Date, comment='实际到货日期')
    is_on_time = db.Column(db.Boolean, comment='是否按时到货')
    is_new_product = db.Column(db.Boolean, default=False, comment='是否新品订单')

    total_amount = db.Column(db.Numeric(12, 2), default=0, comment='采购总金额')
    total_qty = db.Column(db.Integer, default=0, comment='采购总数量')
    sku_count = db.Column(db.Integer, default=0, comment='SKU数量')

    # 首批备货相关
    estimated_30d_sales = db.Column(db.Integer, comment='预估30天销量')
    actual_30d_sales = db.Column(db.Integer, comment='实际30天销量')
    deviation_rate = db.Column(db.Numeric(5, 4), comment='偏差率')

    status = db.Column(db.String(20), default='ordered',
                       comment='状态: ordered/shipped/received/cancelled')
    synced_at = db.Column(db.DateTime, comment='同步时间')

    def to_dict(self):
        return {
            'id': self.id,
            'order_no': self.order_no,
            'supplier': self.supplier,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'expected_date': self.expected_date.isoformat() if self.expected_date else None,
            'actual_date': self.actual_date.isoformat() if self.actual_date else None,
            'is_on_time': self.is_on_time,
            'is_new_product': self.is_new_product,
            'total_amount': float(self.total_amount or 0),
            'deviation_rate': float(self.deviation_rate or 0),
            'status': self.status,
        }
