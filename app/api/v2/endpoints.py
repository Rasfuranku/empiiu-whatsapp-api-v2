from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from app.schemas.models import WhatsAppWebhookPayload
from app.services.chat_service import process_chat_message
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
VERIFY_TOKEN = "meatyhamhock"

async def worker_v2(phone: str, text: str):
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        try:
            response = await process_chat_message(phone, text, session)
            logger.info(f"Sending V2 response to {phone}: {response}")
        except Exception as e:
            logger.error(f"Error in V2 worker: {e}")

@router.get("/whatsapp/webhook")
async def verify_webhook_v2(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/whatsapp/webhook")
async def webhook_handler_v2(
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
                        background_tasks.add_task(worker_v2, phone, text)
    except Exception as e:
        logger.error(f"Error: {e}")
    return {"status": "ok"}
