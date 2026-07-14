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

VALID_CATEGORIES = [
    "Website", "Web App", "Mobile App", "ERP/CRM", "Support",
    "E-Commerce", "Cloud", "Automation", "AI Solution",
    "API Integration", "Hosting", "Maintenance", "General",
]
VALID_PRIORITIES = ["High", "Medium", "Low"]
VALID_INTENTS = [
    "new_enquiry",
    "status_check",
    "faq",
    "greeting",
    "small_talk",
    "compliment",
    "thanks",
    "follow_up",
    "services_info",
    "pricing",
    "cancel",
    "other",
]

# ─────────────────────────────────────────────────
# KEYWORD FALLBACK (used if no API key / API fails)
# ─────────────────────────────────────────────────
CATEGORY_RULES = [
    ("Mobile App", [r"\bmobile\b", r"\bandroid\b", r"\bios\b", r"play store", r"app store", r"flutter", r"react native"]),
    ("ERP/CRM",    [r"\berp\b", r"\bcrm\b", r"\binventory\b", r"\bbilling\b", r"\bpayroll\b", r"\baccounting\b", r"\bhrms\b", r"purchase order"]),
    ("E-Commerce", [r"\becommerce\b", r"e-commerce", r"\bshopify\b", r"\bcheckout\b", r"\bcart\b", r"\bonline store\b", r"\bpayment gateway\b"]),
    ("Cloud",      [r"\bcloud\b", r"\baws\b", r"\bazure\b", r"\bgcp\b", r"\bserver migration\b", r"\bdeployment\b"]),
    ("Automation", [r"\bautomation\b", r"\bautomate\b", r"\bworkflow\b", r"\bscript\b"]),
    ("AI Solution",[r"\bai\b", r"\bmachine learning\b", r"\bchatbot\b", r"\bml model\b", r"\bartificial intelligence\b"]),
    ("API Integration", [r"\bapi\b", r"\bintegration\b", r"\bwebhook\b", r"third[- ]party"]),
    ("Hosting",    [r"\bhosting\b", r"\bdomain\b", r"\bdns\b", r"\bssl\b"]),
    ("Maintenance",[r"\bmaintenance\b", r"\bupdate\b", r"\bupgrade\b", r"\bpatch\b"]),
    ("Web App",    [r"web app", r"\bportal\b", r"\bdashboard\b", r"\bsaas\b", r"\bplatform\b", r"\bsystem\b"]),
    ("Website",    [r"\bwebsite\b", r"landing page", r"\bredesign\b", r"\bwordpress\b", r"\bblog\b", r"\bportfolio\b"]),
    ("Support",    [r"\bsupport\b", r"\bbug\b", r"\bfix\b", r"\bmaintenance\b", r"\bdown\b", r"\bbroken\b", r"\berror\b", r"\bcrash\b"]),
]

HIGH_KEYWORDS = [
    r"\burgent\b", r"\basap\b", r"\bimmediately\b", r"\bcritical\b", r"\btoday\b", r"\bemergency\b",
    r"\bproduction\b", r"server down", r"website down", r"payment failed",
    r"customers cannot login", r"customers can't login", r"business stopped",
]
MEDIUM_KEYWORDS = [r"this week", r"\bsoon\b", r"\bpriority\b", r"\bimportant\b", r"\bquickly\b"]

CANCEL_WORDS = [
    "cancel", "stop", "nevermind", "never mind", "forget it", "forget that",
    "exit", "quit", "go back", "leave it", "drop it", "abort",
]

NEW_ENQUIRY_WORDS = [
    "need", "want", "looking for", "require", "raise", "new enquiry", "new request",
    "build", "create", "develop",
    "issue", "problem", "broken", "bug", "crash", "not working",
    "login", "can't login", "cannot login", "unable",
    "website down", "server down", "payment failed",
    "dashboard error", "api error", "database error",
]

GREETING_WORDS = ["hi", "hello", "hey", "hola", "hii", "hiya"]
SMALL_TALK_WORDS = ["how are you", "how are u", "how's it going", "hows it going", "whats up", "what's up"]
THANKS_WORDS = ["thank", "thanks", "thank you", "thanks a lot", "thank u"]
COMPLIMENT_WORDS = ["love you", "love u", "awesome", "great job", "good bot", "you're the best", "youre the best", "amazing bot"]

PRICING_TEXT = (
    "Here's a rough idea of our pricing:\n\n"
    "• Website: starts around ₹10,000\n"
    "• Business website: ₹25,000–₹75,000\n"
    "• Mobile app: ₹50,000+\n"
    "• ERP/CRM: depends on modules required\n\n"
    "The final quotation depends on your project scope. "
    "Would you like to raise an enquiry so our team can share an exact quote?"
)

FALLBACK_UNKNOWN_TEXT = (
    "I'm not sure I understood that.\n\n"
    "I can help you:\n"
    "• Raise an enquiry\n"
    "• Check enquiry status\n"
    "• Answer questions about our software services"
)


def classify_category(text):
    t = normalize_text(text)
    for category, patterns in CATEGORY_RULES:
        for p in patterns:
            if re.search(p, t):
                return category
    return "General"


def classify_priority(text):
    t = normalize_text(text)
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


def _contains_any(t, words):
    return any(w in t for w in words)


# Common chat shorthand / typos -> normalized words.
# Applied on whole words only (word-boundary), so it won't mangle
# unrelated substrings (e.g. "your" won't get double-normalized).
_SHORTHAND_MAP = {
    "u": "you", "ur": "your", "r": "are", "y": "why",
    "wat": "what", "wht": "what", "wt": "what", "whst": "what",
    "hw": "how", "hru": "how are you",
    "pls": "please", "plz": "please",
    "thx": "thanks", "tnx": "thanks", "ty": "thanks",
    "gr8": "great", "gud": "good",
    "dis": "this", "dat": "that",
    "abt": "about", "b4": "before",
    "msg": "message", "nd": "and", "n": "and",
    "wanna": "want to", "gonna": "going to",
}
_SHORTHAND_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in _SHORTHAND_MAP) + r")\b")


def normalize_text(text: str) -> str:
    """Lowercases and expands common chat shorthand/typos before keyword matching."""
    t = text.lower()
    t = _SHORTHAND_RE.sub(lambda m: _SHORTHAND_MAP[m.group(1)], t)
    return t


def _keyword_intent(text):
    """
    Pure keyword-based intent fallback. Order matters:
    cancel/greeting checks first, then specific intents,
    then new_enquiry as a catch for problem-language,
    then small_talk/thanks/compliment, then other.
    """
    t = normalize_text(text).strip()

    if _contains_any(t, CANCEL_WORDS):
        return "cancel"

    if t in GREETING_WORDS or any(t.startswith(g + " ") for g in GREETING_WORDS):
        return "greeting"

    if any(w in t for w in [
        "what services", "which services", "your services", "services do you offer",
        "services do you provide", "what do you offer", "what do you provide",
        "what kind of work", "what can you build", "what do you build",
    ]):
        return "services_info"

    if any(w in t for w in ["who are you", "what can you do", "how does this work", "how do you work"]):
        return "faq"

    if any(w in t for w in ["status", "update", "track", "where is my", "show my ticket", "show my enquir"]):
        return "status_check"

    if any(w in t for w in ["follow up", "follow-up", "when will", "haven't heard", "any update on"]):
        return "follow_up"

    if any(w in t for w in ["cost", "price", "pricing", "quote", "estimate", "budget", "how much"]):
        return "pricing"

    if _contains_any(t, NEW_ENQUIRY_WORDS):
        return "new_enquiry"

    if _contains_any(t, SMALL_TALK_WORDS):
        return "small_talk"

    if _contains_any(t, THANKS_WORDS):
        return "thanks"

    if _contains_any(t, COMPLIMENT_WORDS):
        return "compliment"

    return "other"


# ─────────────────────────────────────────────────
# GROQ LLM ANALYSIS — covers category + priority + summary
# ─────────────────────────────────────────────────
def _groq_analyse(text):
    prompt = (
        "You are an assistant for a software company's client enquiry system.\n"
        "Read the enquiry below and respond with ONLY a JSON object — no markdown, no explanation:\n\n"
        "{\n"
        f'  "category": one of {VALID_CATEGORIES},\n'
        '  "priority": one of "High", "Medium", "Low",\n'
        '  "ai_summary": a professional 1-2 sentence summary written the way a support agent would '
        'log it (state what the client needs/reports and the impact, e.g. '
        '"Client reports website login failure preventing customer access and requests urgent technical support.")\n'
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
    Classifies free-text chat input into one of VALID_INTENTS.
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
small_talk
thanks
compliment
follow_up
services_info
pricing
cancel
other

Examples:
"hi" -> greeting
"hello" -> greeting
"hey" -> greeting
"how are you" -> small_talk
"how are u" -> small_talk
"how's it going" -> small_talk
"thanks" -> thanks
"thank you" -> thanks
"i love you" -> compliment
"you're awesome" -> compliment
"good bot" -> compliment
"who are you" -> faq
"what can you do" -> faq
"what services do you offer" -> services_info
"what kind of work do you do" -> services_info
"show my tickets" -> status_check
"track my enquiry" -> status_check
"track my enquiry #4" -> status_check
"what's the status of my last request" -> status_check
"I need a website" -> new_enquiry
"I need ERP software" -> new_enquiry
"My website login page is broken" -> new_enquiry
"My app crashes when I login" -> new_enquiry
"Payment gateway is not working" -> new_enquiry
"There is a bug on my website" -> new_enquiry
"My ERP software has issues" -> new_enquiry
"My website is down" -> new_enquiry
"can't login" -> new_enquiry
"cannot login" -> new_enquiry
"any update on ticket 23" -> follow_up
"cancel" -> cancel
"never mind" -> cancel
"actually forget it, I don't want to raise this" -> cancel
"tell me a joke" -> other
"is there a tracking id I can use" -> faq
"how do I track my enquiry" -> faq
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

        # Problem-language should always win over a vague follow_up/other guess
        if keyword_intent == "new_enquiry" and result.get("intent") in ["follow_up", "other"]:
            result["intent"] = "new_enquiry"

        if result.get("intent") not in VALID_INTENTS:
            result["intent"] = keyword_intent

        print("INTENT DETECTED:", result)
        return result

    except Exception as e:
        print("⚠️  Intent detection failed:", e)
        return {"intent": _keyword_intent(text)}


# ─────────────────────────────────────────────────
# CHATBOT FREE-TEXT REPLY — for greeting / small_talk / thanks /
# compliment / faq / services_info / pricing / other intents
# ─────────────────────────────────────────────────
def generate_chat_reply(message: str, intent: str = None) -> str:
    """
    Returns a conversational reply for free-text chat messages.
    `intent` can be passed in if already known (e.g. from detect_intent),
    otherwise it's computed here. Canned replies handle the "small talk"
    style intents instantly (fast + consistent); everything else that
    needs real language goes to Groq if available.
    """
    if intent is None:
        intent = detect_intent(message).get("intent", "other")

    # Fast, consistent canned replies — no need to hit the LLM for these
    if intent == "greeting":
        return "Hello 👋\nHow can I help you today?"

    if intent == "small_talk":
        return "I'm doing great 😊\nThanks for asking. How can I assist you today?"

    if intent == "compliment":
        return "😊 Thank you!\nI'm always happy to help with your software enquiries."

    if intent == "thanks":
        return "You're welcome!\nFeel free to ask if you need anything else."

    if intent == "pricing":
        if not GROQ_API_KEY:
            return PRICING_TEXT
        # let Groq phrase it, but ground it with the same numbers
        base_prompt = (
            "Rephrase the following pricing information in a friendly, professional, "
            "concise way (max 80 words). Keep all the numbers exactly as given. "
            "End by explaining the final quote depends on project scope.\n\n"
            f"{PRICING_TEXT}\n\nCustomer question: {message}"
        )
        try:
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": base_prompt}],
                    "temperature": 0.4,
                    "max_tokens": 200,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip() or PRICING_TEXT
        except Exception as e:
            print("Pricing reply generation failed:", e)
            return PRICING_TEXT

    if not GROQ_API_KEY:
        if intent in ("faq", "services_info"):
            return (
                "I'm Eva, the Enquiry Portal assistant. "
                "I can help with websites, web apps, mobile apps, ERP systems and support enquiries."
            )
        return FALLBACK_UNKNOWN_TEXT

    prompt = f"""You are Eva, a customer support assistant for our software company.

Company services: Website Development, Web Applications, Mobile Applications,
ERP Systems, CRM Systems, E-Commerce, Cloud, Automation, AI Solutions,
API Integration, Hosting, Maintenance, Technical Support, Software Consulting.

You can naturally:
- greet users
- make small talk briefly and steer back to how you can help
- answer pricing questions (use these figures if relevant: Website from ₹10,000;
  Business website ₹25,000–₹75,000; Mobile app ₹50,000+; ERP/CRM depends on modules;
  final quote depends on scope)
- answer questions about our services and how the enquiry portal works
- respond briefly and warmly to compliments and thanks
- politely redirect anything unrelated to our company/services back to raising an
  enquiry or asking about our services — do not answer general knowledge, personal,
  or off-topic questions

Rules:
- Do NOT repeatedly re-introduce yourself ("I'm Eva...") in every message.
- Be friendly, natural, and concise — maximum 80 words.
- Do not invent pricing beyond what's given above.
- If key information is missing for an enquiry, ask one short follow-up question.
- Sound like a real support agent, not a generic chatbot.

Customer Message:
{message}
"""

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 200,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip() or FALLBACK_UNKNOWN_TEXT
    except Exception as e:
        print("Support Agent Error:", e)
        return "Sorry, I'm having trouble answering right now."


# ─────────────────────────────────────────────────
# CONVERSATION MEMORY HELPER
# ─────────────────────────────────────────────────
def merge_enquiry_context(existing_context: dict, new_message: str) -> dict:
    """
    Merges newly extracted info (category/priority/summary hints) from a new
    message into an existing in-progress enquiry context, without overwriting
    fields the user already confirmed earlier in the conversation.

    `existing_context` is expected to be a dict your routes/session layer
    persists between chat turns, e.g.:
        {"category": "Website", "priority": "Low", "description": "Need website."}

    NOTE: this function is stateless — YOUR routes/session code is
    responsible for storing/loading `existing_context` per conversation
    (e.g. in a Flask session, or a DB-backed chat session table).
    """
    existing_context = dict(existing_context or {})
    result = analyse(new_message)

    # Only fill in category if not already set (or was still "General")
    if not existing_context.get("category") or existing_context.get("category") == "General":
        existing_context["category"] = result["category"]

    # Priority should escalate, never downgrade, as new info comes in
    priority_rank = {"Low": 0, "Medium": 1, "High": 2}
    new_priority = result["priority"]
    old_priority = existing_context.get("priority", "Low")
    if priority_rank.get(new_priority, 0) > priority_rank.get(old_priority, 0):
        existing_context["priority"] = new_priority
    else:
        existing_context.setdefault("priority", new_priority)

    # Append to the running description instead of overwriting it
    prior_desc = existing_context.get("description", "").strip()
    existing_context["description"] = (prior_desc + " " + new_message).strip() if prior_desc else new_message

    # Re-summarise the combined description for a coherent final summary
    existing_context["ai_summary"] = analyse(existing_context["description"])["ai_summary"]

    return existing_context


# ─────────────────────────────────────────────────
# EMAIL REPLY GENERATION
# ─────────────────────────────────────────────────
def generate_response(enquiry):
    enquiry_id = getattr(enquiry, "id", None)
    id_line = f"Your enquiry ID is #{enquiry_id}.\n\n" if enquiry_id else ""

    fallback = (
        f"Dear {enquiry.customer_name},\n\n"
        "Thank you for contacting us.\n\n"
        f"We have received your enquiry regarding: {enquiry.ai_summary or enquiry.description}\n\n"
        f"{id_line}"
        "Our team has started reviewing the details and will update you shortly.\n\n"
        "Regards,\nSmart Enquiry Team"
    )

    if not GROQ_API_KEY:
        return fallback

    prompt = f"""Write a polite, professional first email reply for this client enquiry.
Follow this structure and tone:

Dear {enquiry.customer_name},

Thank you for contacting us.

We have received your enquiry regarding [brief restatement of the issue/request].

{"Your enquiry ID is #" + str(enquiry_id) + "." if enquiry_id else ""}

Our team has started reviewing the issue / your request and will update you shortly.

Regards,
Smart Enquiry Team

Rules:
- Keep it under 90 words.
- Do not promise pricing or timelines.
- Do not invent an enquiry ID if none is given above.

Client: {enquiry.customer_name}
Category: {enquiry.category}
Priority: {enquiry.priority}
Summary: {enquiry.ai_summary}
Original message:
\"\"\"{enquiry.description}\"\"\"
"""

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 200,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip() or fallback
    except Exception as e:
        print("Reply generation failed:", e)
        return fallback


def classify_and_summarise(text):
    result = analyse(text)

    class DraftEnquiry:
        customer_name = "Customer"
        description = text
        category = result["category"]
        priority = result["priority"]
        ai_summary = result["ai_summary"]

    return {
        "category": result["category"],
        "priority": result["priority"],
        "summary": result["ai_summary"],
        "suggested_reply": generate_response(DraftEnquiry()),
    }