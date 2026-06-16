import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import API from '../api/axios';
import ActivityLog from '../components/ActivityLog';

const PRI    = { High:'danger', Medium:'warning', Low:'success' };
const BADGE  = { New:'primary','In Discussion':'warning',Quoted:'secondary',Closed:'success',Dropped:'danger' };
const STATUSES = ['New','In Discussion','Quoted','Closed','Dropped'];

export default function EditEnquiry() {
  const { id }     = useParams();
  const navigate   = useNavigate();
  const [enq,    setEnq]    = useState(null);
  const [form,   setForm]   = useState({ status:'', follow_up_date:'', notes:'' });
  const [saved,  setSaved]  = useState(false);
  const [error,  setError]  = useState('');
  const [genSum, setGenSum] = useState('');
  const [sumLoading, setSumLoading] = useState(false);

  useEffect(() => {
    API.get(`/api/enquiries/${id}`)
      .then(r => {
        setEnq(r.data);
        setForm({
          status:         r.data.status,
          follow_up_date: r.data.follow_up_date,
          notes:          r.data.notes,
        });
      })
      .catch(() => setError('Could not load enquiry.'));
  }, [id]);

  function handleChange(e) {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: value }));
  }

  async function handleUpdate(e) {
    e.preventDefault();
    try {
      const r = await API.put(`/api/enquiries/${id}`, form);
      setEnq(r.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError('Update failed.');
    }
  }

  async function generateSummary() {
    setSumLoading(true);
    try {
      const r = await API.post(`/api/enquiries/${id}/summarise`);
      setGenSum(r.data.ai_summary);
      const r2 = await API.get(`/api/enquiries/${id}`);
      setEnq(r2.data);
    } catch {
      setGenSum('Failed to generate summary.');
    } finally {
      setSumLoading(false);
    }
  }

  if (error) return <div className="alert alert-danger mt-3">{error}</div>;
  if (!enq)  return <p className="mt-3 text-muted">Loading...</p>;

  return (
    <div>
      <button className="btn btn-sm btn-secondary mb-3" onClick={() => navigate('/enquiries')}>
        ← Back to List
      </button>

      <div className="row g-3">
        <div className="col-md-7">

          <div className="card mb-3">
            <div className="card-header py-2 bg-dark text-white d-flex justify-content-between">
              <strong>Client Information</strong>
              {enq.client_id && (
                <Link to={`/clients/${enq.client_id}`} className="text-white small">
                  View Client Profile #{enq.client_id} →
                </Link>
              )}
            </div>
            <div className="card-body p-2">
              <table className="table table-sm table-bordered mb-0">
                <tbody>
                  <tr><th>Name</th><td>{enq.customer_name}</td><th>Phone</th><td>{enq.phone||'—'}</td></tr>
                  <tr><th>Email</th><td>{enq.email||'—'}</td><th>Source</th><td>{enq.source||'—'}</td></tr>
                  <tr><th>Created</th><td>{enq.created_at}</td><th>Updated</th><td>{enq.updated_at}</td></tr>
                  <tr>
                    <th>Status</th>
                    <td><span className={`badge bg-${BADGE[enq.status]||'secondary'}`}>{enq.status}</span></td>
                    <th>Priority</th>
                    <td><span className={`badge bg-${PRI[enq.priority]||'secondary'}`}>{enq.priority}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="card mb-3">
            <div className="card-header py-2 bg-info text-white"><strong>🤖 AI Insights</strong></div>
            <div className="card-body p-2">
              <table className="table table-sm table-bordered mb-0">
                <tbody>
                  <tr><th>Category</th><td><span className="badge bg-dark">{enq.category}</span></td></tr>
                  <tr><th>Priority</th><td><span className={`badge bg-${PRI[enq.priority]||'secondary'}`}>{enq.priority}</span></td></tr>
                  <tr><th>AI Summary</th><td className="small">{genSum || enq.ai_summary || '—'}</td></tr>
                </tbody>
              </table>
              <button className="btn btn-outline-info btn-sm mt-2" onClick={generateSummary} disabled={sumLoading}>
                {sumLoading ? 'Generating...' : '✨ Re-generate AI Summary'}
              </button>
            </div>
          </div>

          <div className="card mb-3">
            <div className="card-header py-2"><strong>Full Description</strong></div>
            <div className="card-body">
              <p className="small mb-0">{enq.description}</p>
            </div>
          </div>

          <div className="card">
            <div className="card-header py-2"><strong>Activity Timeline</strong></div>
            <div className="card-body py-2">
              <ActivityLog logs={enq.logs} />
            </div>
          </div>
        </div>

        <div className="col-md-5">
          <div className="card">
            <div className="card-header py-2 bg-success text-white"><strong>Update Enquiry</strong></div>
            <div className="card-body">
              {saved && <div className="alert alert-success py-1 small">✅ Saved!</div>}
              <form onSubmit={handleUpdate}>

                <div className="mb-2">
                  <label className="form-label form-label-sm">Status</label>
                  <select name="status" value={form.status} onChange={handleChange}
                    className="form-select form-select-sm">
                    {STATUSES.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>

                <div className="mb-2">
                  <label className="form-label form-label-sm">Next Action / Follow-up Date</label>
                  <input name="follow_up_date" value={form.follow_up_date} onChange={handleChange}
                    className="form-control form-control-sm" type="date"/>
                </div>

                <div className="mb-3">
                  <label className="form-label form-label-sm">Internal Notes / Remarks</label>
                  <textarea name="notes" value={form.notes} onChange={handleChange}
                    className="form-control form-control-sm" rows="6"
                    placeholder="Add meeting notes, quoted amount, next steps..."/>
                </div>

                <button type="submit" className="btn btn-success btn-sm w-100">
                  Save Changes
                </button>
              </form>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
