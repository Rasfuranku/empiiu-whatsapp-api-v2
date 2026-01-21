import pytest
import pytest_asyncio
import asyncio
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.database import Base, Entrepreneur, Message, DATABASE_URL
from app.models import BusinessCategory, EntrepreneurState
import datetime

# For tests, we use a fresh engine per test
@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def session(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session

@pytest.mark.asyncio
async def test_db_connection(session):
    result = await session.execute(select(1))
    assert result.scalar() == 1

@pytest.mark.asyncio
async def test_entrepreneur_creation(session):
    ent_id = "test_user_123"
    # Manual implementation of the logic to test insertion
    db_ent = Entrepreneur(id=ent_id, current_category="IDEATION", profile_data={})
    session.add(db_ent)
    await session.commit()
    
    result = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
    found = result.scalars().first()
    assert found.id == ent_id

@pytest.mark.asyncio
async def test_message_insertion(session):
    ent_id = "test_msg_user"
    session.add(Entrepreneur(id=ent_id))
    await session.commit()
    
    msg1 = Message(entrepreneur_id=ent_id, role="user", content="Hello")
    msg2 = Message(entrepreneur_id=ent_id, role="assistant", content="Hi")
    session.add_all([msg1, msg2])
    await session.commit()
    
    result = await session.execute(select(Message).where(Message.entrepreneur_id == ent_id))
    msgs = result.scalars().all()
    assert len(msgs) == 2

@pytest.mark.asyncio
async def test_get_last_3_exchanges_logic(session):
    ent_id = "test_history"
    session.add(Entrepreneur(id=ent_id))
    await session.commit()
    
    for i in range(5):
        session.add(Message(entrepreneur_id=ent_id, role="user", content=f"U{i}"))
        session.add(Message(entrepreneur_id=ent_id, role="assistant", content=f"A{i}"))
    await session.commit()
    
    # Logic from app/database.py
    result = await session.execute(
        select(Message)
        .where(Message.entrepreneur_id == ent_id)
        .order_by(desc(Message.timestamp))
        .limit(6)
    )
    messages = result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in reversed(messages)]
    
    assert len(history) == 6
    assert history[0]["content"] == "U2"
    assert history[-1]["content"] == "A4"