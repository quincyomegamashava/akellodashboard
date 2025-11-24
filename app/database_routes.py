"""
Database Routes for SQL Query Interface
Handles all database-related endpoints for the admin query tool
"""

from flask import Blueprint, render_template, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from functools import wraps
from app.database_manager import db_manager
import json
import os
from datetime import datetime
import tempfile

# Create blueprint
database_bp = Blueprint('database', __name__)

def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        if current_user.userRole != 'Admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

@database_bp.route('/databases')
@login_required
@admin_required
def databases_interface():
    """Main database query interface page"""
    return render_template('database_interface.html', title='Database Query Tool')

@database_bp.route('/api/databases/list')
@login_required
@admin_required
def list_databases():
    """Get list of available databases"""
    try:
        databases = db_manager.get_databases()
        return jsonify({
            'success': True,
            'databases': databases
        })
    except Exception as e:
        current_app.logger.error(f"Error listing databases: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/<db_key>/test')
@login_required
@admin_required
def test_database_connection(db_key):
    """Test database connection"""
    try:
        result = db_manager.test_connection(db_key)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error testing connection for {db_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/<db_key>/tables')
@login_required
@admin_required
def get_database_tables(db_key):
    """Get list of tables in database with schema information"""
    try:
        tables = db_manager.get_tables(db_key)
        return jsonify({
            'success': True,
            'database': db_key,
            'tables': tables
        })
    except Exception as e:
        current_app.logger.error(f"Error getting tables for {db_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/<db_key>/tables/<table_name>/sample')
@login_required
@admin_required
def get_table_sample_data(db_key, table_name):
    """Get sample data from a table"""
    try:
        limit = request.args.get('limit', 10, type=int)
        result = db_manager.get_sample_data(db_key, table_name, limit)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error getting sample data for {db_key}.{table_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/<db_key>/query', methods=['POST'])
@login_required
@admin_required
def execute_database_query(db_key):
    """Execute SQL query on database"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Query is required'
            }), 400
        
        query = data['query'].strip()
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query cannot be empty'
            }), 400
        
        # Security check - prevent dangerous operations
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
        query_upper = query.upper()
        
        # Allow only if explicitly permitted or if it's a SELECT query
        allow_modifications = data.get('allow_modifications', False)
        if not allow_modifications:
            for keyword in dangerous_keywords:
                if keyword in query_upper:
                    return jsonify({
                        'success': False,
                        'error': f'Operation {keyword} not allowed. Use "Allow Modifications" option if needed.'
                    }), 400
        
        limit = data.get('limit', 1000)
        result = db_manager.execute_query(db_key, query, limit)
        
        # Log query execution for audit
        current_app.logger.info(f"Query executed by {current_user.username} on {db_key}: {query[:100]}...")
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error executing query on {db_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/<db_key>/build-query', methods=['POST'])
@login_required
@admin_required
def build_visual_query(db_key):
    """Build SQL query from visual query builder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Query configuration is required'
            }), 400
        
        # Build the query
        query = db_manager.build_query(db_key, data)
        
        return jsonify({
            'success': True,
            'query': query
        })
        
    except Exception as e:
        current_app.logger.error(f"Error building query for {db_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/<db_key>/execute-built-query', methods=['POST'])
@login_required
@admin_required
def execute_built_query(db_key):
    """Build and execute query from visual query builder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Query configuration is required'
            }), 400
        
        # Build the query
        query = db_manager.build_query(db_key, data)
        
        # Execute the query
        limit = data.get('limit', 1000)
        result = db_manager.execute_query(db_key, query, limit)
        
        # Add the generated query to the result
        if result.get('success'):
            result['generated_query'] = query
        
        # Log query execution
        current_app.logger.info(f"Visual query executed by {current_user.username} on {db_key}")
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Error executing built query on {db_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/<db_key>/export', methods=['POST'])
@login_required
@admin_required
def export_query_results(db_key):
    """Export query results to CSV"""
    try:
        data = request.get_json()
        if not data or 'results' not in data:
            return jsonify({
                'success': False,
                'error': 'Results data is required'
            }), 400
        
        results = data['results']
        if not results.get('success') or results.get('type') != 'select':
            return jsonify({
                'success': False,
                'error': 'No data to export'
            }), 400
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"query_results_{db_key}_{timestamp}.csv"
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        
        # Export to CSV
        import pandas as pd
        df = pd.DataFrame(results['data'])
        df.to_csv(filepath, index=False)
        
        # Log export
        current_app.logger.info(f"Data exported by {current_user.username} from {db_key}: {filename}")
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error exporting results from {db_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/<db_key>/schema')
@login_required
@admin_required
def get_database_schema(db_key):
    """Get complete database schema information"""
    try:
        tables = db_manager.get_tables(db_key)
        
        # Organize schema information
        schema = {
            'database': db_key,
            'tables': {}
        }
        
        for table in tables:
            schema['tables'][table['name']] = {
                'columns': table['columns'],
                'primary_keys': table['primary_keys'],
                'foreign_keys': table['foreign_keys'],
                'row_count': table['row_count']
            }
        
        return jsonify({
            'success': True,
            'schema': schema
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting schema for {db_key}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/query-history')
@login_required
@admin_required
def get_query_history():
    """Get query history for current user"""
    try:
        # This would typically come from a database table storing query history
        # For now, return empty history
        return jsonify({
            'success': True,
            'history': []
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting query history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/save-query', methods=['POST'])
@login_required
@admin_required
def save_query():
    """Save a query for later use"""
    try:
        data = request.get_json()
        if not data or 'name' not in data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Query name and content are required'
            }), 400
        
        # This would typically save to a database table
        # For now, just return success
        return jsonify({
            'success': True,
            'message': 'Query saved successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error saving query: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@database_bp.route('/api/databases/saved-queries')
@login_required
@admin_required
def get_saved_queries():
    """Get saved queries for current user"""
    try:
        # This would typically come from a database table
        # For now, return empty list
        return jsonify({
            'success': True,
            'queries': []
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting saved queries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers for the blueprint
@database_bp.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@database_bp.errorhandler(500)
def internal_error(error):
    current_app.logger.error(f"Database blueprint internal error: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500