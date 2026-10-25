from pathlib import Path
from flask import Flask, render_template, send_from_directory
from config import Config
from core.extensions import db, login_manager, csrf

def create_app(test_config=None):
    app=Flask(__name__,instance_relative_config=True,template_folder='core/templates',static_folder='core/static',static_url_path='/static')
    app.config.from_object(Config)
    if test_config: app.config.update(test_config)
    if not app.config.get('SECRET_KEY'): raise RuntimeError('Set SECRET_KEY in .env before starting the app. See .env.example.')
    Path(app.instance_path).mkdir(exist_ok=True)
    db.init_app(app); login_manager.init_app(app); csrf.init_app(app)
    login_manager.login_view='auth.login'
    import auth.models, shop.models, core.messages, rewards.models, game.models, shop.inventory, products.media, products.custom, core.popups
    from importlib import import_module
    for name in ('main','about','legal','auth','products','shop','shop.referral','where_to_buy','admin','vibe_test','feed','creators','contact','rewards','game','products.media','core.popups','support','core.i18n'):
        app.register_blueprint(import_module(name).bp)
    from core.cli import register_cli
    from core.nav import NAV_ITEMS
    register_cli(app)
    app.jinja_env.globals['NAV_ITEMS']=NAV_ITEMS
    from core.i18n import init_i18n
    init_i18n(app)
    app.jinja_env.filters['usd']=lambda v:f'${v:,.2f}'
    @app.get('/images/<path:filename>')
    def images(filename): return send_from_directory(Path(app.root_path)/'images',filename)
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='SAMEORIGIN'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        if not response.direct_passthrough: response.headers['Cache-Control']='no-store'
        return response
    for code in (400,403,404,500):
        app.register_error_handler(code,lambda error: (render_template('core/error.html',code=error.code,title='Let’s get you back on track'),error.code))
    return app
