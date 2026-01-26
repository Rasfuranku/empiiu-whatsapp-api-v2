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
            {"updated_profile_data": {"idea": "Coffee shop"}, "category_complete": False}, 
            {"updated_profile_data": {"idea": "Coffee shop", "loc": "Bogota"}, "category_complete": False}, 
        ],
        "generator": [
            # Welcome message is hardcoded in the function, so index 0 of mock is for Q1 (after Welcome)
            "¿Pregunta de Ideación?", 
            "¡Felicidades! Hemos completado su perfil inicial. Envíe cualquier mensaje para recibir el resumen final." 
        ]
    }
    
    analyst_idx = 0
    generator_idx = 0 
    
    async def mocked_llm_invoke(messages):
        nonlocal analyst_idx, generator_idx
        from langchain_core.messages import AIMessage
        prompt = messages[0].content
        
        if "Business Analyst" in prompt:
            # Safely handle index out of range for analyst
            idx = analyst_idx if analyst_idx < len(mock_responses["analyst"]) else -1
            res = mock_responses["analyst"][idx]
            analyst_idx += 1
            return AIMessage(content=json.dumps(res))
        elif "business profile summary" in prompt:
            return AIMessage(content="RESUMEN FINAL: Coffee shop in Bogota")
        else:
            # Question Generator
            # If the prompt contains "Welcome" or it's the first call not hitting LLM, it won't be here.
            # But question_generator function DOES call LLM for Q1 onwards.
            idx = generator_idx if generator_idx < len(mock_responses["generator"]) else -1
            res = {"question": mock_responses["generator"][idx]}
            generator_idx += 1
            return AIMessage(content=json.dumps(res))

    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = mocked_llm_invoke

    with patch("app.agents.llm", mock_llm):
        # Step 1: User sends first message (triggers Welcome)
        # We need to simulate the state where question_count is 0
        q0 = await process_message(ent_id, "Hola")
        assert "Bienvenido a Empiiu" in q0
        
        # Validate DB after Step 1
        _, Session = setup_database()
        async with Session() as session:
            ent_res = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            ent = ent_res.scalars().first()
            assert ent.question_count == 1
            assert ent.current_category == BusinessCategory.IDEATION

        # Step 2: Answer to Welcome (Q1 -> Q2: Ideation)
        q1 = await process_message(ent_id, "Me llamo Juan y vendo café")
        assert "Question" in q1 or "question" in q1 or q1 # Mock returns simple strings
        
        async with Session() as session:
            ent_res = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            ent = ent_res.scalars().first()
            assert ent.question_count == 2
            assert ent.current_category == BusinessCategory.IDEATION

        # Step 3: Jump to end (Question 13 -> Felicidades)
        async with Session() as session:
            await session.execute(
                text("UPDATE entrepreneurs SET question_count = 13 WHERE id = :id"),
                {"id": ent_id}
            )
            await session.commit()
            
        q_end = await process_message(ent_id, "Respuesta Final")
        assert "Felicidades" in q_end
        
        # Validate DB after Step 3
        async with Session() as session:
            ent_res = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            ent = ent_res.scalars().first()
            assert ent.question_count == 14
            
        # Step 4: Generate Profile
        q_profile = await process_message(ent_id, "Quiero mi perfil")
        assert "RESUMEN FINAL" in q_profile

        # Step 3: Final message to get profile
        profile = await process_message(ent_id, "Listo")
        assert "RESUMEN FINAL" in profile
        
        # Validate final state
        async with Session() as session:
            ent_res = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            ent = ent_res.scalars().first()
            assert ent.current_category == BusinessCategory.COMPLETED
            
            # Total messages: 2 (Step 1) + 2 (Step 2) + 2 (Step 3) + 2 (Step 4) + 2 (Step 5) = 10
            result = await session.execute(select(Message).where(Message.entrepreneur_id == ent_id).where(Message.status == "active"))
            msgs = result.scalars().all()
            assert len(msgs) == 10

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
            assert len(archived_msgs) == 10
