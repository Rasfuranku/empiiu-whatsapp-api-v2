# Empiiu Onboarding Agent

Agentic onboarding system for Colombian entrepreneurs called "Empiiu" using FastAPI, LangGraph, and Ollama.

## System Components
- **FastAPI Gateway**: Receives messages and pushes them to background workers.
- **Worker (LangGraph)**:
    - **Context Retriever**: Fetches the last 3 exchanges from the mock DB.
    - **Business Analyst**: Updates the "Entrepreneur Profile" and checks category completion.
    - **Question Generator**: Generates the next follow-up question in Spanish.
- **WhatsApp Integration**: Utility to send messages via Meta's Cloud API (Mocked).

## Prerequisites
- [uv](https://github.com/astral-sh/uv) installed.
- [Ollama](https://ollama.com/) installed and running with `llama3`.

## Setup

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Run Ollama**:
   Ensure you have the `llama3` model pulled:
   ```bash
   ollama pull llama3
   ```

## Running the Application

Start the FastAPI server:
```bash
uv run uvicorn app.main:app --reload
```

## Running Tests

Run the test suite using `pytest`:
```bash
PYTHONPATH=. uv run pytest
```

## Testing the Webhook

You can simulate an incoming WhatsApp message using `curl`:

```bash
curl -X POST http://localhost:8000/api/v1/whatsapp/webhook \
     -H "Content-Type: application/json" \
     -d '{
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
                                    "name": "Entrepreneur Name"
                                },
                                "wa_id": "573001234567"
                            }
                        ],
                        "messages": [
                            {
                                "from": "573001234567",
                                "id": "wamid.test_id",
                                "timestamp": "1706726890",
                                "text": {
                                    "body": "Hola, tengo una idea para una app de café."
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
}'
```

Check the server logs to see the LangGraph nodes processing the message and generating a Spanish response.
