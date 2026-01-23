import pytest
import pytest_asyncio
import os
from unittest.mock import AsyncMock, patch
from app.agents import process_message
from app.database import init_db, Entrepreneur, Message, Base, setup_database
from app.models import BusinessCategory
from sqlalchemy import select, delete

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
async def test_full_onboarding_flow_with_db_and_reset():
    ent_id = "573009999999"
    
    # Mock LLM responses
    responses = []
    for i in range(1, 16):
        responses.append({
            "updated_profile_data": {"info": f"data_{i}"},
            "category_complete": False,
            "question": f"Question {i}?"
        })
    
    # 16th iteration response
    responses.append({
        "updated_profile_data": {"completed_step": True},
        "category_complete": True,
        "question": "¡Felicidades! Hemos completado su perfil inicial."
    })
    
    # Final profile response
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
            idx = generator_calls
            if idx >= len(responses): idx = len(responses) - 1
            res_data = responses[idx]
            generator_calls += 1
            return AIMessage(content=json.dumps({
                "question": res_data["question"]
            }))

    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = mocked_llm_invoke

    with patch("app.agents.llm", mock_llm):
        # 1. Test /reset at the beginning (should work)
        os.environ["APP_ENV"] = "dev"
        reset_response = await process_message(ent_id, "/reset")
        assert "reiniciado" in reset_response

        # 2. Iterate through onboarding
        for i in range(1, 16):
            question = await process_message(ent_id, f"Answer {i}")
            assert f"Question {i}?" in question
            
            # Validate DB storage after each step
            _, Session = setup_database()
            async with Session() as session:
                result = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
                db_ent = result.scalars().first()
                assert db_ent.question_count == i
                
                msg_result = await session.execute(
                    select(Message)
                    .where(Message.entrepreneur_id == ent_id)
                    .where(Message.status == "active")
                    .order_by(Message.id.desc())
                    .limit(2)
                )
                msgs = msg_result.scalars().all()
                assert len(msgs) == 2
                assert msgs[0].role == "assistant"
                assert msgs[1].role == "user"
                assert msgs[1].content == f"Answer {i}"
        
        # 3. 16th message (closing)
        closing_msg = await process_message(ent_id, "Final answer")
        assert "Felicidades" in closing_msg
        
        # 4. Request profile
        profile_msg = await process_message(ent_id, "Get profile")
        assert "Resumen Final" in profile_msg

        # Final DB validation
        async with Session() as session:
            result = await session.execute(select(Entrepreneur).where(Entrepreneur.id == ent_id))
            db_ent = result.scalars().first()
            assert db_ent.current_category == "COMPLETED"
            
            # Check all exchanges stored (15 steps * 2 + 1 reset response? No, reset response is not stored in DB as a message in the current implementation of process_message if it returns early)
            # Actually process_message for /reset:
            # if message_text.strip().lower() == "/reset":
            #     await reset_entrepreneur(entrepreneur_id)
            #     return "..."
            # It doesn't save the /reset message or the response to DB.
            
            # Let's check how many messages: 
            # 15 iterations * 2 = 30
            # + closing iteration * 2 = 32
            # + profile iteration * 2 = 34
            msg_result = await session.execute(select(Message).where(Message.entrepreneur_id == ent_id).where(Message.status == "active"))
            msgs = msg_result.scalars().all()
            assert len(msgs) == 34
