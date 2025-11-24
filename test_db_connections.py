#!/usr/bin/env python3
"""
Test script to verify database connections
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_manager import DatabaseManager

def test_database_connections():
    print("Testing Database Connections...")
    print("=" * 50)
    
    # Create database manager
    db_manager = DatabaseManager()
    
    # Test each database
    databases = db_manager.get_databases()
    
    for db_key, db_info in databases.items():
        print(f"\nTesting {db_key} ({db_info['name']}):")
        print(f"  Status: {db_info['status']}")
        print(f"  Host: {db_info.get('host', 'N/A')}")
        print(f"  Database: {db_info.get('database', 'N/A')}")
        
        if db_info['status'] in ['connected', 'connection_error', 'disconnected']:
            print("  Testing connection...")
            
            # Test connection
            test_result = db_manager.test_connection(db_key)
            
            if test_result['success']:
                print(f"  ✅ Connection successful: {test_result['message']}")
                
                # Try a simple query
                try:
                    query_result = db_manager.execute_query(db_key, "SELECT 1 as test_query", limit=1)
                    if query_result['success']:
                        print("  ✅ Query test successful")
                        
                        # Try to get tables
                        try:
                            tables = db_manager.get_tables(db_key)
                            print(f"  ✅ Schema loaded: {len(tables)} tables found")
                            
                            # Show first few tables
                            if tables:
                                print("    Sample tables:")
                                for table in tables[:3]:
                                    print(f"      - {table['name']} ({len(table['columns'])} columns)")
                            
                        except Exception as e:
                            print(f"  ⚠️  Schema loading failed: {e}")
                            
                    else:
                        print(f"  ❌ Query test failed: {query_result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"  ❌ Query test error: {e}")
                    
            else:
                print(f"  ❌ Connection failed: {test_result['message']}")
        else:
            print(f"  ⏭️  Skipping {db_info['status']} database")
    
    print("\n" + "=" * 50)
    print("Database connection test completed!")

if __name__ == "__main__":
    test_database_connections()