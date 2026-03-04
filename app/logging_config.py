import logging
from logging.handlers import RotatingFileHandler
import os
import sys

class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass

def setup_logging(app):
    """
    Configure file-based logging for the Flask application.
    Logs will be saved to logs/app.log with automatic rotation.
    Captures stdout, stderr, and werkzeug logs.
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, 'app.log')
    
    # Configure log format
    log_format = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create rotating file handler (max 10MB per file, keep 5 backup files)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(logging.DEBUG)  # Capture everything including DEBUG
    
    # Create console handler for development (so we still see logs in terminal)
    console_handler = logging.StreamHandler(sys.__stdout__) # Write to original stdout
    console_handler.setFormatter(log_format)
    console_handler.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    if app.logger.hasHandlers():
        app.logger.handlers.clear()
    
    # Add handlers to app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    
    # Set overall logging level to DEBUG
    app.logger.setLevel(logging.DEBUG)
    
    # --- Capture Werkzeug (Flask Request) Logs ---
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.DEBUG)
    werkzeug_logger.addHandler(file_handler)
    # Note: Werkzeug already prints to stdout, so we don't need to add console_handler 
    # if we are not redirecting stdout yet, but adding file_handler ensures it goes to file.

    # --- Do NOT redirect stdout/stderr to the logger ---
    # Redirecting causes repeated "ERROR:app:..." and "Exception ignored in sys.unraisablehook"
    # when handlers or unraisablehook write to stderr, which is then logged again.
    # sys.stdout = StreamToLogger(app.logger, logging.INFO)
    # sys.stderr = StreamToLogger(app.logger, logging.ERROR)

    # Log application startup
    app.logger.info('='*50)
    app.logger.info('Application starting up - Full Terminal Capture Enabled')
    app.logger.info(f'Log file: {log_file}')
    app.logger.info('='*50)
    
    return app.logger
