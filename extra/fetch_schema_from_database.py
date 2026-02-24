import json
from pymongo import MongoClient
from bson import json_util
import os

def get_field_types(document, prefix=""):
    field_types = {}
    for key, value in document.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            nested = get_field_types(value, full_key)
            field_types.update(nested)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            nested = get_field_types(value[0], full_key + "[]")
            field_types.update(nested)
        else:
            field_types[full_key] = type(value).__name__
    return field_types

def analyze_collection(collection):
    sample = collection.find_one()
    if not sample:
        return {}
    return get_field_types(sample)

def generate_schema(mongo_uri):
    client = MongoClient(mongo_uri)
    schema = {}

    for db_name in client.list_database_names():
        if db_name in ("admin", "local", "config", "mongosync_reserved_for_internal_use", "commondb"):
            continue  # Skip system DBs

        db = client[db_name]
        schema[db_name] = {}

        for coll_name in db.list_collection_names():
            coll = db[coll_name]
            field_info = analyze_collection(coll)
            schema[db_name][coll_name] = field_info

    with open("files/database_description.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=4, default=json_util.default)

    print("✅ Schema saved to 'database_description.json'")

MONGO_URI = os.getenv('MONGODB_URL')

generate_schema(MONGO_URI)
