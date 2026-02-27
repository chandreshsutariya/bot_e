from langchain_classic.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
import os

class SafeConversationBufferMemory(ConversationBufferMemory):
    def save_context(self, inputs, outputs):
        input_val = inputs.get("input")
        if isinstance(input_val, list):
            input_val = " ".join(m.content for m in input_val if isinstance(m, HumanMessage))

        output_val = outputs.get("output")
        if isinstance(output_val, list):
            output_val = " ".join(m.content for m in output_val if isinstance(m, AIMessage))

        return super().save_context({"input": input_val}, {"output": output_val})

MEMORY_DIR = "memory_sessions"
os.makedirs(MEMORY_DIR, exist_ok=True)

def get_memory(session_id: str):
    history = FileChatMessageHistory(file_path=os.path.join(MEMORY_DIR, f"{session_id}.json"))
    return SafeConversationBufferMemory(
        memory_key="chat_history",
        chat_memory=history,
        return_messages=True
    )
