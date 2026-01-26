import os

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://empiiu_user:empiiu_password@127.0.0.1:5433/empiiu_db")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "meatyhamhock")
    
settings = Settings()
