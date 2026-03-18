"""
KPI评分引擎 + 提成计算服务
完整对应：采购主管月度绩效考核表 + 提成方案
"""
from datetime import datetime
from decimal import Decimal
from backend.models.database import db
from backend.models.kpi import MonthlyKPI, MonthlyCommission
from backend.models.slow_moving import SlowMovingMonthlyStats
from backend.models.inventory import InventorySnapshot


class KPIService:
    """KPI评分引擎"""

    # ==================== 一、库存周转与现金效率 (30分) ====================

    @staticmethod
    def score_turnover_days(current: float, prev: float) -> int:
        """整体库存周转天数评分 (满分12分)"""
        change = current - prev
        if change <= -2:
            return 12  # 环比下降≥2天
        elif change <= -1:
            return 8   # 下降1天
        elif abs(change) <= 1:
            return 4   # 持平(±1天以内)
        elif change <= 3:
            return 1   # 上升1-3天
        else:
            return 0   # 上升>3天

    @staticmethod
    def score_high_turnover_sku(current: int, prev: int) -> int:
        """高周转SKU(库存>2个月)数量月度优化幅度 (满分10分)"""
        if prev == 0:
            return 0

        change = prev - current  # 数量减少=优化
        rate = change / prev

        if rate >= 0.08 or change >= 57:
            return 10
        elif rate >= 0.04 or change >= 28:
            return 7
        elif rate >= 0.01 or change >= 7:
            return 4
        elif abs(rate) <= 0.01:
            return 1
        else:
            return 0  # 恶化

    @staticmethod
    def score_n_index(n_current: float, n_prev: float,
                      amount_current: float, amount_prev: float) -> int:
        """库存总金额 & N指数 (满分8分)"""
        n_decreased = n_current < n_prev
        amount_decreased = amount_current < amount_prev
        n_hold = abs(n_current - n_prev) < 0.02
        amount_hold = abs(amount_current - amount_prev) / max(amount_prev, 1) < 0.02

        if n_decreased and amount_decreased:
            return 8
        elif n_hold and amount_decreased:
            return 5
        elif n_hold and amount_hold:
            return 2
        else:
            return 0

    # ==================== 二、滞销管理 (25分) ====================

    @staticmethod
    def score_slow_sku_decrease(current: int, prev: int) -> int:
        """月销<10的SKU数量月度下降幅度 (满分8分, 可扣-3分)"""
        if prev == 0:
            return 0

        change = prev - current
        rate = change / prev

        if rate >= 0.10 or change >= 156:
            return 8
        elif rate >= 0.05 or change >= 78:
            return 5
        elif rate >= 0.01 or change >= 16:
            return 2
        elif abs(rate) < 0.01:
            return 0  # 持平
        else:
            return -3  # 增加 (额外扣分)

    @staticmethod
    def score_system_completion(rate: float) -> int:
        """系统滞销品处理完成率 (满分10分)"""
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
    def score_slow_inventory_decrease(current: float, prev: float) -> int:
        """月销<300链接库存金额月度下降 (满分4分)"""
        if prev == 0:
            return 0

        change = prev - current
        rate = change / prev

        if rate >= 0.10:
            return 4
        elif rate >= 0.05:
            return 2
        elif rate >= 0.01:
            return 1
        else:
            return 0

    @staticmethod
    def score_expiry(miss_count: int) -> int:
        """效期管理: 保质期<1年的SKU漏报次数 (满分3分)"""
        if miss_count == 0:
            return 3
        elif miss_count == 1:
            return 1
        else:
            return 0

    # ==================== 三、采购执行能力 (20分) ====================

    @staticmethod
    def score_delivery(rate: float) -> int:
        """新品到货及时率 (满分6分)"""
        if rate >= 0.95:
            return 6
        elif rate >= 0.90:
            return 4
        elif rate >= 0.85:
            return 2
        else:
            return 0

    @staticmethod
    def score_first_batch(deviation: float) -> int:
        """首批备货准确率 (满分8分)"""
        if deviation < 0.20:
            return 8
        elif deviation < 0.40:
            return 5
        elif deviation < 0.60:
            return 2
        else:
            return 0

    @staticmethod
    def score_supply_stability(disruption_count: int, has_warning: bool = False,
                               has_backup: bool = False) -> int:
        """供货稳定性 (满分6分)"""
        if disruption_count == 0:
            return 6
        elif disruption_count == 1:
            if has_warning and has_backup:
                return 4
            elif not has_warning:
                return 1
            return 3
        else:
            return 0

    # ==================== 四、缺货管控 (12分) ====================

    @staticmethod
    def score_stockout_sku(count: int) -> int:
        """补不到的缺货SKU数量 (满分5分)"""
        if count < 5:
            return 5
        elif count <= 10:
            return 3
        elif count <= 15:
            return 1
        else:
            return 0

    @staticmethod
    def score_top20_stockout(count: int, has_warning: bool = False,
                             has_backup: bool = False) -> int:
        """Top20 SKU断货次数 (满分7分)"""
        if count == 0:
            return 7
        elif count == 1:
            if has_warning and has_backup:
                return 4
            elif not has_warning:
                return 0
            return 2
        else:
            return 0  # 同时触发扣分项-5分

    # ==================== 五、风险合规+无链路 (8分) ====================

    @staticmethod
    def score_risk(incident_count: int, is_settled: bool = False) -> int:
        """风险商品事故次数 (满分5分)"""
        if incident_count == 0:
            return 5
        elif incident_count == 1 and is_settled:
            return 2
        else:
            return 0  # 同时触发扣分项

    @staticmethod
    def score_no_chain(rate: float, prev_rate: float) -> int:
        """无链路占比 (满分3分)"""
        change = rate - prev_rate
        if change <= -0.003:
            return 3
        elif change <= -0.001:
            return 2
        elif abs(change) < 0.001:
            return 1
        else:
            return 0

    # ==================== 六、成本控制 (5分) ====================

    @staticmethod
    def score_cost(negotiation_count: int, turnover_not_worsened: bool) -> int:
        """有效谈价次数 (满分5分) - 硬性前提:周转未恶化"""
        if not turnover_not_worsened:
            return 0  # 因压价导致周转恶化 = 无效

        if negotiation_count >= 3 and turnover_not_worsened:
            return 5
        elif negotiation_count >= 2:
            return 3
        elif negotiation_count >= 1:
            return 1
        else:
            return 0

    # ==================== 完整评分计算 ====================

    @staticmethod
    def calculate_full_kpi(period: str, evaluee: str, data: dict) -> dict:
        """计算完整KPI评分"""
        kpi = MonthlyKPI.query.filter_by(period=period, evaluee=evaluee).first()
        if not kpi:
            kpi = MonthlyKPI(period=period, evaluee=evaluee)
            db.session.add(kpi)

        # 一、库存周转 (30分)
        if 'turnover_days' in data:
            td = data['turnover_days']
            kpi.turnover_days_current = td.get('current', 0)
            kpi.turnover_days_prev = td.get('prev', 0)
            kpi.turnover_days_change = float(kpi.turnover_days_current) - float(kpi.turnover_days_prev)
            kpi.score_turnover_days = KPIService.score_turnover_days(
                float(kpi.turnover_days_current), float(kpi.turnover_days_prev))

        if 'high_turnover_sku' in data:
            ht = data['high_turnover_sku']
            kpi.high_turnover_sku_current = ht.get('current', 0)
            kpi.high_turnover_sku_prev = ht.get('prev', 0)
            kpi.high_turnover_sku_change = kpi.high_turnover_sku_current - kpi.high_turnover_sku_prev
            kpi.score_high_turnover_sku = KPIService.score_high_turnover_sku(
                kpi.high_turnover_sku_current, kpi.high_turnover_sku_prev)

        if 'n_index' in data:
            ni = data['n_index']
            kpi.inventory_amount = ni.get('amount', 0)
            kpi.n_index_current = ni.get('current', 0)
            kpi.n_index_prev = ni.get('prev', 0)
            kpi.score_n_index = KPIService.score_n_index(
                float(kpi.n_index_current), float(kpi.n_index_prev),
                float(kpi.inventory_amount), float(ni.get('prev_amount', kpi.inventory_amount)))

        # 二、滞销管理 (25分) - 部分自动从系统获取
        if 'slow_sku' in data:
            ss = data['slow_sku']
            kpi.score_slow_sku = KPIService.score_slow_sku_decrease(
                ss.get('current', 0), ss.get('prev', 0))

        # 系统完成率自动计算
        stats = SlowMovingMonthlyStats.query.filter_by(period=period).first()
        if stats:
            kpi.score_system_completion = KPIService.score_system_completion(
                float(stats.completion_rate or 0))
        elif 'system_completion_rate' in data:
            kpi.score_system_completion = KPIService.score_system_completion(
                data['system_completion_rate'])

        if 'slow_inventory' in data:
            si = data['slow_inventory']
            kpi.score_slow_inventory = KPIService.score_slow_inventory_decrease(
                si.get('current', 0), si.get('prev', 0))

        kpi.score_expiry = KPIService.score_expiry(data.get('expiry_miss_count', 0))

        # 三、采购执行 (20分)
        if 'delivery_rate' in data:
            kpi.new_product_delivery_rate = data['delivery_rate']
            kpi.score_delivery = KPIService.score_delivery(data['delivery_rate'])

        if 'first_batch_deviation' in data:
            kpi.first_batch_deviation = data['first_batch_deviation']
            kpi.score_first_batch = KPIService.score_first_batch(data['first_batch_deviation'])

        if 'supply_disruption' in data:
            sd = data['supply_disruption']
            kpi.supply_disruption_count = sd.get('count', 0)
            kpi.score_supply_stability = KPIService.score_supply_stability(
                sd['count'], sd.get('has_warning', False), sd.get('has_backup', False))

        # 四、缺货管控 (12分)
        if 'stockout_sku_count' in data:
            kpi.stockout_sku_count = data['stockout_sku_count']
            kpi.score_stockout_sku = KPIService.score_stockout_sku(data['stockout_sku_count'])

        if 'top20_stockout' in data:
            t20 = data['top20_stockout']
            kpi.top20_stockout_count = t20.get('count', 0)
            kpi.score_top20_stockout = KPIService.score_top20_stockout(
                t20['count'], t20.get('has_warning', False), t20.get('has_backup', False))

        # 五、风险合规 (8分)
        if 'risk_incidents' in data:
            ri = data['risk_incidents']
            kpi.risk_incident_count = ri.get('count', 0)
            kpi.score_risk = KPIService.score_risk(ri['count'], ri.get('is_settled', False))

        if 'no_chain_rate' in data:
            nc = data['no_chain_rate']
            kpi.no_chain_rate = nc.get('current', 0)
            kpi.score_no_chain = KPIService.score_no_chain(
                nc.get('current', 0), nc.get('prev', 0))

        # 六、成本控制 (5分)
        if 'negotiation' in data:
            neg = data['negotiation']
            kpi.negotiation_count = neg.get('count', 0)
            kpi.negotiation_turnover_ok = neg.get('turnover_ok', False)
            kpi.score_cost = KPIService.score_cost(neg['count'], neg['turnover_ok'])

        # 加分项 / 扣分项
        kpi.bonus_points = data.get('bonus_points', 0)
        kpi.bonus_detail = str(data.get('bonus_detail', ''))
        kpi.penalty_points = data.get('penalty_points', 0)
        kpi.penalty_detail = str(data.get('penalty_detail', ''))

        # 计算总分
        kpi.calculate_total()

        db.session.commit()
        return kpi.to_dict()


class CommissionService:
    """提成计算服务"""

    @staticmethod
    def calculate_commission(period: str, evaluee: str, data: dict) -> dict:
        """
        计算提成: (A + B) × C - D
        """
        kpi = MonthlyKPI.query.filter_by(period=period, evaluee=evaluee).first()

        commission = MonthlyCommission.query.filter_by(period=period, evaluee=evaluee).first()
        if not commission:
            commission = MonthlyCommission(period=period, evaluee=evaluee)
            db.session.add(commission)

        if kpi:
            commission.kpi_id = kpi.id

        # ===== A. 执行质量提成 (55%) =====
        delivery_rate = data.get('delivery_rate', 0)
        commission.delivery_amount = 700 if delivery_rate >= 0.95 else 0

        deviation = data.get('first_batch_deviation', 1)
        if deviation <= 0.20:
            commission.accuracy_amount = 900
        elif deviation <= 0.40:
            commission.accuracy_amount = 500
        else:
            commission.accuracy_amount = 0

        disruptions = data.get('supply_disruption_count', 0)
        has_plan = data.get('supply_has_plan', False)
        if disruptions == 0:
            commission.stability_amount = 600
        elif disruptions == 1 and has_plan:
            commission.stability_amount = 300
        else:
            commission.stability_amount = 0

        # ===== B. 库存健康奖励 (45%) =====
        turnover_change = data.get('turnover_days_change', 0)
        if turnover_change <= -2:
            commission.turnover_bonus = 2000
        elif turnover_change <= -1:
            commission.turnover_bonus = 1200
        elif abs(turnover_change) <= 1:
            commission.turnover_bonus = 400
        else:
            commission.turnover_bonus = 0

        slow_sku_rate = data.get('slow_sku_decrease_rate', 0)
        if slow_sku_rate >= 0.10:
            commission.slow_sku_bonus = 1000
        elif slow_sku_rate >= 0.05:
            commission.slow_sku_bonus = 600
        elif slow_sku_rate >= 0.01:
            commission.slow_sku_bonus = 200
        else:
            commission.slow_sku_bonus = 0

        slow_amount_rate = data.get('slow_amount_decrease_rate', 0)
        if slow_amount_rate >= 0.10:
            commission.slow_amount_bonus = 800
        elif slow_amount_rate >= 0.05:
            commission.slow_amount_bonus = 400
        elif slow_amount_rate >= 0.01:
            commission.slow_amount_bonus = 100
        else:
            commission.slow_amount_bonus = 0

        # 系统完成率 - 自动从系统获取
        stats = SlowMovingMonthlyStats.query.filter_by(period=period).first()
        completion_rate = float(stats.completion_rate) if stats else data.get('system_completion_rate', 0)
        if completion_rate >= 0.95:
            commission.system_completion_bonus = 700
        elif completion_rate >= 0.90:
            commission.system_completion_bonus = 400
        elif completion_rate >= 0.80:
            commission.system_completion_bonus = 100
        else:
            commission.system_completion_bonus = 0

        # ===== C. 过程行为系数 =====
        processing_rate = data.get('processing_timeliness', 1.0)
        if processing_rate >= 1.0:
            commission.coeff_processing = 1.1
        elif processing_rate < 0.80:
            commission.coeff_processing = 0.9
        else:
            commission.coeff_processing = 1.0

        top20_incident = data.get('top20_stockout_incident', False)
        top20_warning = data.get('top20_has_warning', False)
        if not top20_incident:
            commission.coeff_stockout = 1.0
        elif top20_warning:
            commission.coeff_stockout = 0.95
        else:
            commission.coeff_stockout = 0.8

        has_proactive_return = data.get('has_proactive_return', False)
        commission.coeff_return = 1.05 if has_proactive_return else 1.0

        negotiation_ok = data.get('negotiation_dual_target', False)
        negotiation_only = data.get('negotiation_only', False)
        if negotiation_ok:
            commission.coeff_negotiation = 1.1
        elif negotiation_only:
            commission.coeff_negotiation = 1.0
        else:
            commission.coeff_negotiation = 1.0

        # ===== D. 重大损失扣罚 =====
        if data.get('banned_product_complaint', False):
            commission.major_penalty_type = 'banned_product'
            commission.major_penalty_effect = 'cancel_all'
        elif data.get('legal_dispute', False):
            commission.major_penalty_type = 'legal_dispute'
            commission.major_penalty_effect = 'cancel_all'
        elif data.get('consecutive_2month_worsen', False):
            commission.major_penalty_type = 'consecutive_worsen'
            commission.major_penalty_effect = 'half'
        elif data.get('system_2month_below_60', False):
            commission.major_penalty_type = 'system_below_60'
            commission.major_penalty_effect = 'cancel_b'
        else:
            commission.major_penalty_type = None
            commission.major_penalty_effect = 'none'

        commission.calculate()
        db.session.commit()

        return commission.to_dict()
