# agent/DBSchema_module.py

import json
import os
from pydantic import BaseModel

FILE_MAP = {
    "UserMongoDBAgent":               "oppiwallet_user.json",
    "UserCardMongoDBAgent":           "oppiwallet_usercard.json",
    "TokenMongoDBAgent":              "oppiwallet_tokens.json",
    "TransactionMongoDBAgent":        "oppiwallet_transaction.json",
    "UserPaymentLinkMongoDBAgent":    "oppiwallet_userpaymentlink.json",
    "UserWalletMongoDBAgent":         "oppiwallet_userwallet.json",
}

BASE_PATH = "files"

class PromptRequest(BaseModel):
    agent_name: str

def run_db_schema_agent(request: PromptRequest):
    """
    Returns the schema / DB description for the requested MongoDB agent
    by loading the corresponding JSON file.
    """

    agent_name = request.agent_name 

    # 1. Validate tool name
    if agent_name not in FILE_MAP:
        return {
            "error": f"Unknown agent '{agent_name}'. No schema available."
        }

    file_name = FILE_MAP[agent_name]
    file_path = os.path.join(BASE_PATH, file_name)

    # 2. Ensure file exists
    if not os.path.exists(file_path):
        return {
            "error": f"Schema file '{file_name}' not found."
        }

    # 3. Load and return content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        return {
            "error": f"Failed to load schema file: {str(e)}"
        }