import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')

    # Email settings (SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 't', 'yes', 'y')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # e.g. your Gmail address
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # e.g. Gmail App Password
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME'))
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'false').lower() in ('true', '1', 't', 'yes', 'y')

    # Token salt for password reset
    SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT', 'change-this-salt')

    # Cache configuration
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'SimpleCache')  # or 'redis' for production
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes default
