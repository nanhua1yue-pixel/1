"""
绩效考核与提成模型
对应：采购主管月度绩效考核表 + 采购主管提成方案
"""
from .database import db, BaseModel
from datetime import datetime


class MonthlyKPI(BaseModel):
    """月度绩效考核记录 - 100分制"""
    __tablename__ = 'monthly_kpi'

    period = db.Column(db.String(7), nullable=False, index=True, comment='考核周期(YYYY-MM)')
    evaluee = db.Column(db.String(50), nullable=False, comment='被考核人')
    evaluator = db.Column(db.String(50), comment='考核人')
    status = db.Column(db.String(20), default='draft',
                       comment='状态: draft(草稿)/submitted(已提交)/confirmed(已确认)')

    # ===== 一、库存周转与现金效率 (30分) =====
    # 整体库存周转天数 (12分)
    turnover_days_current = db.Column(db.Numeric(6, 1), comment='本月周转天数')
    turnover_days_prev = db.Column(db.Numeric(6, 1), comment='上月周转天数')
    turnover_days_change = db.Column(db.Numeric(6, 1), comment='周转天数变化')
    score_turnover_days = db.Column(db.Integer, default=0, comment='周转天数得分(满12)')

    # 高周转SKU优化 (10分)
    high_turnover_sku_current = db.Column(db.Integer, comment='本月高周转SKU数')
    high_turnover_sku_prev = db.Column(db.Integer, comment='上月高周转SKU数')
    high_turnover_sku_change = db.Column(db.Integer, comment='高周转SKU变化')
    score_high_turnover_sku = db.Column(db.Integer, default=0, comment='高周转SKU得分(满10)')

    # 库存总金额 & N指数 (8分)
    inventory_amount = db.Column(db.Numeric(14, 2), comment='库存总金额')
    n_index_current = db.Column(db.Numeric(4, 2), comment='本月N指数')
    n_index_prev = db.Column(db.Numeric(4, 2), comment='上月N指数')
    score_n_index = db.Column(db.Integer, default=0, comment='N指数得分(满8)')

    section1_score = db.Column(db.Integer, default=0, comment='库存周转总得分(满30)')

    # ===== 二、滞销管理 (25分) =====
    score_slow_sku = db.Column(db.Integer, default=0, comment='月销<10下降(满8)')
    score_system_completion = db.Column(db.Integer, default=0, comment='系统完成率(满10)')
    score_slow_inventory = db.Column(db.Integer, default=0, comment='滞销金额下降(满4)')
    score_expiry = db.Column(db.Integer, default=0, comment='效期管理(满3)')
    section2_score = db.Column(db.Integer, default=0, comment='滞销管理总得分(满25)')

    # ===== 三、采购执行能力 (20分) =====
    new_product_delivery_rate = db.Column(db.Numeric(5, 4), comment='新品到货及时率')
    score_delivery = db.Column(db.Integer, default=0, comment='到货及时(满6)')

    first_batch_deviation = db.Column(db.Numeric(5, 4), comment='首批备货偏差率')
    score_first_batch = db.Column(db.Integer, default=0, comment='备货准确(满8)')

    supply_disruption_count = db.Column(db.Integer, default=0, comment='断货/延误次数')
    score_supply_stability = db.Column(db.Integer, default=0, comment='供货稳定(满6)')

    section3_score = db.Column(db.Integer, default=0, comment='采购执行总得分(满20)')

    # ===== 四、缺货管控 (12分) =====
    stockout_sku_count = db.Column(db.Integer, default=0, comment='补不到的缺货SKU数')
    score_stockout_sku = db.Column(db.Integer, default=0, comment='缺货SKU(满5)')

    top20_stockout_count = db.Column(db.Integer, default=0, comment='Top20断货次数')
    score_top20_stockout = db.Column(db.Integer, default=0, comment='Top20断货(满7)')

    section4_score = db.Column(db.Integer, default=0, comment='缺货管控总得分(满12)')

    # ===== 五、风险合规+无链路 (8分) =====
    risk_incident_count = db.Column(db.Integer, default=0, comment='风险事故次数')
    score_risk = db.Column(db.Integer, default=0, comment='风险事故(满5)')

    no_chain_rate = db.Column(db.Numeric(5, 4), comment='无链路占比')
    score_no_chain = db.Column(db.Integer, default=0, comment='无链路(满3)')

    section5_score = db.Column(db.Integer, default=0, comment='风险合规总得分(满8)')

    # ===== 六、成本控制 (5分) =====
    negotiation_count = db.Column(db.Integer, default=0, comment='有效谈价次数')
    negotiation_turnover_ok = db.Column(db.Boolean, default=False, comment='周转天数未因此恶化')
    score_cost = db.Column(db.Integer, default=0, comment='成本控制(满5)')

    section6_score = db.Column(db.Integer, default=0, comment='成本控制总得分(满5)')

    # ===== 加分项 =====
    bonus_points = db.Column(db.Integer, default=0, comment='加分项合计')
    bonus_detail = db.Column(db.Text, comment='加分项明细(JSON)')

    # ===== 扣分项 =====
    penalty_points = db.Column(db.Integer, default=0, comment='扣分项合计(铁律)')
    penalty_detail = db.Column(db.Text, comment='扣分项明细(JSON)')

    # ===== 总分 =====
    base_score = db.Column(db.Integer, default=0, comment='基础总分(六大维度)')
    total_score = db.Column(db.Integer, default=0, comment='最终总分(含加减分)')
    score_level = db.Column(db.String(20), comment='等级: excellent/good/pass/fail')
    data_record = db.Column(db.Text, comment='数据记录备注(JSON)')

    def calculate_total(self):
        """计算总分"""
        self.section1_score = (self.score_turnover_days or 0) + (self.score_high_turnover_sku or 0) + (self.score_n_index or 0)
        self.section2_score = (self.score_slow_sku or 0) + (self.score_system_completion or 0) + (self.score_slow_inventory or 0) + (self.score_expiry or 0)
        self.section3_score = (self.score_delivery or 0) + (self.score_first_batch or 0) + (self.score_supply_stability or 0)
        self.section4_score = (self.score_stockout_sku or 0) + (self.score_top20_stockout or 0)
        self.section5_score = (self.score_risk or 0) + (self.score_no_chain or 0)
        self.section6_score = self.score_cost or 0

        self.base_score = (
            self.section1_score + self.section2_score + self.section3_score +
            self.section4_score + self.section5_score + self.section6_score
        )
        self.total_score = self.base_score + (self.bonus_points or 0) - abs(self.penalty_points or 0)

        if self.total_score >= 90:
            self.score_level = 'excellent'
        elif self.total_score >= 75:
            self.score_level = 'good'
        elif self.total_score >= 60:
            self.score_level = 'pass'
        else:
            self.score_level = 'fail'

    def to_dict(self):
        return {
            'id': self.id,
            'period': self.period,
            'evaluee': self.evaluee,
            'evaluator': self.evaluator,
            'status': self.status,
            'section1': {
                'score': self.section1_score,
                'turnover_days': {'current': float(self.turnover_days_current or 0), 'prev': float(self.turnover_days_prev or 0), 'change': float(self.turnover_days_change or 0), 'score': self.score_turnover_days},
                'high_turnover_sku': {'current': self.high_turnover_sku_current, 'prev': self.high_turnover_sku_prev, 'change': self.high_turnover_sku_change, 'score': self.score_high_turnover_sku},
                'n_index': {'amount': float(self.inventory_amount or 0), 'current': float(self.n_index_current or 0), 'prev': float(self.n_index_prev or 0), 'score': self.score_n_index},
            },
            'section2': {
                'score': self.section2_score,
                'slow_sku': self.score_slow_sku,
                'system_completion': self.score_system_completion,
                'slow_inventory': self.score_slow_inventory,
                'expiry': self.score_expiry,
            },
            'section3': {
                'score': self.section3_score,
                'delivery': {'rate': float(self.new_product_delivery_rate or 0), 'score': self.score_delivery},
                'first_batch': {'deviation': float(self.first_batch_deviation or 0), 'score': self.score_first_batch},
                'supply_stability': {'count': self.supply_disruption_count, 'score': self.score_supply_stability},
            },
            'section4': {
                'score': self.section4_score,
                'stockout_sku': {'count': self.stockout_sku_count, 'score': self.score_stockout_sku},
                'top20_stockout': {'count': self.top20_stockout_count, 'score': self.score_top20_stockout},
            },
            'section5': {
                'score': self.section5_score,
                'risk': {'count': self.risk_incident_count, 'score': self.score_risk},
                'no_chain': {'rate': float(self.no_chain_rate or 0), 'score': self.score_no_chain},
            },
            'section6': {
                'score': self.section6_score,
                'negotiation': {'count': self.negotiation_count, 'turnover_ok': self.negotiation_turnover_ok, 'score': self.score_cost},
            },
            'bonus_points': self.bonus_points,
            'penalty_points': self.penalty_points,
            'base_score': self.base_score,
            'total_score': self.total_score,
            'score_level': self.score_level,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MonthlyCommission(BaseModel):
    """月度提成记录"""
    __tablename__ = 'monthly_commission'

    period = db.Column(db.String(7), nullable=False, index=True, comment='考核周期')
    evaluee = db.Column(db.String(50), nullable=False, comment='被考核人')
    kpi_id = db.Column(db.Integer, db.ForeignKey('monthly_kpi.id'), comment='关联KPI')

    # A. 执行质量提成
    delivery_amount = db.Column(db.Numeric(10, 2), default=0, comment='到货及时率提成')
    accuracy_amount = db.Column(db.Numeric(10, 2), default=0, comment='备货准确率提成')
    stability_amount = db.Column(db.Numeric(10, 2), default=0, comment='供货稳定性提成')
    execution_total = db.Column(db.Numeric(10, 2), default=0, comment='A.执行质量提成合计')

    # B. 库存健康奖励
    turnover_bonus = db.Column(db.Numeric(10, 2), default=0, comment='周转天数奖励')
    slow_sku_bonus = db.Column(db.Numeric(10, 2), default=0, comment='滞销SKU下降奖励')
    slow_amount_bonus = db.Column(db.Numeric(10, 2), default=0, comment='滞销金额下降奖励')
    system_completion_bonus = db.Column(db.Numeric(10, 2), default=0, comment='系统完成率奖励')
    health_total = db.Column(db.Numeric(10, 2), default=0, comment='B.库存健康奖励合计')

    # C. 过程行为系数
    coeff_processing = db.Column(db.Numeric(4, 2), default=1.0, comment='系统处理及时率系数')
    coeff_stockout = db.Column(db.Numeric(4, 2), default=1.0, comment='Top20断货系数')
    coeff_return = db.Column(db.Numeric(4, 2), default=1.0, comment='退货止损系数')
    coeff_negotiation = db.Column(db.Numeric(4, 2), default=1.0, comment='谈价周转双达标系数')
    total_coefficient = db.Column(db.Numeric(4, 2), default=1.0, comment='C.综合系数')

    # D. 重大损失扣罚
    major_penalty_type = db.Column(db.String(50), comment='重大扣罚类型')
    major_penalty_effect = db.Column(db.String(50), comment='扣罚效果: cancel_all/half/cancel_b/none')

    # 最终提成
    pre_coefficient_total = db.Column(db.Numeric(10, 2), default=0, comment='系数前合计(A+B)')
    final_commission = db.Column(db.Numeric(10, 2), default=0, comment='最终提成金额')

    kpi = db.relationship('MonthlyKPI', backref=db.backref('commission', uselist=False))

    def calculate(self):
        """计算最终提成 = (A + B) × C - D"""
        self.execution_total = (
            (self.delivery_amount or 0) +
            (self.accuracy_amount or 0) +
            (self.stability_amount or 0)
        )
        self.health_total = (
            (self.turnover_bonus or 0) +
            (self.slow_sku_bonus or 0) +
            (self.slow_amount_bonus or 0) +
            (self.system_completion_bonus or 0)
        )
        self.pre_coefficient_total = self.execution_total + self.health_total

        # 计算综合系数
        self.total_coefficient = (
            float(self.coeff_processing or 1) *
            float(self.coeff_stockout or 1) *
            float(self.coeff_return or 1) *
            float(self.coeff_negotiation or 1)
        )

        result = float(self.pre_coefficient_total) * float(self.total_coefficient)

        # 重大损失扣罚
        if self.major_penalty_effect == 'cancel_all':
            result = 0
        elif self.major_penalty_effect == 'half':
            result = result / 2
        elif self.major_penalty_effect == 'cancel_b':
            result = float(self.execution_total) * float(self.total_coefficient)

        self.final_commission = max(0, result)

    def to_dict(self):
        return {
            'id': self.id,
            'period': self.period,
            'evaluee': self.evaluee,
            'execution': {
                'delivery': float(self.delivery_amount or 0),
                'accuracy': float(self.accuracy_amount or 0),
                'stability': float(self.stability_amount or 0),
                'total': float(self.execution_total or 0),
            },
            'health': {
                'turnover': float(self.turnover_bonus or 0),
                'slow_sku': float(self.slow_sku_bonus or 0),
                'slow_amount': float(self.slow_amount_bonus or 0),
                'system_completion': float(self.system_completion_bonus or 0),
                'total': float(self.health_total or 0),
            },
            'coefficient': {
                'processing': float(self.coeff_processing or 1),
                'stockout': float(self.coeff_stockout or 1),
                'return': float(self.coeff_return or 1),
                'negotiation': float(self.coeff_negotiation or 1),
                'total': float(self.total_coefficient or 1),
            },
            'major_penalty': {
                'type': self.major_penalty_type,
                'effect': self.major_penalty_effect,
            },
            'pre_coefficient_total': float(self.pre_coefficient_total or 0),
            'final_commission': float(self.final_commission or 0),
        }
