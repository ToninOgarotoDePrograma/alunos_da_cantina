from flask import Blueprint


def init_app(app):
    # Cria o blueprint
    web_bp = Blueprint('web', __name__,
                       template_folder='templates',
                       static_folder='static')

    # Importa e configura as rotas
    from . import routes
    routes.configure_routes(web_bp)

    # Registra o blueprint
    app.register_blueprint(web_bp, url_prefix='/admin')  # Opcional: adicione um prefixo