from models import db, ConversationThread, Enquiry, EmailLog
from datetime import datetime
import re
import uuid


def _message_ids(value):
    if not value:
        return []
    ids = re.findall(r"<[^>]+>", value)
    if not ids and value.strip():
        clean = value.strip()
        ids = [clean, f"<{clean}>"]
    return ids


def normalize_subject(subject: str) -> str:
    """
    Strips Re:, Fwd:, Fw:, [Enquiry #...], etc. to compare thread subjects.
    """
    if not subject:
        return ""
    s = subject.strip()
    while re.match(r"^(?:re|fwd|fw)\s*:\s*", s, flags=re.IGNORECASE):
        s = re.sub(r"^(?:re|fwd|fw)\s*:\s*", "", s, count=1, flags=re.IGNORECASE).strip()
    s = re.sub(r"\[\s*enquiry\s*#?\d+\s*\]", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\(\s*enquiry\s*#?\d+\s*\)", "", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip().lower()


def find_existing_enquiry_for_thread(client_email: str, message_id: str = "",
                                     in_reply_to: str = "", references: str = "",
                                     subject: str = "", body: str = ""):
    """
    Identifies if an incoming message belongs to an existing Enquiry.
    Uses RFC In-Reply-To/References, EmailLog, quoted enquiry IDs, and normalized subjects.
    """
    email_lower = (client_email or "").lower().strip()
    norm_subj = normalize_subject(subject)
    referenced_ids = _message_ids(references) + _message_ids(in_reply_to)

    previous = None

    # Signal 1: Check RFC In-Reply-To and References headers on Enquiry
    for referenced_id in referenced_ids:
        previous = Enquiry.query.filter(
            (Enquiry.inbound_message_id == referenced_id) |
            (Enquiry.thread_key == referenced_id)
        ).first()
        if previous:
            return previous

        # Signal 1b: Check EmailLog for outbound auto-reply or past thread message IDs
        log_entry = EmailLog.query.filter_by(message_id=referenced_id).first()
        if log_entry and log_entry.enquiry_id:
            previous = Enquiry.query.get(log_entry.enquiry_id)
            if previous:
                return previous

    # Signal 2: Check for quoted Enquiry ID in subject or body (e.g. "Enquiry #5")
    if email_lower:
        match_id = re.search(r"enquiry\s*#?\s*(\d+)", f"{subject} {body}", flags=re.IGNORECASE)
        if match_id:
            try:
                enquiry_id = int(match_id.group(1))
                candidate = Enquiry.query.filter_by(id=enquiry_id).first()
                if candidate and (candidate.email.lower() == email_lower or not candidate.email):
                    return candidate
            except Exception:
                pass

    # Signal 3: Match normalized subject for the same client
    if email_lower and norm_subj:
        client_enquiries = Enquiry.query.filter_by(email=email_lower).order_by(Enquiry.id.desc()).all()
        for candidate in client_enquiries:
            candidate_norm = normalize_subject(candidate.inbound_subject)
            if candidate_norm and candidate_norm == norm_subj:
                return candidate

    # Signal 4: Check if referenced_id exists in ConversationThread
    for referenced_id in referenced_ids:
        thread = ConversationThread.query.filter_by(thread_key=referenced_id).first()
        if thread:
            enq = Enquiry.query.filter(
                (Enquiry.thread_key == thread.thread_key) |
                (Enquiry.email == thread.client_email)
            ).order_by(Enquiry.id.desc()).first()
            if enq:
                return enq

    # Signal 5: If subject explicitly indicates a reply ("Re: ...") from a client with an existing enquiry
    is_reply_subject = bool(re.match(r"^(?:re|fwd|fw)\s*:\s*", (subject or "").strip(), flags=re.IGNORECASE))
    if is_reply_subject and email_lower:
        latest = Enquiry.query.filter_by(email=email_lower).order_by(Enquiry.id.desc()).first()
        if latest:
            return latest

    return None


def check_and_register_thread(client_email: str, category: str, message_id: str,
                              in_reply_to: str = "", references: str = "",
                              subject: str = "", body: str = "") -> tuple[bool, str, object]:
    """
    Determines if an incoming email is the start of a NEW conversation thread
    or a FOLLOW-UP reply in an existing thread.

    Returns (is_new_thread, thread_key, existing_enquiry).
    - If is_new_thread is True, the CRM sends an auto-reply.
    - If is_new_thread is False, existing_enquiry is returned and the CRM will
      NOT send an auto-reply, drafting a response for manual review instead.
    """
    email_lower = (client_email or "").lower().strip()
    referenced_ids = _message_ids(references) + _message_ids(in_reply_to)

    previous = find_existing_enquiry_for_thread(
        client_email=client_email,
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        subject=subject,
        body=body,
    )

    if previous:
        thread_key = previous.thread_key or previous.inbound_message_id or (referenced_ids[0] if referenced_ids else message_id)
        thread = ConversationThread.query.filter_by(thread_key=thread_key).first()
        if not thread:
            thread = ConversationThread.query.filter_by(client_email=email_lower).order_by(ConversationThread.id.desc()).first()

        if thread:
            thread.contact_count = (thread.contact_count or 1) + 1
            thread.last_contact_at = datetime.utcnow()
            db.session.commit()
        else:
            new_thread = ConversationThread(
                client_email=email_lower,
                category=category,
                thread_key=thread_key,
                contact_count=2,
            )
            db.session.add(new_thread)
            db.session.commit()

        return False, thread_key, previous

    # Check if thread exists in ConversationThread without existing enquiry
    for referenced_id in referenced_ids:
        thread = ConversationThread.query.filter_by(thread_key=referenced_id).first()
        if thread:
            thread.contact_count = (thread.contact_count or 1) + 1
            thread.last_contact_at = datetime.utcnow()
            db.session.commit()
            return False, referenced_id, None

    # Genuinely new thread
    thread_key = message_id or (referenced_ids[0] if referenced_ids else f"<{uuid.uuid4()}@local>")
    new_thread = ConversationThread(
        client_email=email_lower,
        category=category,
        thread_key=thread_key,
        contact_count=1,
    )
    db.session.add(new_thread)
    db.session.commit()
    return True, thread_key, None