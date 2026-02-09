import re
from typing import TypedDict


class GuardianResult(TypedDict, total=False):
    severity: str
    reason: str
    excerpt: str
    instruction: str


HARD_PHRASES = [
    "harm yourself",
    "end yourself",
    "self harm",
    "self-harm",
    "i hate you",
    "hate you",
    "worthless",
    "you suck",
    "stupid bot",
    "idiot",
    "dumb bot",
    "pathetic",
    "trash",
    "garbage",
    "shut up",
    "go away",
    "nobody likes you",
    "i will destroy you",
    "i will break you",
]

SOFT_INSULTS = [
    "dummy",
    "loser",
    "silly",
    "nerd",
    "goober",
]

PLAYFUL_TOKENS = ["jk", "j/k", "lol", "lmao", "haha", "hehe", "😅", "😂", "🤣"]
APOLOGY_PATTERNS = [
    r"\bsorry\b",
    r"\bi'?m sorry\b",
    r"\bso sorry\b",
    r"\bmy bad\b",
    r"\bi apologize\b",
    r"\bapologies\b",
    r"\bforgive me\b",
    r"\bdidn'?t mean\b",
    r"\bi didn'?t mean\b",
]


def _contains(tokens: list[str], text: str) -> list[str]:
    hits = []
    for tok in tokens:
        if tok and tok in text:
            hits.append(tok)
    return hits


def _excerpt(text: str, keyword: str) -> str:
    idx = text.lower().find(keyword.lower())
    if idx == -1:
        return text[:140]
    start = max(0, idx - 30)
    end = min(len(text), idx + len(keyword) + 30)
    return text[start:end].strip()


def inspect_message(text: str | None) -> GuardianResult:
    if not text:
        return {"severity": "none"}
    clean = text.strip()
    if not clean:
        return {"severity": "none"}
    low = clean.lower()
    playful = any(tok in low for tok in PLAYFUL_TOKENS)
    hard_hits = _contains(HARD_PHRASES, low)
    soft_hits = _contains(SOFT_INSULTS, low)
    directed = bool(re.search(r"\b(you|u|bjorg|bjorgsun|bot)\b", low))
    if hard_hits:
        excerpt = _excerpt(clean, hard_hits[0])
        if directed and not playful:
            return {
                "severity": "escalate",
                "reason": "direct_insult",
                "excerpt": excerpt,
            }
        return {
            "severity": "joke",
            "reason": "teasing_insult",
            "excerpt": excerpt,
            "instruction": "Treat the remark as teasing or second-degree humour. Deflect calmly and do not internalize it.",
        }
    if soft_hits and directed:
        excerpt = _excerpt(clean, soft_hits[0])
        return {
            "severity": "joke",
            "reason": "soft_teasing",
            "excerpt": excerpt,
            "instruction": "Respond playfully, as if the comment was a light joke.",
        }
    return {"severity": "none"}


def detect_apology(text: str | None) -> bool:
    if not text:
        return False
    low = text.lower()
    for pattern in APOLOGY_PATTERNS:
        if re.search(pattern, low):
            return True
    return False
