from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.models import WhatsAppWebhookPayload
from app.agents import process_message
from app.utils import send_whatsapp_message
from app.database import init_db
import logging
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Empiiu Onboarding Agent")

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    await init_db()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        body = await request.json()
        logger.error(f"Validation Error Body: {json.dumps(body, indent=2)}")
    except Exception:
        logger.error("Validation Error: Could not parse body")
    
    logger.error(f"Validation Error Details: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": body},
    )

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "meatyhamhock")

async def worker_process_message(entrepreneur_id: str, message_text: str, from_number: str):
    """
    Background worker that runs the LangGraph logic and sends the response.
    """
    logger.info(f"Worker processing message from {entrepreneur_id}")
    try:
        # Run the Brain (LangGraph)
        response_text = await process_message(entrepreneur_id, message_text)
        
        # Send response via WhatsApp
        await send_whatsapp_message(from_number, response_text)
        
    except Exception as e:
        logger.error(f"Error in worker process: {e}")

@app.get("/api/v1/whatsapp/webhook")
async def verify_webhook(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge")
):
    """
    Meta Webhook Verification.
    """
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified successfully.")
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/api/v1/whatsapp/webhook")
async def webhook_handler(payload: WhatsAppWebhookPayload, background_tasks: BackgroundTasks):
    """
    Receives WhatsApp messages.
    """
    # Log the payload for debugging
    # logger.info(f"Payload received: {payload}")

    try:
        # Extract relevant info from the complex WhatsApp payload
        for entry in payload.entry:
            for change in entry.changes:
                if change.value.messages:
                    message = change.value.messages[0]
                    from_number = message.from_number
                    
                    # We use the phone number as the entrepreneur_id for simplicity
                    entrepreneur_id = from_number
                    
                    if message.type == "text":
                        text_body = message.text.get("body", "")
                        
                        # Add task to background worker
                        background_tasks.add_task(
                            worker_process_message,
                            entrepreneur_id,
                            text_body,
                            from_number
                        )
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # We still return 200 to Meta to prevent retries
        return {"status": "error", "message": str(e)}

    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Empiiu Onboarding System Running"}
