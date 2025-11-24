# File-Based Logging Setup

## Overview
The application now has comprehensive file-based logging configured. **All terminal output**, including `print()` statements, Flask request logs, and errors, is automatically saved to `logs/app.log`. Logs can be viewed anytime through the web interface or directly from the file system.

## Features

### 1. Full Terminal Capture
- Redirects `stdout` (print statements) to INFO logs
- Redirects `stderr` (errors/tracebacks) to ERROR logs
- Captures Flask/Werkzeug request logs (e.g., `GET / 200 OK`)
- Ensures nothing is missed from the console output

### 2. Automatic Log Rotation
- Logs automatically rotate when they reach 10MB in size
- Up to 5 backup files are kept (app.log.1, app.log.2, etc.)
- Old logs are automatically archived to prevent disk space issues

### 2. Log Levels
The application uses standard Python logging levels:
- **DEBUG**: Detailed information for diagnosing problems
- **INFO**: General informational messages (default level)
- **WARNING**: Warning messages for potentially problematic situations
- **ERROR**: Error messages for serious problems
- **CRITICAL**: Critical messages for very serious errors

### 3. Web Dashboard
Admin users can access the logs dashboard at `/logs` which provides:
- Real-time log viewing with auto-refresh (every 30 seconds)
- Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Search/filter logs by keywords
- Adjust number of lines displayed (50-1000)
- Download full log files
- View list of all log files including rotated backups
- Color-coded log levels for easy visual scanning

### 4. Log Format
Each log entry includes:
```
[YYYY-MM-DD HH:MM:SS] LEVEL in module: message
```

Example:
```
[2025-11-22 04:15:30] INFO in routes: User john logged in
[2025-11-22 04:15:45] ERROR in database_routes: Database connection failed
```

## Accessing Logs

### Via Web Interface
1. Log in as an Admin user
2. Navigate to the sidebar menu
3. Click on "Application Logs" under the Settings section
4. Use the filters and controls to view specific logs

### Via File System
Logs are stored in the `logs/` directory at the project root:
```
AI Dashboard/
├── logs/
│   ├── app.log           # Current log file
│   ├── app.log.1         # First backup (when rotated)
│   ├── app.log.2         # Second backup
│   └── ...
```

You can view logs directly using:
```bash
# View recent logs
tail -f logs/app.log

# View last 100 lines
tail -n 100 logs/app.log

# Search for errors
grep "ERROR" logs/app.log

# Search for specific term
grep "database" logs/app.log
```

## API Endpoints

Admin users can also access logs programmatically:

### GET `/api/monitoring/logs`
View recent logs with optional filtering
```
Parameters:
- lines: Number of lines to return (default: 100, max: 1000)
- level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- search: Search term to filter logs

Example:
/api/monitoring/logs?lines=500&level=ERROR&search=database
```

### GET `/api/monitoring/logs/download`
Download the full current log file

### GET `/api/monitoring/logs/files`
Get a list of all available log files including rotated backups

## Configuration

The logging configuration is located in `app/logging_config.py`:

```python
def setup_logging(app):
    # Log file location
    log_file = 'logs/app.log'
    
    # Rotation settings
    maxBytes = 10 * 1024 * 1024  # 10MB
    backupCount = 5               # Keep 5 backups
    
    # Log level
    app.logger.setLevel(logging.INFO)
```

To change settings, modify this file and restart the application.

## Using Logging in Your Code

To add logging to your routes or functions:

```python
from app import app

# Log informational messages
app.logger.info("User performed action X")

# Log warnings
app.logger.warning("Unusual condition detected")

# Log errors
app.logger.error(f"Error processing request: {error}")

# Log critical issues
app.logger.critical("System is in critical state")

# Log with formatted strings
app.logger.info(f"User {username} logged in from {ip_address}")
```

### Example Usage in Routes

```python
@app.route('/api/example')
def example_route():
    app.logger.info(f"Example route accessed by {current_user.username}")
    
    try:
        # Your code here
        result = process_data()
        app.logger.info("Data processed successfully")
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error in example route: {e}")
        return jsonify({'error': str(e)}), 500
```

## Troubleshooting

### Logs not appearing?
1. Check that the `logs/` directory exists and is writable
2. Restart the application to reinitialize logging
3. Verify you're logged in as an Admin user to access the dashboard

### Log file too large?
The rotation should handle this automatically, but if needed:
1. Stop the application
2. Archive or delete old log files
3. Restart the application

### Performance issues?
If the web dashboard is slow:
1. Reduce the number of lines displayed
2. Use specific filters to narrow results
3. Download logs and analyze offline for very large files

## Best Practices

1. **Use appropriate log levels**: Don't log everything as ERROR
2. **Include context**: Add relevant information like usernames, IDs, etc.
3. **Avoid logging sensitive data**: Never log passwords, tokens, or PII
4. **Be concise**: Log messages should be clear but not overly verbose
5. **Use structured logging**: Include relevant details in a consistent format

## Monitoring and Alerts

Consider setting up:
- Log monitoring tools to alert on ERROR/CRITICAL messages
- Regular log reviews for WARNING messages
- Automated log analysis for patterns and trends
- Integration with external logging services (Sentry, LogDNA, etc.)
