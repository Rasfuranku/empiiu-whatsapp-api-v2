import pytest
import pytest_asyncio
import os
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base, Entrepreneur, Message, DATABASE_URL, add_message, get_last_n_exchanges, get_entrepreneur_state, setup_database
from app.agents import process_message
from unittest.mock import AsyncMock, patch

@pytest_asyncio.fixture
async def session():
    # Use the app's setup_database but ensure it's fresh for tests
    # Actually, setup_database uses global variables.
    import app.database
    app.database.engine = None
    app.database.AsyncSessionLocal = None
    eng, Session = setup_database()
    
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    await eng.dispose()

@pytest.mark.asyncio
async def test_reset_archives_and_resets_state(session):
    ent_id = "573001112222"
    await get_entrepreneur_state(ent_id)
    
    await add_message(ent_id, "user", "Idea 1")
    await add_message(ent_id, "assistant", "Q1?")
    
    os.environ["APP_ENV"] = "dev"
    response = await process_message(ent_id, "/reset")
    assert "reiniciado" in response
    
    new_history = await get_last_n_exchanges(ent_id, n=3)
    assert len(new_history) == 0
    
    # Verify in DB
    _, Session = setup_database()
    async with Session() as sess:
        result = await sess.execute(select(Message).where(Message.entrepreneur_id == ent_id))
        msgs = result.scalars().all()
        assert len(msgs) == 2
        for m in msgs:
            assert m.status == "archived"

@pytest.mark.asyncio
async def test_reset_not_triggered_in_production(session):
    ent_id = "573003334444"
    await get_entrepreneur_state(ent_id)
    await add_message(ent_id, "user", "Prod data")
    
    os.environ["APP_ENV"] = "production"
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value.content = '{"question": "Q?", "updated_profile_data": {}}'
    
    with patch("app.agents.llm", mock_llm):
        response = await process_message(ent_id, "/reset")
        assert "reiniciado" not in response
        
    history = await get_last_n_exchanges(ent_id, n=1)
    assert len(history) > 0

@pytest.mark.asyncio
async def test_active_messages_isolation(session):
    ent_id = "573005556666"
    await get_entrepreneur_state(ent_id)
    await add_message(ent_id, "user", "Old archived", status="archived")
    await add_message(ent_id, "user", "Current active")
    
    history = await get_last_n_exchanges(ent_id, n=5)
    assert len(history) == 1
    assert history[0]["content"] == "Current active"
