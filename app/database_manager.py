"""
Database Manager for External Database Connections
Handles connections to Ruzivo and Library databases
"""

import os
import logging
import sqlalchemy as sa
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class DatabaseManager:
    """Manages multiple database connections for query interface"""
    
    def __init__(self):
        self.connections = {}
        self.engines = {}
        self.logger = logging.getLogger(__name__)
        self._setup_databases()
    
    def _setup_databases(self):
        """Initialize database connections"""
        # Database configurations with better fallbacks
        self.database_configs = {
            'ruzivo': {
                'name': 'Ruzivo Database',
                'type': 'mysql',
                'host': os.getenv('ASL_DB_HOST', 'localhost'),
                'port': int(os.getenv('ASL_DB_PORT', 3306)),
                'database': os.getenv('ASL_DB_NAME', 'ruzivo_2017'),
                'username': os.getenv('ASL_DB_USER', 'root'),
                'password': os.getenv('ASL_DB_PASS', ''),
                'description': 'Ruzivo production database for content and user management'
            },
            'library': {
                'name': 'Library Database', 
                'type': 'mysql',
                'host': os.getenv('AL_DB_HOST', 'localhost'),
                'port': int(os.getenv('AL_DB_PORT', 3306)),
                'database': os.getenv('AL_DB_NAME', 'akello_library'),
                'username': os.getenv('AL_DB_USER', 'root'),
                'password': os.getenv('AL_DB_PASS', ''),
                'description': 'Library management system database for resources and analytics'
            }
        }
        
        self.logger.info("Initializing database connections...")
        
        # Initialize connections
        connected_count = 0
        for db_key, config in self.database_configs.items():
            try:
                self._create_connection(db_key, config)
                self.logger.info(f"Successfully connected to {config['name']} at {config['host']}:{config['port']}/{config['database']}")
                connected_count += 1
            except Exception as e:
                self.logger.error(f"Failed to connect to {config['name']}: {e}")
                # Don't fail completely - just mark as unavailable
                self.logger.warning(f"Database {db_key} will be unavailable in the interface")
        
        if connected_count == 0:
            self.logger.warning("No databases connected successfully. Database interface may not work properly.")
        else:
            self.logger.info(f"Connected to {connected_count} out of {len(self.database_configs)} databases")
    
    def _create_connection(self, db_key: str, config: Dict[str, Any]):
        """Create database connection and engine"""
        try:
            # Build connection string
            if config['type'] == 'mysql':
                # URL encode the username and password to handle special characters
                encoded_username = quote_plus(str(config['username']))
                encoded_password = quote_plus(str(config['password']))
                connection_string = (
                    f"mysql+pymysql://{encoded_username}:{encoded_password}"
                    f"@{config['host']}:{config['port']}/{config['database']}"
                    f"?charset=utf8mb4"
                )
            else:
                raise ValueError(f"Unsupported database type: {config['type']}")
            
            # Create engine with better connection settings for remote databases
            engine = create_engine(
                connection_string,
                pool_size=3,
                max_overflow=0,
                pool_recycle=1800,  # 30 minutes
                pool_pre_ping=True,
                pool_timeout=30,
                echo=False,
                connect_args={
                    'connect_timeout': 60,
                    'read_timeout': 60,
                    'write_timeout': 60,
                    'autocommit': True,
                    'charset': 'utf8mb4'
                }
            )
            
            # Test connection with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text("SELECT 1"))
                        result.fetchone()  # Ensure we actually get data
                    break  # Connection successful
                except Exception as test_error:
                    if attempt == max_retries - 1:  # Last attempt
                        raise test_error
                    else:
                        self.logger.warning(f"Connection attempt {attempt + 1} failed for {db_key}: {test_error}. Retrying...")
                        import time
                        time.sleep(2)  # Wait before retry
            
            self.engines[db_key] = engine
            self.connections[db_key] = sessionmaker(bind=engine)
            
        except SQLAlchemyError as e:
            self.logger.error(f"Database connection error for {db_key}: {e}")
            raise
    
    def get_databases(self) -> Dict[str, Dict[str, Any]]:
        """Get list of available databases"""
        available_dbs = {}
        for db_key, config in self.database_configs.items():
            if db_key in self.engines:
                # Test connection to ensure it's still active with timeout
                try:
                    engine = self.engines[db_key]
                    # Use a shorter timeout for the test
                    with engine.connect() as conn:
                        # Set a statement timeout
                        conn.execute(text("SELECT 1 as test_connection"))
                    status = 'connected'
                except Exception as e:
                    self.logger.error(f"Database {db_key} connection test failed: {e}")
                    status = 'connection_error'
                    # Try to recreate the connection
                    try:
                        self._create_connection(db_key, config)
                        status = 'connected'
                        self.logger.info(f"Reconnected to {db_key} successfully")
                    except Exception as reconnect_error:
                        self.logger.error(f"Failed to reconnect to {db_key}: {reconnect_error}")
                        status = 'disconnected'
                
                available_dbs[db_key] = {
                    'key': db_key,
                    'name': config['name'],
                    'type': config['type'],
                    'description': config['description'],
                    'status': status,
                    'host': config['host'],
                    'database': config['database']
                }
            else:
                # Try to create connection on-demand
                try:
                    self._create_connection(db_key, config)
                    status = 'connected'
                except Exception as e:
                    self.logger.error(f"Failed to create connection for {db_key}: {e}")
                    status = 'disconnected'
                
                available_dbs[db_key] = {
                    'key': db_key,
                    'name': config['name'],
                    'type': config['type'],
                    'description': config['description'],
                    'status': status,
                    'host': config['host'],
                    'database': config['database'],
                    'error': 'Connection failed during initialization' if status == 'disconnected' else None
                }
        
        # If no databases are available, add a demo entry
        if not available_dbs or all(db['status'] != 'connected' for db in available_dbs.values()):
            available_dbs['demo'] = {
                'key': 'demo',
                'name': 'Demo Database (No Connection)',
                'type': 'demo',
                'description': 'Demo entry - configure database connections in environment variables',
                'status': 'demo',
                'host': 'localhost',
                'database': 'N/A'
            }
        
        return available_dbs
    
    def get_tables(self, db_key: str) -> List[Dict[str, Any]]:
        """Get list of tables in database with fast method to avoid timeouts"""
        if db_key not in self.engines:
            raise ValueError(f"Database {db_key} not connected")
        
        try:
            engine = self.engines[db_key]
            tables = []
            
            # Use direct SQL query instead of SQLAlchemy inspector to avoid timeouts
            with engine.connect() as conn:
                # Get table names quickly
                if engine.dialect.name == 'mysql':
                    table_result = conn.execute(text("SHOW TABLES"))
                    table_names = [row[0] for row in table_result.fetchall()]
                else:
                    # Fallback for other databases
                    table_result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()"))
                    table_names = [row[0] for row in table_result.fetchall()]
                
                self.logger.info(f"Found {len(table_names)} tables in {db_key}")
                
                # For each table, get basic column info using direct SQL
                for table_name in table_names[:50]:  # Limit to first 50 tables to avoid timeout
                    try:
                        # Get column information with timeout protection
                        if engine.dialect.name == 'mysql':
                            col_result = conn.execute(text(f"DESCRIBE `{table_name}`"))
                            columns = []
                            primary_keys = []
                            
                            for row in col_result.fetchall():
                                col_name = row[0]
                                col_type = row[1]
                                is_nullable = row[2] == 'YES'
                                col_key = row[3]
                                col_default = row[4]
                                
                                is_primary = col_key == 'PRI'
                                if is_primary:
                                    primary_keys.append(col_name)
                                
                                columns.append({
                                    'name': col_name,
                                    'type': col_type,
                                    'nullable': is_nullable,
                                    'default': col_default,
                                    'primary_key': is_primary
                                })
                        else:
                            # Basic fallback for non-MySQL databases
                            columns = [{'name': 'id', 'type': 'unknown', 'nullable': True, 'default': None, 'primary_key': False}]
                            primary_keys = []
                        
                        # Get row count with timeout protection
                        try:
                            count_result = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}` LIMIT 1"))
                            row_count = count_result.scalar() or 0
                        except:
                            row_count = 0
                        
                        tables.append({
                            'name': table_name,
                            'columns': columns,
                            'primary_keys': primary_keys,
                            'foreign_keys': [],  # Skip foreign keys for speed
                            'row_count': row_count
                        })
                        
                    except Exception as table_error:
                        self.logger.warning(f"Error processing table {table_name}: {table_error}")
                        # Add basic table info even if we can't get details
                        tables.append({
                            'name': table_name,
                            'columns': [{'name': 'unknown', 'type': 'unknown', 'nullable': True, 'default': None, 'primary_key': False}],
                            'primary_keys': [],
                            'foreign_keys': [],
                            'row_count': 0
                        })
            
            return tables
            
        except SQLAlchemyError as e:
            self.logger.error(f"Error getting tables for {db_key}: {e}")
            raise
    
    def _get_table_row_count(self, db_key: str, table_name: str) -> int:
        """Get approximate row count for table"""
        try:
            engine = self.engines[db_key]
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
                return result.scalar()
        except:
            return 0
    
    def execute_query(self, db_key: str, query: str, limit: int = 1000) -> Dict[str, Any]:
        """Execute SQL query and return results"""
        if db_key not in self.engines:
            raise ValueError(f"Database {db_key} not connected")
        
        try:
            engine = self.engines[db_key]
            start_time = datetime.now()
            
            # Add limit if not present and it's a SELECT query
            query_upper = query.strip().upper()
            if query_upper.startswith('SELECT') and 'LIMIT' not in query_upper:
                query = f"{query.rstrip(';')} LIMIT {limit}"
            
            # Execute query
            with engine.connect() as conn:
                result = conn.execute(text(query))
                
                # Handle different query types
                if query_upper.startswith('SELECT'):
                    # Fetch results for SELECT queries
                    columns = list(result.keys())
                    rows = result.fetchall()
                    
                    # Convert to list of dictionaries
                    data = []
                    for row in rows:
                        row_dict = {}
                        for i, col in enumerate(columns):
                            value = row[i]
                            # Convert datetime objects to strings
                            if isinstance(value, datetime):
                                value = value.isoformat()
                            row_dict[col] = value
                        data.append(row_dict)
                    
                    execution_time = (datetime.now() - start_time).total_seconds()
                    
                    return {
                        'success': True,
                        'type': 'select',
                        'columns': columns,
                        'data': data,
                        'row_count': len(data),
                        'execution_time': execution_time,
                        'message': f"Query returned {len(data)} rows in {execution_time:.3f} seconds"
                    }
                else:
                    # Handle INSERT, UPDATE, DELETE, etc.
                    affected_rows = result.rowcount
                    execution_time = (datetime.now() - start_time).total_seconds()
                    
                    return {
                        'success': True,
                        'type': 'modification',
                        'affected_rows': affected_rows,
                        'execution_time': execution_time,
                        'message': f"Query affected {affected_rows} rows in {execution_time:.3f} seconds"
                    }
                    
        except SQLAlchemyError as e:
            self.logger.error(f"Query execution error: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f"Query failed: {str(e)}"
            }
    
    def build_query(self, db_key: str, query_config: Dict[str, Any]) -> str:
        """Build SQL query from visual query builder configuration"""
        try:
            query_type = query_config.get('type', 'select').upper()
            
            if query_type == 'SELECT':
                return self._build_select_query(query_config)
            else:
                raise ValueError(f"Query type {query_type} not supported in visual builder")
                
        except Exception as e:
            self.logger.error(f"Query building error: {e}")
            raise
    
    def _build_select_query(self, config: Dict[str, Any]) -> str:
        """Build SELECT query from configuration"""
        # Extract configuration
        tables = config.get('tables', [])
        columns = config.get('columns', ['*'])
        joins = config.get('joins', [])
        conditions = config.get('conditions', [])
        group_by = config.get('group_by', [])
        having = config.get('having', [])
        order_by = config.get('order_by', [])
        limit = config.get('limit')
        
        if not tables:
            raise ValueError("At least one table must be selected")
        
        # Build SELECT clause
        if columns == ['*'] or not columns:
            select_clause = "SELECT *"
        else:
            formatted_columns = []
            for col in columns:
                if isinstance(col, dict):
                    table = col.get('table', '')
                    column = col.get('column', '')
                    alias = col.get('alias', '')
                    
                    if table and column:
                        col_str = f"`{table}`.`{column}`"
                    else:
                        col_str = f"`{column}`"
                    
                    if alias:
                        col_str += f" AS `{alias}`"
                    
                    formatted_columns.append(col_str)
                else:
                    formatted_columns.append(f"`{col}`")
            
            select_clause = f"SELECT {', '.join(formatted_columns)}"
        
        # Build FROM clause
        main_table = tables[0]
        from_clause = f"FROM `{main_table}`"
        
        # Build JOIN clauses
        join_clauses = []
        for join in joins:
            join_type = join.get('type', 'INNER').upper()
            table = join.get('table', '')
            condition = join.get('condition', '')
            
            if table and condition:
                join_clauses.append(f"{join_type} JOIN `{table}` ON {condition}")
        
        # Build WHERE clause
        where_clause = ""
        if conditions:
            formatted_conditions = []
            for condition in conditions:
                if isinstance(condition, dict):
                    column = condition.get('column', '')
                    operator = condition.get('operator', '=')
                    value = condition.get('value', '')
                    
                    if column and value is not None:
                        if isinstance(value, str) and not value.isdigit():
                            formatted_conditions.append(f"`{column}` {operator} '{value}'")
                        else:
                            formatted_conditions.append(f"`{column}` {operator} {value}")
                else:
                    formatted_conditions.append(str(condition))
            
            if formatted_conditions:
                where_clause = f"WHERE {' AND '.join(formatted_conditions)}"
        
        # Build GROUP BY clause
        group_clause = ""
        if group_by:
            group_clause = f"GROUP BY {', '.join([f'`{col}`' for col in group_by])}"
        
        # Build HAVING clause
        having_clause = ""
        if having:
            having_clause = f"HAVING {' AND '.join(having)}"
        
        # Build ORDER BY clause
        order_clause = ""
        if order_by:
            formatted_order = []
            for order in order_by:
                if isinstance(order, dict):
                    column = order.get('column', '')
                    direction = order.get('direction', 'ASC').upper()
                    formatted_order.append(f"`{column}` {direction}")
                else:
                    formatted_order.append(f"`{order}` ASC")
            
            if formatted_order:
                order_clause = f"ORDER BY {', '.join(formatted_order)}"
        
        # Build LIMIT clause
        limit_clause = ""
        if limit:
            limit_clause = f"LIMIT {limit}"
        
        # Combine all clauses
        query_parts = [select_clause, from_clause]
        query_parts.extend(join_clauses)
        if where_clause: query_parts.append(where_clause)
        if group_clause: query_parts.append(group_clause)
        if having_clause: query_parts.append(having_clause)
        if order_clause: query_parts.append(order_clause)
        if limit_clause: query_parts.append(limit_clause)
        
        return '\n'.join(query_parts)
    
    def test_connection(self, db_key: str) -> Dict[str, Any]:
        """Test database connection with retry logic"""
        config = self.database_configs.get(db_key)
        if not config:
            return {'success': False, 'message': 'Database configuration not found'}
        
        # If engine doesn't exist, try to create it
        if db_key not in self.engines:
            try:
                self._create_connection(db_key, config)
            except Exception as e:
                return {'success': False, 'message': f'Failed to create connection: {str(e)}'}
        
        # Test with retry logic
        max_retries = 2
        for attempt in range(max_retries):
            try:
                engine = self.engines[db_key]
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1 as connection_test"))
                    test_result = result.fetchone()
                    if test_result:
                        return {'success': True, 'message': 'Connection successful'}
                
            except Exception as e:
                self.logger.error(f"Connection test attempt {attempt + 1} failed for {db_key}: {e}")
                
                if attempt == max_retries - 1:  # Last attempt
                    # Try to recreate the connection
                    try:
                        self.logger.info(f"Attempting to recreate connection for {db_key}")
                        self._create_connection(db_key, config)
                        # Test once more
                        with self.engines[db_key].connect() as conn:
                            result = conn.execute(text("SELECT 1 as connection_test"))
                            result.fetchone()
                        return {'success': True, 'message': 'Connection restored'}
                    except Exception as final_error:
                        return {'success': False, 'message': f'Connection failed: {str(final_error)}'}
                else:
                    import time
                    time.sleep(1)  # Brief pause before retry
        
        return {'success': False, 'message': 'Connection test failed after retries'}
    
    def get_sample_data(self, db_key: str, table_name: str, limit: int = 10) -> Dict[str, Any]:
        """Get sample data from table"""
        query = f"SELECT * FROM `{table_name}` LIMIT {limit}"
        return self.execute_query(db_key, query, limit)
    
    def export_results_to_csv(self, results: Dict[str, Any], filename: str) -> str:
        """Export query results to CSV file"""
        try:
            if not results.get('success') or results.get('type') != 'select':
                raise ValueError("No data to export")
            
            df = pd.DataFrame(results['data'])
            filepath = f"exports/{filename}"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            df.to_csv(filepath, index=False)
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Export error: {e}")
            raise

# Global database manager instance - lazy initialization
_db_manager = None

def get_db_manager():
    """Get or create database manager instance (lazy initialization)"""
    global _db_manager
    if _db_manager is None:
        # Check if we're running a migration command
        import sys
        is_migration = any('db' in arg or 'migrate' in arg for arg in sys.argv)
        if is_migration:
            # During migrations, return a dummy manager that doesn't connect
            class DummyManager:
                def get_databases(self):
                    return []
                def test_connection(self, db_key):
                    return {'success': False, 'error': 'Not available during migrations'}
                def get_tables(self, db_key):
                    return []
                def get_sample_data(self, db_key, table_name, limit=10):
                    return {'success': False, 'error': 'Not available during migrations'}
                def execute_query(self, db_key, query, limit=1000):
                    return {'success': False, 'error': 'Not available during migrations'}
                def build_query(self, db_key, data):
                    return ""
            _db_manager = DummyManager()
        else:
            _db_manager = DatabaseManager()
    return _db_manager

# For backward compatibility - will be initialized lazily when first accessed
# This allows existing code that imports db_manager directly to still work
db_manager = None