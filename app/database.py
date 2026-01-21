import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import Column, String, JSON, DateTime, Integer, ForeignKey, select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://empiiu_user:empiiu_password@127.0.0.1:5433/empiiu_db")

Base = declarative_base()

class Entrepreneur(Base):
    __tablename__ = "entrepreneurs"
    id = Column(String, primary_key=True)  # phone number
    current_category = Column(String, default="IDEATION")
    profile_data = Column(JSON, default={})
    question_count = Column(Integer, default=0)
    messages = relationship("Message", back_populates="entrepreneur", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entrepreneur_id = Column(String, ForeignKey("entrepreneurs.id"))
    role = Column(String)  # 'user' or 'assistant'
    content = Column(String)
    status = Column(String, default="active")  # 'active' or 'archived'
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    entrepreneur = relationship("Entrepreneur", back_populates="messages")

engine = None
AsyncSessionLocal = None

def setup_database():
    global engine, AsyncSessionLocal
    if engine is None:
        engine = create_async_engine(DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, AsyncSessionLocal

async def init_db():
    eng, _ = setup_database()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def reset_entrepreneur(entrepreneur_id: str):
    from sqlalchemy import update
    _, session_factory = setup_database()
    async with session_factory() as session:
        # Mark all active messages as archived
        await session.execute(
            update(Message)
            .where(Message.entrepreneur_id == entrepreneur_id)
            .where(Message.status == "active")
            .values(status="archived")
        )
        
        # Reset entrepreneur state
        await session.execute(
            update(Entrepreneur)
            .where(Entrepreneur.id == entrepreneur_id)
            .values(current_category="IDEATION", profile_data={}, question_count=0)
        )
        await session.commit()

async def get_entrepreneur_state(entrepreneur_id: str):
    from app.models import EntrepreneurState, BusinessCategory
    _, session_factory = setup_database()
    async with session_factory() as session:
        result = await session.execute(select(Entrepreneur).where(Entrepreneur.id == entrepreneur_id))
        db_entrepreneur = result.scalars().first()
        
        if not db_entrepreneur:
            db_entrepreneur = Entrepreneur(id=entrepreneur_id, current_category="IDEATION", profile_data={}, question_count=0)
            session.add(db_entrepreneur)
            await session.commit()
            await session.refresh(db_entrepreneur)
        
        history_result = await session.execute(
            select(Message)
            .where(Message.entrepreneur_id == entrepreneur_id)
            .where(Message.status == "active")
            .order_by(Message.timestamp.asc())
        )
        history = [{"role": m.role, "content": m.content} for m in history_result.scalars().all()]
        
        return EntrepreneurState(
            entrepreneur_id=db_entrepreneur.id,
            current_category=BusinessCategory(db_entrepreneur.current_category),
            profile_data=db_entrepreneur.profile_data,
            conversation_history=history,
            question_count=db_entrepreneur.question_count
        )

async def save_entrepreneur_state(state):
    _, session_factory = setup_database()
    async with session_factory() as session:
        result = await session.execute(select(Entrepreneur).where(Entrepreneur.id == state.entrepreneur_id))
        db_entrepreneur = result.scalars().first()
        
        if db_entrepreneur:
            db_entrepreneur.current_category = state.current_category.value
            db_entrepreneur.profile_data = state.profile_data
            db_entrepreneur.question_count = state.question_count
            await session.commit()

async def add_message(entrepreneur_id: str, role: str, content: str, status: str = "active"):
    _, session_factory = setup_database()
    async with session_factory() as session:
        new_msg = Message(entrepreneur_id=entrepreneur_id, role=role, content=content, status=status)
        session.add(new_msg)
        await session.commit()

async def get_last_n_exchanges(entrepreneur_id: str, n: int = 3) -> List[Dict[str, str]]:
    _, session_factory = setup_database()
    async with session_factory() as session:
        result = await session.execute(
            select(Message)
            .where(Message.entrepreneur_id == entrepreneur_id)
            .where(Message.status == "active")
            .order_by(desc(Message.timestamp), desc(Message.id))
            .limit(n * 2)
        )
        messages = result.scalars().all()
        return [{"role": m.role, "content": m.content} for m in reversed(messages)]
