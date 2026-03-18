"""
采购补货决策系统 - Flask应用主入口
"""
from flask import Flask, send_from_directory
from backend.models.database import db
from backend.config.settings import SQLALCHEMY_DATABASE_URI, APP_CONFIG


def create_app():
    app = Flask(__name__,
                static_folder='../frontend',
                static_url_path='/static')

    # 数据库配置
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = APP_CONFIG['SECRET_KEY']
    app.config['JSON_AS_ASCII'] = False

    # 初始化数据库
    db.init_app(app)

    # 注册蓝图
    from backend.api.slow_moving_api import slow_moving_bp
    from backend.api.kpi_api import kpi_bp
    app.register_blueprint(slow_moving_bp)
    app.register_blueprint(kpi_bp)

    # 前端路由
    @app.route('/')
    def index():
        return send_from_directory('../frontend', 'index.html')

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    # 创建数据库表
    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(
        host=APP_CONFIG['HOST'],
        port=APP_CONFIG['PORT'],
        debug=APP_CONFIG['DEBUG'],
    )
