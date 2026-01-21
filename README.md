# Empiiu Onboarding Agent

Agentic onboarding system for Colombian entrepreneurs called "Empiiu" using FastAPI, LangGraph, and Ollama.

## System Components
- **FastAPI Gateway**: Receives messages and pushes them to background workers.
- **Worker (LangGraph)**:
    - **Context Retriever**: Fetches the last 3 exchanges from the PostgreSQL DB.
    - **Business Analyst**: Updates the "Entrepreneur Profile" and checks category completion.
    - **Question Generator**: Generates the next follow-up question in Spanish.
- **PostgreSQL**: Stores entrepreneur state, profiles, and conversation history.

## Prerequisites
- [uv](https://github.com/astral-sh/uv) installed.
- [Docker](https://www.docker.com/) installed.
- [Ollama](https://ollama.com/) installed and running with `llama3`.

## Setup

1. **Start the Database**:
   ```bash
   docker compose up -d
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Run Ollama**:
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

## Database Management

The database runs in a Docker container. You can inspect the data directly using `psql`.

### View All Entrepreneurs
```bash
docker exec -it onboarding_v2-db-1 psql -U empiiu_user -d empiiu_db -c "SELECT * FROM entrepreneurs;"
```

### View Message History
```bash
docker exec -it onboarding_v2-db-1 psql -U empiiu_user -d empiiu_db -c "SELECT entrepreneur_id, role, content, status FROM messages ORDER BY timestamp ASC;"
```

### Enter Interactive Shell
```bash
docker exec -it onboarding_v2-db-1 psql -U empiiu_user -d empiiu_db
```

## Developer Commands

### `/reset`
Restarts the onboarding process for the current user.
- **Behavior**: Marks all previous messages as `archived`, clears the `profile_data`, and resets `question_count` to 0.
- **Environment**: Only available when `APP_ENV` is set to `dev` (default). It is disabled in `production`.
- **Usage**: Send `/reset` as a message body to the webhook.

## Testing the Webhook (cURL)

```bash
curl -X POST http://localhost:8000/api/v1/whatsapp/webhook \
     -H "Content-Type: application/json" \
     -d 
'{'
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
                        "contacts": [{"profile": {"name": "Test User"}, "wa_id": "573001234567"}],
                        "messages": [
                            {
                                "from": "573001234567",
                                "id": "wamid.test_id",
                                "timestamp": "1706726890",
                                "text": {"body": "/reset"},
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