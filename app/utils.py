import httpx
import os
import logging

logger = logging.getLogger(__name__)

# Environment variables for Meta API
# In production, these should be loaded from .env
META_API_URL = os.getenv("META_API_URL", "https://graph.facebook.com/v19.0")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "800134303188808")
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")

async def send_whatsapp_message(to_number: str, message_text: str):
    """
    Sends a message via Meta's WhatsApp Cloud API.
    """
    url = f"{META_API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text},
    }

    try:
        # In a real scenario, we would make the actual request.
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(url, json=payload, headers=headers)
        #     response.raise_for_status()
        
        # For this prototype/mock, we just log it.
        logger.info(f"--- WhatsApp Message Sent to {to_number} ---")
        logger.info(f"Content: {message_text}")
        logger.info("---------------------------------------------")
        
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
