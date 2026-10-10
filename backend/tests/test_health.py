from fastapi.testclient import TestClient
from main import app
from app.database import get_db
import uuid 
client=TestClient(app)

def test_health():
    response=client.get("/health")
    
    assert response.status_code==200
    assert response.json() == {"status":"ok"}
    
def test_proxy_unknown_service():
    response = client.get(
        "/api/v1/proxy/unknown/hello",
        headers={"X-API-Key": "invalid-key"}
    )

    assert response.status_code == 401
    
def test_register_response():
    username = f"pytest_{uuid.uuid4().hex[:8]}"
    
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "TestPass123!"
        }
    )

    assert response.status_code == 201
    assert response.json() == {
        "message": "User successfully registered",
        "username": username
    }
def test_login():
    username=f"pytest_{uuid.uuid4().hex[:8]}"
    password="TestPass123!"
    
    register_response=client.post(
        "/api/v1/auth/register",
        json={
            "username":username,
            "password":password
        }
    )
    assert register_response.status_code==201
    
    login_response=client.post(
        "/api/v1/auth/login",
        json={
            "username":username,
            "password":password
        }
    )
    assert login_response.status_code==200
    assert login_response.json()["access_token"]
    
    
    access_token = login_response.json()["access_token"]

    key_response = client.post(
        "/api/v1/keys/generate",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    assert key_response.status_code == 200
    assert key_response.json()["api_key"]
    assert key_response.json()["status"] == "active"