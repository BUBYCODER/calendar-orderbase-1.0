from flask import Flask
import os
from app.models import database

def create_app():
    app = Flask(__name__)
    app.secret_key = 'production-calendar-secret-2024'
    
    # Папка для загрузок (макеты)
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Инициализация БД
    if not os.path.exists(database.DB_PATH):
        database.init_db()
    else:
        database.cleanup_db()
        database.upgrade_db()

    # Регистрация старого функционала (календарь)
    from app.blueprints.legacy import legacy_bp
    app.register_blueprint(legacy_bp)
    
    from app.blueprints.orders import orders_bp
    app.register_blueprint(orders_bp)
    
    return app

# Точка входа для Gunicorn хостинга
app = create_app()
