import functools
from flask import session, redirect, url_for, current_app

def is_authenticated():
    """Check if the current session has the correct admin flag."""
    return session.get('is_admin') is True

def login_required(view):
    """Decorator to gate routes behind authentication."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not is_authenticated():
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view

def verify_password(provided_password):
    """Compare provided password against the environment variable."""
    # In a multi-user system, we would hash this.
    # For single-family access, strict equality against ENV is sufficient.
    correct_password = current_app.config['ADMIN_PASSWORD']
    return provided_password == correct_password