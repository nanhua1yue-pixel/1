"""
滞销品处理API接口
"""
from flask import Blueprint, request, jsonify
from backend.services.slow_moving_service import SlowMovingService

slow_moving_bp = Blueprint('slow_moving', __name__, url_prefix='/api/slow-moving')


@slow_moving_bp.route('/list', methods=['GET'])
def get_list():
    """获取滞销品列表"""
    params = {
        'period': request.args.get('period'),
        'status': request.args.get('status'),
        'slow_type': request.args.get('slow_type'),
        'can_return': request.args.get('can_return'),
        'action_type': request.args.get('action_type'),
        'keyword': request.args.get('keyword'),
        'sort_by': request.args.get('sort_by', 'stock_amount'),
        'sort_order': request.args.get('sort_order', 'desc'),
        'page': int(request.args.get('page', 1)),
        'page_size': int(request.args.get('page_size', 20)),
    }
    result = SlowMovingService.get_slow_moving_list(**params)
    return jsonify({'code': 0, 'data': result})


@slow_moving_bp.route('/dashboard', methods=['GET'])
def get_dashboard():
    """获取滞销品仪表盘数据"""
    period = request.args.get('period')
    result = SlowMovingService.get_dashboard_stats(period)
    return jsonify({'code': 0, 'data': result})


@slow_moving_bp.route('/process', methods=['POST'])
def process_sku():
    """处理滞销品 - 标记退货决策+处置动作"""
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': '请求数据为空'}), 400

    required = ['sku_id', 'can_return', 'action_type']
    for field in required:
        if field not in data:
            return jsonify({'code': 400, 'message': f'缺少必填字段: {field}'}), 400

    try:
        result = SlowMovingService.process_sku(
            sku_id=data['sku_id'],
            can_return=data['can_return'],
            return_reason=data.get('return_reason', ''),
            action_type=data['action_type'],
            action_detail=data.get('action_detail', ''),
            action_deadline=data.get('action_deadline'),
            operator=data.get('operator', '采购主管'),
        )
        return jsonify({'code': 0, 'data': result, 'message': '处理成功'})
    except ValueError as e:
        return jsonify({'code': 404, 'message': str(e)}), 404


@slow_moving_bp.route('/complete', methods=['POST'])
def complete_sku():
    """标记滞销品处理完成"""
    data = request.get_json()
    if not data or 'sku_id' not in data:
        return jsonify({'code': 400, 'message': '缺少sku_id'}), 400

    try:
        result = SlowMovingService.complete_sku(
            sku_id=data['sku_id'],
            actual_return_amount=data.get('actual_return_amount', 0),
            actual_clear_amount=data.get('actual_clear_amount', 0),
            result_note=data.get('result_note', ''),
            operator=data.get('operator', '采购主管'),
        )
        return jsonify({'code': 0, 'data': result, 'message': '已标记完成'})
    except ValueError as e:
        return jsonify({'code': 404, 'message': str(e)}), 404


@slow_moving_bp.route('/batch-process', methods=['POST'])
def batch_process():
    """批量处理滞销品"""
    data = request.get_json()
    if not data or 'sku_ids' not in data:
        return jsonify({'code': 400, 'message': '缺少sku_ids'}), 400

    results = SlowMovingService.batch_process(
        sku_ids=data['sku_ids'],
        can_return=data.get('can_return', 'no'),
        action_type=data.get('action_type', 'hold'),
        action_detail=data.get('action_detail', ''),
        operator=data.get('operator', '采购主管'),
    )
    return jsonify({'code': 0, 'data': results})


@slow_moving_bp.route('/logs', methods=['GET'])
def get_logs():
    """获取操作日志"""
    params = {
        'sku_id': request.args.get('sku_id', type=int),
        'operator': request.args.get('operator'),
        'start_date': request.args.get('start_date'),
        'end_date': request.args.get('end_date'),
        'page': int(request.args.get('page', 1)),
        'page_size': int(request.args.get('page_size', 20)),
    }
    result = SlowMovingService.get_process_logs(**params)
    return jsonify({'code': 0, 'data': result})


@slow_moving_bp.route('/monthly-stats', methods=['GET'])
def get_monthly_stats():
    """获取/生成月度统计"""
    period = request.args.get('period')
    result = SlowMovingService.generate_monthly_stats(period)
    return jsonify({'code': 0, 'data': result})
