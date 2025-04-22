from flask import redirect, url_for, session, flash, request, render_template


def configure_auth(app):
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            # Verificação simples (em produção, use bcrypt)
            if username == 'admin' and password == 'senha_segura':
                session['logged_in'] = True
                session['username'] = username
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('web.dashboard'))

            flash('Credenciais inválidas!', 'danger')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Você foi desconectado.', 'info')
        return redirect(url_for('web.login'))