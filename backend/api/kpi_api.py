"""
KPI绩效考核 & 提成计算 API接口
"""
from flask import Blueprint, request, jsonify
from backend.services.kpi_service import KPIService, CommissionService
from backend.models.kpi import MonthlyKPI, MonthlyCommission

kpi_bp = Blueprint('kpi', __name__, url_prefix='/api/kpi')


@kpi_bp.route('/calculate', methods=['POST'])
def calculate_kpi():
    """计算完整KPI评分"""
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '请求数据为空'}), 400

    period = data.get('period')
    evaluee = data.get('evaluee', '采购主管')
    if not period:
        return jsonify({'code': 400, 'message': '缺少考核周期period'}), 400

    result = KPIService.calculate_full_kpi(period, evaluee, data)
    return jsonify({'code': 0, 'data': result})


@kpi_bp.route('/detail', methods=['GET'])
def get_kpi_detail():
    """查询KPI详情"""
    period = request.args.get('period')
    evaluee = request.args.get('evaluee', '采购主管')

    kpi = MonthlyKPI.query.filter_by(period=period, evaluee=evaluee).first()
    if not kpi:
        return jsonify({'code': 404, 'message': '未找到考核记录'}), 404

    return jsonify({'code': 0, 'data': kpi.to_dict()})


@kpi_bp.route('/history', methods=['GET'])
def get_kpi_history():
    """查询KPI历史记录"""
    evaluee = request.args.get('evaluee', '采购主管')
    records = MonthlyKPI.query.filter_by(evaluee=evaluee).order_by(
        MonthlyKPI.period.desc()).limit(12).all()

    return jsonify({
        'code': 0,
        'data': [r.to_dict() for r in records]
    })


@kpi_bp.route('/commission/calculate', methods=['POST'])
def calculate_commission():
    """计算提成"""
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '请求数据为空'}), 400

    period = data.get('period')
    evaluee = data.get('evaluee', '采购主管')
    if not period:
        return jsonify({'code': 400, 'message': '缺少考核周期period'}), 400

    result = CommissionService.calculate_commission(period, evaluee, data)
    return jsonify({'code': 0, 'data': result})


@kpi_bp.route('/commission/detail', methods=['GET'])
def get_commission_detail():
    """查询提成详情"""
    period = request.args.get('period')
    evaluee = request.args.get('evaluee', '采购主管')

    commission = MonthlyCommission.query.filter_by(
        period=period, evaluee=evaluee).first()
    if not commission:
        return jsonify({'code': 404, 'message': '未找到提成记录'}), 404

    return jsonify({'code': 0, 'data': commission.to_dict()})


@kpi_bp.route('/score-preview', methods=['POST'])
def score_preview():
    """实时预览评分（不保存）- 用于前端即时计算"""
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '请求数据为空'}), 400

    preview = {}

    # 各维度分数预览
    if 'turnover_days' in data:
        td = data['turnover_days']
        preview['turnover_days'] = KPIService.score_turnover_days(
            td.get('current', 0), td.get('prev', 0))

    if 'high_turnover_sku' in data:
        ht = data['high_turnover_sku']
        preview['high_turnover_sku'] = KPIService.score_high_turnover_sku(
            ht.get('current', 0), ht.get('prev', 0))

    if 'system_completion_rate' in data:
        preview['system_completion'] = KPIService.score_system_completion(
            data['system_completion_rate'])

    if 'delivery_rate' in data:
        preview['delivery'] = KPIService.score_delivery(data['delivery_rate'])

    if 'first_batch_deviation' in data:
        preview['first_batch'] = KPIService.score_first_batch(
            data['first_batch_deviation'])

    total = sum(preview.values())
    preview['subtotal'] = total

    return jsonify({'code': 0, 'data': preview})
