# Empiiu Onboarding Agent

Agentic onboarding system for Colombian entrepreneurs called "Empiiu" using FastAPI, LangGraph, LangChain, and Ollama.

## System Components
- **FastAPI Gateway**: Exposes V1 (LangGraph) and V2 (LangChain) endpoints.
- **Database**: PostgreSQL database to store entrepreneur profiles and conversation history.
- **V1 (LangGraph)**: Original implementation using LangGraph nodes.
- **V2 (LangChain)**: New implementation using `ConversationChain`, memory, and support for session reset.
- **WhatsApp Integration**: Utility to send messages via Meta's Cloud API (Mocked).

## Prerequisites
- [uv](https://github.com/astral-sh/uv) installed (or standard `pip`).
- [Ollama](https://ollama.com/) installed and running with `llama3`.
- [Docker](https://www.docker.com/) and Docker Compose (for the database).

## Setup

1. **Install dependencies**:
   ```bash
   uv sync
   # OR
   pip install -r requirements.txt
   ```

2. **Run Ollama**:
   Ensure you have the `llama3` model pulled:
   ```bash
   ollama pull llama3
   ```

3. **Database Setup**:
   Start the PostgreSQL database:
   ```bash
   docker-compose up -d
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory:
   ```env
   DATABASE_URL=postgresql+asyncpg://empiiu_user:empiiu_password@127.0.0.1:5433/empiiu_db
   WHATSAPP_VERIFY_TOKEN=meatyhamhock
   ```

5. **Apply Migrations**:
   Initialize the database schema using Alembic:
   ```bash
   uv run alembic upgrade head
   ```

## Running the Application

Start the FastAPI server:
```bash
uv run uvicorn app.main:app --reload
```

## API Endpoints

- **V1 Webhook**: `POST /api/v1/whatsapp/webhook`
  - Uses `app/services/agent_service.py` (LangGraph).
- **V2 Webhook**: `POST /api/v2/whatsapp/webhook`
  - Uses `app/services/chat_service.py` (LangChain).
  - Supports `/reset` command to archive conversation and start fresh.

## Reset Command (V2)

In the V2 chat (WhatsApp), sending the message `/reset` will archive the current entrepreneur session and start a new one. Old data is preserved in the database with `is_active=False`.

## Running Tests

Run the test suite using `pytest`:
```bash
PYTHONPATH=. uv run pytest
```

## Testing the Webhook

You can simulate an incoming WhatsApp message using `curl`.

**Test V2 Endpoint:**
```bash
curl -X POST http://localhost:8000/api/v2/whatsapp/webhook \
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
                                    "body": "Hola, quiero iniciar."
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

To test reset, change body to `"/reset"`.
```