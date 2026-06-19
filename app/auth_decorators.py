"""Shared Flask-Login authorization decorators."""

from functools import wraps

from flask import jsonify
from flask_login import current_user


def super_admin_required(f):
    """Require Admin role and Super-admin privilege."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        if current_user.userRole != 'Admin' or not current_user.has_privilege('Super-admin'):
            return jsonify({'error': 'Super-admin access required'}), 403
        return f(*args, **kwargs)

    return decorated


def is_super_admin() -> bool:
    return (
        current_user.is_authenticated
        and current_user.userRole == 'Admin'
        and current_user.has_privilege('Super-admin')
    )
