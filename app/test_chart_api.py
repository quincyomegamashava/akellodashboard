#!/usr/bin/env python3
"""
Simple test script to verify the chart loading API endpoint works correctly
with the new Windows-compatible timeout mechanism.
"""

import requests
import time
import json

def test_chart_api():
    """Test the platforms_overall_yearly API endpoint"""
    
    print("🚀 Testing Chart API Endpoint")
    print("-" * 50)
    
    # API endpoint
    url = "http://127.0.0.1:5000/api/platforms_overall_yearly"
    
    try:
        print(f"📡 Making request to: {url}")
        start_time = time.time()
        
        # Make request with timeout (slightly longer than server timeout)
        response = requests.get(url, timeout=35)
        
        end_time = time.time()
        execution_time = round(end_time - start_time, 2)
        
        print(f"⏱️  Response time: {execution_time} seconds")
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS: API responded successfully!")
            
            try:
                data = response.json()
                print(f"📅 Year: {data.get('year', 'N/A')}")
                print(f"📈 Monthly data points: {len(data.get('monthly_usage', []))}")
                print(f"📊 Yearly totals: {data.get('yearly_totals', {})}")
                
                # Check for debug info
                if '_debug' in data:
                    debug = data['_debug']
                    print(f"🔍 Debug info:")
                    print(f"   - Execution time: {debug.get('execution_time_seconds', 'N/A')}s")
                    print(f"   - Query count: {debug.get('query_count', 'N/A')}")
                    print(f"   - Cache status: {debug.get('cache_status', 'N/A')}")
                
            except json.JSONDecodeError:
                print("⚠️  Response is not valid JSON")
                print(f"Response content: {response.text[:200]}...")
                
        elif response.status_code == 408:
            print("⏳ TIMEOUT: Request timed out (expected behavior for slow queries)")
            try:
                error_data = response.json()
                print(f"Error message: {error_data.get('error', 'No error message')}")
                print(f"Suggestion: {error_data.get('suggestion', 'No suggestion')}")
            except:
                print(f"Response: {response.text}")
                
        elif response.status_code == 500:
            print("❌ SERVER ERROR: Internal server error occurred")
            try:
                error_data = response.json()
                print(f"Error message: {error_data.get('error', 'No error message')}")
                if 'technical_error' in error_data:
                    print(f"Technical details: {error_data['technical_error']}")
            except:
                print(f"Response: {response.text}")
                
        else:
            print(f"❓ UNEXPECTED STATUS: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            
    except requests.exceptions.Timeout:
        print("⏳ CLIENT TIMEOUT: Request took longer than 35 seconds")
        print("   This means the server timeout (25s) didn't work as expected")
        
    except requests.exceptions.ConnectionError:
        print("🔌 CONNECTION ERROR: Could not connect to the server")
        print("   Make sure the Flask app is running on http://127.0.0.1:5000")
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        
    print("-" * 50)
    print("Test completed!")

def test_authentication_required():
    """Test that the endpoint requires authentication"""
    print("\n🔐 Testing Authentication Requirement")
    print("-" * 50)
    
    url = "http://127.0.0.1:5000/api/platforms_overall_yearly"
    
    try:
        # Make request without session/login
        response = requests.get(url, timeout=10)
        
        if response.status_code == 401 or response.status_code == 302:
            print("✅ GOOD: Endpoint properly requires authentication")
        else:
            print(f"⚠️  WARNING: Expected 401/302, got {response.status_code}")
            
    except Exception as e:
        print(f"Error testing authentication: {e}")

if __name__ == "__main__":
    print("Chart API Test Script")
    print("=" * 50)
    
    # Test 1: Basic API functionality
    test_chart_api()
    
    # Test 2: Authentication requirement
    test_authentication_required()
    
    print("\n📝 NOTE: To fully test this endpoint, you need to:")
    print("1. Start the Flask application")
    print("2. Login to the application to get a valid session")
    print("3. Use a browser or authenticated session to test")
    print("\nFor now, this script tests the basic connectivity and error handling.")