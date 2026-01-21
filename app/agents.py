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
    
    # Force category completion if we reached the limit
    if question_count >= 15:
        return {
            "is_category_complete": True,
            "current_category": BusinessCategory.COMPLETED
        }

    prompt = f"""
    You are an expert Business Analyst for 'Empiiu', an incubator for Colombian entrepreneurs.
    
    Current State:
    - Business Category: {category}
    - Current Profile Data: {json.dumps(profile)}
    - Total Questions Asked so far: {question_count}
    
    User's Latest Answer: "{last_msg}"
    
    Task:
    1. Extract new key facts from the answer to update/enrich the profile data.
    2. Determine if we have enough information to mark the current category ({category}) as COMPLETE.
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
    
    response = await llm.ainvoke([SystemMessage(content=prompt)])
    try:
        content = json.loads(response.content)
    except:
        content = {"updated_profile_data": profile, "category_complete": False}
        
    return {
        "profile_data": content.get("updated_profile_data", profile),
        "is_category_complete": content.get("category_complete", False)
    }

# --- Node 3: Question Generator Agent ---
async def question_generator(state: AgentState):
    """
    Generates the next logical question or the final profile.
    """
    category = state['current_category']
    profile = state['profile_data']
    is_complete = state['is_category_complete']
    question_count = state.get("question_count", 0)
    
    next_category = category
    if question_count >= 16:
        next_category = BusinessCategory.COMPLETED
    elif question_count == 15:
        # This is the 16th iteration (Answer 15)
        # We return a closing message and increment to 16
        return {
            "generated_question": "¡Felicidades! Hemos completado su perfil inicial. Envíe cualquier mensaje para recibir el resumen final.",
            "current_category": category,
            "question_count": 16
        }
    elif is_complete:
        if category == BusinessCategory.IDEATION:
            next_category = BusinessCategory.MARKET
        elif category == BusinessCategory.MARKET:
            next_category = BusinessCategory.FINANCIALS
        elif category == BusinessCategory.FINANCIALS:
            next_category = BusinessCategory.TEAM
        elif category == BusinessCategory.TEAM:
            next_category = BusinessCategory.COMPLETED
            
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
    You are an empathetic mentor for Colombian entrepreneurs.
    Total questions asked so far: {question_count}
    
    Context:
    - Current Category: {next_category}
    - Profile Data: {json.dumps(profile)}
    
    Task:
    Generate EXACTLY ONE follow-up question in Spanish. Localize it to Colombia.
    
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
    from app.database import get_entrepreneur_state, save_entrepreneur_state, add_message
    
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
    final_state = await app_graph.ainvoke(input_state)
    
    # 5. Save Assistant Message
    await add_message(entrepreneur_id, "assistant", final_state["generated_question"])
    
    # 6. Update State
    db_state.current_category = final_state["current_category"]
    db_state.profile_data = final_state["profile_data"]
    db_state.question_count = final_state.get("question_count", db_state.question_count)
    await save_entrepreneur_state(db_state)
    
    return final_state["generated_question"]
