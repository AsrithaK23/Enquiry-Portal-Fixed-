import re
from flask import Blueprint, request, jsonify
from database import db
from models import Client, Enquiry, ActivityLog, ChatSession, ChatMessage
from services.ai_service import (
    analyse,
    detect_intent as _detect_intent,
    generate_chat_reply,
    is_edit_delete_request,
    is_start_enquiry_phrase,
    validate_enquiry_legitimacy,
    refine_enquiry_with_feedback,
    SUPPORT_CONTACT_MSG
)

chat_bp = Blueprint("chat", __name__)

BOT_NAME = "Eva"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NO_RE = re.compile(r"^(no|nope|nah|n)\b[\s,.\-:]*(.*)$", re.IGNORECASE)

QUICK_CANCEL_PHRASES = {
    "cancel", "stop", "nevermind", "never mind", "forget it",
    "forget that", "exit", "quit", "go back", "leave it", "drop it", "abort"
}

QUESTION_STARTERS = ("how ", "what ", "why ", "when ", "where ", "who ",
                     "can you", "do you", "does it", "is it", "are you",
                     "could you", "would you", "will you")
SCOPE_REPLY = "I can help with the Enquiry Portal: raising a software or service enquiry, checking its status, or answering questions about our services and pricing. What would you like help with?"


def get_session_history(session_id, limit=6):
    if not session_id:
        return []
    msgs = (
        ChatMessage.query.filter_by(session_id=session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    history = []
    for m in reversed(msgs):
        history.append({
            "role": "assistant" if m.sender == "bot" else "user",
            "content": m.message
        })
    return history


def detect_intent(user_input):
    result = _detect_intent(user_input)
    print("INTENT DETECTED:", result)
    return result


def looks_like_question(text):
    t = text.strip().lower()
    return t.endswith("?") or t.startswith(QUESTION_STARTERS)


def bot_reply(session, text):
    db.session.add(ChatMessage(session_id=session.id, sender="bot", message=text))


def user_msg(session, text):
    db.session.add(ChatMessage(session_id=session.id, sender="user", message=text))


def enquiry_card(e):
    lines = [
        f"🆔 Enquiry #{e.id} — {e.category} ({e.priority} priority)",
        f"   Status: {e.status}",
        f"   Raised on: {e.created_at.strftime('%d %b %Y')}",
    ]
    if e.follow_up_date:
        lines.append(f"   Next follow-up: {e.follow_up_date}")
    if e.ai_summary:
        lines.append(f"   Summary: {e.ai_summary}")
    if e.notes:
        lines.append(f"   Latest note from our team: {e.notes}")
    return "\n".join(lines)


def client_enquiry_list(client, detailed=False):
    enqs = (
        Enquiry.query.filter_by(client_id=client.id)
        .order_by(Enquiry.created_at.desc())
        .limit(5)
        .all()
    )
    if not enqs:
        return "You don't have any enquiries with us yet."
    if detailed:
        return "\n\n".join(enquiry_card(e) for e in enqs)
    lines = [f"• #{e.id} — {e.category} — {e.status} ({e.created_at.strftime('%d %b %Y')})" for e in enqs]
    return "\n".join(lines)


def resolve_client(session, context):
    """session.client_id is the durable, write-once value set in the DB at chat
    start — always prefer it over context.client_id, which is just a JSON value
    bounced between frontend and backend and can drift out of sync."""
    client = None

    if session.client_id:
        client = Client.query.get(session.client_id)

    if not client and context.get("client_id"):
        client = Client.query.get(context["client_id"])

    if not client and context.get("email"):
        client = Client.query.filter_by(email=context["email"]).first()

    return client


@chat_bp.route("/api/clients", methods=["GET"])
def list_clients():
    clients = Client.query.order_by(Client.created_at.desc()).all()
    result = []
    for c in clients:
        d = c.to_dict()
        d["enquiry_count"] = Enquiry.query.filter_by(client_id=c.id).count()
        result.append(d)
    return jsonify(result), 200


@chat_bp.route("/api/clients/<int:id>/enquiries", methods=["GET"])
def client_enquiries(id):
    client = Client.query.get_or_404(id)
    enqs = Enquiry.query.filter_by(client_id=id).order_by(Enquiry.created_at.desc()).all()
    return jsonify({
        "client": client.to_dict(),
        "enquiries": [e.to_dict(include_logs=False) for e in enqs],
    }), 200


@chat_bp.route("/api/chat/start", methods=["POST"])
def start_chat():
    data = request.get_json(silent=True) or {}
    client_id = data.get("client_id")
    user_name = data.get("user_name", "Customer")

    session = ChatSession(client_id=client_id)
    db.session.add(session)
    db.session.flush()

    client = Client.query.get(client_id) if client_id else None

    recent = ""
    recent_enquiries = []
    if client:
        recent_enquiries = (
            Enquiry.query
            .filter_by(client_id=client.id)
            .order_by(Enquiry.created_at.desc())
            .limit(5)
            .all()
        )
        if recent_enquiries:
            recent = "\n\n📂 Your recent enquiries:\n"
            for e in recent_enquiries:
                recent += f"• #{e.id} — {e.category} ({e.status})\n"

    # IMPORTANT: a Client row can exist (e.g. auto-created at signup or by an
    # inbound email) with zero enquiries yet. "Welcome back" should only show
    # when there's actual history to welcome them back to — otherwise every
    # brand-new signed-up user gets greeted as a returning customer.
    if client and recent_enquiries:
        greeting = (
            f"Welcome back, **{user_name}** 👋\n\n"
            f"I'm **{BOT_NAME}**, your virtual assistant."
            f"{recent}\n\n"
            "What would you like to do? Just tell me in your own words — for example "
            "*\"I need a new website\"* or *\"what's the status of my last request\"*."
        )
    else:
        greeting = (
            f"Hi {user_name}! 👋 I'm **{BOT_NAME}**, your virtual assistant.\n\n"
            "I can help you raise a new enquiry, check on an existing one, or answer "
            "questions about our services. What would you like to do?"
        )

    bot_reply(session, greeting)
    db.session.commit()

    return jsonify({
        "session_id": session.id,
        "state": "returning",
        "message": greeting,
        "context": {
            "client_id": client_id,
            "client_name": user_name,
            "email": client.email if client else None
        }
    }), 201


@chat_bp.route("/api/chat/message", methods=["POST"])
def chat_message():
    data       = request.get_json()
    session_id = data.get("session_id")
    user_input = (data.get("message") or "").strip()
    state      = data.get("state", "identify")
    context    = data.get("context", {})

    session = ChatSession.query.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    user_msg(session, user_input)

    # Global check: if user asks to edit or delete any query/enquiry
    if is_edit_delete_request(user_input):
        reply = SUPPORT_CONTACT_MSG
        bot_reply(session, reply)
        db.session.commit()
        return jsonify({"state": state, "message": reply, "context": context})

    if state != "identify" and user_input.lower() in QUICK_CANCEL_PHRASES:
        reply = "No problem — I've cancelled that. What else can I help you with?"
        bot_reply(session, reply)
        db.session.commit()
        return jsonify({"state": "returning", "message": reply, "context": context})

    if state == "identify":
        email = user_input.lower().strip()

        if not EMAIL_RE.match(email):
            reply = (
                "Hmm, that doesn't look like a valid email address 🤔\n\n"
                "Could you double-check and type it again? "
                "It should look something like *name@example.com*."
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "identify", "message": reply, "context": context})

        client = Client.query.filter_by(email=email).first()
        if client:
            session.client_id = client.id
            db.session.flush()
            past = client_enquiry_list(client)
            reply = (
                f"Good to see you again, **{client.name}**! 👋\n\n"
                f"Here's a quick look at your recent enquiries:\n{past}\n\n"
                "What would you like to do next? Just tell me in your own words."
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({
                "state": "returning", "message": reply,
                "context": {"email": email, "client_id": client.id, "client_name": client.name}
            })
        else:
            reply = (
                f"I couldn't find an account with **{email}** — no problem, "
                "let's get you set up. It only takes a moment. 🙂\n\n"
                "First, what's your **full name**?"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "new_name", "message": reply, "context": {"email": email}})

    elif state == "returning":
        intent = detect_intent(user_input).get("intent", "other")
        history = get_session_history(session.id)

        if intent == "edit_delete_query" or is_edit_delete_request(user_input):
            reply = SUPPORT_CONTACT_MSG
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "returning", "message": reply, "context": context})

        if intent == "greeting":
            reply = (
                f"Hey there! 👋 I'm {BOT_NAME}. I can help you raise a new enquiry, "
                "check on an existing one, or answer questions about how this works. "
                "What can I do for you?"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "returning", "message": reply, "context": context})

        elif intent in ("faq", "services_info"):
            reply = generate_chat_reply(user_input, intent=intent, chat_history=history)
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "returning", "message": reply, "context": context})

        elif intent in ("status_check", "follow_up"):
            client = resolve_client(session, context)
            detailed = client_enquiry_list(client, detailed=True) if client else "No enquiries found."
            reply = f"Here's the latest on your enquiries:\n\n{detailed}"
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "returning", "message": reply, "context": context})

        elif intent == "new_enquiry":
            # 1. Did the user express the intent to start/raise an enquiry?
            if is_start_enquiry_phrase(user_input):
                reply = (
                    "Absolutely 👍\n\nTell me a bit more about what you need and I'll create an enquiry for you. "
                    "(Type **cancel** anytime if you change your mind.)"
                )
                bot_reply(session, reply)
                db.session.commit()
                return jsonify({"state": "describe", "message": reply, "context": context})

            # 2. Check for actual lorem ipsum / keysmash / placeholder
            is_legit, reason = validate_enquiry_legitimacy(user_input)
            if not is_legit:
                reply = (
                    "It looks like your message contains placeholder or unrecognized text.\n\n"
                    "Could you please provide a legitimate enquiry describing what you need help with "
                    "(for example, the type of service, features needed, or issue faced)?"
                )
                bot_reply(session, reply)
                db.session.commit()
                return jsonify({"state": "describe", "message": reply, "context": context})

            ai_preview = analyse(user_input)
            if not ai_preview.get("is_legitimate", True):
                reply = (
                    "Could you please share a few more details about what you need "
                    "(for example, the type of service, features needed, or issue faced)?"
                )
                bot_reply(session, reply)
                db.session.commit()
                return jsonify({"state": "describe", "message": reply, "context": context})

            is_specific = len(user_input.strip()) >= 15 and ai_preview.get("category") != "General"

            if is_specific:
                context["description"] = user_input
                context["ai"] = ai_preview
                reply = (
                    "Thanks, that's really helpful! Here's how I've logged it on our side:\n\n"
                    f"🏷️ Service area: **{ai_preview['category']}**\n"
                    f"⚡ Priority: **{ai_preview['priority']}**\n"
                    f"📝 Summary: {ai_preview['ai_summary']}\n\n"
                    "Shall I go ahead and submit this to our team? (**yes** / **no** / **cancel**)"
                )
                bot_reply(session, reply)
                db.session.commit()
                return jsonify({"state": "confirm", "message": reply, "context": context})

            reply = (
                "Absolutely 👍\n\nTell me a bit more about what you need and I'll create an enquiry for you. "
                "(Type **cancel** anytime if you change your mind.)"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        elif intent == "pricing":
            reply = (
                "Typical pricing depends on requirements:\n\n"
                "🌐 Website:\n₹10,000 - ₹50,000+\n\n"
                "📱 Mobile App:\n₹50,000 - ₹5,00,000+\n\n"
                "🏢 ERP / CRM:\n₹1,00,000+\n\n"
                "If you tell me your exact requirements, I can help prepare a more accurate estimate."
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "returning", "message": reply, "context": context})

        else:
            reply = SCOPE_REPLY
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "returning", "message": reply, "context": context})

    elif state == "new_name":
        if len(user_input.strip()) < 2:
            reply = "Could you share your full name? Just so I know who I'm chatting with 🙂"
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "new_name", "message": reply, "context": context})

        context["name"] = user_input.strip()
        reply = f"Thanks, {user_input.strip()}! And what's the best **phone number** to reach you on? (type *skip* if you'd rather not)"
        bot_reply(session, reply)
        db.session.commit()
        return jsonify({"state": "new_phone", "message": reply, "context": context})

    elif state == "new_phone":
        context["phone"] = "" if user_input.lower() == "skip" else user_input.strip()
        reply = "And which **company** are you with, if any? (type *skip* if it's just you)"
        bot_reply(session, reply)
        db.session.commit()
        return jsonify({"state": "new_co", "message": reply, "context": context})

    elif state == "new_co":
        context["company"] = "" if user_input.lower() == "skip" else user_input.strip()
        reply = (
            "Perfect, you're all set up ✅\n\n"
            "Now, tell me — what can we help you with? Feel free to describe your "
            "issue or request in your own words, with as much detail as you can. "
            "(Type **cancel** anytime to stop.)"
        )
        bot_reply(session, reply)
        db.session.commit()
        return jsonify({"state": "describe", "message": reply, "context": context})

    elif state == "describe":
        intent = detect_intent(user_input).get("intent", "other")
        is_question = looks_like_question(user_input)
        history = get_session_history(session.id)

        if intent == "edit_delete_query" or is_edit_delete_request(user_input):
            reply = SUPPORT_CONTACT_MSG
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        if is_start_enquiry_phrase(user_input):
            reply = (
                "I'm ready! Please describe what you need help with — for example, "
                "are you looking to build a website, a mobile app, an ERP/CRM system, "
                "or do you have a technical bug or issue that needs fixing?"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        if intent in ("faq", "services_info", "greeting"):
            reply = (
                generate_chat_reply(user_input, intent=intent, chat_history=history)
                + "\n\nWhenever you're ready, just describe what you need and I'll log it for you."
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        if intent == "other" and is_question:
            reply = SCOPE_REPLY + "\n\nWhenever you're ready, describe the software or service issue and I'll log it."
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        if intent in ("status_check", "follow_up"):
            client = resolve_client(session, context)
            detailed = client_enquiry_list(client, detailed=True) if client else "No enquiries found yet."
            reply = (
                f"Here's the latest on your enquiries:\n\n{detailed}\n\n"
                "Whenever you're ready, go ahead and describe the new request and I'll log it."
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        # Check legitimacy of enquiry details (lorem ipsum, keysmash, gibberish)
        is_legit, reason = validate_enquiry_legitimacy(user_input)
        if not is_legit:
            reply = (
                "It looks like your message contains placeholder or unrecognized text.\n\n"
                "Could you please provide a legitimate enquiry describing what you need help with "
                "(for example, the type of service, features needed, or issue faced)?"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        ai = analyse(user_input)
        if not ai.get("is_legitimate", True):
            reply = (
                "Could you please share a few more details about what you need "
                "(for example, the type of service, features needed, or issue faced)?"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        if ai.get("category") == "General" and len(user_input.strip()) < 20:
            reply = (
                "Could you give me a bit more detail — for example, what kind of service this "
                "relates to (website, app, ERP, etc.) and what's going wrong or what you need?"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "describe", "message": reply, "context": context})

        context["description"] = user_input
        context["ai"] = ai

        reply = (
            "Thanks, that's really helpful! Here's how I've logged it on our side:\n\n"
            f"🏷️ Service area: **{ai['category']}**\n"
            f"⚡ Priority: **{ai['priority']}**\n"
            f"📝 Summary: {ai['ai_summary']}\n\n"
            "Shall I go ahead and submit this to our team? (**yes** / **no** / **cancel**)"
        )
        bot_reply(session, reply)
        db.session.commit()
        return jsonify({"state": "confirm", "message": reply, "context": context})

    elif state == "confirm":
        answer = user_input.strip().lower()

        if answer in ("yes", "y", "correct", "ok", "submit", "yeah", "yep"):
            try:
                client = resolve_client(session, context)
                if not client:
                    import uuid
                    guest_email = context.get("email") or f"guest-{uuid.uuid4().hex[:10]}@no-email.local"
                    client = Client(
                        name=context.get("name") or context.get("client_name", "Guest"),
                        email=guest_email,
                        phone=context.get("phone", ""),
                        company=context.get("company", ""),
                    )
                    db.session.add(client)
                    db.session.flush()

                session.client_id = client.id
                ai = context.get("ai", {})
                enq = Enquiry(
                    client_id=client.id,
                    customer_name=client.name,
                    phone=client.phone,
                    email=client.email,
                    source="Chatbot",
                    description=context.get("description", ""),
                    category=ai.get("category", "General"),
                    priority=ai.get("priority", "Medium"),
                    ai_summary=ai.get("ai_summary", ""),
                    status="New",
                )
                db.session.add(enq)
                db.session.flush()
                db.session.add(ActivityLog(
                    enquiry_id=enq.id,
                    action=f"Submitted via chatbot. Category: {enq.category}, Priority: {enq.priority}"
                ))

                eta = {
                    "High": "within a few hours",
                    "Medium": "within 1–2 business days",
                    "Low": "within 3–5 business days"
                }.get(enq.priority, "soon")
                reply = (
                    f"All done! ✅ Your enquiry has been logged as **#{enq.id}**.\n\n"
                    f"Based on the priority, someone from our team should get back to you {eta}. "
                    f"You can quote **#{enq.id}** any time you contact us about this.\n\n"
                    "Anything else? Just ask — I'm right here."
                )
                bot_reply(session, reply)
                db.session.commit()
                return jsonify({
                    "state": "returning", "message": reply,
                    "enquiry_id": enq.id, "client_id": client.id, "context": context
                })

            except Exception as e:
                db.session.rollback()
                print(f"[Chat Confirm Error]: {e}")
                reply = "Sorry, something went wrong while saving that. Could you try **yes** again?"
                bot_reply(session, reply)
                db.session.commit()
                return jsonify({"state": "confirm", "message": reply, "context": context})

        no_match = NO_RE.match(user_input.strip())
        if no_match:
            remainder = no_match.group(2).strip()

            if len(remainder) >= 5:
                current_draft = {
                    "category": context.get("ai", {}).get("category", "General"),
                    "priority": context.get("ai", {}).get("priority", "Medium"),
                    "description": context.get("description", ""),
                    "ai_summary": context.get("ai", {}).get("ai_summary", ""),
                }
                updated = refine_enquiry_with_feedback(current_draft, remainder)
                context["ai"] = updated
                context["description"] = updated.get("description", context.get("description", ""))
                reply = (
                    "No problem, I've updated your enquiry details:\n\n"
                    f"🏷️ Service area: **{updated['category']}**\n"
                    f"⚡ Priority: **{updated['priority']}**\n"
                    f"📝 Summary: {updated['ai_summary']}\n\n"
                    "Shall I go ahead and submit this instead? (**yes** / **no** / **cancel**)"
                )
                bot_reply(session, reply)
                db.session.commit()
                return jsonify({"state": "confirm", "message": reply, "context": context})

            reply = (
                "No problem! What would you like to adjust or add to the enquiry? "
                "Just tell me what needs changing and I'll update it for you. "
                "(Or type **cancel** anytime to discard this draft.)"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "confirm", "message": reply, "context": context})

        if is_edit_delete_request(user_input):
            reply = SUPPORT_CONTACT_MSG
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "confirm", "message": reply, "context": context})

        intent = detect_intent(user_input).get("intent", "other")
        is_question = looks_like_question(user_input)
        history = get_session_history(session.id)

        if intent in ("faq", "services_info", "pricing") or is_question:
            if intent == "pricing":
                answer_reply = (
                    "Typical pricing depends on requirements:\n\n"
                    "🌐 Website: ₹10,000 - ₹50,000+\n\n"
                    "📱 Mobile App: ₹50,000 - ₹5,00,000+\n\n"
                    "🏢 ERP / CRM: ₹1,00,000+\n\n"
                    "The final cost depends on features, integrations, design, and timelines."
                )
            else:
                answer_reply = generate_chat_reply(user_input, intent=intent, chat_history=history)

            reply = (
                f"{answer_reply}\n\n"
                "Getting back to your enquiry draft — shall I go ahead and submit this to our team? "
                "(**yes** / **no** / **cancel**)"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "confirm", "message": reply, "context": context})

        elif intent in ("status_check", "follow_up"):
            client = resolve_client(session, context)
            detailed = (
                client_enquiry_list(client, detailed=True)
                if client else
                "No enquiries found."
            )
            reply = (
                f"📋 Here's the latest on your enquiries:\n\n"
                f"{detailed}\n\n"
                "Getting back to the draft enquiry — should I submit it? "
                "(**yes** / **no** / **cancel**)"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "confirm", "message": reply, "context": context})

        # Adaptive feedback: User provides corrections, modifications, or extra requirements
        if len(user_input.strip()) >= 5:
            is_legit, reason = validate_enquiry_legitimacy(user_input)
            if not is_legit and len(user_input.strip()) > 15:
                reply = (
                    "It looks like your message contains placeholder or unrecognized text.\n\n"
                    "Could you clarify the changes you'd like to make to your enquiry, or reply **yes** to submit the current draft?"
                )
                bot_reply(session, reply)
                db.session.commit()
                return jsonify({"state": "confirm", "message": reply, "context": context})

            current_draft = {
                "category": context.get("ai", {}).get("category", "General"),
                "priority": context.get("ai", {}).get("priority", "Medium"),
                "description": context.get("description", ""),
                "ai_summary": context.get("ai", {}).get("ai_summary", ""),
            }
            updated = refine_enquiry_with_feedback(current_draft, user_input)
            context["ai"] = updated
            context["description"] = updated.get("description", context.get("description", ""))

            reply = (
                "Got it! I've updated your enquiry based on your feedback:\n\n"
                f"🏷️ Service area: **{updated['category']}**\n"
                f"⚡ Priority: **{updated['priority']}**\n"
                f"📝 Summary: {updated['ai_summary']}\n\n"
                "Shall I go ahead and submit this to our team? (**yes** / **no** / **cancel**)"
            )
            bot_reply(session, reply)
            db.session.commit()
            return jsonify({"state": "confirm", "message": reply, "context": context})

        reply = (
            "Just to confirm — should I submit this to our team?\n\n"
            "Reply with **yes** to submit, or tell me any changes you'd like to make. (Type **cancel** to discard.)"
        )
        bot_reply(session, reply)
        db.session.commit()
        return jsonify({"state": "confirm", "message": reply, "context": context})

    return jsonify({"error": "Unknown state"}), 400
