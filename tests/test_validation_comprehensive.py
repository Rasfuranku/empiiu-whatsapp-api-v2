import pytest
import pytest_asyncio
import os
import json
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, text
from app.agents import process_message
from app.database import setup_database, Base, Entrepreneur, Message
from app.models import BusinessCategory

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    import app.database
    app.database.engine = None
    app.database.AsyncSessionLocal = None
    eng, _ = setup_database()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await eng.dispose()

@pytest.mark.asyncio
async def test_comprehensive_validation():
    """
    Validates:
    - Correct functionality for the onboarding flow
    - Correct processing of /reset command
    - Generation of final profile after questions
    - Correct storage of all exchanges in DB
    """
    ent_id = "573000000000"
    os.environ["APP_ENV"] = "dev"

    # 1. Validate /reset on empty state
    response = await process_message(ent_id, "/reset")
    assert "reiniciado" in response
    
    # 2. Mock LLM for the flow
    # We'll simulate a few steps of the flow
    mock_responses = {
        "analyst": [
            {"updated_profile_data": {"idea": "Coffee shop"}, "category_complete": False}, # Ans 1
            {"updated_profile_data": {"idea": "Coffee shop", "loc": "Bogota"}, "category_complete": True}, # Ans 2
        ],
        "generator": [
            "¿Cuál es su idea?", # Initial (not used here as we start with Ans 1)
            "¿Dónde estará ubicada?", # After Ans 1
            "¡Felicidades! Hemos completado su perfil inicial. Envíe cualquier mensaje para recibir el resumen final." # After Ans 2 (Force complete)
        ]
    }
    
    analyst_idx = 0
    generator_idx = 1 # Start from 1 because the first question is usually assumed or handled elsewhere, but process_message calls the graph which generates the NEXT question.
    
    async def mocked_llm_invoke(messages):
        nonlocal analyst_idx, generator_idx
        from langchain_core.messages import AIMessage
        prompt = messages[0].content
        
        if "Business Analyst" in prompt:
            res = mock_responses["analyst"][analyst_idx]
            analyst_idx += 1
            return AIMessage(content=json.dumps(res))
        elif "business profile summary" in prompt:
            return AIMessage(content="RESUMEN FINAL: Coffee shop in Bogota")
        else:
            # Question Generator
            res = {"question": mock_responses["generator"][generator_idx]}
            generator_idx += 1
            return AIMessage(content=json.dumps(res))

    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = mocked_llm_invoke

    with patch("app.agents.llm", mock_llm):
        # Step 1: User sends first answer
        q1 = await process_message(ent_id, "Quiero abrir una cafetería")
        assert q1 == "¿Dónde estará ubicada?"
        
        # Validate DB after Step 1
        _, Session = setup_database()
        async with Session() as session:
            result = await session.execute(select(Message).where(Message.entrepreneur_id == ent_id).order_by(Message.id))
            msgs = result.scalars().all()
            assert len(msgs) == 2
            assert msgs[0].role == "user"
            assert msgs[0].content == "Quiero abrir una cafetería"
            assert msgs[1].role == "assistant"
            assert msgs[1].content == "¿Dónde estará ubicada?"
            
            ent_res = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            ent = ent_res.scalars().first()
            assert ent.profile_data == {"idea": "Coffee shop"}
            assert ent.question_count == 1

        # Step 2: User sends second answer
        # We'll manually set question_count to 15 to trigger the closing message
        async with Session() as session:
            await session.execute(
                text("UPDATE entrepreneurs SET question_count = 15 WHERE id = :id"),
                {"id": ent_id}
            )
            await session.commit()
            
        q2 = await process_message(ent_id, "En Bogotá")
        assert "Felicidades" in q2
        
        # Validate DB after Step 2
        async with Session() as session:
            ent_res = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            ent = ent_res.scalars().first()
            assert ent.question_count == 16

        # Step 3: Final message to get profile
        profile = await process_message(ent_id, "Listo")
        assert "RESUMEN FINAL" in profile
        
        # Validate final state
        async with Session() as session:
            ent_res = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            ent = ent_res.scalars().first()
            assert ent.current_category == BusinessCategory.COMPLETED
            
            # Total messages: 2 (Step 1) + 2 (Step 2) + 2 (Step 3) = 6
            result = await session.execute(select(Message).where(Message.entrepreneur_id == ent_id).where(Message.status == "active"))
            msgs = result.scalars().all()
            assert len(msgs) == 6

        # Step 4: Validate /reset actually clears active messages
        await process_message(ent_id, "/reset")
        async with Session() as session:
            # Check entrepreneur state
            ent_res = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            ent = ent_res.scalars().first()
            assert ent.current_category == BusinessCategory.IDEATION
            assert ent.question_count == 0
            assert ent.profile_data == {}
            
            # Check messages are archived
            result = await session.execute(select(Message).where(Message.entrepreneur_id == ent_id).where(Message.status == "active"))
            active_msgs = result.scalars().all()
            assert len(active_msgs) == 0
            
            result = await session.execute(select(Message).where(Message.entrepreneur_id == ent_id).where(Message.status == "archived"))
            archived_msgs = result.scalars().all()
            assert len(archived_msgs) == 6
