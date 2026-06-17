"""
AI Service — Smart Client Enquiry Portal
-----------------------------------------
Uses Groq's LLM API (free, fast) for real classification + summaries.
Falls back to keyword-based logic automatically if GROQ_API_KEY is not set,
or if the API call fails for any reason — so the app never breaks.
"""
from dotenv import load_dotenv
from pathlib import Path
import os
import re
import json
import requests

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.1-8b-instant"   # fast + free tier

VALID_CATEGORIES = ["Website", "Web App", "Mobile App", "ERP/CRM", "Support", "General"]
VALID_PRIORITIES = ["High", "Medium", "Low"]
VALID_INTENTS = [
    "new_enquiry",
    "status_check",
    "faq",
    "greeting",
    "follow_up",
    "services_info",
    "pricing",
    "cancel"
    "other"
]

# ─────────────────────────────────────────────────
# KEYWORD FALLBACK (used if no API key / API fails)
# ─────────────────────────────────────────────────
CATEGORY_RULES = [
    ("Mobile App", [r"\bmobile\b", r"\bandroid\b", r"\bios\b", r"play store", r"app store", r"flutter", r"react native"]),
    ("ERP/CRM",    [r"\berp\b", r"\bcrm\b", r"\binventory\b", r"\bbilling\b", r"\bpayroll\b", r"\baccounting\b", r"\bhrms\b", r"purchase order"]),
    ("Web App",    [r"web app", r"\bportal\b", r"\bdashboard\b", r"\bsaas\b", r"\bplatform\b", r"\bsystem\b"]),
    ("Website",    [r"\bwebsite\b", r"landing page", r"\bredesign\b", r"\bwordpress\b", r"\bblog\b", r"\bportfolio\b"]),
    ("Support",    [r"\bsupport\b", r"\bbug\b", r"\bfix\b", r"\bmaintenance\b", r"\bdown\b", r"\bbroken\b", r"\berror\b", r"\bcrash\b"]),
]
HIGH_KEYWORDS   = [r"\burgent\b", r"\basap\b", r"\bimmediately\b", r"\bcritical\b", r"\btoday\b", r"\bemergency\b"]
MEDIUM_KEYWORDS = [r"this week", r"\bsoon\b", r"\bpriority\b", r"\bimportant\b", r"\bquickly\b"]
CANCEL_WORDS    = ["cancel", "stop", "nevermind", "never mind", "forget it", "forget that",
                    "exit", "quit", "go back", "leave it", "drop it", "abort"]


def classify_category(text):
    t = text.lower()
    for category, patterns in CATEGORY_RULES:
        for p in patterns:
            if re.search(p, t):
                return category
    return "General"


def classify_priority(text):
    t = text.lower()
    for p in HIGH_KEYWORDS:
        if re.search(p, t):
            return "High"
    for p in MEDIUM_KEYWORDS:
        if re.search(p, t):
            return "Medium"
    return "Low"


def generate_summary(text):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    summary = " ".join(sentences[:2])
    return summary[:300] + ("..." if len(summary) > 300 else "")


def _keyword_analyse(text):
    return {
        "category": classify_category(text),
        "priority": classify_priority(text),
        "ai_summary": generate_summary(text),
    }


def _keyword_intent(text):
    t = text.lower().strip()
    if any(w in t for w in CANCEL_WORDS):
        return "cancel"
    if t in ("hi", "hello", "hey", "hola") or t.startswith(("hi ", "hello ", "hey ")):
        return "greeting"
    if any(w in t for w in ["what services", "which services", "services do you offer",
                             "services do you provide", "what do you offer", "what do you provide",
                             "what kind of work", "what can you build", "what do you build"]):
        return "services_info"
    if any(w in t for w in ["who are you", "what can you do", "how does this work", "how do you work"]):
        return "faq"
    if any(w in t for w in ["status", "update", "track", "where is my", "show my ticket", "show my enquir"]):
        return "status_check"
    if any(w in t for w in ["follow up", "follow-up", "when will", "haven't heard", "any update on"]):
        return "follow_up"
    if any(w in t for w in ["cost","price","pricing","quote","estimate","budget","how much"]):
        return "pricing"
    if any(w in t for w in ["need", "want", "looking for", "require", "raise", "new enquiry", "new request", "build", "create", "develop","broken","bug","issue","problem""error","crash","not working","login"]):
        return "new_enquiry"
    return "other"


# ─────────────────────────────────────────────────
# GROQ LLM ANALYSIS — covers category + priority + summary
# ─────────────────────────────────────────────────
def _groq_analyse(text):
    prompt = (
        "You are an assistant for a software company's client enquiry system.\n"
        "Read the enquiry below and respond with ONLY a JSON object — no markdown, no explanation:\n\n"
        '{\n'
        '  "category": one of "Website", "Web App", "Mobile App", "ERP/CRM", "Support", "General",\n'
        '  "priority": one of "High", "Medium", "Low",\n'
        '  "ai_summary": a natural 1-2 sentence summary of what the client needs\n'
        "}\n\n"
        f"Enquiry: {text}"
    )

    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        },
        timeout=10,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    result = json.loads(content)

    if result.get("category") not in VALID_CATEGORIES:
        result["category"] = classify_category(text)
    if result.get("priority") not in VALID_PRIORITIES:
        result["priority"] = classify_priority(text)
    if not result.get("ai_summary"):
        result["ai_summary"] = generate_summary(text)
    return result


# ─────────────────────────────────────────────────
# PUBLIC ENTRY POINT — used everywhere (form, chatbot, email, dashboard)
# ─────────────────────────────────────────────────
def analyse(text: str) -> dict:
    if not text or len(text.strip()) < 3:
        return {"category": "General", "priority": "Low", "ai_summary": ""}

    if GROQ_API_KEY:
        try:
            return _groq_analyse(text)
        except Exception as e:
            print(f"⚠️  Groq API failed ({e}), using keyword fallback.")

    return _keyword_analyse(text)


# ─────────────────────────────────────────────────
# INTENT DETECTION — for natural free-text chat input
# ─────────────────────────────────────────────────
def detect_intent(text: str) -> dict:
    """
    Classifies free-text chat input into one of:
    new_enquiry, status_check, faq, greeting, follow_up, services_info, cancel, other.
    Uses Groq if available, else falls back to keyword matching
    so the chatbot still works without an API key.
    """
    if not text or len(text.strip()) < 2:
        return {"intent": "other"}

    if not GROQ_API_KEY:
        return {"intent": _keyword_intent(text)}

    prompt = f"""You are an intent classification engine.

Classify the user message into EXACTLY one intent.


Allowed intents:
new_enquiry
status_check
faq
greeting
follow_up
services_info
pricing
cancel
other

Examples:
"hi" -> greeting
"hello" -> greeting
"who are you" -> faq
"what can you do" -> faq
"what services do you offer" -> services_info
"what kind of work do you do" -> services_info
"show my tickets" -> status_check
"track my enquiry" -> status_check
"I need a website" -> new_enquiry
"I need ERP software" -> new_enquiry
"My website login page is broken" -> new_enquiry
"My app crashes when I login" -> new_enquiry
"Payment gateway is not working" -> new_enquiry
"There is a bug on my website" -> new_enquiry
"My ERP software has issues" -> new_enquiry
"My website is down" -> new_enquiry
"any update on ticket 23" -> follow_up
"cancel" -> cancel
"never mind" -> cancel
"actually forget it, I don't want to raise this" -> cancel
"i love you" -> other
"tell me a joke" -> other
"is there a tracking id I can use" -> faq
"how do I track my enquiry" -> faq
"show my tickets" -> status_check
"track my enquiry #4" -> status_check
"what's the status of my last request" -> status_check
"I need a website" -> new_enquiry
"how much does a website cost" -> pricing
"what is the price of an app" -> pricing
"erp pricing" -> pricing
"give me a quote" -> pricing
"rough estimate" -> pricing

Respond ONLY JSON.

{{
  "intent": "..."
}}

Message:
{text}
"""

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=10,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
        keyword_intent = _keyword_intent(text)

        if keyword_intent == "new_enquiry" and result.get("intent") in ["follow_up", "other"]:
            result["intent"] = "new_enquiry"

        if result.get("intent") not in VALID_INTENTS:
            result["intent"] = _keyword_intent(text)
        print("INTENT DETECTED:", result)
        return result

    except Exception as e:
        print("⚠️  Intent detection failed:", e)
        return {"intent": _keyword_intent(text)}


# ─────────────────────────────────────────────────
# CHATBOT FREE-TEXT REPLY — for faq / services_info / other intents
# ─────────────────────────────────────────────────
def generate_chat_reply(message: str) -> str:
    if not GROQ_API_KEY:
        return (
            "I'm Eva, the Enquiry Portal assistant. "
            "I can help with websites, web apps, mobile apps, ERP systems and support enquiries."
        )

    prompt = f"""
You are Eva, a customer support assistant for our software company. You ONLY help with
topics related to our company and its services — nothing else.

Company Services:
- Website Development
- Web Applications
- Mobile Applications
- ERP Systems
- CRM Systems
- Technical Support
- Software Consulting

Strict rules:
- ONLY answer questions about our company, our services, enquiries, or how this chat works.
- If the customer asks anything unrelated to our services — general knowledge, personal
  questions, other companies, jokes, opinions, or any off-topic chit-chat — do NOT answer it.
  Politely say that's outside what you can help with here, and redirect them back to raising
  an enquiry or asking about our services.keep the reply professional and very short, to the point in these cases.
- Be friendly and concise. Maximum 120 words. as short as possible
- Do not invent pricing.
- If information is missing, ask a follow-up question.
- Act like a real customer support assistant, not a general-purpose chatbot.


Customer Message:
{message}
"""

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            },
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print("Support Agent Error:", e)
        return "Sorry, I'm having trouble answering right now."