"""
Real-time User Activity Monitoring Routes
"""
from flask import jsonify, render_template, request, send_file
from flask_login import current_user, login_required
from datetime import datetime, timedelta
import os
from app import app, db
from app.models import UserActivity, ActiveSession, PageAnalytics
from app.activity_tracker import get_active_users_count, get_recent_activities, get_popular_pages, get_user_journey


@app.route('/monitoring', methods=['GET'])
@login_required
def monitoring_dashboard():
    """Admin monitoring dashboard page"""
    if current_user.userRole != 'Admin':
        return "Unauthorized", 403
    
    return render_template('monitoring_dashboard.html', title='Real-time Monitoring')


@app.route('/api/monitoring/activities', methods=['GET'])
@login_required
def get_activities():
    """Get user activities with optional filtering"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Parse query parameters
        username = request.args.get('username')
        activity_type = request.args.get('activity_type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
        
        # Build query
        query = UserActivity.query
        
        if username:
            query = query.filter(UserActivity.username.ilike(f'%{username}%'))
        
        if activity_type:
            query = query.filter(UserActivity.activity_type == activity_type)
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(UserActivity.timestamp >= start_dt)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            query = query.filter(UserActivity.timestamp <= end_dt)
        
        # Get total count
        total_count = query.count()
        
        # Get paginated results
        activities = query.order_by(
            UserActivity.timestamp.desc()
        ).offset(offset).limit(limit).all()
        
        return jsonify({
            'activities': [activity.to_dict() for activity in activities],
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'has_more': (offset + limit) < total_count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/sessions', methods=['GET'])
@login_required
def get_active_sessions():
    """Get currently active sessions"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get sessions active in the last 15 minutes
        cutoff_time = datetime.utcnow() - timedelta(minutes=15)
        
        sessions = ActiveSession.query.filter(
            ActiveSession.is_active == True,
            ActiveSession.last_seen >= cutoff_time
        ).order_by(
            ActiveSession.last_seen.desc()
        ).all()
        
        return jsonify({
            'sessions': [session.to_dict() for session in sessions],
            'active_count': len(sessions),
            'cutoff_time': cutoff_time.isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/stats', methods=['GET'])
@login_required
def get_monitoring_stats():
    """Get current monitoring statistics"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Time ranges
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(weeks=1)
        
        # Active users
        active_users = get_active_users_count()
        
        # Activity counts by time period
        hour_activities = UserActivity.query.filter(
            UserActivity.timestamp >= hour_ago
        ).count()
        
        day_activities = UserActivity.query.filter(
            UserActivity.timestamp >= day_ago
        ).count()
        
        week_activities = UserActivity.query.filter(
            UserActivity.timestamp >= week_ago
        ).count()
        
        # Activity type breakdown (last 24 hours)
        activity_types = db.session.query(
            UserActivity.activity_type,
            db.func.count(UserActivity.id).label('count')
        ).filter(
            UserActivity.timestamp >= day_ago
        ).group_by(UserActivity.activity_type).all()
        
        activity_type_counts = {activity_type: count for activity_type, count in activity_types}
        
        # Most active users (last 24 hours)
        most_active_users = db.session.query(
            UserActivity.username,
            db.func.count(UserActivity.id).label('activity_count')
        ).filter(
            UserActivity.timestamp >= day_ago,
            UserActivity.username.isnot(None)
        ).group_by(
            UserActivity.username
        ).order_by(
            db.func.count(UserActivity.id).desc()
        ).limit(10).all()
        
        # Popular pages
        popular_pages = get_popular_pages(10)
        
        return jsonify({
            'active_users': active_users,
            'activity_counts': {
                'last_hour': hour_activities,
                'last_day': day_activities,
                'last_week': week_activities
            },
            'activity_types': activity_type_counts,
            'most_active_users': [{
                'username': username,
                'activity_count': count
            } for username, count in most_active_users],
            'popular_pages': [page.to_dict() for page in popular_pages],
            'timestamp': now.isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/user-journey/<session_id>', methods=['GET'])
@login_required
def get_user_journey_api(session_id):
    """Get user journey for a specific session"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        activities = get_user_journey(session_id, 50)
        
        # Get session details
        session_info = ActiveSession.query.filter_by(session_id=session_id).first()
        
        return jsonify({
            'session_id': session_id,
            'session_info': session_info.to_dict() if session_info else None,
            'activities': [activity.to_dict() for activity in activities],
            'journey_length': len(activities)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/heartbeat', methods=['POST'])
@login_required
def monitoring_heartbeat():
    """Heartbeat endpoint to keep monitoring connection alive"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat(),
        'user': current_user.username
    })


@app.route('/api/monitoring/page-analytics', methods=['GET'])
@login_required
def get_page_analytics():
    """Get page analytics data"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get page analytics with optional filtering
        limit = min(int(request.args.get('limit', 20)), 100)
        
        page_analytics = PageAnalytics.query.order_by(
            PageAnalytics.total_visits.desc()
        ).limit(limit).all()
        
        return jsonify({
            'page_analytics': [page.to_dict() for page in page_analytics],
            'total_pages_tracked': PageAnalytics.query.count()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/activity-summary', methods=['GET'])
@login_required
def get_activity_summary():
    """Get activity summary for different time periods"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        now = datetime.utcnow()
        
        # Time periods
        periods = {
            'last_hour': now - timedelta(hours=1),
            'last_6_hours': now - timedelta(hours=6),
            'last_24_hours': now - timedelta(days=1),
            'last_week': now - timedelta(weeks=1)
        }
        
        summary = {}
        
        for period_name, start_time in periods.items():
            # Activity count
            activity_count = UserActivity.query.filter(
                UserActivity.timestamp >= start_time
            ).count()
            
            # Unique users
            unique_users = db.session.query(
                UserActivity.username
            ).filter(
                UserActivity.timestamp >= start_time,
                UserActivity.username.isnot(None)
            ).distinct().count()
            
            # Most common activity types
            activity_types = db.session.query(
                UserActivity.activity_type,
                db.func.count(UserActivity.id).label('count')
            ).filter(
                UserActivity.timestamp >= start_time
            ).group_by(UserActivity.activity_type).all()
            
            summary[period_name] = {
                'activity_count': activity_count,
                'unique_users': unique_users,
                'activity_types': {activity_type: count for activity_type, count in activity_types}
            }
        
        return jsonify({
            'summary': summary,
            'generated_at': now.isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/user-activity/<username>', methods=['GET'])
@login_required
def get_user_activity(username):
    """Get activity for a specific user"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        
        activities = UserActivity.query.filter_by(
            username=username
        ).order_by(
            UserActivity.timestamp.desc()
        ).limit(limit).all()
        
        # Get user's sessions
        sessions = ActiveSession.query.filter_by(
            username=username
        ).order_by(
            ActiveSession.last_seen.desc()
        ).limit(10).all()
        
        return jsonify({
            'username': username,
            'recent_activities': [activity.to_dict() for activity in activities],
            'sessions': [session.to_dict() for session in sessions],
            'total_activities': UserActivity.query.filter_by(username=username).count()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/logs', methods=['GET'])
@login_required
def view_logs():
    """View application logs with optional filtering"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get query parameters
        lines = min(int(request.args.get('lines', 100)), 1000)  # Max 1000 lines
        level = request.args.get('level', '').upper()  # Filter by log level
        search = request.args.get('search', '')  # Search term
        
        # Get log file path
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        log_file = os.path.join(log_dir, 'app.log')
        
        if not os.path.exists(log_file):
            return jsonify({
                'logs': [],
                'message': 'Log file does not exist yet',
                'log_file': log_file
            })
        
        # Read log file (last N lines)
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Get last N lines
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Filter by log level if specified
        if level and level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            recent_lines = [line for line in recent_lines if level in line]
        
        # Filter by search term if specified
        if search:
            recent_lines = [line for line in recent_lines if search.lower() in line.lower()]
        
        # Reverse to show most recent first
        recent_lines.reverse()
        
        return jsonify({
            'logs': recent_lines,
            'total_lines': len(all_lines),
            'returned_lines': len(recent_lines),
            'log_file': log_file,
            'filters': {
                'level': level if level else 'all',
                'search': search,
                'lines_requested': lines
            }
        })
        
    except Exception as e:
        app.logger.error(f"Error reading logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/logs/download', methods=['GET'])
@login_required
def download_logs():
    """Download the full log file"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        log_file = os.path.join(log_dir, 'app.log')
        
        if not os.path.exists(log_file):
            return jsonify({'error': 'Log file does not exist'}), 404
        
        return send_file(
            log_file,
            mimetype='text/plain',
            as_attachment=True,
            download_name=f'app_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
        
    except Exception as e:
        app.logger.error(f"Error downloading logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/monitoring/logs/files', methods=['GET'])
@login_required
def list_log_files():
    """List all available log files (including rotated backups)"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        
        if not os.path.exists(log_dir):
            return jsonify({'files': [], 'message': 'Logs directory does not exist yet'})
        
        # Get all log files
        log_files = []
        for filename in os.listdir(log_dir):
            if filename.startswith('app.log'):
                filepath = os.path.join(log_dir, filename)
                file_stat = os.stat(filepath)
                log_files.append({
                    'filename': filename,
                    'size': file_stat.st_size,
                    'size_mb': round(file_stat.st_size / (1024 * 1024), 2),
                    'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    'is_current': filename == 'app.log'
                })
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({
            'files': log_files,
            'log_dir': log_dir
        })
        
    except Exception as e:
        app.logger.error(f"Error listing log files: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/logs', methods=['GET'])
@login_required
def logs_dashboard():
    """Logs viewing dashboard page"""
    if current_user.userRole != 'Admin':
        return "Unauthorized", 403
    
    return render_template('logs_dashboard.html', title='Application Logs')