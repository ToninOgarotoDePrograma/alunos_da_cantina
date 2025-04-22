from flask import render_template, request, redirect, url_for, flash, session
from functools import wraps


def configure_routes(bp):
    # ===== ROTA DE LOGIN =====
    @bp.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            # Verificação simples (em produção use bcrypt)
            if username == 'admin' and password == 'admin123':
                session['logged_in'] = True
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('web.dashboard'))

            flash('Credenciais inválidas!', 'danger')
        return render_template('login.html')

    @bp.route('/logout')
    def logout():
        session.clear()
        flash('Você foi desconectado.', 'info')
        return redirect(url_for('web.login'))

    # ===== PROTEGER ROTAS =====
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                return redirect(url_for('web.login'))  # Agora esta rota existe
            return f(*args, **kwargs)

        return decorated_function

    # ===== DASHBOARD =====
    @bp.route('/')
    @login_required
    def dashboard():
        return render_template('dashboard.html')