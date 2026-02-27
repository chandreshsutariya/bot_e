# agent/security_checks.py

import re

def detect_cross_user_access(prompt: str, allowed_identifiers: dict) -> bool:
    """
    Check if the prompt includes identifiers that do not match the logged-in user's.
    Returns True if cross-user access is detected.
    """
    # Patterns for email, mobile, player ID, etc.
    suspicious_patterns = {
        'email': r'[\w\.-]+@[\w\.-]+',
        'mobile': r'\b\d{10}\b',
        # 'player_id': r'\b\d{8}\b',
        'user_id': r'ObjectId\(["\']?([a-fA-F\d]{24})["\']?\)',
    }

    for key, pattern in suspicious_patterns.items():
        matches = re.findall(pattern, prompt)
        if not matches:
            continue
        for match in matches:
            if key in allowed_identifiers and match != allowed_identifiers[key]:
                return True  # Mismatch found

    return False

def replace_values_for_keys(query: str, replacements: dict) -> str:
    """
    Replaces any value of the specified keys with the provided new values.
    - If the value is 'ObjectId:<id>', it replaces with ObjectId("<id>")
    - If the value is 'str:<text>', it replaces with "<text>"
    - Otherwise, assumes raw replacement (like a number or unquoted string).
    """
    for key, value in replacements.items():
        if isinstance(value, str) and value.startswith('ObjectId:'):
            replacement_value = f"ObjectId('{value[9:]}')"
        elif isinstance(value, str) and value.startswith('str:'):
            replacement_value = f'"{value[4:]}"'
        else:
            replacement_value = value  # raw, e.g., number

        pattern = rf'({key}\s*:\s*)([^,\}}]+)'
        replacement = rf'\1{replacement_value}'
        query = re.sub(pattern, replacement, query)

    return query.replace("\n", "").replace("\\", "")



def split_queries(query_str: str) -> list:
    """
    Splits MongoDB queries by identifying each 'db.' block.
    """
    pattern = r'db\.[\s\S]*?(?=(?=db\.)|$)'  # Matches each query from 'db.' to next 'db.' or end
    raw_queries = re.findall(pattern, query_str)
    queries = [q.strip().rstrip(';') for q in raw_queries if q.strip()]
    return queries

def enforce_security_policy_from_query(query: str, db_name: str) -> dict:
    """
    Checks if a MongoDB query targets a restricted collection and applies policy if needed.
    """
    restricted_collections = [
        "usersupportedpayments",
        "userroles",
        "usermails",
        "userbanks",
        "roles",
        "admin", 
        "local", 
        "config", 
        "mongosync_reserved_for_internal_use", 
        "commondb",
        "supportdb"
    ]
 
    match = re.search(r'db\.([a-zA-Z0-9_]+)\.find', query)
    if match:
        collection_name = match.group(1)
        if collection_name.lower() in [c.lower() for c in restricted_collections]:
            return {
                "database_name": db_name,
                "query": "This query breaks user's security policy. Don't entertain this type of question."
            }

    return {
        "database_name": db_name,
        "query": query
    }
