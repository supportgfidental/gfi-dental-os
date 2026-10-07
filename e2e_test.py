"""
GFI Dental OS — End-to-End Agent Verification Script
Tests all 4 monopoly agent endpoints against the live FastAPI server.
"""
import requests
import json
import sys
import time

BASE = "http://127.0.0.1:8000"
BYPASS_HEADER = {"X-Admin-Bypass-Key": "GFI_MASTER_ADMIN_BYPASS_2026_SECURE_KEY"}

results = []

def test_endpoint(name, method, url, expect_keys=None):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"  {method} {url}")
    try:
        if method == "POST":
            resp = requests.post(url, headers=BYPASS_HEADER, json={}, timeout=30)
        else:
            resp = requests.get(url, headers=BYPASS_HEADER, timeout=30)
        
        print(f"  STATUS: {resp.status_code}")
        try:
            body = resp.json()
            print(f"  RESPONSE: {json.dumps(body, indent=2)[:500]}")
        except Exception:
            body = resp.text
            print(f"  RESPONSE (text): {body[:500]}")
        
        passed = resp.status_code < 500
        if expect_keys and isinstance(body, dict):
            for k in expect_keys:
                if k not in body:
                    print(f"  WARN: Expected key '{k}' missing from response")
                    passed = False
        
        status = "PASS" if passed else "FAIL"
        print(f"  RESULT: {status}")
        results.append({"test": name, "status_code": resp.status_code, "result": status, "body": body if isinstance(body, dict) else str(body)[:200]})
        return passed
    except requests.exceptions.ConnectionError:
        print(f"  RESULT: FAIL (Connection refused — server not running?)")
        results.append({"test": name, "status_code": 0, "result": "FAIL", "body": "Connection refused"})
        return False
    except Exception as e:
        print(f"  RESULT: FAIL ({e})")
        results.append({"test": name, "status_code": 0, "result": "FAIL", "body": str(e)})
        return False

# Test 0: Health check
test_endpoint("Health Check", "GET", f"{BASE}/")

# Test 1: Insurance Pre-Auth Agent
test_endpoint(
    "Insurance Pre-Auth Agent (clinic=1, treatment_plan=1)",
    "POST",
    f"{BASE}/api/v1/agents/insurance/process/1/1",
    expect_keys=["status"]
)

# Test 2: Patient Retention Agent
test_endpoint(
    "Patient Retention Agent (clinic=1)",
    "POST",
    f"{BASE}/api/v1/agents/retention/scan/1",
    expect_keys=["status"]
)

# Test 3: Inventory Auto-Pilot Agent
test_endpoint(
    "Inventory Auto-Pilot Agent (clinic=1)",
    "POST",
    f"{BASE}/api/v1/agents/inventory/monitor/1",
    expect_keys=["status"]
)

# Test 4: Chair-Side Safety Audit Agent
test_endpoint(
    "Chair-Side Safety Audit Agent (clinic=1, treatment_plan=1)",
    "POST",
    f"{BASE}/api/v1/agents/audit/check/1/1",
    expect_keys=["status", "safety_status", "notes"]
)

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
total = len(results)
passed = sum(1 for r in results if r["result"] == "PASS")
failed = total - passed
for r in results:
    icon = "✓" if r["result"] == "PASS" else "✗"
    print(f"  {icon} [{r['status_code']}] {r['test']}: {r['result']}")

print(f"\n  Total: {total}  Passed: {passed}  Failed: {failed}")

# Write JSON report
with open("e2e_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)

sys.exit(0 if failed == 0 else 1)
