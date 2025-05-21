import os
from flask import Flask, current_app
from flask_login import LoginManager, UserMixin
from flask_bootstrap import Bootstrap
from flask import Flask, render_template

from flask_wtf.csrf import CSRFProtect
from supabase import create_client

# Define User class
class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.username = username
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-unique-secret-key'  # Replace with a secure string
    
    
    # 通过环境变量获取 Supabase URL 和 API 密钥
    SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://rvse******zic.supabase.co')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '***********dXBhYmFzZSIsInJlZiI6InJ2c2V6cnFrbndnbmJid2Z2emljIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDc3MjI5MjQsImV4cCI6MjA2MzI5ODkyNH0.TrYdoNWGJA1JJbluilGDvWiRZDsh9zZ3Kg-l8dPJwSQ')

    # 创建 Supabase 客户端
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    # supabase = create_client(SUPABASE_URL, SUPABASE_KEY, options={"verify_ssl": False})

    app.db = supabase 
    
    # Initialize Bootstrap
    Bootstrap(app)
    CSRFProtect(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'



    # Register user_loader
    @login_manager.user_loader
    def load_user(user_id):
        return User(user_id)

    # Register blueprints
    from auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')  # Add /auth prefix
    # Custom 404 error handler
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    

    return app
