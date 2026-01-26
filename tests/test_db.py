import pytest
import pytest_asyncio
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Entrepreneur, Message
from app.schemas.models import BusinessCategory, EntrepreneurState
import os

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def session(engine):
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session

@pytest.mark.asyncio
async def test_db_connection(session):
    result = await session.execute(select(1))
    assert result.scalar() == 1

@pytest.mark.asyncio
async def test_entrepreneur_creation(session):
    phone = "test_user_123"
    db_ent = Entrepreneur(phone_number=phone, current_category="IDEATION", profile_data={})
    session.add(db_ent)
    await session.commit()
    
    result = await session.execute(select(Entrepreneur).where(Entrepreneur.phone_number == phone))
    found = result.scalars().first()
    assert found.phone_number == phone
    assert isinstance(found.id, int)

@pytest.mark.asyncio
async def test_message_insertion(session):
    phone = "test_msg_user"
    ent = Entrepreneur(phone_number=phone)
    session.add(ent)
    await session.commit()
    await session.refresh(ent)
    
    msg1 = Message(entrepreneur_id=ent.id, role="user", content="Hello")
    msg2 = Message(entrepreneur_id=ent.id, role="assistant", content="Hi")
    session.add_all([msg1, msg2])
    await session.commit()
    
    result = await session.execute(select(Message).where(Message.entrepreneur_id == ent.id))
    msgs = result.scalars().all()
    assert len(msgs) == 2

@pytest.mark.asyncio
async def test_get_last_3_exchanges_logic(session):
    phone = "test_history"
    ent = Entrepreneur(phone_number=phone)
    session.add(ent)
    await session.commit()
    await session.refresh(ent)
    
    for i in range(5):
        session.add(Message(entrepreneur_id=ent.id, role="user", content=f"U{i}"))
        session.add(Message(entrepreneur_id=ent.id, role="assistant", content=f"A{i}"))
    await session.commit()
    
    result = await session.execute(
        select(Message)
        .where(Message.entrepreneur_id == ent.id)
        .order_by(desc(Message.id))
        .limit(6)
    )
    messages = result.scalars().all()
    history = [{"role": m.role, "content": m.content} for m in reversed(messages)]
    
    assert len(history) == 6
    assert history[0]["content"] == "U2"
    assert history[-1]["content"] == "A4"
