import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_webhook_text_message():
    # Standard text message payload
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "123456789",
                                "phone_number_id": "123456789"
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "Test User"
                                    },
                                    "wa_id": "1234567890"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "1234567890",
                                    "id": "wamid.HBgLM...",
                                    "timestamp": "1706726890",
                                    "text": {
                                        "body": "Hola"
                                    },
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_webhook_status_update():
    # Status update payload (e.g. sent, delivered, read)
    # This often causes 422 if the schema expects 'messages' or 'contacts' rigidly
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "123456789",
                                "phone_number_id": "123456789"
                            },
                            "statuses": [
                                {
                                    "id": "wamid.HBgLM...",
                                    "status": "sent",
                                    "timestamp": "1706726891",
                                    "recipient_id": "1234567890"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    response = client.post("/api/v1/whatsapp/webhook", json=payload)
    # We expect 200 even for statuses, though we might ignore them in logic
    # But schema validation must pass
    assert response.status_code == 200
