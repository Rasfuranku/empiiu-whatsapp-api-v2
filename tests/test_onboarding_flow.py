import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from app.services.agent_service import process_agent_message
from app.db.models import Entrepreneur, Message, Base
from app.schemas.models import BusinessCategory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
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
async def test_full_onboarding_flow(session):
    phone = "573009999999"
    
    responses = []
    # 1-15: Questions
    for i in range(1, 16):
        responses.append({
            "updated_profile_data": {"info": f"data_{i}"},
            "category_complete": False,
            "question": f"Question {i}?"
        })
    
    # 16: Closing
    responses.append({
        "updated_profile_data": {"completed_step": True},
        "category_complete": True,
        "question": "¡Felicidades!"
    })
    
    # 17: Profile
    responses.append({
        "updated_profile_data": {"profile_built": True},
        "category_complete": True,
        "question": "Resumen Final: [RESUMEN]"
    })

    analyst_calls = 0
    generator_calls = 0
    
    async def mocked_llm_invoke(messages):
        nonlocal analyst_calls, generator_calls
        import json
        from langchain_core.messages import AIMessage
        
        prompt_content = messages[0].content
        
        if "Business Analyst" in prompt_content:
            idx = analyst_calls
            if idx >= len(responses): idx = len(responses) - 1
            res_data = responses[idx]
            analyst_calls += 1
            return AIMessage(content=json.dumps({
                "updated_profile_data": res_data["updated_profile_data"],
                "category_complete": res_data["category_complete"]
            }))
        elif "business profile summary" in prompt_content:
            return AIMessage(content=responses[-1]["question"])
        else:
            # Question Generator
            idx = generator_calls
            if idx >= len(responses): idx = len(responses) - 1
            res_data = responses[idx]
            generator_calls += 1
            return AIMessage(content=json.dumps({
                "question": res_data["question"]
            }))

    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = mocked_llm_invoke

    # Need to patch the llm in app.services.agent_service
    with patch("app.services.agent_service.llm", mock_llm):
        # Run 15 iterations of questions
        for i in range(1, 16):
            question = await process_agent_message(phone, f"Answer {i}", session)
            assert f"Question {i}?" in question
            
        # 16th iteration: Closing Message
        closing_msg = await process_agent_message(phone, "Final answer", session)
        assert "Felicidades" in closing_msg
        
        # 17th iteration: Profile
        profile_msg = await process_agent_message(phone, "Get profile", session)
        assert "Resumen Final" in profile_msg

        # Final validation in DB
        result = await session.execute(select(Entrepreneur).where(Entrepreneur.phone_number == phone))
        db_ent = result.scalars().first()
        assert db_ent.current_category == "COMPLETED"
        
        # Check message count (17 user + 17 assistant = 34)
        msg_result = await session.execute(select(Message).where(Message.entrepreneur_id == db_ent.id))
        msgs = msg_result.scalars().all()
        assert len(msgs) == 34
