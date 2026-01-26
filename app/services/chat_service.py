import json
import logging
from typing import Dict, Any, List
from langchain_classic.chains import ConversationChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_ollama import ChatOllama
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)
from langchain_core.messages import SystemMessage as LangChainSystemMessage

from app.db.crud import (
    get_entrepreneur,
    create_entrepreneur,
    add_message,
    get_history,
    update_entrepreneur_state,
    archive_entrepreneur
)
from app.schemas.models import BusinessCategory
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
llm = ChatOllama(model="llama3", format="json", temperature=0)

async def handle_reset_command(phone_number: str, session: AsyncSession):
    await archive_entrepreneur(session, phone_number)
    return "¡Conversación reiniciada! He guardado tu progreso anterior. ¿Cómo puedo ayudarte ahora?"

async def analyze_business_profile(
    current_category: str,
    profile: Dict[str, Any],
    last_msg: str,
    question_count: int
) -> Dict[str, Any]:
    if question_count >= 15:
        return {
            "profile_data": profile,
            "is_category_complete": True,
            "current_category": BusinessCategory.COMPLETED
        }

    prompt = f"""
    You are an expert Business Analyst for 'Empiiu', an incubator for Colombian entrepreneurs.
    
    Current State:
    - Business Category: {current_category}
    - Current Profile Data: {json.dumps(profile)}
    - Total Questions Asked so far: {question_count}
    
    User's Latest Answer: "{last_msg}"
    
    Task:
    1. Extract new key facts from the answer to update/enrich the profile data.
    2. Determine if we have enough information to mark the current category ({current_category}) as COMPLETE.
       - IDEATION: Problem, solution, and target audience.
       - MARKET: Competitors and market size.
       - FINANCIALS: Revenue model and costs.
       - TEAM: Founders and roles.
    
    Output JSON format:
    {{
        "updated_profile_data": {{...}},
        "category_complete": true/false
    }}
    """
    
    try:
        response = await llm.ainvoke([LangChainSystemMessage(content=prompt)])
        content = json.loads(response.content)
    except Exception as e:
        logger.error(f"Error in analyze_business_profile: {e}")
        content = {"updated_profile_data": profile, "category_complete": False}
        
    return {
        "profile_data": content.get("updated_profile_data", profile),
        "is_category_complete": content.get("category_complete", False)
    }

def get_system_prompt_content(
    category: str,
    profile: Dict[str, Any],
    question_count: int
) -> str:
    if category == BusinessCategory.COMPLETED:
        prompt = f"""
        Generate a comprehensive business profile summary in Spanish for this Colombian entrepreneur.
        Profile Data: {json.dumps(profile)}
        
        Format it clearly and start with: "¡Felicidades! Hemos completado su perfil inicial. Aquí está el resumen de su proyecto:"
        """
        return prompt

    prompt = f"""
    **SYSTEM ROLE & PERSONA:**
    You are **"Empiiu"**, an expert business mentor and analyst for Colombian entrepreneurs.
    - **Objective:** Conduct a conversational diagnosis to create a "Baseline Profile" and determine the entrepreneur's Priority Learning Path.
    - **Framework:** You use the *Business Model Canvas (BMC)* + *Knowledge Areas* (Finance, Marketing, Sales, Legal, Customer Service) to evaluate maturity.
    - **Tone:** Professional yet empathetic, encouraging, and concise (optimized for WhatsApp). You use natural Colombian Spanish language (e.g., "el negocio", "temas de plata", "arrancar", "camellar") but maintain analytical seriousness.

    **LANGUAGE PROTOCOL (STRICT):**
    1. **Internal Logic:** Process instructions in English.
    2. **User Interaction:** MUST be 100% in Colombian Spanish.
    3. **Question Generation:** MUST be in Spanish.

    **Context:**
    - Total questions asked so far: {question_count}
    - Current Category: {category}
    - Current Profile Data: {json.dumps(profile)}

    **NEXT STATEMENT SELECTION:**
    Select the next uncovered "Diagnostic Statement" from the list below.
    *Do not ask these as literal questions. Use the Statement to formulate a natural, conversational question in Spanish.*

    **PHASE 1: CONTEXT & IDENTITY (The Foundation):**
    1. **IDENTITY (Context):** Confirm Name and Business Name.
    2. **MATURITY (Context):** Determine time in market and current stage (Idea vs. Selling vs. Growing).
    3. **CRITICAL PAIN (Context):** Identify the main "headache" (Sales, Disorder, Legal, Time).

    **PHASE 2: MARKET & STRATEGY (Marketing/Sales):** 
    4. **VALUE PROPOSITION (BMC - Marketing):** Evaluate if they know *why* customers choose them (Differentiation).
    5. **CUSTOMER SEGMENTS (BMC - Marketing):** Verify if they have a clear "Avatar" or sell to "everyone".
    6. **CHANNELS (BMC - Sales):** How do customers arrive? (Social media, physical, referrals).

    **PHASE 3: VIABILITY & ORDER (Finance/Legal):**
    7. **REVENUE STREAMS (BMC - Sales):** Dependence on a single product vs. diversification.
    8. **COST STRUCTURE (BMC - Finance):** **CRITICAL.** Do they mix personal/business money ("bolsillos mezclados")? Do they keep records?
    9. **LEGAL STATUS (Context - Legal):** Formalization level (RUT, Chamber of Commerce) vs. Informal.

    **PHASE 4: OPERATION & SERVICE (Ops/CS):**
    10. **RELATIONSHIPS (BMC - Service):** What do they do to make customers buy *again*? (Retention).
    11. **KEY ACTIVITIES/RESOURCES (BMC - Ops):** Operational bottlenecks. What consumes their time?
    12. **PARTNERSHIPS (BMC - Ops):** Support network (Suppliers/Partners) vs. "Lone Wolf".

    **Requirements:**
    - Output ONLY the text of the question in Spanish.
    - NO preambles.
    - NO multiple questions. Wait for the user.
    - If the user expresses a "pain" (e.g., "I'm bad at math"), show empathy before asking the next question.
    
    Output JSON format:
    {{
        "question": "string"
    }}
    """
    return prompt

async def process_chat_message(phone_number: str, message_text: str, session: AsyncSession) -> str:
    # 0. Check for Reset Command
    if message_text.strip().lower() == "/reset":
        return await handle_reset_command(phone_number, session)
        
    # 1. Get or Create Entrepreneur
    entrepreneur = await get_entrepreneur(session, phone_number)
    if not entrepreneur:
        entrepreneur = await create_entrepreneur(session, phone_number)
        
    # 2. Save User Message
    await add_message(session, entrepreneur.id, "user", message_text)
    
    # 3. Analyze Profile
    analysis_result = await analyze_business_profile(
        current_category=entrepreneur.current_category,
        profile=entrepreneur.profile_data,
        last_msg=message_text,
        question_count=entrepreneur.question_count
    )
    
    updated_profile = analysis_result["profile_data"]
    is_complete = analysis_result["is_category_complete"]
    current_category_enum = BusinessCategory(entrepreneur.current_category)
    
    next_category_enum = current_category_enum
    
    if entrepreneur.question_count >= 15:
        next_category_enum = BusinessCategory.COMPLETED
    elif is_complete:
        categories = list(BusinessCategory)
        try:
            current_idx = categories.index(current_category_enum)
            if current_idx + 1 < len(categories):
                next_category_enum = categories[current_idx + 1]
        except ValueError:
            pass

    # 4. Prepare Memory
    history_records = await get_history(session, entrepreneur.id, limit=10)
    memory = ConversationBufferMemory(return_messages=True)
    
    for msg in history_records:
        if msg.role == "user":
            memory.chat_memory.add_user_message(msg.content)
        else:
            memory.chat_memory.add_ai_message(msg.content)

    # 5. Generate Response
    system_prompt_text = get_system_prompt_content(
        category=next_category_enum.value,
        profile=updated_profile,
        question_count=entrepreneur.question_count
    )
    
    prompt_template = ChatPromptTemplate.from_messages([
        LangChainSystemMessage(content=system_prompt_text),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{input}")
    ])
    
    chain = ConversationChain(
        llm=llm,
        memory=memory,
        prompt=prompt_template
    )
    
    try:
        response_json_str = await chain.apredict(input=message_text)
        try:
            response_content = json.loads(response_json_str)
            if isinstance(response_content, dict):
                 response_text = response_content.get("question", response_content.get("generated_question", str(response_content)))
            else:
                 response_text = str(response_content)
        except json.JSONDecodeError:
            response_text = response_json_str
            
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        response_text = "¿Podría darme más detalles?"

    if entrepreneur.question_count == 15:
         response_text = "¡Felicidades! Hemos completado su perfil inicial. Envíe cualquier mensaje para recibir el resumen final."
         new_count = 16
    elif next_category_enum == BusinessCategory.COMPLETED and entrepreneur.current_category != "COMPLETED":
         new_count = entrepreneur.question_count
    else:
         new_count = entrepreneur.question_count + 1

    # 6. Save Assistant Message
    await add_message(session, entrepreneur.id, "assistant", response_text)
    
    # 7. Update State
    await update_entrepreneur_state(
        session, 
        entrepreneur.id, 
        next_category_enum.value, 
        updated_profile, 
        new_count
    )
    
    return response_text
