import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.main import app
from app.services.chat_service import handle_reset_command
from app.db.models import Entrepreneur

# Use a test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_reset_command(client, db_session):
    phone = "573001234567"
    
    # 1. Create an entrepreneur state
    from app.db.crud import create_entrepreneur, update_entrepreneur_state
    ent = await create_entrepreneur(db_session, phone)
    await update_entrepreneur_state(db_session, ent.id, "MARKETING", {"foo": "bar"}, 5)
    
    # Verify created
    from sqlalchemy import select
    res = await db_session.execute(select(Entrepreneur).where(Entrepreneur.phone_number == phone).where(Entrepreneur.is_active == True))
    current = res.scalars().first()
    assert current is not None
    assert current.current_category == "MARKETING"
    
    # 2. Call Reset via Service (Direct test of logic)
    await handle_reset_command(phone, db_session)
    
    # Verify archived
    res = await db_session.execute(select(Entrepreneur).where(Entrepreneur.phone_number == phone).where(Entrepreneur.is_active == True))
    current = res.scalars().first()
    assert current is None # Should be no active record
    
    res = await db_session.execute(select(Entrepreneur).where(Entrepreneur.phone_number == phone).where(Entrepreneur.is_active == False))
    archived = res.scalars().first()
    assert archived is not None
    
    # 3. Test via Webhook (Reset Command)
    # Simulate /reset command payload
    reset_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "123", "phone_number_id": "123"},
                    "contacts": [{"profile": {"name": "Test"}, "wa_id": phone}],
                                            "messages": [{
                                                "from": phone,
                                                "id": "msg2",
                                                "type": "text",
                                                "text": {"body": "/reset"},
                                                "timestamp": "1706726890"
                                            }]                },
                "field": "messages"
            }]
        }]
    }
    
    # We post to V2 webhook
    response = await client.post("/api/v2/whatsapp/webhook", json=reset_payload)
    assert response.status_code == 200
    
    # Since webhook runs background task, checking DB immediately might be flaky without waiting.
    # But we already tested the service logic above. 
    # The webhook test confirms the endpoint accepts the payload.