from fastapi.testclient import TestClient
from main import app
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