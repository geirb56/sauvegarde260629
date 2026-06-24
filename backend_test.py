#!/usr/bin/env python3
"""
Comprehensive backend test suite for CardioCoach Garmin connector.
Tests all endpoints with the MockProvider (no real Garmin credentials needed).
"""

import requests
import json
import sys
from typing import Dict, Any

# Backend URL from frontend/.env
BASE_URL = "https://charge-load.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log_test(name: str):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*80}{Colors.RESET}")

def log_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def log_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def log_info(msg: str):
    print(f"{Colors.YELLOW}ℹ {msg}{Colors.RESET}")

def pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2)

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self):
        self.passed += 1
    
    def add_fail(self, error: str):
        self.failed += 1
        self.errors.append(error)
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{Colors.BLUE}{'='*80}{Colors.RESET}")
        print(f"{Colors.BLUE}TEST SUMMARY{Colors.RESET}")
        print(f"{Colors.BLUE}{'='*80}{Colors.RESET}")
        print(f"Total: {total} | Passed: {Colors.GREEN}{self.passed}{Colors.RESET} | Failed: {Colors.RED}{self.failed}{Colors.RESET}")
        
        if self.errors:
            print(f"\n{Colors.RED}FAILED TESTS:{Colors.RESET}")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error}")
        
        return self.failed == 0

results = TestResults()

def test_connect_basic():
    """Test 1: Basic connect without MFA (empty body or no body)"""
    log_test("1. POST /api/garmin/connect?user_id=testuser1 (basic connect)")
    
    user_id = "testuser1"
    url = f"{BASE_URL}/garmin/connect?user_id={user_id}"
    
    try:
        # Test with empty JSON body
        response = requests.post(url, json={}, timeout=10)
        log_info(f"Status Code: {response.status_code}")
        log_info(f"Response: {pretty_json(response.json())}")
        
        if response.status_code != 200:
            log_error(f"Expected status 200, got {response.status_code}")
            results.add_fail(f"Test 1: Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Verify response structure
        if data.get("status") != "connected":
            log_error(f"Expected status 'connected', got '{data.get('status')}'")
            results.add_fail(f"Test 1: Expected status 'connected', got '{data.get('status')}'")
            return False
        
        if data.get("provider") != "mock":
            log_error(f"Expected provider 'mock', got '{data.get('provider')}'")
            results.add_fail(f"Test 1: Expected provider 'mock', got '{data.get('provider')}'")
            return False
        
        if "message" not in data:
            log_error("Missing 'message' field in response")
            results.add_fail("Test 1: Missing 'message' field in response")
            return False
        
        # CRITICAL: Verify no password was required
        log_success("Connect succeeded without password ✓")
        log_success(f"Status: {data['status']}")
        log_success(f"Provider: {data['provider']}")
        log_success(f"Message: {data['message']}")
        
        results.add_pass()
        return True
        
    except Exception as e:
        log_error(f"Exception: {str(e)}")
        results.add_fail(f"Test 1: Exception - {str(e)}")
        return False

def test_sync():
    """Test 2: Sync activities after connect"""
    log_test("2. POST /api/garmin/sync?user_id=testuser1")
    
    user_id = "testuser1"
    url = f"{BASE_URL}/garmin/sync?user_id={user_id}"
    
    try:
        response = requests.post(url, timeout=10)
        log_info(f"Status Code: {response.status_code}")
        log_info(f"Response: {pretty_json(response.json())}")
        
        if response.status_code != 200:
            log_error(f"Expected status 200, got {response.status_code}")
            results.add_fail(f"Test 2: Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get("success"):
            log_error(f"Expected success=true, got {data.get('success')}")
            results.add_fail(f"Test 2: Expected success=true, got {data.get('success')}")
            return False
        
        synced_count = data.get("synced_count", 0)
        if synced_count <= 0:
            log_error(f"Expected synced_count > 0, got {synced_count}")
            results.add_fail(f"Test 2: Expected synced_count > 0, got {synced_count}")
            return False
        
        log_success(f"Sync succeeded: {synced_count} activities synced")
        log_success(f"Message: {data.get('message')}")
        
        results.add_pass()
        return True
        
    except Exception as e:
        log_error(f"Exception: {str(e)}")
        results.add_fail(f"Test 2: Exception - {str(e)}")
        return False

def test_status():
    """Test 3: Get connection status"""
    log_test("3. GET /api/garmin/status?user_id=testuser1")
    
    user_id = "testuser1"
    url = f"{BASE_URL}/garmin/status?user_id={user_id}"
    
    try:
        response = requests.get(url, timeout=10)
        log_info(f"Status Code: {response.status_code}")
        log_info(f"Response: {pretty_json(response.json())}")
        
        if response.status_code != 200:
            log_error(f"Expected status 200, got {response.status_code}")
            results.add_fail(f"Test 3: Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get("connected"):
            log_error(f"Expected connected=true, got {data.get('connected')}")
            results.add_fail(f"Test 3: Expected connected=true, got {data.get('connected')}")
            return False
        
        if data.get("provider") != "mock":
            log_error(f"Expected provider='mock', got '{data.get('provider')}'")
            results.add_fail(f"Test 3: Expected provider='mock', got '{data.get('provider')}'")
            return False
        
        if data.get("last_sync") is None:
            log_error("Expected last_sync to be non-null")
            results.add_fail("Test 3: Expected last_sync to be non-null")
            return False
        
        activity_count = data.get("activity_count", 0)
        if activity_count <= 0:
            log_error(f"Expected activity_count > 0, got {activity_count}")
            results.add_fail(f"Test 3: Expected activity_count > 0, got {activity_count}")
            return False
        
        log_success(f"Connected: {data['connected']}")
        log_success(f"Provider: {data['provider']}")
        log_success(f"Last sync: {data['last_sync']}")
        log_success(f"Activity count: {activity_count}")
        
        results.add_pass()
        return True
        
    except Exception as e:
        log_error(f"Exception: {str(e)}")
        results.add_fail(f"Test 3: Exception - {str(e)}")
        return False

def test_activities():
    """Test 4: Get activities list with normalized fields"""
    log_test("4. GET /api/garmin/activities?user_id=testuser1&limit=20")
    
    user_id = "testuser1"
    url = f"{BASE_URL}/garmin/activities?user_id={user_id}&limit=20"
    
    try:
        response = requests.get(url, timeout=10)
        log_info(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            log_error(f"Expected status 200, got {response.status_code}")
            results.add_fail(f"Test 4: Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        log_info(f"Response: {pretty_json(data)}")
        
        if "activities" not in data:
            log_error("Missing 'activities' field in response")
            results.add_fail("Test 4: Missing 'activities' field in response")
            return False
        
        if "count" not in data:
            log_error("Missing 'count' field in response")
            results.add_fail("Test 4: Missing 'count' field in response")
            return False
        
        activities = data["activities"]
        count = data["count"]
        
        if count <= 0:
            log_error(f"Expected count > 0, got {count}")
            results.add_fail(f"Test 4: Expected count > 0, got {count}")
            return False
        
        if len(activities) != count:
            log_error(f"Count mismatch: count={count}, len(activities)={len(activities)}")
            results.add_fail(f"Test 4: Count mismatch")
            return False
        
        # Verify normalized fields in first activity
        if activities:
            activity = activities[0]
            required_fields = ["external_id", "source", "distance", "duration", "pace", "avg_hr"]
            missing_fields = [f for f in required_fields if f not in activity]
            
            if missing_fields:
                log_error(f"Missing required fields in activity: {missing_fields}")
                results.add_fail(f"Test 4: Missing fields {missing_fields}")
                return False
            
            if activity.get("source") != "garmin":
                log_error(f"Expected source='garmin', got '{activity.get('source')}'")
                results.add_fail(f"Test 4: Expected source='garmin'")
                return False
            
            log_success(f"Retrieved {count} activities")
            log_success(f"Sample activity: {activity.get('name')} - {activity.get('distance')}m, {activity.get('duration')}s, pace {activity.get('pace')}, HR {activity.get('avg_hr')}")
            log_success("All required normalized fields present ✓")
        
        results.add_pass()
        return True
        
    except Exception as e:
        log_error(f"Exception: {str(e)}")
        results.add_fail(f"Test 4: Exception - {str(e)}")
        return False

def test_mfa_mode():
    """Test 5: MFA Mode 2 path (simulate_mfa flag)"""
    log_test("5. MFA Mode 2: POST /api/garmin/connect with simulate_mfa=true")
    
    user_id = "mfauser1"
    url = f"{BASE_URL}/garmin/connect?user_id={user_id}"
    
    try:
        # First call with simulate_mfa=true should return mfa_required
        log_info("First call with simulate_mfa=true...")
        response1 = requests.post(url, json={"simulate_mfa": True}, timeout=10)
        log_info(f"Status Code: {response1.status_code}")
        log_info(f"Response: {pretty_json(response1.json())}")
        
        if response1.status_code != 200:
            log_error(f"Expected status 200, got {response1.status_code}")
            results.add_fail(f"Test 5a: Expected status 200, got {response1.status_code}")
            return False
        
        data1 = response1.json()
        
        if data1.get("status") != "mfa_required":
            log_error(f"Expected status 'mfa_required', got '{data1.get('status')}'")
            results.add_fail(f"Test 5a: Expected status 'mfa_required', got '{data1.get('status')}'")
            return False
        
        log_success(f"First call returned mfa_required ✓")
        
        # Retry the same call - should now return connected
        log_info("\nRetrying the same call...")
        response2 = requests.post(url, json={"simulate_mfa": True}, timeout=10)
        log_info(f"Status Code: {response2.status_code}")
        log_info(f"Response: {pretty_json(response2.json())}")
        
        if response2.status_code != 200:
            log_error(f"Expected status 200, got {response2.status_code}")
            results.add_fail(f"Test 5b: Expected status 200, got {response2.status_code}")
            return False
        
        data2 = response2.json()
        
        if data2.get("status") != "connected":
            log_error(f"Expected status 'connected', got '{data2.get('status')}'")
            results.add_fail(f"Test 5b: Expected status 'connected', got '{data2.get('status')}'")
            return False
        
        log_success(f"Retry returned connected ✓")
        log_success("MFA Mode 2 flow working correctly")
        
        results.add_pass()
        return True
        
    except Exception as e:
        log_error(f"Exception: {str(e)}")
        results.add_fail(f"Test 5: Exception - {str(e)}")
        return False

def test_sync_before_connect():
    """Test 6: Sync without connect (should fail gracefully)"""
    log_test("6. Sync-before-connect guard: POST /api/garmin/sync for unconnected user")
    
    user_id = "freshuser_random_12345"
    url = f"{BASE_URL}/garmin/sync?user_id={user_id}"
    
    try:
        response = requests.post(url, timeout=10)
        log_info(f"Status Code: {response.status_code}")
        log_info(f"Response: {pretty_json(response.json())}")
        
        if response.status_code != 200:
            log_error(f"Expected status 200 (graceful failure), got {response.status_code}")
            results.add_fail(f"Test 6: Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        if data.get("success") != False:
            log_error(f"Expected success=false, got {data.get('success')}")
            results.add_fail(f"Test 6: Expected success=false")
            return False
        
        if data.get("synced_count") != 0:
            log_error(f"Expected synced_count=0, got {data.get('synced_count')}")
            results.add_fail(f"Test 6: Expected synced_count=0")
            return False
        
        message = data.get("message", "")
        if "not connected" not in message.lower():
            log_error(f"Expected message about 'not connected', got '{message}'")
            results.add_fail(f"Test 6: Expected 'not connected' message")
            return False
        
        log_success("Sync correctly rejected for unconnected user ✓")
        log_success(f"Message: {message}")
        log_success("No 500 error - graceful failure ✓")
        
        results.add_pass()
        return True
        
    except Exception as e:
        log_error(f"Exception: {str(e)}")
        results.add_fail(f"Test 6: Exception - {str(e)}")
        return False

def test_disconnect():
    """Test 7: Disconnect and verify cleanup"""
    log_test("7. Disconnect: POST /api/garmin/disconnect?user_id=testuser1")
    
    user_id = "testuser1"
    disconnect_url = f"{BASE_URL}/garmin/disconnect?user_id={user_id}"
    status_url = f"{BASE_URL}/garmin/status?user_id={user_id}"
    
    try:
        # Disconnect
        log_info("Disconnecting...")
        response = requests.post(disconnect_url, timeout=10)
        log_info(f"Status Code: {response.status_code}")
        log_info(f"Response: {pretty_json(response.json())}")
        
        if response.status_code != 200:
            log_error(f"Expected status 200, got {response.status_code}")
            results.add_fail(f"Test 7a: Expected status 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get("success"):
            log_error(f"Expected success=true, got {data.get('success')}")
            results.add_fail(f"Test 7a: Expected success=true")
            return False
        
        log_success("Disconnect succeeded ✓")
        
        # Verify status shows disconnected
        log_info("\nVerifying status after disconnect...")
        status_response = requests.get(status_url, timeout=10)
        log_info(f"Status Code: {status_response.status_code}")
        log_info(f"Response: {pretty_json(status_response.json())}")
        
        if status_response.status_code != 200:
            log_error(f"Expected status 200, got {status_response.status_code}")
            results.add_fail(f"Test 7b: Expected status 200, got {status_response.status_code}")
            return False
        
        status_data = status_response.json()
        
        if status_data.get("connected") != False:
            log_error(f"Expected connected=false, got {status_data.get('connected')}")
            results.add_fail(f"Test 7b: Expected connected=false")
            return False
        
        if status_data.get("activity_count") != 0:
            log_error(f"Expected activity_count=0, got {status_data.get('activity_count')}")
            results.add_fail(f"Test 7b: Expected activity_count=0 after disconnect")
            return False
        
        log_success("Status shows disconnected ✓")
        log_success("Activity count reset to 0 ✓")
        
        results.add_pass()
        return True
        
    except Exception as e:
        log_error(f"Exception: {str(e)}")
        results.add_fail(f"Test 7: Exception - {str(e)}")
        return False

def test_idempotency():
    """Test 8: Idempotency - sync twice should not duplicate activities"""
    log_test("8. Idempotency: Connect + sync twice for fresh user")
    
    user_id = "idempotency_test_user_99"
    connect_url = f"{BASE_URL}/garmin/connect?user_id={user_id}"
    sync_url = f"{BASE_URL}/garmin/sync?user_id={user_id}"
    status_url = f"{BASE_URL}/garmin/status?user_id={user_id}"
    
    try:
        # Connect
        log_info("Connecting...")
        connect_resp = requests.post(connect_url, json={}, timeout=10)
        if connect_resp.status_code != 200 or connect_resp.json().get("status") != "connected":
            log_error("Failed to connect")
            results.add_fail("Test 8: Failed to connect")
            return False
        log_success("Connected ✓")
        
        # First sync
        log_info("\nFirst sync...")
        sync1_resp = requests.post(sync_url, timeout=10)
        if sync1_resp.status_code != 200:
            log_error(f"First sync failed with status {sync1_resp.status_code}")
            results.add_fail(f"Test 8: First sync failed")
            return False
        
        sync1_data = sync1_resp.json()
        synced_count_1 = sync1_data.get("synced_count", 0)
        log_info(f"First sync: {pretty_json(sync1_data)}")
        log_success(f"First sync: {synced_count_1} activities")
        
        # Get status after first sync
        status1_resp = requests.get(status_url, timeout=10)
        status1_data = status1_resp.json()
        activity_count_1 = status1_data.get("activity_count", 0)
        log_success(f"Activity count after first sync: {activity_count_1}")
        
        # Second sync (should be idempotent)
        log_info("\nSecond sync (should be idempotent)...")
        sync2_resp = requests.post(sync_url, timeout=10)
        if sync2_resp.status_code != 200:
            log_error(f"Second sync failed with status {sync2_resp.status_code}")
            results.add_fail(f"Test 8: Second sync failed")
            return False
        
        sync2_data = sync2_resp.json()
        synced_count_2 = sync2_data.get("synced_count", 0)
        log_info(f"Second sync: {pretty_json(sync2_data)}")
        log_success(f"Second sync: {synced_count_2} activities")
        
        # Get status after second sync
        status2_resp = requests.get(status_url, timeout=10)
        status2_data = status2_resp.json()
        activity_count_2 = status2_data.get("activity_count", 0)
        log_success(f"Activity count after second sync: {activity_count_2}")
        
        # Verify idempotency
        if activity_count_1 != activity_count_2:
            log_error(f"Activity count changed: {activity_count_1} -> {activity_count_2} (should be stable)")
            results.add_fail(f"Test 8: Activity count not stable (duplicates?)")
            return False
        
        # The synced_count on second sync should be the same (re-upserting same activities)
        # or could be 0 if provider returns same activities and upsert doesn't count as "new"
        # Based on the code, it will still count as synced since it processes all activities
        log_success(f"Activity count stable: {activity_count_1} == {activity_count_2} ✓")
        log_success("No duplicate activities created ✓")
        
        results.add_pass()
        return True
        
    except Exception as e:
        log_error(f"Exception: {str(e)}")
        results.add_fail(f"Test 8: Exception - {str(e)}")
        return False

def main():
    print(f"\n{Colors.BLUE}{'='*80}{Colors.RESET}")
    print(f"{Colors.BLUE}CardioCoach Garmin Connector Backend Test Suite{Colors.RESET}")
    print(f"{Colors.BLUE}Base URL: {BASE_URL}{Colors.RESET}")
    print(f"{Colors.BLUE}Provider: MockProvider (GARMIN_PROVIDER=mock){Colors.RESET}")
    print(f"{Colors.BLUE}{'='*80}{Colors.RESET}")
    
    # Run all tests in order
    test_connect_basic()
    test_sync()
    test_status()
    test_activities()
    test_mfa_mode()
    test_sync_before_connect()
    test_disconnect()
    test_idempotency()
    
    # Print summary
    success = results.summary()
    
    if success:
        print(f"\n{Colors.GREEN}{'='*80}{Colors.RESET}")
        print(f"{Colors.GREEN}ALL TESTS PASSED ✓{Colors.RESET}")
        print(f"{Colors.GREEN}{'='*80}{Colors.RESET}")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}{'='*80}{Colors.RESET}")
        print(f"{Colors.RED}SOME TESTS FAILED ✗{Colors.RESET}")
        print(f"{Colors.RED}{'='*80}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
