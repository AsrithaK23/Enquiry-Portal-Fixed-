import React, { useState, useEffect, useRef, useCallback } from 'react';
import API from '../api/axios';

const BADGE = { New:'primary','In Discussion':'warning',Quoted:'secondary',Closed:'success',Dropped:'danger' };
const PRI   = { High:'danger', Medium:'warning', Low:'success' };

export default function ClientChatbot({ user }) {
  const [messages,  setMessages]  = useState([]);
  const [input,     setInput]     = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [state,     setState]     = useState('identify');
  const [context,   setContext]   = useState({});
  const [loading,   setLoading]   = useState(false);
  const [started,   setStarted]   = useState(false);
  const [myEnquiries, setMyEnquiries] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Load "My Enquiries" side panel ──────────────────────────────────
  const loadMyEnquiries = useCallback(() => {
    if (!user?.client_id) { setMyEnquiries([]); return; }
    API.get(`/api/clients/${user.client_id}/enquiries`)
      .then(r => setMyEnquiries(r.data.enquiries || []))
      .catch(() => setMyEnquiries([]));
  }, [user]);

  useEffect(() => { loadMyEnquiries(); }, [loadMyEnquiries]);

async function startChat() {
  setLoading(true);

  try {
    const res = await API.post('/api/chat/start', {
      client_id: user.client_id,
      user_name: user.name,
    });

    setSessionId(res.data.session_id);
    setState(res.data.state);
    setContext(res.data.context || {});
    setMessages([
      {
        sender: 'bot',
        message: res.data.message,
        time: now(),
      },
    ]);
    setStarted(true);
  } catch {
    setMessages([
      {
        sender: 'bot',
        message: 'Could not connect. Is the backend running?',
        time: now(),
      },
    ]);
    setStarted(true);
  }

  setLoading(false);
}

  async function sendMessage(e) {
    e?.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input.trim();
    setInput('');
    setMessages(m => [...m, { sender: 'user', message: userText, time: now() }]);
    setLoading(true);

    try {
      const res = await API.post('/api/chat/message', {
        session_id: sessionId, message: userText, state, context,
      });
      setState(res.data.state);
      setContext(res.data.context || {});
      setMessages(m => [...m, { sender: 'bot', message: res.data.message, time: now() }]);

      if (res.data.enquiry_id) {
        loadMyEnquiries();
      }
    } catch {
      setMessages(m => [...m, { sender: 'bot', message: '⚠️ Something went wrong on my end — please try again in a moment.', time: now() }]);
    }
    setLoading(false);
  }

  function now() {
    return new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  }

  // Quick-reply pills per state
  const quickReplies = {
    returning: ['Raise a new enquiry', 'Check status'],
    confirm:   ['yes', 'no'],
    done:      ['Raise another enquiry', 'Check status'],
  };

  function pillClick(text) {
    if (text === 'Raise a new enquiry') return submitDirect('I want to raise a new enquiry');
    if (text === 'Check status')        return submitDirect('What is the status of my enquiries?');
    return submitDirect(text);
  }

  // Send a value directly (used by quick-reply pills)
  async function submitDirect(text) {
    if (loading) return;
    setMessages(m => [...m, { sender: 'user', message: text, time: now() }]);
    setLoading(true);
    try {
      const res = await API.post("/api/chat/message", {
        session_id: sessionId,
        message: text,
        state: state,
        context: context,
      });
      setState(res.data.state);
      setContext(res.data.context || {});
      setMessages(m => [...m, { sender: 'bot', message: res.data.message, time: now() }]);
      if (res.data.enquiry_id) loadMyEnquiries();
    } catch {
      setMessages(m => [...m, { sender: 'bot', message: '⚠️ Something went wrong — please try again.', time: now() }]);
    }
    setLoading(false);
  }

  function formatText(text) {
    return text.split('\n').map((line, li) => (
      <div key={li}>
        {line.split('**').map((part, i) =>
          i % 2 === 1 ? <strong key={i}>{part}</strong> : part
        )}
      </div>
    ));
  }

  function renderMessage(msg, i) {
    const isBot = msg.sender === 'bot';
    return (
      <div key={i} className={`d-flex mb-2 ${isBot ? 'justify-content-start' : 'justify-content-end'}`}>
        {isBot && <div style={S.botAvatar}>E</div>}
        <div style={{ ...(isBot ? S.botBubble : S.userBubble), maxWidth: '78%' }}>
          {formatText(msg.message)}
          <div style={{ fontSize: 10, opacity: .55, marginTop: 4, textAlign: isBot ? 'left' : 'right' }}>
            {msg.time}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container-fluid py-3">
      <div className="row g-3">

        {/* ── CHAT (Messenger style) ── */}
        <div className="col-lg-7">
          <div style={S.card}>
            {/* Header */}
            <div style={S.header}>
              <div style={S.headerAvatar}>E</div>
              <div className="flex-grow-1">
                <div style={{ fontWeight: 700, fontSize: 15 }}>Eva</div>
                <div style={{ fontSize: 11, opacity: .85 }}>
                  {loading ? 'typing…' : 'Online · Enquiry Portal Assistant'}
                </div>
              </div>
            </div>

            {/* Messages */}
            <div style={S.messages}>
              {!started ? (
                <div className="text-center py-5">
                  <div style={S.headerAvatar2}>E</div>
                  <h6 className="mt-3 mb-1">Chat with Eva</h6>
                  <p className="small text-muted">Your AI assistant for enquiries &amp; support</p>
                  <button className="btn btn-primary" onClick={startChat} disabled={loading}>
                    {loading ? 'Connecting…' : 'Start Chat'}
                  </button>
                </div>
              ) : (
                <>
                  {messages.map(renderMessage)}
                  {loading && (
                    <div className="d-flex mb-2">
                      <div style={S.botAvatar}>E</div>
                      <div style={{ ...S.botBubble, padding: '10px 16px' }}>
                        <span style={S.typingDot}>●</span>
                        <span style={{ ...S.typingDot, animationDelay: '.15s' }}>●</span>
                        <span style={{ ...S.typingDot, animationDelay: '.3s' }}>●</span>
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef}/>
                </>
              )}
            </div>

            {/* Quick reply pills */}
            {started && quickReplies[state] && !loading && (
              <div style={S.pillRow}>
                {quickReplies[state].map(q => (
                  <button key={q} style={S.pill} onClick={() => pillClick(q)}>{q}</button>
                ))}
              </div>
            )}

            {/* Input */}
            {started && (
              <form onSubmit={sendMessage} style={S.inputRow}>
                <input
                  style={S.input}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder={state === 'done' ? 'Type "menu" for options…' : 'Type a message…'}
                  disabled={loading}
                  autoFocus
                />
                <button style={S.sendBtn} type="submit" disabled={loading || !input.trim()}>
                  ➤
                </button>
              </form>
            )}
          </div>
          <style>{`
            @keyframes blink { 0%,80%,100% {opacity:.2;} 40% {opacity:1;} }
          `}</style>
        </div>

        {/* ── MY ENQUIRIES SIDE PANEL ── */}
        <div className="col-lg-5">
          <div className="card">
            <div className="card-header bg-dark text-white py-2 d-flex justify-content-between align-items-center">
              <strong>📂 My Enquiries</strong>
              <button className="btn btn-sm btn-outline-light" onClick={loadMyEnquiries}>Refresh</button>
            </div>
            <div className="card-body p-2" style={{ maxHeight: 560, overflowY: 'auto' }}>
              {myEnquiries === null && <p className="text-muted small mb-0">Loading...</p>}
              {myEnquiries?.length === 0 && (
                <p className="text-muted small mb-0">
                  No enquiries yet. Chat with Eva to raise your first one — it'll show up here.
                </p>
              )}
              {myEnquiries?.map(e => (
                <div key={e.id} className="border rounded p-2 mb-2">
                  <div className="d-flex justify-content-between align-items-start mb-1">
                    <strong className="small">#{e.id} · {e.category}</strong>
                    <span className={`badge bg-${BADGE[e.status]||'secondary'}`}>{e.status}</span>
                  </div>
                  <div className="small text-muted mb-1">{e.ai_summary || e.description.slice(0,80)}</div>
                  <div className="d-flex justify-content-between small">
                    <span className={`badge bg-${PRI[e.priority]||'secondary'}`}>{e.priority}</span>
                    <span className="text-muted">{e.created_at}</span>
                  </div>
                  {e.follow_up_date && (
                    <div className="small text-muted mt-1">📅 Next follow-up: {e.follow_up_date}</div>
                  )}
                  {e.notes && (
                    <div className="small mt-1" style={{ background:'#f8f9fa', borderRadius:6, padding:'4px 8px' }}>
                      <strong>Note from team:</strong> {e.notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Email channel info */}
          <div className="card mt-3">
            <div className="card-header py-2"><strong>✉️ Prefer email?</strong></div>
            <div className="card-body p-2 small text-muted">
              You can also email us directly — our system automatically reads incoming emails,
              creates an enquiry on your behalf, and replies with your enquiry ID.
              Anything you email us will also appear in this list.
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

const S = {
  card: {
    background: '#fff', borderRadius: 14, overflow: 'hidden',
    boxShadow: '0 4px 20px rgba(0,0,0,.06)', display: 'flex', flexDirection: 'column',
    height: 640,
  },
  header: {
    display: 'flex', alignItems: 'center', gap: 10,
    background: 'linear-gradient(135deg,#6c63ff,#5347d6)', color: '#fff', padding: '12px 16px',
  },
  headerAvatar: {
    width: 36, height: 36, borderRadius: '50%', background: 'rgba(255,255,255,.2)',
    display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 16, flexShrink: 0,
  },
  headerAvatar2: {
    width: 56, height: 56, borderRadius: '50%', background: '#6c63ff', color: '#fff',
    display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 22, margin: '0 auto',
  },
  messages: {
    flex: 1, overflowY: 'auto', padding: '14px 14px 6px', background: '#f5f6fa',
  },
  botAvatar: {
    width: 28, height: 28, borderRadius: '50%', background: '#6c63ff', color: '#fff',
    display: 'grid', placeItems: 'center', fontWeight: 700, fontSize: 12,
    marginRight: 8, flexShrink: 0, alignSelf: 'flex-end',
  },
  botBubble: {
    background: '#fff', borderRadius: '14px 14px 14px 4px', padding: '10px 14px',
    fontSize: 13.5, lineHeight: 1.55, boxShadow: '0 1px 2px rgba(0,0,0,.06)', whiteSpace: 'pre-wrap',
  },
  userBubble: {
    background: '#6c63ff', color: '#fff', borderRadius: '14px 14px 4px 14px',
    padding: '10px 14px', fontSize: 13.5, lineHeight: 1.55, whiteSpace: 'pre-wrap',
  },
  pillRow: {
    display: 'flex', gap: 8, padding: '8px 14px', flexWrap: 'wrap',
    borderTop: '1px solid #eee', background: '#fff',
  },
  pill: {
    border: '1.5px solid #6c63ff', color: '#6c63ff', background: '#fff',
    borderRadius: 20, padding: '6px 16px', fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
  },
  inputRow: {
    display: 'flex', gap: 8, padding: 10, borderTop: '1px solid #eee', background: '#fff',
  },
  input: {
    flex: 1, border: '1px solid #ddd', borderRadius: 24, padding: '10px 16px',
    fontSize: 13.5, outline: 'none',
  },
  sendBtn: {
    width: 40, height: 40, borderRadius: '50%', border: 'none',
    background: '#6c63ff', color: '#fff', fontSize: 16, cursor: 'pointer', flexShrink: 0,
  },
  typingDot: {
    display: 'inline-block', marginRight: 3, animation: 'blink 1.2s infinite', color: '#9089b5',
  },
};
