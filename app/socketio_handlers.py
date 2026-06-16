"""
SocketIO Event Handlers for Real-time User Activity Monitoring
"""
from flask import session
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room, disconnect
from datetime import datetime, timedelta
from app import db
from app.models import UserActivity, ActiveSession
from app.activity_tracker import get_active_users_count, get_recent_activities
import json


def init_socketio_handlers(socketio):
    """Initialize SocketIO event handlers"""
    
    @socketio.on('connect', namespace='/monitoring')
    def on_connect():
        """Handle client connection to monitoring namespace"""
        # Only allow admin users to connect to monitoring
        if not current_user.is_authenticated or current_user.userRole != 'Admin':
            disconnect()
            return False
        
        # Join the monitoring room
        join_room('monitoring')
        
        # Send initial data
        emit('connected', {
            'message': 'Connected to monitoring dashboard',
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Send current stats
        emit('initial_stats', {
            'active_users': get_active_users_count(),
            'recent_activities': [activity.to_dict() for activity in get_recent_activities(10)],
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @socketio.on('disconnect', namespace='/monitoring')
    def on_disconnect():
        """Handle client disconnection from monitoring namespace"""
        leave_room('monitoring')
        print(f'Admin user {current_user.username if current_user.is_authenticated else "Unknown"} disconnected from monitoring')
    
    @socketio.on('request_stats', namespace='/monitoring')
    def handle_stats_request():
        """Handle request for current statistics"""
        if not current_user.is_authenticated or current_user.userRole != 'Admin':
            return
        
        try:
            # Get current statistics
            active_users = get_active_users_count()
            recent_activities = get_recent_activities(20)
            
            # Get active sessions
            cutoff_time = datetime.utcnow() - timedelta(minutes=15)
            active_sessions = ActiveSession.query.filter(
                ActiveSession.is_active == True,
                ActiveSession.last_seen >= cutoff_time
            ).order_by(ActiveSession.last_seen.desc()).all()
            
            emit('stats_update', {
                'active_users': active_users,
                'recent_activities': [activity.to_dict() for activity in recent_activities],
                'active_sessions': [session.to_dict() for session in active_sessions],
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            print(f"Error handling stats request: {e}")
            emit('error', {'message': 'Failed to fetch statistics'})
    
    @socketio.on('request_user_journey', namespace='/monitoring')
    def handle_user_journey_request(data):
        """Handle request for user journey data"""
        if not current_user.is_authenticated or current_user.userRole != 'Admin':
            return
        
        try:
            session_id = data.get('session_id')
            if not session_id:
                emit('error', {'message': 'Session ID required'})
                return
            
            # Get user journey
            activities = UserActivity.query.filter_by(
                session_id=session_id
            ).order_by(
                UserActivity.timestamp.asc()
            ).limit(50).all()
            
            emit('user_journey', {
                'session_id': session_id,
                'activities': [activity.to_dict() for activity in activities],
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            print(f"Error handling user journey request: {e}")
            emit('error', {'message': 'Failed to fetch user journey'})
    
    @socketio.on('request_activity_filter', namespace='/monitoring')
    def handle_activity_filter_request(data):
        """Handle filtered activity requests"""
        if not current_user.is_authenticated or current_user.userRole != 'Admin':
            return
        
        try:
            # Parse filter parameters
            username = data.get('username')
            activity_type = data.get('activity_type')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            limit = min(data.get('limit', 50), 200)  # Max 200 records
            
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
            
            activities = query.order_by(
                UserActivity.timestamp.desc()
            ).limit(limit).all()
            
            emit('filtered_activities', {
                'activities': [activity.to_dict() for activity in activities],
                'filters': data,
                'count': len(activities),
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            print(f"Error handling activity filter request: {e}")
            emit('error', {'message': 'Failed to filter activities'})
    
    @socketio.on('heartbeat', namespace='/monitoring')
    def handle_heartbeat():
        """Handle heartbeat to keep connection alive"""
        emit('heartbeat_response', {
            'timestamp': datetime.utcnow().isoformat()
        })

    @socketio.on('join_meeting', namespace='/meeting-notes')
    def on_join_meeting(data):
        if not current_user.is_authenticated:
            disconnect()
            return False
        meeting_id = (data or {}).get('meeting_id')
        if not meeting_id:
            return False
        room = f"meeting_{meeting_id}"
        join_room(room)
        emit('joined', {'meeting_id': meeting_id, 'user': current_user.username})

    @socketio.on('leave_meeting', namespace='/meeting-notes')
    def on_leave_meeting(data):
        meeting_id = (data or {}).get('meeting_id')
        if meeting_id:
            leave_room(f"meeting_{meeting_id}")

    _meeting_presence = {}

    @socketio.on('presence_join', namespace='/meeting-notes')
    def on_presence_join(data):
        if not current_user.is_authenticated:
            return False
        meeting_id = (data or {}).get('meeting_id')
        if not meeting_id:
            return False
        room = f"meeting_{meeting_id}"
        join_room(room)
        key = f"meeting_{meeting_id}"
        users = _meeting_presence.setdefault(key, set())
        users.add(current_user.username)
        emit('presence_update', {'users': sorted(users)}, room=room)

    @socketio.on('presence_leave', namespace='/meeting-notes')
    def on_presence_leave(data):
        meeting_id = (data or {}).get('meeting_id')
        if not meeting_id:
            return
        key = f"meeting_{meeting_id}"
        users = _meeting_presence.get(key, set())
        users.discard(getattr(current_user, 'username', ''))
        room = f"meeting_{meeting_id}"
        emit('presence_update', {'users': sorted(users)}, room=room)
        leave_room(room)

    @socketio.on('field_patch', namespace='/meeting-notes')
    def on_field_patch(data):
        meeting_id = (data or {}).get('meeting_id')
        if not meeting_id or not current_user.is_authenticated:
            return
        room = f"meeting_{meeting_id}"
        emit('item_updated', {'patch': data, 'user': current_user.username}, room=room, include_self=False)


def emit_activity_to_monitoring(activity_data):
    """Emit new activity to all monitoring clients"""
    try:
        from flask_socketio import emit
        emit('new_activity', activity_data, room='monitoring', namespace='/monitoring')
    except Exception as e:
        print(f"Error emitting activity to monitoring: {e}")


def emit_session_update(session_data):
    """Emit session update to all monitoring clients"""
    try:
        from flask_socketio import emit
        emit('session_update', session_data, room='monitoring', namespace='/monitoring')
    except Exception as e:
        print(f"Error emitting session update to monitoring: {e}")


def emit_stats_update():
    """Emit updated statistics to all monitoring clients"""
    try:
        from flask_socketio import emit
        
        active_users = get_active_users_count()
        
        emit('stats_broadcast', {
            'active_users': active_users,
            'timestamp': datetime.utcnow().isoformat()
        }, room='monitoring', namespace='/monitoring')
        
    except Exception as e:
        print(f"Error emitting stats update to monitoring: {e}")


def emit_meeting_item_event(meeting_id: int, event_type: str, payload: dict):
    """Broadcast meeting action-item changes to collaborators."""
    try:
        from flask_socketio import emit

        emit(
            event_type,
            payload,
            room=f"meeting_{meeting_id}",
            namespace="/meeting-notes",
        )
    except Exception as e:
        print(f"Error emitting meeting notes event: {e}")
