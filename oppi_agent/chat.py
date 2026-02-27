# agent/chat.py

import os
import re
import json
import traceback
from langchain.agents import Tool, AgentExecutor, create_structured_chat_agent
from langchain_openai import ChatOpenAI
from langdetect import detect, DetectorFactory
DetectorFactory.seed = 0
from agent.rag_tool import answer_from_faq
from agent.shortcut_handler import match_shortcut, contains_blocked_keyword
from agent.prompt_config import get_agent_prompt
from agent.json_memory import get_memory
from dotenv import load_dotenv
from cerebras.cloud.sdk import Cerebras

load_dotenv()

API_KEY = os.getenv("CEREBRAS_API_KEY_3")
CEREBRAS_API_KEY = os.environ.get("CEREBAS_API_KEY_2")


# =========================
# Tool Registry
# =========================

def build_tools():
    return [
        Tool(
            name="BACK_OFFICE_FAQRetriever",
            func=answer_from_faq,
            description=(
                "Use this tool whenever the user asks questions about Oppi Wallet, its features, or troubleshooting steps. "
                "This includes account setup, security & recovery, crypto transactions, swaps/exchanges, Oppi cards & virtual cards, "
                "rewards/referrals, travel bookings, app usage, and general platform-related inquiries. "
                "The tool retrieves official answers directly from the Oppi Wallet FAQ and user guide PDF, ensuring accurate and consistent responses."
            )
        ),
    ]


# =========================
# Turkish Translation Helper
# =========================

def ensure_turkish(text: str) -> str:
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
# Main Entry Point
# =========================

async def process_user_message(
    message: str,
    session_id: str,
    username: str = None,
    user_lang: str = "En",
    context: str = "customer_support",
) -> str:
    """Pure RAG-based support handler. Accepts: message, session_id, username, user_lang, context."""

    # Blocked keywords check
    if contains_blocked_keyword(message):
        return "I'm just your support buddy, Eva — here to help with anything about OppiWallet."

    # Static shortcut responses (greetings, timepass, etc.)
    shortcut_response = match_shortcut(message)
    if shortcut_response:
        return shortcut_response

    # Build tools and LLM
    tools = build_tools()
    full_message = f"(username: {username}) {message}" if username else message

    llm = ChatOpenAI(
        base_url="https://api.cerebras.ai/v1",
        openai_api_key=API_KEY,
        model="llama-4-scout-17b-16e-instruct",
        temperature=0.2,
        model_kwargs={
            "response_format": {"type": "json_object"}
        }
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
        max_iterations=5,
    )

    try:
        result = executor.invoke({"input": full_message})
        raw_response = result.get("output", str(result))

        if "Agent stopped due to iteration limit or time limit" in raw_response:
            return "Sorry, I can't process your request right now. Please try again later."

        json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)

        if json_match:
            json_blob = json_match.group(1)
            try:
                parsed = json.loads(json_blob)
                response = parsed.get("action_input", raw_response)
            except json.JSONDecodeError:
                print("⚠️ Failed to parse JSON inside markdown block")
                response = raw_response
        else:
            response = re.sub(r"\s*\([^)]*\)", "", raw_response).strip()

    except Exception as e:
        print("❌ FULL TRACEBACK:")
        traceback.print_exc()
        if hasattr(e, "__dict__"):
            print("🔧 Exception details:", e.__dict__)
        print(f"⚠️ Error occurred: {str(e)}")
        return "Sorry, I can't process your request right now. Please try again later."

    # Turkish translation if needed
    if user_lang.lower() == "tr":
        try:
            response = ensure_turkish(response)
        except Exception as e:
            print(f"⚠️ Turkish conversion/cleaning error: {e}")

    return response
