from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from src.services.auth_service import verify_password

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        password = request.form['password']
        error = None

        if verify_password(password):
            session.clear()
            session['is_admin'] = True
            return redirect(url_for('main.dashboard'))
        else:
            error = 'Invalid Password'
            flash(error)

    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))