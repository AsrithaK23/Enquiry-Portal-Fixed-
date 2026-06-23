from models import db, ConversationThread
from datetime import datetime

def check_and_register_thread(client_email: str, category: str) -> bool:
    """
    Returns True if this is the FIRST contact for this client+category.
    Registers or updates the thread record accordingly.
    """
    email_lower = client_email.lower().strip()
    
    thread = ConversationThread.query.filter_by(
        client_email=email_lower,
        category=category
    ).first()
    
    if thread is None:
        # First time this client contacts about this category
        new_thread = ConversationThread(
            client_email=email_lower,
            category=category
        )
        db.session.add(new_thread)
        db.session.commit()
        return True   # → auto-send
    else:
        # Follow-up on same issue
        thread.contact_count += 1
        thread.last_contact_at = datetime.utcnow()
        db.session.commit()
        return False  # → manual queue