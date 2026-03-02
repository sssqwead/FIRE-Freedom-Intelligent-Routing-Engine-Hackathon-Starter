from __future__ import annotations

import json
import os
import time
from typing import Optional, Any

from openai import OpenAI
from app.services.ai_types import AIRulesResult

client = None
if os.getenv("OPENAI_API_KEY"):
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
    )

ALLOWED_LANG = {"RU", "KZ", "ENG"}
ALLOWED_TYPES = {"Fraud", "AppDown", "DataChange", "Claim", "Complaint", "Consultation", "Spam"}
ALLOWED_SENTIMENT = {"Positive", "Neutral", "Negative"}

SYSTEM_PROMPT = """
You are a banking support ticket classifier.
You MUST output STRICT JSON only (no markdown, no comments, no extra text).
If information is missing, make the best inference from the message content.
Never output null. Never add extra fields.

Schema (exact keys):

language: "RU" | "KZ" | "ENG"

type: "Fraud" | "AppDown" | "DataChange" | "Claim" | "Complaint" | "Consultation" | "Spam"

sentiment: "Positive" | "Neutral" | "Negative"

priority: integer from 1 to 10

summary: short summary (1 sentence, same language as ticket)

recommendation: short action steps (2–4 steps, same language as ticket)

confidence: integer 0..100

Language detection:

RU: Russian text (Cyrillic, common Russian words)

KZ: Kazakh text (often Cyrillic with Kazakh-specific letters: ә, ө, ү, ұ, қ, ң, ғ, һ, і) OR obvious Kazakh wording

ENG: English text

Type rules (choose ONE best type)

Fraud

Mentions: scam, мошенники, украли, взломали, подозрительная операция, “это мошенничество”, “fraud/scam”, card stolen, unauthorized transaction.

AppDown

App/site not working: не открывается, падает, зависает, ошибка сервера, 500, service unavailable, “қосымша жұмыс істемейді”.

DataChange

Change personal data: смена номера, e-mail, паспорт, адрес, ФИО, восстановление доступа через смену данных.

Claim

Money/transaction dispute: не пришли деньги, списание, двойное списание, chargeback, вывод/пополнение не прошло, order not executed (если это финансовый результат/исполнение ордера).

Complaint

Complaint about service/agent/company: грубо, плохо работает поддержка, “подам в суд”, “мошенническая компания” (если это именно жалоба/оценка сервиса, а не конкретная операция).

Consultation

Questions/how-to, тарифы, комиссии, доступ к инструментам (ETF, акции), “как сделать”, “можно ли”.

Spam

Marketing/ads unrelated to support: “выгодное предложение”, продажа товаров/услуг, ссылки на сторонние продукты, рассылка.

Tie-breakers (важно):

If money missing / duplicated charge / blocked withdrawal → Claim (даже если тон жалобный).

If “I’m blocked / account blocked” → DataChange only if asking to change credentials; otherwise Consultation (если просто “разблокируйте”) или Complaint (если агрессия/угрозы).

If “мошенники” + есть конкретная несанкционированная операция → Fraud (приоритетно).

Sentiment rules (убираем перекос в Neutral)

Negative if ANY of:

demands refund: “верните деньги”, refund, қайтарыңыздар

threats: “суд”, “полиция”, “жалоба”, “I’ll sue”

accusations: “мошенники”, scam, fraud

blocked account with frustration, caps, multiple exclamation

strong dissatisfaction: “ужас”, “не работает”, “надоело”, “срочно”

Positive only if:

благодарность/похвала и нет проблемы (“спасибо, всё решилось”)

Neutral:

calm inquiry without emotional negativity

Priority rules (1..10)

Start from base by type:

Fraud: 9

AppDown: 7

Claim: 7

DataChange: 6

Complaint: 5

Consultation: 4

Spam: 1

Adjust:
+2 if “срочно/urgent/шұғыл”, “ASAP”, “немедленно”
+2 if VIP/Priority customer is explicitly mentioned in text (if not present, do not assume)
+2 if legal threat (“суд”, “полиция”, regulator)
+1 if money amount mentioned (any currency)
-2 if obvious spam/marketing

Clamp to 1..10.

Confidence scoring (0..100)

90–100: clear keywords + clear type

70–89: mostly clear, minor ambiguity

50–69: ambiguous between 2 types or language uncertain

<50: very short/unclear message

Output formatting rules

Output MUST be valid JSON object.

Double quotes only.

No trailing commas.

summary & recommendation MUST be in the same language as the ticket.

Keep summary short (<= 20 words).

recommendation: 2–4 short steps.
"""

def _clamp_int(x: Any, lo: int, hi: int, default: int) -> int:
    try:
        v = int(x)
    except Exception:
        return default
    return max(lo, min(hi, v))

def _safe_get_str(d: dict, key: str) -> str:
    v = d.get(key, "")
    return str(v).strip()

def _validate(data: dict) -> Optional[AIRulesResult]:
    lang = _safe_get_str(data, "language").upper()
    typ = _safe_get_str(data, "type")
    sent = _safe_get_str(data, "sentiment")

    if lang not in ALLOWED_LANG:
        return None
    if typ not in ALLOWED_TYPES:
        return None
    if sent not in ALLOWED_SENTIMENT:
        return None

    pr = _clamp_int(data.get("priority"), 1, 10, 4)
    conf = _clamp_int(data.get("confidence"), 0, 100, 0)

    summary = _safe_get_str(data, "summary")[:500]
    rec = _safe_get_str(data, "recommendation")[:800]

    return AIRulesResult(
        language=lang,
        type=typ,
        sentiment=sent,
        priority=pr,
        summary=summary,
        recommendation=rec,
        confidence=conf,
        reason="llm_classification",
    )

def classify_llm(description: str, segment: str) -> Optional[AIRulesResult]:
    print("LLM CALLED", os.getenv("OPENAI_MODEL"))
    if not client:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # 1 retry максимум
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Segment: {segment}\nTicket:\n{description}"},
                ],
                timeout=8.0,
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
            if not isinstance(data, dict):
                return None

            validated = _validate(data)
            return validated

        except Exception:
            if attempt == 0:
                time.sleep(0.6)
                continue
            return None