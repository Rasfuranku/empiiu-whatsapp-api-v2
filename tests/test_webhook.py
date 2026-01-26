import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_webhook_text_message_v1():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123", "phone_number_id": "123"},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": "1234567890"}],
                    "messages": [{
                        "from": "1234567890",
                        "id": "msg1",
                        "timestamp": "1706726890",
                        "text": {"body": "Hola"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_webhook_text_message_v2():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123", "phone_number_id": "123"},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": "1234567890"}],
                    "messages": [{
                        "from": "1234567890",
                        "id": "msg2",
                        "timestamp": "1706726890",
                        "text": {"body": "Hola"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    
    response = client.post("/api/v2/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_webhook_verify_v1():
    response = client.get("/api/v1/whatsapp/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "meatyhamhock",
        "hub.challenge": "12345"
    })
    assert response.status_code == 200
    assert response.text == "12345"

def test_webhook_verify_v2():
    response = client.get("/api/v2/whatsapp/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "meatyhamhock",
        "hub.challenge": "67890"
    })
    assert response.status_code == 200
    assert response.text == "67890"