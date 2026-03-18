"""
采购补货决策系统 - 配置文件
"""
import os

# ==================== 数据库配置 ====================
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'purchase_system'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'purchase_decision'),
    'charset': 'utf8mb4',
}

SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    f"?charset={DB_CONFIG['charset']}"
)

# ==================== 旺店通API配置 ====================
WDT_API = {
    'base_url': 'https://openapi.wangdian.cn/openapi2',
    'sid': os.getenv('WDT_SID', 'yhcs03'),
    'appkey': os.getenv('WDT_APPKEY', 'yhcs03-otb'),
    'appsecret': os.getenv('WDT_APPSECRET', '3f14833b7e0cab5e12093d8683a415eb:13919219130536059064aa5236ea922c'),
}

# ==================== 绩效考核配置 ====================
# 一、库存周转与现金效率 (30分)
KPI_INVENTORY_TURNOVER = {
    'total_score': 30,
    'metrics': {
        # 整体库存周转天数 (12分)
        'turnover_days': {
            'score': 12,
            'rules': [
                {'condition': 'decrease >= 2', 'score': 12, 'label': '环比下降≥2天'},
                {'condition': 'decrease >= 1', 'score': 8, 'label': '下降1天'},
                {'condition': 'abs(change) <= 1', 'score': 4, 'label': '持平(±1天以内)'},
                {'condition': 'increase <= 3', 'score': 1, 'label': '上升1-3天'},
                {'condition': 'increase > 3', 'score': 0, 'label': '上升>3天'},
            ]
        },
        # 高周转SKU优化 (10分)
        'high_turnover_sku': {
            'score': 10,
            'rules': [
                {'condition': 'optimize >= 8%', 'count': '>=57', 'score': 10},
                {'condition': 'optimize 4%-8%', 'count': '28-56', 'score': 7},
                {'condition': 'optimize 1%-4%', 'count': '7-27', 'score': 4},
                {'condition': 'hold ±1%', 'score': 1},
                {'condition': 'worsen', 'score': 0},
            ]
        },
        # 库存总金额 & N指数 (8分)
        'n_index': {
            'score': 8,
            'rules': [
                {'condition': 'n_decrease_and_amount_decrease', 'score': 8},
                {'condition': 'n_hold_amount_decrease', 'score': 5},
                {'condition': 'n_hold_amount_hold', 'score': 2},
                {'condition': 'n_increase_or_amount_increase', 'score': 0},
            ]
        },
    }
}

# 二、滞销管理 (25分)
KPI_SLOW_MOVING = {
    'total_score': 25,
    'metrics': {
        # 月销<10 SKU数量下降 (8分)
        'slow_sku_decrease': {
            'score': 8,
            'rules': [
                {'condition': 'decrease >= 10%', 'count': '>=156', 'score': 8},
                {'condition': 'decrease 5%-10%', 'count': '78-155', 'score': 5},
                {'condition': 'decrease 1%-5%', 'count': '16-77', 'score': 2},
                {'condition': 'hold', 'score': 0},
                {'condition': 'increase', 'score': -3, 'label': '额外扣分'},
            ]
        },
        # 系统滞销品处理完成率 (10分) ★核心
        'system_completion_rate': {
            'score': 10,
            'rules': [
                {'condition': 'rate >= 95%', 'score': 10},
                {'condition': 'rate 90%-95%', 'score': 7},
                {'condition': 'rate 80%-90%', 'score': 3},
                {'condition': 'rate 60%-80%', 'score': 1},
                {'condition': 'rate < 60%', 'score': 0, 'penalty': -10, 'label': '同时触发扣分项'},
            ]
        },
        # 月销<300链接库存金额 (4分)
        'slow_inventory_amount': {
            'score': 4,
            'rules': [
                {'condition': 'decrease >= 10%', 'amount': '>=12w', 'score': 4},
                {'condition': 'decrease 5%-10%', 'amount': '6-12w', 'score': 2},
                {'condition': 'decrease 1%-5%', 'amount': '1-6w', 'score': 1},
                {'condition': 'hold_or_increase', 'score': 0},
            ]
        },
        # 效期管理 (3分)
        'expiry_management': {
            'score': 3,
            'rules': [
                {'condition': '0_miss', 'score': 3},
                {'condition': '1_miss', 'score': 1},
                {'condition': '>=2_miss', 'score': 0},
            ]
        },
    }
}

# 三、采购执行能力 (20分)
KPI_PURCHASE_EXECUTION = {
    'total_score': 20,
    'metrics': {
        'new_product_delivery': {'score': 6},
        'first_batch_accuracy': {'score': 8},
        'supply_stability': {'score': 6},
    }
}

# 四、缺货管控 (12分)
KPI_STOCKOUT_CONTROL = {
    'total_score': 12,
    'metrics': {
        'stockout_sku_count': {'score': 5},
        'top20_stockout': {'score': 7},
    }
}

# 五、风险合规+无链路 (8分)
KPI_RISK_COMPLIANCE = {
    'total_score': 8,
    'metrics': {
        'risk_incidents': {'score': 5},
        'no_supply_chain': {'score': 3},
    }
}

# 六、成本控制 (5分)
KPI_COST_CONTROL = {
    'total_score': 5,
    'metrics': {
        'effective_negotiation': {'score': 5},
    }
}

# ==================== 提成方案配置 ====================
COMMISSION_CONFIG = {
    # A. 执行质量提成 (55%)
    'execution_quality': {
        'new_product_delivery': {
            'target': 0.95,
            'amount': 700,  # 达标=700元
        },
        'first_batch_accuracy': {
            'rules': [
                {'max_deviation': 0.20, 'amount': 900},
                {'max_deviation': 0.40, 'amount': 500},
                {'max_deviation': 1.00, 'amount': 0},
            ]
        },
        'supply_stability': {
            'rules': [
                {'incidents': 0, 'amount': 600},
                {'incidents': 1, 'has_plan': True, 'amount': 300},
                {'incidents': 1, 'has_plan': False, 'amount': 0},
            ]
        },
    },
    # B. 库存健康奖励 (45%)
    'inventory_health': {
        'turnover_days_change': {
            'rules': [
                {'decrease': 2, 'amount': 2000},
                {'decrease': 1, 'amount': 1200},
                {'hold': True, 'amount': 400},
                {'increase': True, 'amount': 0},
            ]
        },
        'slow_sku_decrease': {
            'rules': [
                {'rate': 0.10, 'amount': 1000},
                {'rate': 0.05, 'amount': 600},
                {'rate': 0.01, 'amount': 200},
                {'rate': 0, 'amount': 0},
            ]
        },
        'slow_inventory_decrease': {
            'rules': [
                {'rate': 0.10, 'amount': 800},
                {'rate': 0.05, 'amount': 400},
                {'rate': 0.01, 'amount': 100},
                {'rate': 0, 'amount': 0},
            ]
        },
        'system_completion_rate': {
            'rules': [
                {'rate': 0.95, 'amount': 700},
                {'rate': 0.90, 'amount': 400},
                {'rate': 0.80, 'amount': 100},
                {'rate': 0, 'amount': 0},
            ]
        },
    },
    # C. 过程行为系数
    'behavior_coefficient': {
        'system_processing_timeliness': {'positive': 1.1, 'negative': 0.9, 'threshold': 0.80},
        'top20_stockout_incident': {'positive': 1.0, 'negative': 0.8},
        'proactive_return': {'positive': 1.05, 'negative': 1.0},
        'negotiation_turnover_dual': {'positive': 1.1, 'negative': 1.0},
    },
    # D. 重大损失扣罚
    'major_penalty': {
        'banned_product_complaint': 'cancel_all',
        'legal_dispute': 'cancel_all',
        'consecutive_2month_worsen': 'half',
        'system_completion_2month_below_60': 'cancel_b',
    },
}

# ==================== 应用配置 ====================
APP_CONFIG = {
    'SECRET_KEY': os.getenv('SECRET_KEY', 'purchase-decision-system-2026'),
    'DEBUG': os.getenv('FLASK_DEBUG', 'True').lower() == 'true',
    'HOST': '0.0.0.0',
    'PORT': int(os.getenv('APP_PORT', 5000)),
}
