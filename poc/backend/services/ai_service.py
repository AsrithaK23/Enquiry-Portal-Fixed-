"""
AI Service — Smart Client Enquiry Portal
-----------------------------------------
Uses Groq API (openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b) for real classification + summaries.
Falls back to keyword-based logic automatically if GROQ_API_KEY is not set,
or if the API call fails for any reason — so the app never breaks.
"""
from dotenv import load_dotenv
from pathlib import Path
import os
import re
import json
from groq import Groq

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
PRIMARY_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
CANDIDATE_MODELS = [
    PRIMARY_MODEL,
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]

_groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def _generate_with_groq(prompt: str = None, messages: list = None, json_mode: bool = False, temperature: float = 0.2, max_tokens: int = 500) -> str:
    """
    Calls Groq chat completion API with automatic candidate model fallback.
    Supports json_mode=True (response_format={'type': 'json_object'}).
    Supports either prompt string or full messages list.
    """
    if not _groq_client:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    if not messages:
        messages = [{"role": "user", "content": prompt or ""}]

    last_err = None
    seen = set()
    for model_name in CANDIDATE_MODELS:
        if not model_name or model_name in seen:
            continue
        seen.add(model_name)
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = _groq_client.chat.completions.create(**kwargs)
            if response and response.choices:
                content = response.choices[0].message.content or ""
                return content.strip()
        except Exception as e:
            last_err = e
            continue

    if last_err:
        raise last_err
    raise RuntimeError("No Groq models responded successfully.")

VALID_CATEGORIES = [
    "Website", "Web App", "Mobile App", "ERP/CRM", "Support",
    "E-Commerce", "Cloud", "Automation", "AI Solution",
    "API Integration", "Hosting", "Maintenance", "General",
]
VALID_PRIORITIES = ["High", "Medium", "Low"]
VALID_INTENTS = [
    "new_enquiry",
    "status_check",
    "edit_delete_query",
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

SUPPORT_CONTACT_MSG = "To edit or delete an existing enquiry, please reach out to : nas4.crm@gmail.com and our team will be happy to assist you."

LOREM_IPSUM_WORDS = {
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit",
    "sed", "eiusmod", "tempor", "incididunt", "labore", "dolore", "magna", "aliqua",
    "enim", "minim", "veniam", "quis", "nostrud", "exercitation", "ullamco", "laboris",
    "nisi", "aliquip", "commodo", "consequat", "duis", "aute", "irure", "reprehenderit",
    "voluptate", "velit", "cillum", "fugiat", "nulla", "pariatur", "excepteur", "sint",
    "occaecat", "cupidatat", "non", "proident", "sunt", "culpa", "officia", "deserunt",
    "mollit", "anim", "id", "est", "laborum"
}

PLACEHOLDER_PHRASES = [
    "dummy text", "sample text", "placeholder text", "test enquiry",
    "test message", "random text", "testing 123", "just testing",
    "asdf asdf", "qwerty qwerty", "foo bar", "foobar", "blah blah",
    "nothing much", "test test", "sample enquiry", "asdfghjkl", "qwertyuiop"
]


def is_start_enquiry_phrase(text: str) -> bool:
    """
    Checks if the user's message is an expression of wanting to start or raise
    a new enquiry/ticket (e.g. clicking 'Raise a new enquiry', typing 'I want to raise a new enquiry',
    'raise enquiry', 'can I raise a ticket', 'new enquiry').
    """
    if not text:
        return False
    t = normalize_text(text).strip().lower()
    t_clean = re.sub(r"[^\w\s]", "", t).strip()

    exact_matches = {
        "raise a new enquiry", "raise a enquiry", "raise an enquiry",
        "raise new enquiry", "raise enquiry", "new enquiry", "create enquiry",
        "i want to raise a new enquiry", "i want to raise an enquiry",
        "i want to raise a enquiry", "i want to raise new enquiry",
        "i want to raise enquiry", "i want to create an enquiry",
        "i want to create a new enquiry", "i want to submit an enquiry",
        "i want to submit a new enquiry", "i would like to raise an enquiry",
        "i would like to raise a new enquiry", "i want to make an enquiry",
        "i have an enquiry", "i have a new enquiry", "i have a query",
        "start an enquiry", "start new enquiry", "submit an enquiry",
        "can i raise an enquiry", "can i raise a new enquiry",
        "can i submit an enquiry", "how can i raise an enquiry",
        "raise a query", "raise query", "new query",
    }
    if t_clean in exact_matches:
        return True

    patterns = [
        r"^(?:i\s+(?:want|need|would\s+like)\s+to\s+)?(?:raise|create|submit|make|start|open|post|log)\s+(?:a\s+|an\s+)?(?:new\s+)?(?:enquiry|inquiry|query|ticket|request)(?:\s+please)?$",
        r"^(?:raise|new|create|open|start)\s+(?:an?\s+)?(?:enquiry|inquiry|query|ticket|request)$",
        r"^(?:can|could)\s+i\s+(?:raise|create|submit|make|open)\s+(?:an?\s+)?(?:new\s+)?(?:enquiry|inquiry|query|ticket|request)(?:\s+here)?$",
        r"^(?:i\s+have|got)\s+(?:an?\s+)?(?:new\s+)?(?:enquiry|inquiry|query|question|ticket|request)$",
    ]
    for p in patterns:
        if re.match(p, t_clean):
            return True

    return False


def is_edit_delete_request(text: str) -> bool:
    """
    Detects if the user is asking to edit, update, modify, cancel, or delete an enquiry/query.
    """
    t = (text or "").lower().strip()
    if re.search(r"\b(edit|modify|update|change|delete|remove|cancel|drop|withdraw)\b.*\b(enquiry|enquiries|query|queries|ticket|tickets|request|requests)\b", t):
        return True
    if re.search(r"\b(delete|edit|modify|remove)\b\s*#?\d+", t):
        return True
    if any(p in t for p in [
        "edit query", "delete query", "edit enquiry", "delete enquiry",
        "edit ticket", "delete ticket", "cancel query", "cancel my query",
        "edit my query", "delete my query", "change my query", "modify query",
        "how to edit", "how to delete", "how can i edit", "how can i delete",
        "want to delete", "want to edit", "need to delete", "need to edit",
    ]):
        return True
    return False


def validate_enquiry_legitimacy(text: str) -> tuple[bool, str]:
    """
    Validates whether enquiry details are genuine requirements vs.
    lorem ipsum, keysmash, placeholder, or gibberish.
    Returns (is_legitimate: bool, reason: str).
    """
    if not text:
        return False, "Enquiry description cannot be empty."

    raw = text.strip()
    if len(raw) < 8:
        return False, "Enquiry description is too brief. Please provide a few more details."

    lower = raw.lower()

    # 1. Direct Lorem Ipsum phrase check
    if "lorem ipsum" in lower:
        return False, "Contains placeholder Lorem Ipsum text."

    # 2. Tokenize words
    words = re.findall(r"\b[a-z]{2,}\b", lower)
    if not words or len(words) < 2:
        return False, "Please provide a complete description with real words."

    # 3. Check for multiple Lorem Ipsum vocabulary words
    lorem_count = sum(1 for w in words if w in LOREM_IPSUM_WORDS)
    if lorem_count >= 3 or (len(words) >= 4 and (lorem_count / len(words)) >= 0.4):
        return False, "Contains placeholder Lorem Ipsum text."

    # 4. Known placeholder phrases (exact or short dummy input)
    clean_punct = re.sub(r"[^\w\s]", "", lower).strip()
    for phrase in PLACEHOLDER_PHRASES:
        if clean_punct == phrase or (len(words) <= 5 and re.search(rf"\b{re.escape(phrase)}\b", lower)):
            return False, f"Contains placeholder phrase '{phrase}'."

    # 5. Excessive repeated characters (e.g. aaaaa, zzzzz)
    if re.search(r"(.)\1{4,}", lower):
        return False, "Contains repetitive keyboard characters."

    # 6. Unbroken consonant clusters of 7+ letters (gibberish/keysmash like asdfghjkl, zxcvbnm, jvjldvblhdbv)
    if re.search(r"\b[bcdfghjklmnpqrstvwxz]{7,}\b", lower):
        return False, "Contains unrecognizable keyboard smash words."

    # 7. Repetitive single word spam (e.g., test test test test)
    if len(words) >= 4 and len(set(words)) <= 2:
        return False, "Contains repetitive filler words."

    return True, ""

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
    r"\bdown\b", r"\bcrash\b", r"\bcrashed\b", r"\bdata loss\b", r"\bsecurity\b",
]
MEDIUM_KEYWORDS = [r"this week", r"\bsoon\b", r"\bpriority\b", r"\bimportant\b", r"\bquickly\b", r"\bdeadline\b"]
LOW_PRIORITY_PATTERNS = [
    r"\bquote\b", r"\bpricing\b", r"\bestimate\b", r"\bhow much\b", r"\bcost\b",
    r"\bportfolio\b", r"\bbasic\b", r"\bsimple\b", r"\bsmall\b", r"\bhobby\b",
    r"\blanding page\b", r"\bblog\b", r"\bfuture\b", r"\bnext year\b", r"\bsometime\b",
    r"\bno rush\b", r"\bwhenever\b", r"\bexplor(e|ing)\b", r"\bjust wondering\b",
    r"\bquestion\b", r"\bbrochure\b", r"\btypo\b", r"\bminor\b", r"\bcosmetic\b",
    r"\blocal bakery\b", r"\blocal shop\b", r"\bstatic website\b", r"\binfo\b",
    r"\binformation\b", r"\bconsultation\b", r"\bgeneral\b"
]


def refine_priority(text: str, detected_priority: str) -> str:
    """
    Ensures that low priority enquiries are not inappropriately classified as Medium.
    """
    if not text:
        return detected_priority or "Low"

    t = normalize_text(text)

    # 1. High priority keywords take precedence
    for p in HIGH_KEYWORDS:
        if re.search(p, t):
            return "High"

    # 2. Check for low priority indicators
    has_low = any(re.search(p, t) for p in LOW_PRIORITY_PATTERNS)
    has_complex = any(re.search(p, t) for p in [r"\berp\b", r"\bcrm\b", r"\benterprise\b", r"\bcomplex\b", r"\bpayroll\b", r"\binventory system\b"])

    if has_low and not has_complex:
        return "Low"

    # 3. If detected as Medium, but lacks explicit urgency or complex business scope, default to Low
    if detected_priority == "Medium" and not has_complex:
        has_urgency = any(re.search(p, t) for p in MEDIUM_KEYWORDS)
        if not has_urgency:
            return "Low"

    return detected_priority or "Low"

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
    priority = "Low"
    for p in HIGH_KEYWORDS:
        if re.search(p, t):
            return "High"
    for p in MEDIUM_KEYWORDS:
        if re.search(p, t):
            priority = "Medium"
            break
    return refine_priority(text, priority)


def generate_summary(text):
    if not text:
        return "Customer sent an enquiry requiring review."
    cleaned = re.sub(r"(?im)^[ \t]*(subject|from|to|date|sent):[^\r\n]*[\r\n]?", "", text or "")
    cleaned = re.sub(r"(?m)^[ \t]*>[^\r\n]*[\r\n]?", "", cleaned)
    cleaned = re.sub(r"(?is)\nOn .*?wrote:\s*.*$", "", cleaned)
    # Strip greetings like "Hi sir,", "Dear team,"
    cleaned = re.sub(r"(?i)^(?:dear|hi|hello|hey)\s+[^,\n]+[,:\n]?", "", cleaned.strip()).strip()
    # Strip sign-offs
    cleaned = re.sub(r"(?i)(?:thanks|thank you|regards|best regards|cheers|sincerely)[^\n]*$", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    category = classify_category(text)
    # Extract the first substantive sentence
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned) if len(s.strip()) > 5]
    if sentences:
        core = sentences[0]
        if len(core) > 150:
            core = core[:147] + "..."
        return f"{category} enquiry regarding: {core}"
    return f"{category} enquiry requiring review."


def _keyword_analyse(text):
    summary = generate_summary(text)
    return {
        "category": classify_category(text),
        "priority": classify_priority(text),
        "ai_summary": summary,
    }


def _contains_any(t, words):
    return any(w in t for w in words)


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

    if is_edit_delete_request(t):
        return "edit_delete_query"

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
def _groq_analyse(text: str) -> dict:
    prompt = (
        "You are an assistant for a software company's client enquiry system.\n"
        "Analyze the customer's enquiry below and respond with ONLY a JSON object:\n\n"
        "{\n"
        f'  "category": one of {VALID_CATEGORIES},\n'
        '  "priority": one of "High", "Medium", "Low". Priority Rules:\n'
        '     * "High": System down, server crash, payment gateway broken, customers cannot login, production blocker, or explicit urgent timeline ("urgent", "asap", "immediately", "today", "emergency").\n'
        '     * "Medium": Complex enterprise solutions (ERP, CRM, custom multi-module portal), active bugs with a workaround, or major projects with explicit upcoming deadlines ("this week", "soon", "launching next month").\n'
        '     * "Low": General inquiries, quotes/pricing/cost estimates, simple/basic/portfolio websites, landing pages, blogs, minor cosmetic/text tweaks, future planning ("next year", "sometime in future"), non-urgent requests ("whenever", "no rush"), or any standard inquiry without immediate deadlines. NOTE: Default to "Low" for ordinary enquiries, quotes, and standard websites unless explicit urgency or enterprise complexity is stated.\n'
        '  "ai_summary": a concise 1-sentence summary (10-25 words) capturing what the customer needs or reports (e.g. "Customer requesting urgent fix for crashed yoga website ahead of Monday sale"). NEVER copy the raw text verbatim, and omit greetings, pleasantries, and email signatures,\n'
        '  "is_legitimate": boolean, true for any genuine customer request, enquiry, question, bug report, or business requirement (even if brief, general, or preliminary); false ONLY if the text is pure gibberish/keysmash (e.g. "jvjldvblhdbv"), Lorem Ipsum Latin filler, or explicit dummy/placeholder text (e.g. "dummy text", "asdfasdf").\n'
        '  "rejection_reason": string explaining why it is not legitimate if is_legitimate is false, otherwise null\n'
        "}\n\n"
        f"Enquiry:\n{text}"
    )

    response_text = _generate_with_groq(
        prompt,
        json_mode=True,
        temperature=0.2,
        max_tokens=350
    )
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
        clean_text = re.sub(r"\n?```$", "", clean_text).strip()

    result = json.loads(clean_text)

    if result.get("category") not in VALID_CATEGORIES:
        result["category"] = classify_category(text)
    raw_pri = result.get("priority")
    if raw_pri not in VALID_PRIORITIES:
        raw_pri = classify_priority(text)
    result["priority"] = refine_priority(text, raw_pri)

    if not result.get("ai_summary"):
        result["ai_summary"] = generate_summary(text)
    else:
        result["ai_summary"] = result["ai_summary"].strip()

    result["is_legitimate"] = bool(result.get("is_legitimate", True))
    result["rejection_reason"] = result.get("rejection_reason")
    return result


# ─────────────────────────────────────────────────
# PUBLIC ENTRY POINT — used everywhere (form, chatbot, email, dashboard)
# ─────────────────────────────────────────────────
def analyse(text: str) -> dict:
    if not text or len(text.strip()) < 3:
        return {
            "category": "General",
            "priority": "Low",
            "ai_summary": "",
            "is_legitimate": False,
            "rejection_reason": "Text is too short.",
        }

    is_legit, reason = validate_enquiry_legitimacy(text)
    if not is_legit:
        return {
            "category": "General",
            "priority": "Low",
            "ai_summary": "",
            "is_legitimate": False,
            "rejection_reason": reason,
        }

    if GROQ_API_KEY:
        try:
            res = _groq_analyse(text)
            if "is_legitimate" not in res:
                res["is_legitimate"] = True
            rej_reason = (res.get("rejection_reason") or "").lower()
            if not res["is_legitimate"] and any(term in rej_reason for term in ["vague", "detail", "brief", "short", "clarif", "specific", "insufficient", "actionable"]):
                res["is_legitimate"] = True
                res["rejection_reason"] = None
            if "priority" in res:
                res["priority"] = refine_priority(text, res["priority"])
            return res
        except Exception as e:
            print(f"[AI Service] Groq API call failed: {e}. Using keyword fallback.")

    kw = _keyword_analyse(text)
    kw["is_legitimate"] = True
    kw["rejection_reason"] = None
    return kw


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
edit_delete_query
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
"edit enquiry" -> edit_delete_query
"delete enquiry" -> edit_delete_query
"i want to delete my enquiry" -> edit_delete_query
"can i edit my query" -> edit_delete_query
"how can i delete ticket #14" -> edit_delete_query
"modify my previous request" -> edit_delete_query
"cancel my existing enquiry" -> edit_delete_query
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

Respond with ONLY a JSON object:
{{
  "intent": "..."
}}

Message:
{text}
"""

    try:
        response_text = _generate_with_groq(
            prompt,
            json_mode=True,
            temperature=0,
            max_tokens=150
        )
        clean_text = response_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text).strip()
        result = json.loads(clean_text)
        keyword_intent = _keyword_intent(text)

        # Problem-language should always win over a vague follow_up/other guess
        if keyword_intent == "new_enquiry" and result.get("intent") in ["follow_up", "other"]:
            result["intent"] = "new_enquiry"

        if result.get("intent") not in VALID_INTENTS:
            result["intent"] = keyword_intent

        return result

    except Exception as e:
        print("[AI Service] Intent detection fallback:", e)
        return {"intent": _keyword_intent(text)}


# ─────────────────────────────────────────────────
# CHATBOT FREE-TEXT REPLY — for greeting / small_talk / thanks /
# compliment / faq / services_info / pricing / other intents
# ─────────────────────────────────────────────────
def generate_chat_reply(message: str, intent: str = None, chat_history: list = None) -> str:
    """
    Returns a conversational reply for free-text chat messages.
    `intent` can be passed in if already known (e.g. from detect_intent),
    otherwise it's computed here.
    Supports multi-turn `chat_history` for natural, context-aware dialogue.
    """
    if intent is None:
        intent = detect_intent(message).get("intent", "other")

    if intent == "edit_delete_query" or is_edit_delete_request(message):
        return SUPPORT_CONTACT_MSG

    # Fast, consistent canned replies — no need to hit the LLM for simple greetings
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
        
        base_prompt = (
            "Rephrase the following pricing information in a friendly, professional, "
            "concise way (max 80 words). Keep all the numbers exactly as given. "
            "End by explaining the final quote depends on project scope.\n\n"
            f"{PRICING_TEXT}\n\nCustomer question: {message}"
        )
        try:
            response_text = _generate_with_groq(
                base_prompt,
                temperature=0.4,
                max_tokens=200
            )
            return response_text.strip() or PRICING_TEXT
        except Exception as e:
            print("[AI Service] Pricing reply generation failed:", e)
            return PRICING_TEXT

    if not GROQ_API_KEY:
        if intent in ("faq", "services_info"):
            return (
                "I'm Eva, the Enquiry Portal assistant. "
                "I can help with websites, web apps, mobile apps, ERP systems and support enquiries."
            )
        return FALLBACK_UNKNOWN_TEXT

    system_prompt = f"""You are Eva, an intelligent customer support assistant for our software company.

Company services: Website Development, Web Applications, Mobile Applications,
ERP Systems, CRM Systems, E-Commerce, Cloud, Automation, AI Solutions,
API Integration, Hosting, Maintenance, Technical Support, Software Consulting.

Capabilities:
- Greet users and answer queries in natural, friendly, conversational language.
- Answer pricing questions: Website from ₹10,000; Business website ₹25,000–₹75,000;
  Mobile app ₹50,000+; ERP/CRM depends on modules; final quote depends on scope.
- If the user asks to edit, update, modify, cancel, or delete an existing enquiry or query, reply: "To edit or delete an existing enquiry, please reach out to : nas4.crm@gmail.com".
- Answer questions about our company, software services, and enquiry process.
- If the customer corrects you or gives feedback, adapt smoothly without repeating rigid canned lines.
- Keep responses friendly, natural, and concise (under 80 words).
- Sound like a real consultant, not a robotic script.
"""

    groq_msgs = [{"role": "system", "content": system_prompt}]
    if chat_history:
        for h in chat_history[-6:]:
            if isinstance(h, dict) and "role" in h and "content" in h:
                groq_msgs.append({"role": h["role"], "content": h["content"]})
    groq_msgs.append({"role": "user", "content": message})

    try:
        response_text = _generate_with_groq(
            messages=groq_msgs,
            temperature=0.7,
            max_tokens=220
        )
        return response_text.strip() or FALLBACK_UNKNOWN_TEXT
    except Exception as e:
        print("[AI Service] Support Agent Error:", e)
        return "Sorry, I'm having trouble answering right now."


def refine_enquiry_with_feedback(current_context: dict, user_feedback: str) -> dict:
    """
    Learns from user feedback/corrections to update an in-progress enquiry draft.
    Takes existing context and incorporates user modifications via Groq LLM.
    """
    current_context = dict(current_context or {})
    cat = current_context.get("category", "General")
    prio = current_context.get("priority", "Medium")
    desc = current_context.get("description", "")
    summ = current_context.get("ai_summary", "")

    if not GROQ_API_KEY:
        return merge_enquiry_context(current_context, user_feedback)

    prompt = f"""You are Eva, an intelligent customer support assistant for a software company.
A customer has an in-progress enquiry draft:
- Current Category: {cat}
- Current Priority: {prio}
- Current Description: {desc}
- Current Summary: {summ}

The customer just gave this feedback, correction, or additional requirement:
"{user_feedback}"

Update the enquiry details adaptively based on the customer's instruction.
Keep unchanged fields consistent, and update category, priority, description, or requirements as requested.

Respond with ONLY a JSON object:
{{
  "category": one of {VALID_CATEGORIES},
  "priority": "High" | "Medium" | "Low",
  "description": complete updated description combining previous details with the customer's changes,
  "ai_summary": concise 1-sentence summary (10-25 words) reflecting the updated requirement
}}
"""
    try:
        response_text = _generate_with_groq(prompt, json_mode=True, temperature=0.2, max_tokens=300)
        clean = response_text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean).strip()
        res = json.loads(clean)
        if res.get("category") not in VALID_CATEGORIES:
            res["category"] = cat
        if res.get("priority") not in VALID_PRIORITIES:
            res["priority"] = prio
        if not res.get("ai_summary"):
            res["ai_summary"] = summ
        res["is_legitimate"] = True
        return res
    except Exception as e:
        print("[AI Service] Refine enquiry feedback fallback:", e)
        return merge_enquiry_context(current_context, user_feedback)


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
    customer_name = getattr(enquiry, "customer_name", "Customer") or "Customer"
    summary = (getattr(enquiry, "ai_summary", "") or "").strip()
    if not summary:
        summary = generate_summary(getattr(enquiry, "description", ""))

    enquiry_id = getattr(enquiry, "id", None)
    id_line = f"Enquiry ID: #{enquiry_id}\n\n" if enquiry_id else ""

    return (
        f"Dear {customer_name},\n\n"
        "Thank you for contacting us.\n\n"
        f"We have received your enquiry regarding: {summary}\n\n"
        f"{id_line}"
        "Our team will reach back shortly to assist you.\n\n"
        "Best regards,\nSmart Enquiry Team"
    )


def generate_followup_draft(enquiry, customer_name="Customer", message_body=""):
    """
    Drafts an AI-assisted response for an employee to review and edit when
    a customer sends a follow-up reply in an ongoing email thread.
    """
    clean_body = re.sub(r"(?m)^[ \t]*>[^\r\n]*[\r\n]?", "", message_body or "")
    clean_body = re.sub(r"(?is)\nOn .*?wrote:\s*.*$", "", clean_body).strip()
    name = customer_name or getattr(enquiry, "customer_name", "Customer") or "Customer"

    if GROQ_API_KEY and clean_body:
        prompt = (
            "You are a professional customer support representative for a software services company.\n"
            f"The customer '{name}' sent this follow-up message in an ongoing email thread:\n"
            f"'''{clean_body}'''\n\n"
            "Draft a helpful, polite, and concise reply (2-4 sentences) addressing their follow-up message. "
            "Do not include placeholders like '[Your Name]' or '[Company Name]'. "
            "Sign off as 'Best regards,\nSmart Enquiry Team'."
        )
        try:
            draft = _generate_with_groq(prompt, temperature=0.4, max_tokens=250)
            if draft:
                return draft.strip()
        except Exception as e:
            print("[AI Service] Follow-up draft generation fallback:", e)

    return (
        f"Dear {name},\n\n"
        "Thank you for your update.\n\n"
        "We have received your message and our team is currently reviewing the details. "
        "We will get back to you with the next steps shortly.\n\n"
        "Best regards,\nSmart Enquiry Team"
    )


def classify_and_summarise(text, customer_name="Customer", enquiry_id=None):
    result = analyse(text)
    summary = (result.get("ai_summary") or "").strip() or generate_summary(text)

    class DraftEnquiry:
        pass

    draft_enq = DraftEnquiry()
    draft_enq.customer_name = customer_name or "Customer"
    draft_enq.description = text
    draft_enq.category = result["category"]
    draft_enq.priority = result["priority"]
    draft_enq.ai_summary = summary
    draft_enq.id = enquiry_id

    return {
        "category": result["category"],
        "priority": result["priority"],
        "summary": summary,
        "suggested_reply": generate_response(draft_enq),
    }