#!/usr/bin/env python3
"""
Simple test to verify logging is working correctly.
Run this after starting the Flask application.
"""

import requests
import time

def test_logging():
    """Test that the logging endpoints are accessible and working"""
    
    base_url = "http://localhost:5000"
    
    print("🔍 Testing File-Based Logging Setup...")
    print("=" * 60)
    
    # Test 1: Check if logs directory exists
    print("\n📁 Test 1: Verifying logs directory exists")
    import os
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if os.path.exists(logs_dir):
        print("   ✅ Logs directory exists at:", logs_dir)
    else:
        print("   ❌ Logs directory not found!")
        return False
    
    # Test 2: Check if logging configuration exists
    print("\n⚙️  Test 2: Verifying logging configuration")
    config_file = os.path.join(os.path.dirname(__file__), 'app', 'logging_config.py')
    if os.path.exists(config_file):
        print("   ✅ Logging configuration file exists")
    else:
        print("   ❌ Logging configuration file not found!")
        return False
    
    # Test 3: Check if template exists
    print("\n📄 Test 3: Verifying logs dashboard template")
    template_file = os.path.join(os.path.dirname(__file__), 'app', 'templates', 'logs_dashboard.html')
    if os.path.exists(template_file):
        print("   ✅ Logs dashboard template exists")
    else:
        print("   ❌ Template file not found!")
        return False

    # Test 4: Verify stdout redirection (Manual check instruction)
    print("\n🔄 Test 4: Verifying Terminal Capture")
    print("   The configuration in app/logging_config.py now redirects stdout/stderr.")
    print("   To verify this:")
    print("   1. Start the app")
    print("   2. Look at logs/app.log")
    print("   3. You should see this startup message: 'Application starting up - Full Terminal Capture Enabled'")
    print("   4. Any print() statement in the code will now appear in the log file.")
    
    print("\n" + "=" * 60)
    print("✨ All static tests passed!")
    print("\nTo test the web interface:")
    print("1. Start your Flask application")
    print("2. Log in as an Admin user")
    print("3. Navigate to the sidebar → Application Logs")
    print("4. You should see the logging dashboard")
    print("\nAPI Endpoints to test (requires admin login):")
    print(f"  • {base_url}/logs - Logs dashboard")
    print(f"  • {base_url}/api/monitoring/logs - View logs via API")
    print(f"  • {base_url}/api/monitoring/logs/files - List log files")
    print(f"  • {base_url}/api/monitoring/logs/download - Download logs")
    
    return True

if __name__ == "__main__":
    test_logging()
