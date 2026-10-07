"""
test_auth.py — Tests for authentication, authorization, and RBAC.
"""

import pytest


def test_login_admin_success(client):
    """Admin can login with correct credentials and receive a JWT."""
    response = client.post(
        "/api/auth/token",
        data={"username": "test_admin", "password": "Admin@123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "ADMIN"
    assert data["token_type"] == "bearer"


def test_login_manager_success(client):
    """Manager can login with correct credentials."""
    response = client.post(
        "/api/auth/token",
        data={"username": "test_manager", "password": "Manager@123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "WAREHOUSE_MANAGER"


def test_login_wrong_password(client):
    """Login fails with wrong password."""
    response = client.post(
        "/api/auth/token",
        data={"username": "test_admin", "password": "WrongPassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


def test_login_unknown_user(client):
    """Login fails for non-existent user."""
    response = client.post(
        "/api/auth/token",
        data={"username": "nobody", "password": "anything"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


def test_get_me_authenticated(client, admin_headers):
    """Authenticated user can retrieve their own profile."""
    response = client.get("/api/auth/me", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "test_admin"
    assert data["role"] == "ADMIN"


def test_get_me_unauthenticated(client):
    """Unauthenticated request to /api/auth/me returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_invalid_token(client):
    """Tampered token is rejected with 401."""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer fake.jwt.token"},
    )
    assert response.status_code == 401


def test_admin_can_list_users(client, admin_headers):
    """Admin can list all users."""
    response = client.get("/api/auth/users", headers=admin_headers)
    assert response.status_code == 200
    users = response.json()
    usernames = [u["username"] for u in users]
    assert "test_admin" in usernames
    assert "test_manager" in usernames


def test_manager_cannot_list_users(client, manager_headers):
    """Warehouse manager cannot access admin-only user list."""
    response = client.get("/api/auth/users", headers=manager_headers)
    assert response.status_code == 403
    assert "Admin role required" in response.json()["detail"]


def test_manager_cannot_create_user(client, manager_headers):
    """Warehouse manager cannot create new users (admin-only)."""
    response = client.post(
        "/api/auth/users",
        json={"username": "hacker", "email": "h@h.com", "password": "Hacker@123"},
        headers=manager_headers,
    )
    assert response.status_code == 403


def test_health_check_public(client):
    """Health check endpoint is publicly accessible (no auth)."""
    response = client.get("/api/monitoring/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
