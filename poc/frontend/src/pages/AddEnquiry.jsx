import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api/axios';

const EMPTY = {
  customer_name: '', phone: '', email: '', source: '',
  description: '', follow_up_date: '', notes: '',
};

export default function AddEnquiry() {
  const [form, setForm]     = useState(EMPTY);
  const [ai, setAi]         = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState('');
  const navigate            = useNavigate();
  const aiTimer             = useRef(null);

  function handleChange(e) {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: value }));
    if (name === 'description') {
      clearTimeout(aiTimer.current);
      aiTimer.current = setTimeout(() => liveClassify(value), 600);
    }
  }

  function liveClassify(text) {
    if (text.trim().length < 10) { setAi(null); return; }
    API.post('/api/classify', { text })
      .then(r => setAi(r.data))
      .catch(() => {});
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.customer_name || !form.description) {
      setError('Name and Description are required.'); return;
    }
    setLoading(true);
    try {
      await API.post('/api/enquiries', form);
      navigate('/enquiries');
    } catch {
      setError('Failed to save. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="row">
      <div className="col-md-7">
        <h5 className="mb-3">New Client Enquiry</h5>
        {error && <div className="alert alert-danger py-1 small">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="row g-2 mb-2">
            <div className="col-md-6">
              <label className="form-label form-label-sm">Client Name *</label>
              <input name="customer_name" value={form.customer_name} onChange={handleChange}
                className="form-control form-control-sm" placeholder="e.g. Rahul Sharma" required/>
            </div>
            <div className="col-md-6">
              <label className="form-label form-label-sm">Phone</label>
              <input name="phone" value={form.phone} onChange={handleChange}
                className="form-control form-control-sm" placeholder="+91 98765 43210"/>
            </div>
          </div>

          <div className="row g-2 mb-2">
            <div className="col-md-6">
              <label className="form-label form-label-sm">Email</label>
              <input name="email" value={form.email} onChange={handleChange}
                className="form-control form-control-sm" type="email"/>
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
              placeholder="Describe what the client is looking for..."/>
          </div>

          <div className="row g-2 mb-2">
            <div className="col-md-6">
              <label className="form-label form-label-sm">Follow-up Date</label>
              <input name="follow_up_date" value={form.follow_up_date} onChange={handleChange}
                className="form-control form-control-sm" type="date"/>
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
            <strong>🤖 AI Auto-Tag (live)</strong>
          </div>
          <div className="card-body">
            {!ai && <p className="text-muted small mb-0">Start typing the description to see AI suggestions...</p>}
            {ai && (
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
