"""
Activity Tracker Module
Handles logging of user activities, session management, and real-time notifications
"""
import time
from datetime import datetime, timedelta
from flask import request, session, g, current_app
from flask_login import current_user
from sqlalchemy import and_
from app import db
from app.models import UserActivity, ActiveSession, PageAnalytics
import json


class ActivityTracker:
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the activity tracker with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        
        # Set up periodic cleanup
        with app.app_context():
            self._schedule_cleanup()
    
    def before_request(self):
        """Log activity before each request"""
        g.start_time = time.time()
        
        # Skip static files and some internal routes
        if self._should_skip_logging():
            return
        
        try:
            self._log_activity()
            self._update_session()
        except Exception as e:
            current_app.logger.error(f"Error logging activity: {e}")
    
    def after_request(self, response):
        """Update activity with response details after request"""
        if hasattr(g, 'start_time') and hasattr(g, 'activity_id'):
            try:
                response_time = int((time.time() - g.start_time) * 1000)  # Convert to ms
                activity = UserActivity.query.get(g.activity_id)
                if activity:
                    activity.response_time_ms = response_time
                    db.session.commit()
                    
                    # Emit real-time update if SocketIO is available
                    self._emit_activity_update(activity)
                    
            except Exception as e:
                current_app.logger.error(f"Error updating activity response time: {e}")
        
        return response
    
    def _should_skip_logging(self):
        """Determine if we should skip logging this request"""
        skip_paths = [
            '/static/',
            '/favicon.ico',
            '/_monitoring/heartbeat',
            '/api/monitoring/activities'  # Avoid recursive logging
        ]
        
        # Skip if path matches any skip pattern
        for skip_path in skip_paths:
            if request.path.startswith(skip_path):
                return True
        
        # Skip if it's an AJAX heartbeat or monitoring request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and \
           request.endpoint and 'monitoring' in request.endpoint:
            return True
            
        return False
    
    def _log_activity(self):
        """Log the current request as a user activity"""
        # Determine activity type
        activity_type = self._get_activity_type()
        
        # Get session ID (create one if it doesn't exist)
        session_id = session.get('session_id')
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            session['session_id'] = session_id
        
        # Prepare metadata
        metadata = self._prepare_metadata()
        
        # Create activity record
        activity = UserActivity(
            user_id=current_user.id if current_user.is_authenticated else None,
            username=current_user.username if current_user.is_authenticated else None,
            session_id=session_id,
            activity_type=activity_type,
            endpoint=request.endpoint or 'unknown',
            url_path=request.path,
            http_method=request.method,
            ip_address=self._get_client_ip(),
            user_agent=request.headers.get('User-Agent'),
            referrer=request.headers.get('Referer'),
                meta_data=metadata
        )
        
        db.session.add(activity)
        db.session.commit()
        
        # Store activity ID for response time update
        g.activity_id = activity.id
        
        # Update page analytics
        self._update_page_analytics(activity)
    
    def _get_activity_type(self):
        """Determine the type of activity based on request details"""
        if request.endpoint:
            if 'login' in request.endpoint:
                return 'login'
            elif 'logout' in request.endpoint:
                return 'logout'
            elif request.endpoint.startswith('api/'):
                return 'api_call'
            elif request.method == 'POST':
                return 'form_submit'
        
        return 'page_visit'
    
    def _get_client_ip(self):
        """Get the real client IP address"""
        # Check for forwarded headers first (if behind proxy)
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr
    
    def _prepare_metadata(self):
        """Prepare metadata for the activity log"""
        metadata = {}
        
        # Add query parameters
        if request.args:
            metadata['query_params'] = dict(request.args)
        
        # Add form data for POST requests (be careful with sensitive data)
        if request.method == 'POST' and request.form:
            # Filter out sensitive fields
            sensitive_fields = ['password', 'password_confirm', 'csrf_token']
            form_data = {}
            for key, value in request.form.items():
                if key.lower() not in sensitive_fields:
                    form_data[key] = value
                else:
                    form_data[key] = '[REDACTED]'
            metadata['form_data'] = form_data
        
        # Add browser/device info
        user_agent = request.headers.get('User-Agent', '')
        if user_agent:
            metadata['browser_info'] = self._parse_user_agent(user_agent)
        
        return metadata
    
    def _parse_user_agent(self, user_agent):
        """Extract basic browser info from user agent string"""
        ua_lower = user_agent.lower()
        
        # Detect browser
        if 'chrome' in ua_lower:
            browser = 'Chrome'
        elif 'firefox' in ua_lower:
            browser = 'Firefox'
        elif 'safari' in ua_lower and 'chrome' not in ua_lower:
            browser = 'Safari'
        elif 'edge' in ua_lower:
            browser = 'Edge'
        else:
            browser = 'Other'
        
        # Detect OS
        if 'windows' in ua_lower:
            os = 'Windows'
        elif 'mac' in ua_lower:
            os = 'macOS'
        elif 'linux' in ua_lower:
            os = 'Linux'
        elif 'android' in ua_lower:
            os = 'Android'
        elif 'iphone' in ua_lower or 'ipad' in ua_lower:
            os = 'iOS'
        else:
            os = 'Other'
        
        # Detect device type
        if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
            device = 'Mobile'
        elif 'tablet' in ua_lower or 'ipad' in ua_lower:
            device = 'Tablet'
        else:
            device = 'Desktop'
        
        return {
            'browser': browser,
            'os': os,
            'device': device
        }
    
    def _update_session(self):
        """Update or create active session record"""
        session_id = session.get('session_id')
        if not session_id:
            return
        
        active_session = ActiveSession.query.filter_by(session_id=session_id).first()
        
        if active_session:
            # Update existing session
            active_session.update_activity(request.path)
            if current_user.is_authenticated:
                active_session.user_id = current_user.id
                active_session.username = current_user.username
        else:
            # Create new session
            active_session = ActiveSession(
                session_id=session_id,
                user_id=current_user.id if current_user.is_authenticated else None,
                username=current_user.username if current_user.is_authenticated else None,
                ip_address=self._get_client_ip(),
                user_agent=request.headers.get('User-Agent'),
                last_activity_url=request.path
            )
            db.session.add(active_session)
            db.session.commit()
    
    def _update_page_analytics(self, activity):
        """Update page analytics for the visited page"""
        page_analytics = PageAnalytics.query.filter_by(url_path=activity.url_path).first()
        
        if page_analytics:
            page_analytics.total_visits += 1
            page_analytics.last_visited = datetime.utcnow()
        else:
            page_analytics = PageAnalytics(
                url_path=activity.url_path,
                endpoint=activity.endpoint,
                total_visits=1,
                unique_visitors=1,
                last_visited=datetime.utcnow()
            )
            db.session.add(page_analytics)
        
        db.session.commit()
    
    def _emit_activity_update(self, activity):
        """Emit real-time activity update via SocketIO"""
        try:
            from flask_socketio import emit
            
            # Prepare activity data for real-time updates
            activity_data = {
                'id': activity.id,
                'username': activity.username or 'Anonymous',
                'activity_type': activity.activity_type,
                'url_path': activity.url_path,
                'timestamp': activity.timestamp.strftime('%H:%M:%S'),
                'ip_address': activity.ip_address,
                'response_time_ms': activity.response_time_ms
            }
            
            # Emit to monitoring room (admin users)
            emit('new_activity', activity_data, room='monitoring', namespace='/monitoring')
            
        except ImportError:
            # SocketIO not available, skip real-time updates
            pass
        except Exception as e:
            current_app.logger.error(f"Error emitting activity update: {e}")
    
    def _schedule_cleanup(self):
        """Schedule cleanup of old activity logs"""
        # This would typically be done with a background task
        # For now, we'll just clean up very old records
        cutoff_date = datetime.utcnow() - timedelta(days=90)  # Keep 90 days of data
        
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            
            # Check if tables exist before trying to clean them
            if 'user_activities' not in inspector.get_table_names():
                return  # Skip cleanup if tables don't exist yet
            
            # Clean old activities
            old_activities = UserActivity.query.filter(
                UserActivity.timestamp < cutoff_date
            ).limit(1000)  # Delete in batches
            
            for activity in old_activities:
                db.session.delete(activity)
            
            # Clean inactive sessions (older than 24 hours) if table exists
            if 'active_sessions' in inspector.get_table_names():
                inactive_cutoff = datetime.utcnow() - timedelta(hours=24)
                inactive_sessions = ActiveSession.query.filter(
                    ActiveSession.last_seen < inactive_cutoff
                ).all()
                
                for session_record in inactive_sessions:
                    session_record.is_active = False
            
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Error during cleanup: {e}")
            db.session.rollback()


def get_active_users_count():
    """Get count of currently active users (last 15 minutes)"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        if 'active_sessions' not in inspector.get_table_names():
            return 0
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=15)
        return ActiveSession.query.filter(
            and_(ActiveSession.is_active == True, ActiveSession.last_seen >= cutoff_time)
        ).count()
    except Exception:
        return 0


def get_recent_activities(limit=50):
    """Get recent user activities"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        if 'user_activities' not in inspector.get_table_names():
            return []
        
        return UserActivity.query.order_by(
            UserActivity.timestamp.desc()
        ).limit(limit).all()
    except Exception:
        return []


def get_popular_pages(limit=10):
    """Get most popular pages based on visit count"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        if 'page_analytics' not in inspector.get_table_names():
            return []
        
        return PageAnalytics.query.order_by(
            PageAnalytics.total_visits.desc()
        ).limit(limit).all()
    except Exception:
        return []


def get_user_journey(session_id, limit=20):
    """Get user journey for a specific session"""
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        if 'user_activities' not in inspector.get_table_names():
            return []
        
        return UserActivity.query.filter_by(
            session_id=session_id
        ).order_by(
            UserActivity.timestamp.asc()
        ).limit(limit).all()
    except Exception:
        return []
