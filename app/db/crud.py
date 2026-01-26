from sqlalchemy.future import select
from sqlalchemy import desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Entrepreneur, Message
from app.schemas.models import EntrepreneurState, BusinessCategory

async def get_entrepreneur(session: AsyncSession, phone_number: str) -> Entrepreneur:
    result = await session.execute(
        select(Entrepreneur)
        .where(Entrepreneur.phone_number == phone_number)
        .where(Entrepreneur.is_active == True)
    )
    return result.scalars().first()

async def create_entrepreneur(session: AsyncSession, phone_number: str) -> Entrepreneur:
    entrepreneur = Entrepreneur(
        phone_number=phone_number,
        current_category="IDEATION",
        profile_data={},
        question_count=0,
        is_active=True
    )
    session.add(entrepreneur)
    await session.commit()
    await session.refresh(entrepreneur)
    return entrepreneur

async def archive_entrepreneur(session: AsyncSession, phone_number: str):
    # Set all records for this phone to inactive (should only be one active)
    await session.execute(
        update(Entrepreneur)
        .where(Entrepreneur.phone_number == phone_number)
        .where(Entrepreneur.is_active == True)
        .values(is_active=False)
    )
    await session.commit()

async def add_message(session: AsyncSession, entrepreneur_id: int, role: str, content: str):
    msg = Message(entrepreneur_id=entrepreneur_id, role=role, content=content)
    session.add(msg)
    await session.commit()

async def get_history(session: AsyncSession, entrepreneur_id: int, limit: int = 6):
    result = await session.execute(
        select(Message)
        .where(Message.entrepreneur_id == entrepreneur_id)
        .order_by(desc(Message.timestamp), desc(Message.id))
        .limit(limit)
    )
    messages = result.scalars().all()
    return list(reversed(messages))

async def update_entrepreneur_state(session: AsyncSession, entrepreneur_id: int, category: str, profile: dict, count: int):
    await session.execute(
        update(Entrepreneur)
        .where(Entrepreneur.id == entrepreneur_id)
        .values(current_category=category, profile_data=profile, question_count=count)
    )
    await session.commit()
