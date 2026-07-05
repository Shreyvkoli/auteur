"""
Smoke test: verify critical API endpoints respond correctly.
Run: python -m pytest tests/test_smoke.py -v
"""

import httpx

HOST = "http://localhost:8000"
BASE = f"{HOST}/api"


def test_root():
    r = httpx.get(f"{HOST}/")
    assert r.status_code == 200


def test_health():
    r = httpx.get(f"{HOST}/health")
    assert r.status_code == 200


def test_auth_signup_dev():
    r = httpx.post(f"{BASE}/auth/signup", json={
        "email": "test@example.com",
        "password": "password123",
        "name": "Test User",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"


def test_auth_signin_dev():
    r = httpx.post(f"{BASE}/auth/signin", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data


def test_video_list():
    r = httpx.get(f"{BASE}/video/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_style_profiles():
    r = httpx.get(f"{BASE}/style/profiles")
    assert r.status_code == 200


def test_jobs():
    r = httpx.get(f"{BASE}/jobs/")
    assert r.status_code == 200


def test_docs():
    r = httpx.get(f"{HOST}/docs", follow_redirects=True)
    assert r.status_code == 200
