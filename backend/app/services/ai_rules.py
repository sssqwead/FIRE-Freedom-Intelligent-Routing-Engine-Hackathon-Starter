from __future__ import annotations
from app.services.ai_llm import classify_llm
import re
from app.core.config import settings
from app.services.ai_types import AIRulesResult

KZ_CHARS = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")

def detect_language(text: str) -> str:
    if any(ch in KZ_CHARS for ch in text):
        return "KZ"
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    cyr = sum(1 for ch in text if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    if latin > max(8, cyr * 2):
        return "ENG"
    return "RU"

def classify_type(text: str) -> tuple[str, int, str]:
    t = text.lower()
    # order matters
    rules = [
        ("Fraud", [r"мошен", r"взлом", r"списал", r"не\s*я", r"подозр", r"scam", r"fraud"], 90),
        ("AppDown", [r"не\s*работ", r"ошибк", r"error", r"crash", r"bug", r"не\s*запуска"], 80),
        ("DataChange", [r"смен", r"измен", r"фио", r"телефон", r"паспорт", r"документ", r"email"], 75),
        ("Claim", [r"возмест", r"компенсац", r"верните\s+деньги", r"суд", r"ущерб"], 75),
        ("Complaint", [r"возмущ", r"ужас", r"плохо", r"обман", r"недоволен", r"жалоб"], 70),
        ("Consultation", [r"как\s+сделать", r"подскаж", r"хочу\s+узнать", r"вопрос"], 60),
        ("Spam", [r"реклам", r"спам", r"http", r"www"], 55),
    ]
    hits = 0
    best = ("Consultation", 35, "no strong keywords")
    for typ, pats, base in rules:
        local_hits = sum(1 for p in pats if re.search(p, t))
        if local_hits > 0 and (local_hits > hits or base > best[1]):
            hits = local_hits
            conf = min(95, base + local_hits * 3)
            best = (typ, conf, f"matched {local_hits} keyword groups for {typ}")
    return best

def classify_sentiment(text: str) -> tuple[str, int, str]:
    t = text.lower()
    neg = any(k in t for k in ["ужас", "возмущ", "обман", "срочно", "плохо", "ненавиж", "разочар"])
    pos = any(k in t for k in ["спасибо", "благодар", "thank"])
    if neg and not pos:
        return ("Negative", 80, "negative keywords")
    if pos and not neg:
        return ("Positive", 75, "positive keywords")
    if neg and pos:
        return ("Neutral", 55, "mixed keywords")
    return ("Neutral", 60, "no strong sentiment keywords")

def priority_score(typ: str, sentiment: str, segment: str) -> int:
    base = {
        "Fraud": 9,
        "AppDown": 8,
        "Claim": 7,
        "Complaint": 6,
        "DataChange": 6,
        "Consultation": 4,
        "Spam": 1,
    }.get(typ, 4)
    if segment.upper() in ["VIP", "PRIORITY"]:
        base += 2
    if sentiment == "Negative":
        base += 1
    return max(1, min(10, base))

def summarize_simple(text: str, typ: str) -> tuple[str, str]:
    if not text.strip():
        return ("Пустое обращение (возможно, клиент отправил только вложение).", "Открыть вложение, уточнить проблему у клиента.")
    clipped = text.strip()
    if len(clipped) > 240:
        clipped = clipped[:240].rstrip() + "…"
    summary = f"{typ}: {clipped}"
    rec_map = {
        "Fraud": "Проверить подозрительные операции, запросить детали/время, при необходимости заблокировать доступ и эскалировать.",
        "AppDown": "Запросить шаги воспроизведения, версию приложения, проверить статус платформы, эскалировать в техподдержку.",
        "DataChange": "Проверить запрос на изменение данных, собрать подтверждающие документы, обработать по регламенту.",
        "Claim": "Уточнить требования клиента, собрать доказательства, оценить компенсацию/эскалировать.",
        "Complaint": "Извиниться, уточнить детали, зафиксировать проблему, предложить решение/эскалацию.",
        "Consultation": "Ответить на вопрос, дать пошаговую инструкцию, предложить дополнительные материалы.",
        "Spam": "Пометить как спам и закрыть/игнорировать.",
    }
    return (summary, rec_map.get(typ, "Уточнить детали и обработать по стандартному регламенту."))

def run_rules(description: str, segment: str) -> AIRulesResult:
    lang = detect_language(description)
    typ, tconf, treason = classify_type(description)
    sent, sconf, sreason = classify_sentiment(description)
    pr = priority_score(typ, sent, segment)
    summary, rec = summarize_simple(description, typ)
    conf = int((tconf * 0.65) + (sconf * 0.35))
    reason = f"type:{treason}; sentiment:{sreason}"
    return AIRulesResult(lang, typ, sent, pr, summary, rec, conf, reason)

LLM_CONF_THRESHOLD = 70

def run_hybrid(description: str, segment: str) -> AIRulesResult:
    # LLM выключен — сразу rules
    if not settings.USE_LLM:
        return run_rules(description, segment)

    # LLM включен — пробуем
    try:
        from app.services.ai_llm import classify_llm
        llm_result = classify_llm(description, segment)
    except Exception:
        llm_result = None

    if llm_result and llm_result.confidence >= LLM_CONF_THRESHOLD:
        return llm_result

    return run_rules(description, segment)