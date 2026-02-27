# agent/chat_graph.py

import os
import re
import json
import traceback
from typing import Dict, Any
from langgraph.graph import StateGraph
from langchain_core.tools import Tool
from cerebras.cloud.sdk import Cerebras
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0
from agent.shortcut_handler import contains_blocked_keyword, match_shortcut
from agent.rag_tool import answer_from_faq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import create_structured_chat_agent, AgentExecutor
from agent.prompt_config import get_agent_prompt
from agent.json_memory import get_memory

CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY_OPPI_2")
GEMINI_API_KEY = os.getenv("GEMINI_API")

# Defining states
State = Dict[str, Any]


# =========================
# Tool Registry
# =========================

def build_all_tools():
    return {
        "BACK_OFFICE_FAQRetriever": Tool(
            name="BACK_OFFICE_FAQRetriever",
            func=answer_from_faq,
            description=(
                "Use this tool whenever the user asks questions about Oppi Wallet, its features, or troubleshooting steps. "
                "This includes account setup, security & recovery, crypto transactions, swaps/exchanges, Oppi cards & virtual cards, "
                "rewards/referrals, travel bookings, app usage, and general platform-related inquiries. "
                "The tool retrieves official answers directly from the Oppi Wallet FAQ and user guide PDF, ensuring accurate and consistent responses."
            )
        ),
    }


# =========================
# Turkish Translation Helper
# =========================

def ensure_turkish(text: str) -> str:
    print("-------------------ENSURE TURKISH CALLED---------------------")
    client = Cerebras(api_key=CEREBRAS_API_KEY)
    system_prompt = (
        "You are a professional Turkish language translator and spelling and grammar checker. "
        "If the provided text is in Turkish, check and correct any spelling or grammar mistakes. "
        "If the provided text is in English, translate it into Turkish while keeping the tone friendly and conversational. "
        "Preserve the original tone and meaning, but adapt expressions and sentence structure for clarity, warmth, and fluency in Turkish. "
        "Always return only the final, polished Turkish text without extra explanations."
    )
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        model="gpt-oss-120b",
        temperature=0.1,
        top_p=1
    )
    return response.choices[0].message.content.strip()


# =========================
# Graph Nodes
# =========================

def shortcut_node(state: State) -> State:
    """Handle static responses and blocked keywords."""
    print("-----------------SHORTCUT NODE CALLED-----------------------")
    message = state.get("message", "")

    if contains_blocked_keyword(message):
        print("-----------------CHECKING BLOCKED KEYWORD----------------------")
        state["reply"] = "I'm just your support buddy, Eva — here to help with anything about OppiWallet."
        state["__end__"] = True
        return state

    shortcut_response = match_shortcut(message)
    if shortcut_response:
        print("-------------REPLYING MATCH SHORTCUT-----------------")
        state["reply"] = shortcut_response
        state["__end__"] = True
        return state

    return state


def tool_selection_node(state: State) -> State:
    """Load all available tools into state."""
    print("--------------TOOL SELECTION---------------------")
    all_tools = build_all_tools()
    state["allowed_tools"] = list(all_tools.values())
    return state


def executor_node(state: State) -> State:
    """Execute agent with selected tools."""
    print("---------------EXECUTOR NODE-----------------------")
    tools = state.get("allowed_tools", [])
    message = state.get("message", "")
    session_id = state.get("session_id")
    username = state.get("username")

    full_message = f"(username: {username}) {message}" if username else message

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GEMINI_API_KEY,
        temperature=0.2,
        convert_system_message_to_human=True,
        response_mime_type="application/json",
        streaming=False
    )

    prompt = get_agent_prompt().partial(
        tools="\n".join([tool.description for tool in tools]),
        tool_names=", ".join([tool.name for tool in tools]),
        extra_rules=""
    )

    agent = create_structured_chat_agent(llm=llm, tools=tools, prompt=prompt)
    memory = get_memory(session_id)

    executor = AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
        max_iterations=10,
        stream_runnable=False,
    )

    try:
        result = executor.invoke({"input": full_message})
        raw_response = result.get("output", str(result))

        if "Agent stopped due to iteration limit or time limit" in raw_response:
            print("-------ERROR: Agent stopped due to iteration limit or time limit")
            state["reply"] = "I have reviewed all accessible data but was unable to find relevant information. Please let me know if you'd like me to proceed with an alternative method."
            return state

        json_match = re.search(r"\{(?:.|\n)*\}", raw_response)

        if json_match:
            json_blob = json_match.group(0)
            try:
                parsed = json.loads(json_blob)
                response = parsed.get("action_input", raw_response)
            except json.JSONDecodeError:
                print("⚠️ Failed to parse JSON inside markdown block")
                response = raw_response
        else:
            response = re.sub(r"\s*\([^)]*\)", "", raw_response).strip()

        state["reply"] = response

    except Exception as e:
        print("❌ FULL TRACEBACK:")
        traceback.print_exc()

        if hasattr(e, "__dict__"):
            print("🔧 Exception details:", e.__dict__)

        error_msg = str(e)
        print(f"⚠️ Error occurred: {error_msg}")

        if "503" in error_msg and "model is overloaded" in error_msg.lower():
            state["reply"] = "Quota Reached. Try after a couple of minutes: The model is overloaded."
        else:
            state["reply"] = "I have reviewed all accessible data but was unable to find relevant information."

    return state


def translator_node(state: State) -> State:
    """Translate reply to Turkish if user_lang is 'tr'."""
    print("-------------------CHECKING TURKISH---------------------")
    try:
        reply = state.get("reply", "")
        user_lang = state.get("user_lang", "").lower()
        print("-----------------", user_lang)

        detected_lang = None
        if reply:
            try:
                detected_lang = detect(reply)
            except Exception:
                detected_lang = None

        if user_lang == "tr" or detected_lang == "tr":
            if reply:
                state["reply"] = ensure_turkish(reply)

    except Exception as e:
        print(f"⚠️ Turkish conversion/cleaning error: {e}")

    return state


# =========================
# Graph Construction
# =========================

def build_graph():
    graph = StateGraph(State)

    graph.add_node("shortcut", shortcut_node)
    graph.add_node("tool_selection", tool_selection_node)
    graph.add_node("executor", executor_node)
    graph.add_node("translator", translator_node)

    graph.set_entry_point("shortcut")
    graph.set_finish_point("translator")

    nodes = ["shortcut", "tool_selection", "executor", "translator"]

    def next_node_lambda(current_node):
        def fn(state):
            if state.get("__end__", False):
                return nodes[-1]
            idx = nodes.index(current_node)
            if idx + 1 < len(nodes):
                return nodes[idx + 1]
            return nodes[-1]
        return fn

    for idx, node in enumerate(nodes[:-1]):
        following_nodes = nodes[idx + 1:]
        path_map = {n: n for n in following_nodes}
        graph.add_conditional_edges(
            node,
            next_node_lambda(node),
            path_map=path_map
        )

    return graph.compile()


# =========================
# Entry Point
# =========================

chat_graph = build_graph()


async def process_user_message(
    message: str,
    session_id: str,
    username: str = None,
    user_lang: str = "En",
    context: str = "customer_support",
) -> dict:
    """Main entry point. Accepts only: message, session_id, username, user_lang, context."""
    state: State = {
        "session_id": session_id,
        "message": message,
        "username": username,
        "user_lang": user_lang,
        "context": context,
    }

    result = await chat_graph.ainvoke(state)

    return {
        "reply": result.get("reply", "Sorry, I couldn't process your request."),
        "mode": "bot"
    }
