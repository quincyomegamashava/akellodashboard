import os
from pathlib import Path

basedir = os.path.abspath(os.path.dirname(__file__))

# Load .env so HELP_DESK_* / HELPDESK_* are available when Config is evaluated
try:
    from dotenv import load_dotenv
    env_path = Path(basedir) / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


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

    # Helpdesk email tickets: IMAP (Outlook)
    # Set HELPDESK_EMAIL or HELP_DESK_EMAIL to your Outlook address; HELPDESK_APP_PASSWORD or HELP_DESK_EMAIL_APP_PASSWORD to the app password.
    HELPDESK_IMAP_SERVER = os.environ.get('HELPDESK_IMAP_SERVER') or os.environ.get('HELP_DESK_IMAP_SERVER') or 'outlook.office365.com'
    HELPDESK_IMAP_PORT = int(os.environ.get('HELPDESK_IMAP_PORT') or os.environ.get('HELP_DESK_IMAP_PORT') or '993')
    HELPDESK_EMAIL = os.environ.get('HELPDESK_EMAIL') or os.environ.get('HELP_DESK_EMAIL')
    HELPDESK_APP_PASSWORD = os.environ.get('HELPDESK_APP_PASSWORD') or os.environ.get('HELP_DESK_EMAIL_APP_PASSWORD')

    # Cache configuration
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'SimpleCache')  # or 'redis' for production
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes default

    # AI generation (do not hardcode secrets in source code)
    # Default provider: ollama | gemini | openai (UI may override per request)
    GENERATION_PROVIDER = os.environ.get('GENERATION_PROVIDER', 'ollama').lower()
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini')

    # Google Gemini (Generative Language API). AI Studio often exports GOOGLE_API_KEY.
    GEMINI_API_KEY = (
        os.environ.get('GEMINI_API_KEY')
        or os.environ.get('GOOGLE_API_KEY')
        or os.environ.get('GOOGLE_GENERATIVE_AI_API_KEY')
    )
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
    GEMINI_TEMPERATURE = float(os.environ.get('GEMINI_TEMPERATURE', '0.2'))
    GEMINI_MAX_OUTPUT_TOKENS = int(os.environ.get('GEMINI_MAX_OUTPUT_TOKENS', '8192'))

    # Ollama integration
    OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.1')
    OLLAMA_CONTENT_MODEL = os.environ.get('OLLAMA_CONTENT_MODEL')
    OLLAMA_AUTHORIZATION = os.environ.get('OLLAMA_AUTHORIZATION')
    OLLAMA_API_KEY = os.environ.get('OLLAMA_API_KEY')
    OLLAMA_TEMPERATURE = float(os.environ.get('OLLAMA_TEMPERATURE', '0.2'))
    OLLAMA_NUM_PREDICT = int(os.environ.get('OLLAMA_NUM_PREDICT', '900'))
    GENERATION_PROGRESS_TARGET_CHARS = int(os.environ.get('GENERATION_PROGRESS_TARGET_CHARS', '2600'))
