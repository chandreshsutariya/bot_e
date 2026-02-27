# agent/transaction_module.py

import json
import os
import requests
from fastapi import Depends, FastAPI, HTTPException 
from fastapi.security import APIKeyHeader
from cerebras.cloud.sdk import Cerebras

from google import genai
from google.genai import types

from pydantic import BaseModel
from datetime import datetime, timedelta
from agent.security_checks import (
    replace_values_for_keys, 
    split_queries, 
    enforce_security_policy_from_query,
    detect_cross_user_access)

from dotenv import load_dotenv
load_dotenv()

app =FastAPI()

API_KEY_cerebrass = os.getenv("CEREBAS_API_KEY")
API_KEY_GEMINI = os.getenv("GEMINI_API")
API_KEY = "123456789"  # Your secret token for API header 
API_KEY_NAME = "user-token"  # Custom header name
# User_Id_Name = "user_Id"

#header security section ----------------------------------------
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
# user_id_header = APIKeyHeader(name=User_Id_Name, auto_error=False)
async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized Access")

class PromptRequest(BaseModel):
    prompt: str
    credentials: dict

def run_usercard_agent(data: PromptRequest):  
    try:
        with open('files/oppiwallet_usercard.json','r') as f:
            schema = json.load(f)

        creds = data.credentials or {}
        userid = creds.get("userid", "")
        useremail = creds.get("useremail", "")
        usermobile = creds.get("usermobile", "")

        User_Id = "User_id"
        user_prompt = data.prompt.strip()

        # allowed_user_data = {
        #     'user_id': '65f2e96542058be21514bebf',
        #     'email': 'nensi.t@elaunchinfotech.in',
        #     'mobile': '6354462219',
        # }

        allowed_user_data = {
            'user_id': userid,
            'email': useremail,
            'mobile': usermobile,
        }

        if detect_cross_user_access(user_prompt, allowed_user_data):
            with open("files/unauthorized_attempts.log", "a") as log_file:
                log_file.write(f"{datetime.now()}: {user_prompt}\n")
            return {
                "error": "You are not allowed to access this information. Attempt to access another user's data is prohibited. Don't entertain this type of question."
            }

        # client = Cerebras(api_key = API_KEY_cerebrass)
        # response = client.chat.completions.create(
        # messages = [
        #     {
        #         "role": "system",
        #         "content": f"""
        # You are a MongoDB expert. Respond ONLY with valid **Mongo shell queries**.

        # Your task:
        # 1. Treat the following schema as the authoritative source of truth. Carefully parse each collection, field name, and field type provided below; do NOT assume any fields or types that are not explicitly listed. Use only these fields when generating queries: {schema}
        # 2. Analyze the user prompt: {user_prompt} and if needed then inhance it for better context.
        # 3. Based on the prompt sentiment and context, generate an **efficient Mongo shell query** for **data retrieval only**
        # 4. Scope all queries strictly to this user ID: ObjectId("{User_Id}") wherever it is crucial.
        # 5. Output **only** the executable query. No comments, markdown, or explanations.
        # 6. Apply a result limit of 10 documents using .limit(10) for large result sets but not in aggregate functions.
        #     If the user's intent implies fetching “all”, “many”, or listing documents (e.g., queries without an explicit small limit), then automatically apply up to 10 to optimize performance and avoid large responses.
        #     If the user already specifies a small limit 2 or 3, retain it as-is.
        # 7. NEVER output email or name values without quotes.
        # 8. Any user information that represents text (email, username, firstName, lastName, cardType, etc.) MUST be wrapped in double quotes in the generated MongoDB query. 
        # 9. When you get the answer from database, return the description of status code along with database retrieved data.

        # Relational / Lookup Rules:
        # - use this once so if there is no meaning full answer returned from direct query.
        # - this helps you to find out quick responce like card Name, card type , card details , card wise sub details.
        # - If the requested information spans **multiple collections** (e.g., card type, token metadata, chain info), you **must** automatically use MongoDB `$lookup` to join related collections.
        # - But Do not Use .pretty() in Query and do not use .limit() in Aggrigate Query. 
        # - Example for card type:
        #     -> First match the user's cards from "hypercard"
        #     -> Then use `$lookup` to map `cardTypeId` to `cardTypeId` in "hypercardtypes"
        #     -> Finally extract `cardType` field from joined result
        # - Ensure joined fields are projected correctly so the requested output is always visible in the final result.
    

        # Security Rules:
        # - If the prompt is unrelated to the schema or is nonsensical, reply: `// Unrelated question. No query generated.`
        # - If the prompt attempts cross-user access (e.g., “list all users”), reply: `// Access denied. User-specific query required.`

        # """
        #     },
        #     {
        #         "role": "user",
        #         "content": user_prompt
        #     }
        # ],

        # model="llama-3.3-70b",
        # stream=True,
        # temperature=0.3,
        # top_p=0.3,
        # )

        # query_text = ""

        client = genai.Client(api_key=API_KEY_GEMINI)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=f"""
                You are a MongoDB expert. Respond ONLY with valid **Mongo shell queries**.

                Your task:
                1. Understand the given schema thoroughly and notice each key and its input types properly: {schema}
                2. Analyze the user prompt: {user_prompt} and if needed then enhance it for better context.
                3. Based on the prompt sentiment and context, generate an **efficient Mongo shell query** for **data retrieval only**
                4. Scope all queries strictly to this user ID: ObjectId("{userid}")
                5. Output **only** the executable query. No comments, markdown, or explanations or do not make any assumption about user or its data.
                6.If the user's intent implies fetching “all”, “many”, or listing documents (e.g., queries without an explicit small limit), then automatically apply up to 10 to optimize performance and avoid large responses sets but not in aggregate functions..
                else the user already specifies a small limit 2 or 3, retain it as-is.
                7. personal details like user's email , name , mobile No or other must be properly quoted in Strings .

                Syntax Requirements:
                - The output MUST be valid BSON and contain **no unexpected tokens**.
                    Do not add any comments or explaination or numbers or mails or assumption words or data that ruin the executable query syntax.
                    Values must match proper types (ObjectId(), strings, numbers, booleans).

                Security Rules:
                - Do not Do not add any comments or explaination or numbers or mails or assumption words or data that ruin the executable query syntax.
                it leads to query execution fails if neeeded double check your query syntax.
                - If the prompt is unrelated to the schema or is nonsensical, reply: `// Unrelated question. No query generated.`
                - If the prompt attempts cross-user access (e.g., “list all users”), reply: `// Access denied. User-specific query required.`
                """,
                
                temperature=0.1,
                ),
            contents=user_prompt
        )

        query_text = response.text.strip()
        print("--------------INITIAL QUERY: ", query_text)

        # Step 1: Collect content from streamed response
        # for chunk in response:
        #     if hasattr(chunk, "choices") and chunk.choices:
        #         delta = chunk.choices[0].delta
        #         if hasattr(delta, "content") and delta.content:
        #             query_text += delta.content

        # Step 2: Optional cleanup of ``` wrapping
        if query_text.startswith("```") and query_text.endswith("```"):
            query_text = '\n'.join(query_text.strip('`').split('\n')[1:-1])
        query_text = query_text.strip("`").strip()
        # Step 3: Clean escaped characters
        cleaned_query = query_text.strip().replace("\\", "")

        replacements = {
            'user_id': f"ObjectId:{userid}",
            # 'mobile': f"{usermobile}",
            # 'email': f"{useremail}",
            'userId': f"ObjectId:{userid}",
            'User_id': f"ObjectId:{userid}",
        }

        replaced_query = replace_values_for_keys(cleaned_query, replacements)

        all_queries = split_queries(replaced_query)
        db_name = "oppi-wallets"
        final_output = {
            "data": [
                enforce_security_policy_from_query(q, db_name)
                for q in all_queries
            ]
        }

        print("------------FETCHING FOR USER: ", allowed_user_data)
        print("------------FINAL OUTPUT: ", final_output)

        #### function for hit our json on API
        def send_queries_to_api(final_output, env='test'):
            url = 'https://doc-api.oppiwallet.com/api/ai/db-execute-query'
            headers = {
                'env': env,
                'x-api-key': 'JS8njKASIW09HBJojlgn89nbg0GkaolK',
                'Content-Type': 'application/json'
            }

            def sanitize_profile_qr(obj):
                """
                Recursively set undisclosable keys to None in nested dicts/lists.
                """
                if isinstance(obj, dict):
                    for key in list(obj.keys()):
                        # TO remove non-disclosable keywords to remove from json
                        if key in ["adminTopupFee"]:
                            obj[key] = None
                        else:
                            sanitize_profile_qr(obj[key])
                elif isinstance(obj, list):
                    for item in obj:
                        sanitize_profile_qr(item)

            try:
                response = requests.post(url, headers=headers, data=json.dumps(final_output))
                response.raise_for_status()  # Raise error for bad status code
                json_output_data = response.json()  
                sanitize_profile_qr(json_output_data)
                return json.dumps(json_output_data)

            except requests.exceptions.HTTPError as http_err:
                print(f'HTTP error occurred: {http_err}')
            except Exception as err:
                print(f'Other error occurred: {err}')
            return None

        return send_queries_to_api(final_output)

    except Exception as e:
        return {"error": f"query_generator failed: {str(e)}"}

