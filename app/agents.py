import json
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from app.models import EntrepreneurState, BusinessCategory

# --- LLM Setup ---
# Assuming 'llama3' is available in Ollama
llm = ChatOllama(model="llama3", format="json", temperature=0)

# --- Graph State ---
class AgentState(TypedDict):
    entrepreneur_id: str
    current_category: str
    profile_data: Dict[str, Any]
    conversation_history: List[Dict[str, str]]
    last_user_message: str
    generated_question: str
    is_category_complete: bool
    question_count: int

# --- Node 1: Context Retriever ---
async def context_retriever(state: AgentState):
    """
    Fetches context from the database. Ensures we only focus on the last 3 exchanges.
    """
    from app.database import get_last_n_exchanges
    
    # Get last 3 exchanges (6 messages)
    history = await get_last_n_exchanges(state['entrepreneur_id'], n=3)
    state["conversation_history"] = history
    return state

# --- Node 2: Business Analyst Agent ---
async def business_analyst(state: AgentState):
    """
    Analyzes the answer and updates the 'Entrepreneur Profile'.
    """
    category = state['current_category']
    profile = state['profile_data']
    last_msg = state['last_user_message']
    question_count = state.get("question_count", 0)
    
    prompt = f"""
    You are an expert Business Analyst for 'Empiiu', an incubator for Colombian entrepreneurs.
    
    Current State:
    - Business Category: {category}
    - Current Profile Data: {json.dumps(profile)}
    - Total Questions Asked so far: {question_count}
    
    User's Latest Answer: "{last_msg}"
    
    Task:
    1. Extract new key facts from the answer to update/enrich the profile data.
    2. Analyze information relevant to the current category:
       - IDEATION
       - MARKETING
       - FINANCIALS
       - SALES
       - CUSTOMER_SERVICES
       - LEGAL
    
    Output JSON format:
    {{
        "updated_profile_data": {{...}},
        "category_complete": false
    }}
    """
    
    response = await llm.ainvoke([SystemMessage(content=prompt)])
    try:
        content = json.loads(response.content)
    except:
        content = {"updated_profile_data": profile, "category_complete": False}
        
    return {
        "profile_data": content.get("updated_profile_data", profile),
        "is_category_complete": False # Logic handled by Question Generator based on count
    }

# --- Node 3: Question Generator Agent ---
async def question_generator(state: AgentState):
    """
    Generates the next logical question or the final profile.
    """
    category = state['current_category']
    profile = state['profile_data']
    question_count = state.get("question_count", 0)
    
    # Logic for Welcome Message (Question 0)
    if question_count == 0:
        return {
            "generated_question": "¡Hola! Bienvenido a Empiiu. Soy tu copiloto de negocios. Para crear tu ruta de crecimiento, necesito entender en qué punto estás. Empecemos por lo básico: ¿Cuál es tu nombre, cómo se llama tu emprendimiento y de qué trata?",
            "current_category": BusinessCategory.IDEATION,
            "question_count": 1
        }
    
    # Logic for Categories: 2 questions per category
    # 0 -> Welcome (handled above)
    # 1-2 -> Ideation
    # 3-4 -> Marketing
    # 5-6 -> Financials
    # 7-8 -> Sales
    # 9-10 -> Customer Services
    # 11-12 -> Legal
    # 13 -> Complete
    
    next_category = category
    
    if question_count == 1 or question_count == 2:
        next_category = BusinessCategory.IDEATION
    elif question_count == 3 or question_count == 4:
        next_category = BusinessCategory.MARKETING
    elif question_count == 5 or question_count == 6:
        next_category = BusinessCategory.FINANCIALS
    elif question_count == 7 or question_count == 8:
        next_category = BusinessCategory.SALES
    elif question_count == 9 or question_count == 10:
        next_category = BusinessCategory.CUSTOMER_SERVICES
    elif question_count == 11 or question_count == 12:
        next_category = BusinessCategory.LEGAL
    elif question_count == 13:
        # End of questions. Send intermediate closing message.
        return {
            "generated_question": "¡Felicidades! Hemos completado su perfil inicial. Envíe cualquier mensaje para recibir el resumen final.",
            "current_category": category, # Stay in previous category or move to COMPLETED? Let's stay or move to COMPLETED but not generate profile yet.
            # Actually, to generate profile in NEXT turn, we should set state to COMPLETED here?
            # Or use a special count logic.
            # Let's say at 13 we send this message. And output state has count 14.
            # Next turn (count 14) -> goes to COMPLETED block.
            "question_count": 14
        }
    elif question_count >= 14:
        next_category = BusinessCategory.COMPLETED
            
    # Profile generation prompt
    if next_category == BusinessCategory.COMPLETED:
        prompt = f"""
        Generate a comprehensive business profile summary in Spanish for this Colombian entrepreneur.
        Profile Data: {json.dumps(profile)}
        
        Format it clearly and start with: "¡Felicidades! Hemos completado su perfil inicial. Aquí está el resumen de su proyecto:"
        """
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        return {
            "generated_question": response.content if hasattr(response, 'content') else str(response),
            "current_category": BusinessCategory.COMPLETED
        }

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
    - Current Category: {next_category}
    - Current Profile Data: {json.dumps(profile)}

    **NEXT STATEMENT SELECTION:**
    Select the next uncovered "Diagnostic Statement" from the list below based on the Current Category.
    *Do not ask these as literal questions. Use the Statement to formulate a natural, conversational question in Spanish.*

    **PHASE 1: CONTEXT & IDENTITY (Ideation):**
    - Problem, solution, and target audience.

    **PHASE 2: MARKET & STRATEGY (Marketing):** 
    - Value Proposition (Differentiation).
    - Customer Segments.

    **PHASE 3: VIABILITY (Financials):**
    - Revenue model and costs.
    - Cost structure.

    **PHASE 4: SALES:**
    - Channels and sales strategy.

    **PHASE 5: CUSTOMER SERVICE:**
    - Relationships and retention.

    **PHASE 6: LEGAL:**
    - Formalization level (RUT, Chamber of Commerce).

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
    
    response = await llm.ainvoke([SystemMessage(content=prompt)])
    try:
        content = json.loads(response.content)
        question = content["question"]
    except:
        question = "¿Podría darme más detalles sobre su idea?"
        
    return {
        "generated_question": question,
        "current_category": next_category,
        "question_count": question_count + 1
    }

# --- Graph Construction ---
workflow = StateGraph(AgentState)
workflow.add_node("context_retriever", context_retriever)
workflow.add_node("business_analyst", business_analyst)
workflow.add_node("question_generator", question_generator)
workflow.set_entry_point("context_retriever")
workflow.add_edge("context_retriever", "business_analyst")
workflow.add_edge("business_analyst", "question_generator")
workflow.add_edge("question_generator", END)
app_graph = workflow.compile()

async def process_message(entrepreneur_id: str, message_text: str):
    from app.database import get_entrepreneur_state, save_entrepreneur_state, add_message, reset_entrepreneur
    import os
    
    # Check for /reset command
    if message_text.strip().lower() == "/reset":
        # Only allow in non-production environments
        if os.getenv("APP_ENV", "dev") != "production":
            await reset_entrepreneur(entrepreneur_id)
            return "El proceso de registro ha sido reiniciado. ¿Cuál es su idea de negocio?"

    # 1. Get State (Creates entrepreneur if not exists)
    db_state = await get_entrepreneur_state(entrepreneur_id)
    
    # 2. Save User Message
    await add_message(entrepreneur_id, "user", message_text)
    
    # 3. Graph Input
    input_state: AgentState = {
        "entrepreneur_id": entrepreneur_id,
        "current_category": db_state.current_category,
        "profile_data": db_state.profile_data,
        "conversation_history": [], # Will be populated by retriever node
        "last_user_message": message_text,
        "generated_question": "",
        "is_category_complete": False,
        "question_count": db_state.question_count
    }
    
    # 4. Run Graph
    print(f"--- Running Graph for {entrepreneur_id} (Category: {db_state.current_category}, Count: {db_state.question_count}) ---")
    final_state = await app_graph.ainvoke(input_state)
    print(f"--- Graph Finished. Next Category: {final_state['current_category']}, Next Count: {final_state.get('question_count')} ---")
    
    # 5. Save Assistant Message
    await add_message(entrepreneur_id, "assistant", final_state["generated_question"])
    
    # 6. Update State
    db_state.current_category = final_state["current_category"]
    db_state.profile_data = final_state["profile_data"]
    db_state.question_count = final_state.get("question_count", db_state.question_count)
    await save_entrepreneur_state(db_state)
    
    return final_state["generated_question"]
