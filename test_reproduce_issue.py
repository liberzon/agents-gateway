#!/usr/bin/env python3
"""
Script to reproduce the duplicate key violation issue with concurrent token creation.
"""

import concurrent.futures
import threading
import time
from datetime import datetime, timedelta

import requests

# Test configuration
API_BASE_URL = "http://localhost:8000"  # Adjust as needed
USER_ID = "895b3648-2bec-4dc9-b036-9b28963f793d"
INTEGRATION_KEY = "google_calendar"


def create_token_request():
    """Create a single token creation request."""
    url = f"{API_BASE_URL}/v2/users/{USER_ID}/tokens"

    # Sample token data matching the error from the issue
    token_data = {
        "integration_key": INTEGRATION_KEY,
        "provider": "google",
        "token_type": "oauth2",
        "token_data": {
            "access_token": "test_access_token_" + str(time.time()),
            "refresh_token": "test_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
        "scopes": ["https://www.googleapis.com/auth/calendar.events"],
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
    }

    headers = {"Content-Type": "application/json"}

    try:
        print(f"[{threading.current_thread().name}] Making request at {datetime.now()}")
        response = requests.post(url, json=token_data, headers=headers, timeout=10)
        print(f"[{threading.current_thread().name}] Response: {response.status_code}")

        if response.status_code != 201 and response.status_code != 200:
            print(f"[{threading.current_thread().name}] Error: {response.text}")
            return response.status_code, response.text

        return response.status_code, response.json()

    except Exception as e:
        print(f"[{threading.current_thread().name}] Exception: {e}")
        return 500, str(e)


def test_concurrent_requests(num_threads=5):
    """Test concurrent token creation requests to reproduce race condition."""
    print(f"Testing concurrent requests with {num_threads} threads...")
    print(f"Target URL: {API_BASE_URL}/v2/users/{USER_ID}/tokens")
    print(f"Integration: {INTEGRATION_KEY}")
    print("-" * 50)

    results = []
    start_time = time.time()

    # Use ThreadPoolExecutor to make concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all requests at once to maximize concurrency
        futures = [executor.submit(create_token_request) for _ in range(num_threads)]

        # Collect results
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            try:
                status_code, response = future.result()
                results.append((status_code, response))
                print(f"Request {i + 1} completed: Status {status_code}")
            except Exception as e:
                print(f"Request {i + 1} failed with exception: {e}")
                results.append((500, str(e)))

    end_time = time.time()

    print("-" * 50)
    print(f"Total execution time: {end_time - start_time:.2f} seconds")

    # Analyze results
    success_count = sum(1 for status, _ in results if status in [200, 201])
    error_count = len(results) - success_count
    duplicate_errors = sum(
        1 for _, response in results if isinstance(response, str) and "duplicate key value" in response.lower()
    )

    print(f"Successful requests: {success_count}/{len(results)}")
    print(f"Failed requests: {error_count}/{len(results)}")
    print(f"Duplicate key errors: {duplicate_errors}/{len(results)}")

    if duplicate_errors > 0:
        print("\n✗ ISSUE REPRODUCED: Duplicate key violation detected!")
        for i, (status, response) in enumerate(results):
            if isinstance(response, str) and "duplicate key value" in response.lower():
                print(f"  Request {i + 1}: {response[:100]}...")
    else:
        print("\n✓ No duplicate key errors found (issue may be fixed)")

    return duplicate_errors > 0


if __name__ == "__main__":
    print("=== Token Upsert Issue Reproduction Test ===")
    print(f"Testing at: {datetime.now()}")
    print()

    # Test with different concurrency levels
    for num_threads in [3, 5, 10]:
        print(f"\n=== Testing with {num_threads} concurrent requests ===")
        issue_found = test_concurrent_requests(num_threads)

        if issue_found:
            print("Issue reproduced! Stopping tests.")
            break

        # Small delay between test batches
        time.sleep(1)

    print("\n=== Test completed ===")
