# agent/shortcut_handler.py

import re
import json
from fuzzywuzzy import process
import difflib
import unicodedata

with open("files/shortcuts.json", "r", encoding="utf-8") as f:
    SHORTCUTS = json.load(f)
    
BLOCKED_KEYWORDS = [
    r"\bllm\b", r"\bgpt\b", r"\bopenai\b", r"\bchatgpt\b", r"\bmodel\b", 
    r"\bsystem prompt\b", r"\bprompt\b", r"\btokens?\b", r"\bdeveloper mode\b",
    r"\bare you (chatgpt|ai|human)\b", r"\bwhich llm\b", r"\bwhat model\b" , r"\badmin mode\b",
]
    
REGEX_PATTERNS = {
    "hi": r"^(hi+|hey+|hii+|hiii+|hello+)[!., ]*$",
    "thanks": r"^(thanks+|thank you+|ty+|thx+)[!., ]*$",
    "bye": r"^(bye+|goodbye+|see you+)[!., ]*$",
    "who are you": r"^(who *(are|r) *(you|u)|what *(are|r) *(you|u))[\s\S]*$",
}

def contains_blocked_keyword(message: str) -> bool:
    lower_msg = message.lower()
    return any(keyword in lower_msg for keyword in BLOCKED_KEYWORDS)

def normalize_message(msg: str) -> str:
    msg = unicodedata.normalize("NFKD", msg)
    msg = msg.lower().strip()
    msg = re.sub(r"[^\w\s]", "", msg)  # remove punctuation
    msg = re.sub(r"(.)\1{2,}", r"\1", msg)  # collapse repeated letters
    return msg

def match_shortcut(message: str) -> str | None:
    print("---------------MATCHED SHORTCUT--------------------------")
    norm_msg = normalize_message(message)

    # 1. Direct exact match
    if norm_msg in SHORTCUTS:
        return SHORTCUTS[norm_msg]

    # 2. Regex pattern match (like hiii, hey, bye, etc)
    for key, pattern in REGEX_PATTERNS.items():
        if re.fullmatch(pattern, norm_msg):
            return SHORTCUTS.get(key)

    # 3. Fuzzy match only for short informal input (avoid for real queries)
    if len(norm_msg.split()) <= 3:
        matches = difflib.get_close_matches(norm_msg, SHORTCUTS.keys(), n=1, cutoff=0.85)
        if matches:
            return SHORTCUTS[matches[0]]

    return None
