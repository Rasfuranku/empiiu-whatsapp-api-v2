from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends
from app.schemas.models import WhatsAppWebhookPayload
from app.services.agent_service import process_agent_message
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
VERIFY_TOKEN = "meatyhamhock"

# Helper for background task that needs a fresh DB session
async def worker_v1(phone: str, text: str):
    # We need a new session here because background tasks run after the request session closes
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        try:
            response = await process_agent_message(phone, text, session)
            # Send WhatsApp (mock)
            logger.info(f"Sending V1 response to {phone}: {response}")
        except Exception as e:
            logger.error(f"Error in V1 worker: {e}")

@router.get("/whatsapp/webhook")
async def verify_webhook_v1(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/whatsapp/webhook")
async def webhook_handler_v1(
    payload: WhatsAppWebhookPayload, 
    background_tasks: BackgroundTasks
):
    try:
        for entry in payload.entry:
            for change in entry.changes:
                if change.value.messages:
                    message = change.value.messages[0]
                    if message.type == "text":
                        text = message.text.get("body", "")
                        phone = message.from_number
                        background_tasks.add_task(worker_v1, phone, text)
    except Exception as e:
        logger.error(f"Error: {e}")
    return {"status": "ok"}
