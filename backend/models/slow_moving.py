"""
滞销品管理模型 - 核心模块
对应考核：二、滞销管理【25分】中的"系统滞销品处理完成率(10分)"
对应提成：B.库存健康奖励 - 系统滞销处理完成率(700元)
对应系数：C.过程行为系数 - 系统滞销处理及时率(×1.1/×0.9)
对应扣分：铁律扣分 - 月度滞销处理完成率<60%: -10分
对应否决：D.重大损失 - 连续2月完成率<60% → B部分提成全部取消
"""
from .database import db, BaseModel
from datetime import datetime


class SlowMovingSKU(BaseModel):
    """滞销品SKU记录"""
    __tablename__ = 'slow_moving_sku'

    # 基础信息
    sku_code = db.Column(db.String(100), nullable=False, index=True, comment='SKU编码')
    goods_name = db.Column(db.String(500), comment='商品名称')
    spec_name = db.Column(db.String(500), comment='规格名称')
    category = db.Column(db.String(200), comment='品类')
    supplier = db.Column(db.String(200), comment='供应商')

    # 库存与销售数据
    current_stock = db.Column(db.Integer, default=0, comment='当前库存数量')
    stock_amount = db.Column(db.Numeric(12, 2), default=0, comment='库存金额(元)')
    cost_price = db.Column(db.Numeric(10, 2), default=0, comment='成本价')
    monthly_sales_30d = db.Column(db.Integer, default=0, comment='近30天销量')
    monthly_sales_60d = db.Column(db.Integer, default=0, comment='近60天销量')
    monthly_sales_90d = db.Column(db.Integer, default=0, comment='近90天销量')
    last_sale_date = db.Column(db.Date, comment='最后一次销售日期')
    stock_days = db.Column(db.Integer, default=0, comment='库存天数(库存/日均销量)')

    # 滞销分类: monthly_sales_30d < 10 为滞销
    slow_type = db.Column(db.String(50), comment='滞销类型: zero_sale(0销量)/very_slow(<5)/slow(<10)')

    # 处理状态
    status = db.Column(db.String(30), default='pending', index=True,
                       comment='状态: pending(待处理)/processing(处理中)/completed(已完成)')

    # 处置决策
    can_return = db.Column(db.String(20), comment='能否退货: yes(能退)/no(不能退)/partial(部分可退)')
    return_reason = db.Column(db.Text, comment='退/不退原因说明')

    # 处置动作
    action_type = db.Column(db.String(50),
                            comment='处置动作: return(退货)/discount(打折清仓)/bundle(搭配销售)/'
                                    'transfer(调拨)/write_off(报损)/hold(暂不处理-需说明)')
    action_detail = db.Column(db.Text, comment='处置动作详情')
    action_deadline = db.Column(db.Date, comment='处置截止日期')

    # 处理结果
    processed_by = db.Column(db.String(50), comment='处理人')
    processed_at = db.Column(db.DateTime, comment='处理完成时间')
    actual_return_amount = db.Column(db.Numeric(12, 2), default=0, comment='实际退货金额')
    actual_clear_amount = db.Column(db.Numeric(12, 2), default=0, comment='实际清仓回款金额')
    result_note = db.Column(db.Text, comment='处理结果备注')

    # 数据同步
    period = db.Column(db.String(7), index=True, comment='所属考核周期(YYYY-MM)')
    synced_at = db.Column(db.DateTime, comment='最近同步时间')
    wdt_goods_id = db.Column(db.String(100), comment='旺店通商品ID')

    def to_dict(self):
        return {
            'id': self.id,
            'sku_code': self.sku_code,
            'goods_name': self.goods_name,
            'spec_name': self.spec_name,
            'category': self.category,
            'supplier': self.supplier,
            'current_stock': self.current_stock,
            'stock_amount': float(self.stock_amount) if self.stock_amount else 0,
            'cost_price': float(self.cost_price) if self.cost_price else 0,
            'monthly_sales_30d': self.monthly_sales_30d,
            'monthly_sales_60d': self.monthly_sales_60d,
            'monthly_sales_90d': self.monthly_sales_90d,
            'last_sale_date': self.last_sale_date.isoformat() if self.last_sale_date else None,
            'stock_days': self.stock_days,
            'slow_type': self.slow_type,
            'status': self.status,
            'can_return': self.can_return,
            'return_reason': self.return_reason,
            'action_type': self.action_type,
            'action_detail': self.action_detail,
            'action_deadline': self.action_deadline.isoformat() if self.action_deadline else None,
            'processed_by': self.processed_by,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'actual_return_amount': float(self.actual_return_amount) if self.actual_return_amount else 0,
            'actual_clear_amount': float(self.actual_clear_amount) if self.actual_clear_amount else 0,
            'result_note': self.result_note,
            'period': self.period,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SlowMovingProcessLog(BaseModel):
    """滞销品处理操作日志 - 全程可追溯"""
    __tablename__ = 'slow_moving_process_log'

    sku_id = db.Column(db.Integer, db.ForeignKey('slow_moving_sku.id'), nullable=False, index=True)
    operator = db.Column(db.String(50), nullable=False, comment='操作人')
    action = db.Column(db.String(50), nullable=False,
                       comment='操作类型: mark_return/mark_no_return/set_action/complete/reopen')
    old_value = db.Column(db.Text, comment='变更前值')
    new_value = db.Column(db.Text, comment='变更后值')
    remark = db.Column(db.Text, comment='操作备注')

    sku = db.relationship('SlowMovingSKU', backref=db.backref('process_logs', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'sku_id': self.sku_id,
            'operator': self.operator,
            'action': self.action,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'remark': self.remark,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SlowMovingMonthlyStats(BaseModel):
    """滞销品月度统计 - 用于KPI和提成计算"""
    __tablename__ = 'slow_moving_monthly_stats'

    period = db.Column(db.String(7), unique=True, nullable=False, comment='考核周期(YYYY-MM)')

    # SKU数量统计
    total_slow_sku = db.Column(db.Integer, default=0, comment='月销<10的SKU总数')
    prev_total_slow_sku = db.Column(db.Integer, default=0, comment='上月月销<10的SKU总数')
    slow_sku_change = db.Column(db.Integer, default=0, comment='SKU数量变化(正=增加,负=减少)')
    slow_sku_change_rate = db.Column(db.Numeric(6, 4), default=0, comment='SKU数量变化率')

    # 库存金额统计 (月销<300链接)
    slow_inventory_amount = db.Column(db.Numeric(14, 2), default=0, comment='滞销库存金额(月销<300)')
    prev_slow_inventory_amount = db.Column(db.Numeric(14, 2), default=0, comment='上月滞销库存金额')
    inventory_amount_change = db.Column(db.Numeric(14, 2), default=0, comment='金额变化')
    inventory_amount_change_rate = db.Column(db.Numeric(6, 4), default=0, comment='金额变化率')

    # 系统处理完成率
    total_to_process = db.Column(db.Integer, default=0, comment='待处理总数')
    completed_count = db.Column(db.Integer, default=0, comment='已完成数')
    completion_rate = db.Column(db.Numeric(5, 4), default=0, comment='完成率')

    # 退货统计
    total_return_amount = db.Column(db.Numeric(14, 2), default=0, comment='退货总金额')
    total_clear_amount = db.Column(db.Numeric(14, 2), default=0, comment='清仓回款总金额')

    # 得分
    score_slow_sku_decrease = db.Column(db.Integer, default=0, comment='月销<10下降得分(满8)')
    score_system_completion = db.Column(db.Integer, default=0, comment='系统完成率得分(满10)')
    score_inventory_decrease = db.Column(db.Integer, default=0, comment='滞销金额下降得分(满4)')
    score_expiry = db.Column(db.Integer, default=0, comment='效期管理得分(满3)')
    total_score = db.Column(db.Integer, default=0, comment='滞销管理总得分(满25)')

    def to_dict(self):
        return {
            'id': self.id,
            'period': self.period,
            'total_slow_sku': self.total_slow_sku,
            'prev_total_slow_sku': self.prev_total_slow_sku,
            'slow_sku_change': self.slow_sku_change,
            'slow_sku_change_rate': float(self.slow_sku_change_rate) if self.slow_sku_change_rate else 0,
            'slow_inventory_amount': float(self.slow_inventory_amount) if self.slow_inventory_amount else 0,
            'prev_slow_inventory_amount': float(self.prev_slow_inventory_amount) if self.prev_slow_inventory_amount else 0,
            'inventory_amount_change_rate': float(self.inventory_amount_change_rate) if self.inventory_amount_change_rate else 0,
            'total_to_process': self.total_to_process,
            'completed_count': self.completed_count,
            'completion_rate': float(self.completion_rate) if self.completion_rate else 0,
            'total_return_amount': float(self.total_return_amount) if self.total_return_amount else 0,
            'score_slow_sku_decrease': self.score_slow_sku_decrease,
            'score_system_completion': self.score_system_completion,
            'score_inventory_decrease': self.score_inventory_decrease,
            'score_expiry': self.score_expiry,
            'total_score': self.total_score,
        }
