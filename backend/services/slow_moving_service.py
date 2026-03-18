"""
滞销品处理服务 - 核心业务逻辑
考核影响: 10分(考核) + 700元(提成) + ×1.1系数 + -10分(铁律) + 一票否决B部分
"""
from datetime import datetime, date
from backend.models.database import db
from backend.models.slow_moving import SlowMovingSKU, SlowMovingProcessLog, SlowMovingMonthlyStats


class SlowMovingService:

    @staticmethod
    def get_current_period():
        """获取当前考核周期"""
        return datetime.now().strftime('%Y-%m')

    # ==================== 滞销品列表查询 ====================

    @staticmethod
    def get_slow_moving_list(period=None, status=None, slow_type=None,
                             can_return=None, action_type=None,
                             keyword=None, sort_by='stock_amount',
                             sort_order='desc', page=1, page_size=20):
        """查询滞销品列表，支持多种筛选和排序"""
        query = SlowMovingSKU.query

        if period:
            query = query.filter(SlowMovingSKU.period == period)
        if status:
            query = query.filter(SlowMovingSKU.status == status)
        if slow_type:
            query = query.filter(SlowMovingSKU.slow_type == slow_type)
        if can_return:
            query = query.filter(SlowMovingSKU.can_return == can_return)
        if action_type:
            query = query.filter(SlowMovingSKU.action_type == action_type)
        if keyword:
            query = query.filter(
                db.or_(
                    SlowMovingSKU.sku_code.contains(keyword),
                    SlowMovingSKU.goods_name.contains(keyword),
                    SlowMovingSKU.supplier.contains(keyword),
                )
            )

        # 排序
        sort_column = getattr(SlowMovingSKU, sort_by, SlowMovingSKU.stock_amount)
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # 分页
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        return {
            'items': [item.to_dict() for item in pagination.items],
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
            'total_pages': pagination.pages,
        }

    # ==================== 处理滞销品 ====================

    @staticmethod
    def process_sku(sku_id: int, can_return: str, return_reason: str,
                    action_type: str, action_detail: str,
                    action_deadline: str = None, operator: str = 'system'):
        """
        处理滞销品 - 标记"能退/不能退" + 处置动作
        这是考核表中要求的核心操作
        """
        sku = SlowMovingSKU.query.get(sku_id)
        if not sku:
            raise ValueError(f'SKU不存在: {sku_id}')

        old_status = sku.status
        old_can_return = sku.can_return
        old_action = sku.action_type

        # 更新处置信息
        sku.can_return = can_return
        sku.return_reason = return_reason
        sku.action_type = action_type
        sku.action_detail = action_detail
        if action_deadline:
            sku.action_deadline = datetime.strptime(action_deadline, '%Y-%m-%d').date()
        sku.status = 'processing'
        sku.processed_by = operator

        # 记录操作日志
        log = SlowMovingProcessLog(
            sku_id=sku_id,
            operator=operator,
            action='set_action',
            old_value=f'status={old_status}, can_return={old_can_return}, action={old_action}',
            new_value=f'can_return={can_return}, action={action_type}',
            remark=return_reason,
        )
        db.session.add(log)
        db.session.commit()

        return sku.to_dict()

    @staticmethod
    def complete_sku(sku_id: int, actual_return_amount: float = 0,
                     actual_clear_amount: float = 0, result_note: str = '',
                     operator: str = 'system'):
        """标记滞销品处理完成"""
        sku = SlowMovingSKU.query.get(sku_id)
        if not sku:
            raise ValueError(f'SKU不存在: {sku_id}')

        sku.status = 'completed'
        sku.processed_at = datetime.now()
        sku.actual_return_amount = actual_return_amount
        sku.actual_clear_amount = actual_clear_amount
        sku.result_note = result_note

        log = SlowMovingProcessLog(
            sku_id=sku_id,
            operator=operator,
            action='complete',
            old_value=f'status=processing',
            new_value=f'status=completed, return={actual_return_amount}, clear={actual_clear_amount}',
            remark=result_note,
        )
        db.session.add(log)
        db.session.commit()

        return sku.to_dict()

    @staticmethod
    def batch_process(sku_ids: list, can_return: str, action_type: str,
                      action_detail: str = '', operator: str = 'system'):
        """批量处理滞销品"""
        results = []
        for sku_id in sku_ids:
            try:
                result = SlowMovingService.process_sku(
                    sku_id=sku_id,
                    can_return=can_return,
                    return_reason=f'批量处理: {action_detail}',
                    action_type=action_type,
                    action_detail=action_detail,
                    operator=operator,
                )
                results.append({'id': sku_id, 'success': True})
            except Exception as e:
                results.append({'id': sku_id, 'success': False, 'error': str(e)})
        return results

    # ==================== 统计与仪表盘 ====================

    @staticmethod
    def get_dashboard_stats(period=None):
        """获取滞销品处理仪表盘数据"""
        if not period:
            period = SlowMovingService.get_current_period()

        query = SlowMovingSKU.query.filter(SlowMovingSKU.period == period)

        total = query.count()
        pending = query.filter(SlowMovingSKU.status == 'pending').count()
        processing = query.filter(SlowMovingSKU.status == 'processing').count()
        completed = query.filter(SlowMovingSKU.status == 'completed').count()

        completion_rate = completed / total if total > 0 else 0

        # 按处置类型统计
        action_stats = db.session.query(
            SlowMovingSKU.action_type,
            db.func.count(SlowMovingSKU.id)
        ).filter(
            SlowMovingSKU.period == period,
            SlowMovingSKU.action_type.isnot(None)
        ).group_by(SlowMovingSKU.action_type).all()

        # 退货统计
        can_return_stats = db.session.query(
            SlowMovingSKU.can_return,
            db.func.count(SlowMovingSKU.id)
        ).filter(
            SlowMovingSKU.period == period,
            SlowMovingSKU.can_return.isnot(None)
        ).group_by(SlowMovingSKU.can_return).all()

        # 库存金额统计
        total_stock_amount = db.session.query(
            db.func.sum(SlowMovingSKU.stock_amount)
        ).filter(SlowMovingSKU.period == period).scalar() or 0

        total_return_amount = db.session.query(
            db.func.sum(SlowMovingSKU.actual_return_amount)
        ).filter(
            SlowMovingSKU.period == period,
            SlowMovingSKU.status == 'completed'
        ).scalar() or 0

        # 计算考核得分
        score = SlowMovingService._calculate_completion_score(completion_rate)
        commission = SlowMovingService._calculate_completion_commission(completion_rate)

        return {
            'period': period,
            'total': total,
            'pending': pending,
            'processing': processing,
            'completed': completed,
            'completion_rate': round(completion_rate * 100, 1),
            'action_stats': {k: v for k, v in action_stats},
            'can_return_stats': {k: v for k, v in can_return_stats},
            'total_stock_amount': float(total_stock_amount),
            'total_return_amount': float(total_return_amount),
            'kpi_score': score,
            'commission_amount': commission,
            'score_detail': SlowMovingService._get_score_detail(completion_rate),
        }

    @staticmethod
    def _calculate_completion_score(rate: float) -> int:
        """计算系统滞销品处理完成率得分 (满分10分)"""
        if rate >= 0.95:
            return 10
        elif rate >= 0.90:
            return 7
        elif rate >= 0.80:
            return 3
        elif rate >= 0.60:
            return 1
        else:
            return 0  # 同时触发铁律扣分-10分

    @staticmethod
    def _calculate_completion_commission(rate: float) -> float:
        """计算系统完成率对应提成 (最高700元)"""
        if rate >= 0.95:
            return 700
        elif rate >= 0.90:
            return 400
        elif rate >= 0.80:
            return 100
        else:
            return 0

    @staticmethod
    def _get_score_detail(rate: float) -> dict:
        """获取得分详情说明"""
        score = SlowMovingService._calculate_completion_score(rate)
        commission = SlowMovingService._calculate_completion_commission(rate)
        coefficient = 1.1 if rate >= 1.0 else (0.9 if rate < 0.80 else 1.0)
        penalty = -10 if rate < 0.60 else 0

        return {
            'completion_rate': round(rate * 100, 1),
            'kpi_score': score,
            'kpi_max': 10,
            'commission': commission,
            'commission_max': 700,
            'behavior_coefficient': coefficient,
            'penalty': penalty,
            'warning': '完成率<60%将触发铁律扣分-10分！' if rate < 0.60 else (
                '连续2月<60%将取消B部分全部提成！' if rate < 0.60 else None
            ),
        }

    # ==================== 月度统计 ====================

    @staticmethod
    def generate_monthly_stats(period=None):
        """生成月度统计数据"""
        if not period:
            period = SlowMovingService.get_current_period()

        query = SlowMovingSKU.query.filter(SlowMovingSKU.period == period)

        total = query.count()
        completed = query.filter(SlowMovingSKU.status == 'completed').count()
        completion_rate = completed / total if total > 0 else 0

        total_return = db.session.query(
            db.func.sum(SlowMovingSKU.actual_return_amount)
        ).filter(SlowMovingSKU.period == period, SlowMovingSKU.status == 'completed').scalar() or 0

        total_clear = db.session.query(
            db.func.sum(SlowMovingSKU.actual_clear_amount)
        ).filter(SlowMovingSKU.period == period, SlowMovingSKU.status == 'completed').scalar() or 0

        # 查找或创建月度统计
        stats = SlowMovingMonthlyStats.query.filter_by(period=period).first()
        if not stats:
            stats = SlowMovingMonthlyStats(period=period)
            db.session.add(stats)

        stats.total_to_process = total
        stats.completed_count = completed
        stats.completion_rate = completion_rate
        stats.total_return_amount = total_return
        stats.total_clear_amount = total_clear
        stats.score_system_completion = SlowMovingService._calculate_completion_score(completion_rate)

        # 计算滞销管理总得分
        stats.total_score = (
            (stats.score_slow_sku_decrease or 0) +
            stats.score_system_completion +
            (stats.score_inventory_decrease or 0) +
            (stats.score_expiry or 0)
        )

        db.session.commit()
        return stats.to_dict()

    # ==================== 操作日志查询 ====================

    @staticmethod
    def get_process_logs(sku_id: int = None, operator: str = None,
                         start_date: str = None, end_date: str = None,
                         page=1, page_size=20):
        """查询操作日志 - 全程可追溯"""
        query = SlowMovingProcessLog.query

        if sku_id:
            query = query.filter(SlowMovingProcessLog.sku_id == sku_id)
        if operator:
            query = query.filter(SlowMovingProcessLog.operator == operator)
        if start_date:
            query = query.filter(SlowMovingProcessLog.created_at >= start_date)
        if end_date:
            query = query.filter(SlowMovingProcessLog.created_at <= end_date)

        query = query.order_by(SlowMovingProcessLog.created_at.desc())
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        return {
            'items': [item.to_dict() for item in pagination.items],
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
        }
