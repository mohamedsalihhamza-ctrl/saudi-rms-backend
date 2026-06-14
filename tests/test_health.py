import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_register_user(client):
    response = await client.post(
        "/api/v1/users/register",
        json={
            "email": "test@example.com",
            "password": "password123",
            "full_name": "Test User",
            "organization_name": "Test Hotel Co",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_duplicate_email(client):
    await client.post(
        "/api/v1/users/register",
        json={
            "email": "dup@example.com",
            "password": "password123",
            "full_name": "User One",
            "organization_name": "Org",
        },
    )
    response = await client.post(
        "/api/v1/users/register",
        json={
            "email": "dup@example.com",
            "password": "password456",
            "full_name": "User Two",
            "organization_name": "Org",
        },
    )
    assert response.status_code == 400
