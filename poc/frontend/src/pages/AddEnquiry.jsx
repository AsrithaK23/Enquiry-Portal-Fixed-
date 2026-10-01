import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api/axios';

const EMPTY = {
  customer_name: '', phone: '', email: '', source: '',
  description: '', follow_up_date: '', notes: '',
};

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function isGibberish(text) {
  if (!text || text.trim().length < 8) return true;
  const lower = text.toLowerCase();
  if (lower.includes('lorem ipsum')) return true;
  const latinWords = ['lorem', 'ipsum', 'dolor', 'sit', 'amet', 'consectetur', 'adipiscing', 'elit', 'sed', 'eiusmod', 'tempor', 'incididunt', 'labore', 'dolore', 'magna', 'aliqua'];
  const words = lower.match(/\b[a-z]{2,}\b/g) || [];
  const matches = words.filter(w => latinWords.includes(w)).length;
  if (matches >= 3) return true;
  if (/(.)\1{4,}/.test(lower)) return true;
  if (/\b[bcdfghjklmnpqrstvwxz]{6,}\b/i.test(lower)) return true;
  if (words.length >= 4 && new Set(words).size <= 2) return true;
  return false;
}

function getTodayLocal() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export default function AddEnquiry() {
  const [form, setForm]     = useState(EMPTY);
  const [ai, setAi]         = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState('');
  const navigate            = useNavigate();
  const aiTimer             = useRef(null);

  function handleChange(e) {
    const { name, value } = e.target;

    if (name === 'phone') {
      // Accept only digits, reject alphabets and symbols, max 15 digits
      const digitsOnly = value.replace(/\D/g, '').slice(0, 15);
      setForm(f => ({ ...f, phone: digitsOnly }));
      return;
    }

    setForm(f => ({ ...f, [name]: value }));

    if (name === 'description') {
      clearTimeout(aiTimer.current);
      aiTimer.current = setTimeout(() => liveClassify(value), 500);
    }
  }

  function liveClassify(text) {
    if (text.trim().length < 8) { setAi(null); return; }
    API.post('/api/classify', { text })
      .then(r => setAi(r.data))
      .catch(() => {});
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    // 1. Client Name check
    if (!form.customer_name.trim()) {
      setError('Client Name is required.');
      return;
    }

    // 2. Compulsory & Valid Email check
    const cleanEmail = form.email.trim();
    if (!cleanEmail) {
      setError('Email is compulsory.');
      return;
    }
    if (!EMAIL_REGEX.test(cleanEmail)) {
      setError('Please enter a valid email address (e.g. abc@xyz.in or name@example.com).');
      return;
    }

    // 3. Phone check (digits only, valid count)
    if (form.phone && (form.phone.length < 10 || form.phone.length > 15)) {
      setError('Phone number must contain between 10 and 15 digits.');
      return;
    }

    // 4. Description & Gibberish check
    if (!form.description.trim()) {
      setError('Description is required.');
      return;
    }
    if (isGibberish(form.description)) {
      setError('Please enter a legitimate enquiry description (no placeholder text, lorem ipsum, or random keysmash).');
      return;
    }

    // 5. Follow-up date validation (no past date allowed)
    const today = getTodayLocal();
    if (form.follow_up_date && form.follow_up_date < today) {
      setError('Follow-up date cannot be in the past. Please select today or a future date.');
      return;
    }

    setLoading(true);
    try {
      await API.post('/api/enquiries', {
        ...form,
        email: cleanEmail,
      });
      navigate('/enquiries');
    } catch (err) {
      const serverMsg = err.response?.data?.error || 'Failed to save enquiry. Please check your inputs.';
      setError(serverMsg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="row">
      <div className="col-md-7">
        <h5 className="mb-3">New Client Enquiry</h5>
        {error && <div className="alert alert-danger py-2 small">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="row g-2 mb-2">
            <div className="col-md-6">
              <label className="form-label form-label-sm">Client Name *</label>
              <input name="customer_name" value={form.customer_name} onChange={handleChange}
                className="form-control form-control-sm" placeholder="e.g. Rahul Sharma" required/>
            </div>
            <div className="col-md-6">
              <label className="form-label form-label-sm">Phone Number</label>
              <input name="phone" value={form.phone} onChange={handleChange}
                className="form-control form-control-sm" placeholder="10-digit number (e.g. 9876543210)"
                maxLength={15} />
              <small className="text-muted d-block" style={{ fontSize: '11px', marginTop: '2px' }}>
                Digits only (no letters or symbols)
              </small>
            </div>
          </div>

          <div className="row g-2 mb-2">
            <div className="col-md-6">
              <label className="form-label form-label-sm">Email *</label>
              <input name="email" value={form.email} onChange={handleChange}
                className="form-control form-control-sm" type="email" placeholder="e.g. abc@xyz.in" required/>
            </div>
            <div className="col-md-6">
              <label className="form-label form-label-sm">Source</label>
              <select name="source" value={form.source} onChange={handleChange}
                className="form-select form-select-sm">
                <option value="">-- Select --</option>
                <option>Website</option><option>Referral</option>
                <option>Phone Call</option><option>WhatsApp</option><option>Email</option>
              </select>
            </div>
          </div>

          <div className="mb-2">
            <label className="form-label form-label-sm">
              Description * <small className="text-muted">(AI classifies as you type)</small>
            </label>
            <textarea name="description" value={form.description} onChange={handleChange}
              className="form-control form-control-sm" rows="4" required
              placeholder="Describe what the client is looking for (no placeholder or gibberish)..."/>
          </div>

          <div className="row g-2 mb-2">
            <div className="col-md-6">
              <label className="form-label form-label-sm">Follow-up Date</label>
              <input name="follow_up_date" value={form.follow_up_date} onChange={handleChange}
                className="form-control form-control-sm" type="date" min={getTodayLocal()}/>
            </div>
          </div>

          <div className="mb-3">
            <label className="form-label form-label-sm">Initial Notes</label>
            <textarea name="notes" value={form.notes} onChange={handleChange}
              className="form-control form-control-sm" rows="2"/>
          </div>

          <button type="submit" className="btn btn-primary btn-sm" disabled={loading}>
            {loading ? 'Saving...' : 'Save Enquiry'}
          </button>
          <button type="button" className="btn btn-secondary btn-sm ms-2"
            onClick={() => navigate('/enquiries')}>Cancel</button>
        </form>
      </div>

      <div className="col-md-5">
        <div className="card mt-4">
          <div className="card-header bg-info text-white py-2">
            <strong>AI Auto-Tag (live)</strong>
          </div>
          <div className="card-body">
            {!ai && <p className="text-muted small mb-0">Start typing the description to see AI suggestions...</p>}
            {ai && ai.is_legitimate === false && (
              <div className="alert alert-warning py-2 mb-0 small">
                <strong>Invalid Enquiry Content</strong>
                <div className="mt-1">{ai.rejection_reason || 'Please describe an actual project or issue.'}</div>
              </div>
            )}
            {ai && ai.is_legitimate !== false && (
              <table className="table table-sm table-bordered mb-0">
                <tbody>
                  <tr><th>Category</th><td><span className="badge bg-dark">{ai.category}</span></td></tr>
                  <tr><th>Priority</th>
                    <td>
                      <span className={`badge bg-${ai.priority==='High'?'danger':ai.priority==='Medium'?'warning':'success'}`}>
                        {ai.priority}
                      </span>
                    </td>
                  </tr>
                  <tr><th>AI Summary</th><td className="small text-muted">{ai.ai_summary}</td></tr>
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
