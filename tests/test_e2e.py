import pytest
import requests
import time
import subprocess
import os

# kubectl port-forward svc/api-gateway 30080:8080

API_URL = os.getenv("API_URL", "http://localhost:30080")


def wait_for_status(booking_id, target_status, timeout=15):
    start = time.time()
    last_status = None
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{API_URL}/trips/{booking_id}")
            if resp.status_code == 200:
                data = resp.json()
                last_status = data["status"]
                if last_status == target_status:
                    return data
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    pytest.fail(
        f"Timeout waiting for status {target_status}. Last status: {last_status}"
    )


def test_happy_path():
    """Role 1: The Employee (The Happy Path)"""
    resp = requests.post(
        f"{API_URL}/trips", json={"destination": "Seattle", "travelerId": "emp-123"}
    )
    assert resp.status_code == 200
    booking_id = resp.json()["bookingId"]

    # Wait for Routing -> AwaitingApproval
    data = wait_for_status(booking_id, "AwaitingApproval")
    assert data["current_route"] is not None

    # Approve
    resp = requests.post(f"{API_URL}/trips/{booking_id}/approve")
    assert resp.status_code == 200

    # Wait for completion (could be Completed or Compensating)
    start = time.time()
    final_status = None
    last_status = None
    while time.time() - start < 15:
        resp = requests.get(f"{API_URL}/trips/{booking_id}")
        if resp.status_code == 200:
            st = resp.json()["status"]
            last_status = st
            if st in ["Completed", "Compensating"]:
                final_status = st
                break
        time.sleep(1)

    assert final_status in ["Completed", "Compensating"], (
        f"Did not complete. Last status: {last_status}"
    )


def test_picky_employee_loop():
    """Role 2: The Picky Employee (The Workflow Loop)"""
    resp = requests.post(
        f"{API_URL}/trips", json={"destination": "New York", "travelerId": "emp-456"}
    )
    assert resp.status_code == 200
    booking_id = resp.json()["bookingId"]

    data = wait_for_status(booking_id, "AwaitingApproval")
    initial_route = data["current_route"]["routeId"]

    # Reject
    resp = requests.post(f"{API_URL}/trips/{booking_id}/reject")
    assert resp.status_code == 200

    # Wait for it to come back to AwaitingApproval
    data = wait_for_status(booking_id, "AwaitingApproval")
    new_route = data["current_route"]["routeId"]

    assert new_route != initial_route
    assert len(data["rejected_routes"]) >= 1
    assert initial_route in data["rejected_routes"]


def test_infrastructure_chaos():
    """Role 3: The Infrastructure Chaos Engineer (Resilience Testing)"""
    resp = requests.post(
        f"{API_URL}/trips", json={"destination": "Chaos", "travelerId": "emp-999"}
    )
    assert resp.status_code == 200
    booking_id = resp.json()["bookingId"]

    wait_for_status(booking_id, "AwaitingApproval")

    # Scale down trip-booking-manager to simulate a crash
    subprocess.run(
        ["kubectl", "scale", "deploy", "trip-booking-manager", "--replicas=0"],
        check=True,
    )
    time.sleep(5)

    # Scale back up to verify it recovers and can continue the process
    subprocess.run(
        ["kubectl", "scale", "deploy", "trip-booking-manager", "--replicas=1"],
        check=True,
    )

    # Wait for service to become responsive again via the gateway proxying it
    start = time.time()
    while time.time() - start < 30:
        try:
            r = requests.get(f"{API_URL}/trips/{booking_id}")
            if r.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)

    # Approve should work now
    resp = requests.post(f"{API_URL}/trips/{booking_id}/approve")
    assert resp.status_code == 200

    final_status = None
    start = time.time()
    while time.time() - start < 20:
        try:
            r = requests.get(f"{API_URL}/trips/{booking_id}")
            if r.status_code == 200:
                st = r.json()["status"]
                if st in ["Completed", "Compensating"]:
                    final_status = st
                    break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)

    assert final_status in ["Completed", "Compensating"], (
        "System did not recover from crash to finish the booking."
    )
