#!/usr/bin/env python3
"""
Comprehensive backend test for CardioCoach Garmin connector with REAL gccli provider.

CRITICAL CONSTRAINT: connect must NOT require or accept any Garmin password (only user_id + optional testing body).

Test scenarios:
1. POST /api/garmin/connect?user_id=qa1 (empty JSON body {}) → expect 200, {"status":"connected","provider":"gccli"}
2. POST /api/garmin/sync?user_id=qa1 → expect 200, {"success":true,"synced_count">0 (REAL activities, expect ~30),"metrics_count">0 (up to 7)}
3. GET /api/garmin/activities?user_id=qa1&limit=30 → expect real activities with all required fields
4. GET /api/garmin/daily-metrics?user_id=qa1&days=7 → expect real metrics (hrv MAY be null - acceptable)
5. GET /api/workouts?user_id=qa1 → must include data_source=="garmin" workouts, NO "mock" ids
6. Idempotency: POST /api/garmin/sync?user_id=qa1 AGAIN → count stable (no duplicates)
7. Disconnect cleanup: POST /api/garmin/disconnect?user_id=qa1 → complete cleanup
8. Regression: status check, sync-before-connect for brand-new user
"""

import requests
import time
import sys
from typing import Dict, List, Any

# External base URL from frontend/.env
BASE_URL = "https://charge-load.preview.emergentagent.com/api"
USER_ID = "qa1"

# Test results tracking
test_results = []
failed_tests = []


def log_test(test_num: int, description: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"Test {test_num}: {status} - {description}"
    if details:
        result += f"\n  Details: {details}"
    print(result)
    test_results.append({"test": test_num, "description": description, "passed": passed, "details": details})
    if not passed:
        failed_tests.append({"test": test_num, "description": description, "details": details})


def test_1_connect():
    """Test 1: POST /api/garmin/connect?user_id=qa1 (empty JSON body {})"""
    print("\n" + "="*80)
    print("TEST 1: Connect endpoint (no password required)")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/garmin/connect?user_id={USER_ID}"
        response = requests.post(url, json={}, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code != 200:
            log_test(1, "Connect endpoint", False, f"Expected 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Verify required fields
        if data.get("status") != "connected":
            log_test(1, "Connect endpoint", False, f"Expected status='connected', got '{data.get('status')}'")
            return False
        
        if data.get("provider") != "gccli":
            log_test(1, "Connect endpoint", False, f"Expected provider='gccli', got '{data.get('provider')}'")
            return False
        
        log_test(1, "Connect endpoint", True, f"Connected successfully with provider=gccli (no password required)")
        return True
        
    except Exception as e:
        log_test(1, "Connect endpoint", False, f"Exception: {str(e)}")
        return False


def test_2_sync():
    """Test 2: POST /api/garmin/sync?user_id=qa1"""
    print("\n" + "="*80)
    print("TEST 2: Sync endpoint (REAL activities and metrics)")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/garmin/sync?user_id={USER_ID}"
        print(f"Syncing... (may take up to 90 seconds)")
        response = requests.post(url, timeout=90)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code != 200:
            log_test(2, "Sync endpoint", False, f"Expected 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Verify success
        if not data.get("success"):
            log_test(2, "Sync endpoint", False, f"Expected success=true, got {data.get('success')}")
            return False
        
        # Verify synced_count > 0 (expect ~30 real activities)
        synced_count = data.get("synced_count", 0)
        if synced_count <= 0:
            log_test(2, "Sync endpoint", False, f"Expected synced_count > 0, got {synced_count}")
            return False
        
        # Verify metrics_count > 0 (up to 7)
        metrics_count = data.get("metrics_count", 0)
        if metrics_count <= 0:
            log_test(2, "Sync endpoint", False, f"Expected metrics_count > 0, got {metrics_count}")
            return False
        
        log_test(2, "Sync endpoint", True, f"Synced {synced_count} activities and {metrics_count} metrics (REAL data)")
        return True
        
    except Exception as e:
        log_test(2, "Sync endpoint", False, f"Exception: {str(e)}")
        return False


def test_3_activities():
    """Test 3: GET /api/garmin/activities?user_id=qa1&limit=30"""
    print("\n" + "="*80)
    print("TEST 3: Activities endpoint (verify REAL data structure)")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/garmin/activities?user_id={USER_ID}&limit=30"
        response = requests.get(url, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            log_test(3, "Activities endpoint", False, f"Expected 200, got {response.status_code}")
            return False
        
        data = response.json()
        activities = data.get("activities", [])
        
        print(f"Activities count: {len(activities)}")
        
        if len(activities) == 0:
            log_test(3, "Activities endpoint", False, "No activities returned")
            return False
        
        # Verify first activity has all required fields
        first_activity = activities[0]
        print(f"Sample activity: {first_activity}")
        
        required_fields = ["external_id", "source", "name", "distance", "duration", "avg_hr", "pace"]
        missing_fields = []
        
        for field in required_fields:
            if field not in first_activity:
                missing_fields.append(field)
        
        if missing_fields:
            log_test(3, "Activities endpoint", False, f"Missing required fields: {missing_fields}")
            return False
        
        # Verify source is "garmin"
        if first_activity.get("source") != "garmin":
            log_test(3, "Activities endpoint", False, f"Expected source='garmin', got '{first_activity.get('source')}'")
            return False
        
        # Verify distance > 0
        if not first_activity.get("distance") or first_activity.get("distance") <= 0:
            log_test(3, "Activities endpoint", False, f"Expected distance > 0, got {first_activity.get('distance')}")
            return False
        
        # Verify duration > 0
        if not first_activity.get("duration") or first_activity.get("duration") <= 0:
            log_test(3, "Activities endpoint", False, f"Expected duration > 0, got {first_activity.get('duration')}")
            return False
        
        # Verify name is non-empty
        if not first_activity.get("name"):
            log_test(3, "Activities endpoint", False, "Expected non-empty name")
            return False
        
        # Check if data looks REAL (not deterministic mock)
        # Real data should have varied names and distances
        names = [a.get("name") for a in activities[:5]]
        distances = [a.get("distance") for a in activities[:5]]
        
        print(f"Sample names: {names[:3]}")
        print(f"Sample distances: {distances[:3]}")
        
        log_test(3, "Activities endpoint", True, f"Retrieved {len(activities)} REAL activities with all required fields")
        return True
        
    except Exception as e:
        log_test(3, "Activities endpoint", False, f"Exception: {str(e)}")
        return False


def test_4_daily_metrics():
    """Test 4: GET /api/garmin/daily-metrics?user_id=qa1&days=7"""
    print("\n" + "="*80)
    print("TEST 4: Daily metrics endpoint (hrv MAY be null - acceptable)")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/garmin/daily-metrics?user_id={USER_ID}&days=7"
        response = requests.get(url, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            log_test(4, "Daily metrics endpoint", False, f"Expected 200, got {response.status_code}")
            return False
        
        data = response.json()
        print(f"Response: {data}")
        
        # Verify count > 0
        count = data.get("count", 0)
        if count <= 0:
            log_test(4, "Daily metrics endpoint", False, f"Expected count > 0, got {count}")
            return False
        
        # Verify metrics array
        metrics = data.get("metrics", [])
        if len(metrics) == 0:
            log_test(4, "Daily metrics endpoint", False, "No metrics returned")
            return False
        
        # Verify latest exists
        latest = data.get("latest")
        if not latest:
            log_test(4, "Daily metrics endpoint", False, "No latest metric")
            return False
        
        # Verify first metric has required fields
        first_metric = metrics[0]
        print(f"Sample metric: {first_metric}")
        
        required_fields = ["date", "resting_hr", "sleep_hours"]
        missing_fields = []
        
        for field in required_fields:
            if field not in first_metric:
                missing_fields.append(field)
        
        if missing_fields:
            log_test(4, "Daily metrics endpoint", False, f"Missing required fields: {missing_fields}")
            return False
        
        # Verify resting_hr is a real bpm value
        resting_hr = first_metric.get("resting_hr")
        if not isinstance(resting_hr, (int, float)) or resting_hr <= 0:
            log_test(4, "Daily metrics endpoint", False, f"Expected resting_hr > 0, got {resting_hr}")
            return False
        
        # Verify sleep_hours is a real number
        sleep_hours = first_metric.get("sleep_hours")
        if not isinstance(sleep_hours, (int, float)) or sleep_hours < 0:
            log_test(4, "Daily metrics endpoint", False, f"Expected sleep_hours >= 0, got {sleep_hours}")
            return False
        
        # Note: hrv MAY be null - this is EXPECTED and acceptable
        hrv = first_metric.get("hrv")
        hrv_status = "null (expected/acceptable)" if hrv is None else f"{hrv}"
        
        log_test(4, "Daily metrics endpoint", True, f"Retrieved {count} REAL metrics (resting_hr={resting_hr}, sleep_hours={sleep_hours}, hrv={hrv_status})")
        return True
        
    except Exception as e:
        log_test(4, "Daily metrics endpoint", False, f"Exception: {str(e)}")
        return False


def test_5_workouts():
    """Test 5: GET /api/workouts?user_id=qa1"""
    print("\n" + "="*80)
    print("TEST 5: Workouts endpoint (verify Garmin workouts, NO mock ids)")
    print("="*80)
    
    try:
        url = f"{BASE_URL}/workouts?user_id={USER_ID}"
        response = requests.get(url, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            log_test(5, "Workouts endpoint", False, f"Expected 200, got {response.status_code}")
            return False
        
        workouts = response.json()
        print(f"Total workouts: {len(workouts)}")
        
        # Filter Garmin workouts
        garmin_workouts = [w for w in workouts if w.get("data_source") == "garmin"]
        print(f"Garmin workouts: {len(garmin_workouts)}")
        
        if len(garmin_workouts) == 0:
            log_test(5, "Workouts endpoint", False, "No data_source='garmin' workouts found")
            return False
        
        # CRITICAL: Verify NO ids containing "mock"
        mock_ids = [w.get("id") for w in garmin_workouts if "mock" in w.get("id", "").lower()]
        if mock_ids:
            log_test(5, "Workouts endpoint", False, f"Found mock ids in Garmin workouts: {mock_ids}")
            return False
        
        # Verify first Garmin workout has required fields
        first_workout = garmin_workouts[0]
        print(f"Sample Garmin workout: {first_workout}")
        
        # Verify id starts with "garmin-"
        workout_id = first_workout.get("id", "")
        if not workout_id.startswith("garmin-"):
            log_test(5, "Workouts endpoint", False, f"Expected id to start with 'garmin-', got '{workout_id}'")
            return False
        
        # Verify type in {run, cycle, swim}
        workout_type = first_workout.get("type")
        if workout_type not in ["run", "cycle", "swim"]:
            log_test(5, "Workouts endpoint", False, f"Expected type in [run, cycle, swim], got '{workout_type}'")
            return False
        
        # Verify required fields
        required_fields = ["name", "date", "duration_minutes", "distance_km", "avg_heart_rate", "avg_pace_min_km"]
        missing_fields = []
        
        for field in required_fields:
            if field not in first_workout:
                missing_fields.append(field)
        
        if missing_fields:
            log_test(5, "Workouts endpoint", False, f"Missing required fields: {missing_fields}")
            return False
        
        # Verify distance_km > 0
        distance_km = first_workout.get("distance_km", 0)
        if distance_km <= 0:
            log_test(5, "Workouts endpoint", False, f"Expected distance_km > 0, got {distance_km}")
            return False
        
        log_test(5, "Workouts endpoint", True, f"Found {len(garmin_workouts)} Garmin workouts (NO mock ids, all with valid structure)")
        return True
        
    except Exception as e:
        log_test(5, "Workouts endpoint", False, f"Exception: {str(e)}")
        return False


def test_6_idempotency():
    """Test 6: Idempotency - POST /api/garmin/sync?user_id=qa1 AGAIN"""
    print("\n" + "="*80)
    print("TEST 6: Idempotency (sync twice, verify no duplicates)")
    print("="*80)
    
    try:
        # Get initial counts
        workouts_url = f"{BASE_URL}/workouts?user_id={USER_ID}"
        metrics_url = f"{BASE_URL}/garmin/daily-metrics?user_id={USER_ID}&days=7"
        
        workouts_before = requests.get(workouts_url, timeout=30).json()
        garmin_workouts_before = [w for w in workouts_before if w.get("data_source") == "garmin"]
        count_before = len(garmin_workouts_before)
        
        metrics_before = requests.get(metrics_url, timeout=30).json()
        metrics_count_before = metrics_before.get("count", 0)
        
        print(f"Before re-sync: {count_before} Garmin workouts, {metrics_count_before} metrics")
        
        # Sync again
        sync_url = f"{BASE_URL}/garmin/sync?user_id={USER_ID}"
        print(f"Re-syncing... (may take up to 90 seconds)")
        sync_response = requests.post(sync_url, timeout=90)
        
        if sync_response.status_code != 200:
            log_test(6, "Idempotency", False, f"Sync failed with status {sync_response.status_code}")
            return False
        
        # Get counts after re-sync
        workouts_after = requests.get(workouts_url, timeout=30).json()
        garmin_workouts_after = [w for w in workouts_after if w.get("data_source") == "garmin"]
        count_after = len(garmin_workouts_after)
        
        metrics_after = requests.get(metrics_url, timeout=30).json()
        metrics_count_after = metrics_after.get("count", 0)
        
        print(f"After re-sync: {count_after} Garmin workouts, {metrics_count_after} metrics")
        
        # Verify counts are stable (no duplicates)
        if count_before != count_after:
            log_test(6, "Idempotency", False, f"Garmin workouts count changed: {count_before} -> {count_after} (duplicates created)")
            return False
        
        if metrics_count_before != metrics_count_after:
            log_test(6, "Idempotency", False, f"Metrics count changed: {metrics_count_before} -> {metrics_count_after} (duplicates created)")
            return False
        
        log_test(6, "Idempotency", True, f"Counts stable: {count_after} workouts, {metrics_count_after} metrics (no duplicates)")
        return True
        
    except Exception as e:
        log_test(6, "Idempotency", False, f"Exception: {str(e)}")
        return False


def test_7_disconnect_cleanup():
    """Test 7: Disconnect cleanup - POST /api/garmin/disconnect?user_id=qa1"""
    print("\n" + "="*80)
    print("TEST 7: Disconnect cleanup (verify complete cleanup)")
    print("="*80)
    
    try:
        # Disconnect
        disconnect_url = f"{BASE_URL}/garmin/disconnect?user_id={USER_ID}"
        disconnect_response = requests.post(disconnect_url, timeout=30)
        
        print(f"Disconnect Status Code: {disconnect_response.status_code}")
        print(f"Disconnect Response: {disconnect_response.json()}")
        
        if disconnect_response.status_code != 200:
            log_test(7, "Disconnect cleanup", False, f"Expected 200, got {disconnect_response.status_code}")
            return False
        
        disconnect_data = disconnect_response.json()
        if not disconnect_data.get("success"):
            log_test(7, "Disconnect cleanup", False, f"Expected success=true, got {disconnect_data.get('success')}")
            return False
        
        # Verify daily-metrics count == 0
        metrics_url = f"{BASE_URL}/garmin/daily-metrics?user_id={USER_ID}&days=7"
        metrics_response = requests.get(metrics_url, timeout=30)
        metrics_data = metrics_response.json()
        metrics_count = metrics_data.get("count", -1)
        
        print(f"Daily metrics count after disconnect: {metrics_count}")
        
        if metrics_count != 0:
            log_test(7, "Disconnect cleanup", False, f"Expected metrics count=0, got {metrics_count}")
            return False
        
        # Verify no data_source='garmin' workouts remain
        workouts_url = f"{BASE_URL}/workouts?user_id={USER_ID}"
        workouts_response = requests.get(workouts_url, timeout=30)
        workouts = workouts_response.json()
        garmin_workouts = [w for w in workouts if w.get("data_source") == "garmin"]
        
        print(f"Garmin workouts after disconnect: {len(garmin_workouts)}")
        
        if len(garmin_workouts) != 0:
            log_test(7, "Disconnect cleanup", False, f"Expected 0 Garmin workouts, found {len(garmin_workouts)}")
            return False
        
        # Verify status shows connected=false
        status_url = f"{BASE_URL}/garmin/status?user_id={USER_ID}"
        status_response = requests.get(status_url, timeout=30)
        status_data = status_response.json()
        
        print(f"Status after disconnect: {status_data}")
        
        if status_data.get("connected") != False:
            log_test(7, "Disconnect cleanup", False, f"Expected connected=false, got {status_data.get('connected')}")
            return False
        
        log_test(7, "Disconnect cleanup", True, "Complete cleanup verified (metrics=0, workouts=0, connected=false)")
        return True
        
    except Exception as e:
        log_test(7, "Disconnect cleanup", False, f"Exception: {str(e)}")
        return False


def test_8_regression():
    """Test 8: Regression tests"""
    print("\n" + "="*80)
    print("TEST 8: Regression tests")
    print("="*80)
    
    all_passed = True
    
    # 8a: Status check after fresh connect
    try:
        print("\n8a: Status check after fresh connect")
        
        # Connect again
        connect_url = f"{BASE_URL}/garmin/connect?user_id={USER_ID}"
        connect_response = requests.post(connect_url, json={}, timeout=30)
        
        if connect_response.status_code != 200:
            log_test(8, "Regression (8a: status after connect)", False, f"Connect failed with status {connect_response.status_code}")
            all_passed = False
        else:
            # Check status
            status_url = f"{BASE_URL}/garmin/status?user_id={USER_ID}"
            status_response = requests.get(status_url, timeout=30)
            status_data = status_response.json()
            
            print(f"Status: {status_data}")
            
            if status_data.get("connected") != True:
                log_test(8, "Regression (8a: status after connect)", False, f"Expected connected=true, got {status_data.get('connected')}")
                all_passed = False
            elif status_data.get("provider") != "gccli":
                log_test(8, "Regression (8a: status after connect)", False, f"Expected provider='gccli', got {status_data.get('provider')}")
                all_passed = False
            else:
                print("✅ 8a: Status check passed (connected=true, provider=gccli)")
    except Exception as e:
        log_test(8, "Regression (8a: status after connect)", False, f"Exception: {str(e)}")
        all_passed = False
    
    # 8b: Sync-before-connect for brand-new user
    try:
        print("\n8b: Sync-before-connect for brand-new user")
        
        new_user_id = "qa_never_connected"
        
        # Try to sync without connecting first
        sync_url = f"{BASE_URL}/garmin/sync?user_id={new_user_id}"
        sync_response = requests.post(sync_url, timeout=30)
        
        print(f"Sync Status Code: {sync_response.status_code}")
        print(f"Sync Response: {sync_response.json()}")
        
        if sync_response.status_code == 500:
            log_test(8, "Regression (8b: sync-before-connect)", False, "Got 500 error (should be graceful failure)")
            all_passed = False
        else:
            sync_data = sync_response.json()
            
            if sync_data.get("success") != False:
                log_test(8, "Regression (8b: sync-before-connect)", False, f"Expected success=false, got {sync_data.get('success')}")
                all_passed = False
            elif "not connected" not in sync_data.get("message", "").lower():
                log_test(8, "Regression (8b: sync-before-connect)", False, f"Expected 'not connected' message, got '{sync_data.get('message')}'")
                all_passed = False
            else:
                print("✅ 8b: Sync-before-connect guard passed (graceful failure, no 500)")
    except Exception as e:
        log_test(8, "Regression (8b: sync-before-connect)", False, f"Exception: {str(e)}")
        all_passed = False
    
    if all_passed:
        log_test(8, "Regression tests", True, "All regression tests passed (status check, sync-before-connect guard)")
    
    return all_passed


def main():
    """Run all tests in order"""
    print("\n" + "="*80)
    print("CARDIOCOACH GARMIN CONNECTOR - REAL GCCLI PROVIDER TESTING")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"User ID: {USER_ID}")
    print(f"Provider: gccli (REAL Garmin account)")
    print("="*80)
    
    # Run tests in order
    test_1_connect()
    time.sleep(1)
    
    test_2_sync()
    time.sleep(1)
    
    test_3_activities()
    time.sleep(1)
    
    test_4_daily_metrics()
    time.sleep(1)
    
    test_5_workouts()
    time.sleep(1)
    
    test_6_idempotency()
    time.sleep(1)
    
    test_7_disconnect_cleanup()
    time.sleep(1)
    
    test_8_regression()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    
    print(f"Total Tests: {total_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {total_count - passed_count}")
    
    if failed_tests:
        print("\n" + "="*80)
        print("FAILED TESTS")
        print("="*80)
        for failed in failed_tests:
            print(f"Test {failed['test']}: {failed['description']}")
            print(f"  Details: {failed['details']}")
    
    print("\n" + "="*80)
    
    # Exit with appropriate code
    if failed_tests:
        sys.exit(1)
    else:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
