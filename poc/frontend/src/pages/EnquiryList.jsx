import React, { useEffect, useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import API from '../api/axios';

const BADGE   = { New:'primary','In Discussion':'warning',Quoted:'secondary',Closed:'success',Dropped:'danger' };
const PRI     = { High:'danger', Medium:'warning', Low:'success' };
const STATUSES = ['','New','In Discussion','Quoted','Closed','Dropped'];
const CATS     = ['','Website','Web App','Mobile App','ERP/CRM','Support','General'];

export default function EnquiryList() {
  const [enquiries, setEnquiries] = useState([]);
  const [search,    setSearch]    = useState('');
  const [status,    setStatus]    = useState('');
  const [category,  setCategory]  = useState('');
  const [loading,   setLoading]   = useState(true);
  const navigate = useNavigate();

  const fetchData = useCallback(() => {
    setLoading(true);
    const params = {};
    if (search)   params.search   = search;
    if (status)   params.status   = status;
    if (category) params.category = category;
    API.get('/api/enquiries', { params })
      .then(r => setEnquiries(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [search, status, category]);

  useEffect(() => { fetchData(); }, [fetchData]);

  function deleteEnquiry(id) {
    if (!window.confirm('Delete this enquiry?')) return;
    API.delete(`/api/enquiries/${id}`)
      .then(fetchData)
      .catch(() => alert('Delete failed'));
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 className="mb-0">All Enquiries ({enquiries.length})</h5>
        <Link to="/add" className="btn btn-primary btn-sm">+ New Enquiry</Link>
      </div>

      <div className="row g-2 mb-3">
        <div className="col-md-4">
          <input className="form-control form-control-sm" placeholder="Search by name or email..."
            value={search} onChange={e => setSearch(e.target.value)}/>
        </div>
        <div className="col-md-3">
          <select className="form-select form-select-sm" value={status} onChange={e => setStatus(e.target.value)}>
            {STATUSES.map(s => <option key={s} value={s}>{s || 'All Statuses'}</option>)}
          </select>
        </div>
        <div className="col-md-3">
          <select className="form-select form-select-sm" value={category} onChange={e => setCategory(e.target.value)}>
            {CATS.map(c => <option key={c} value={c}>{c || 'All Categories'}</option>)}
          </select>
        </div>
        <div className="col-md-2">
          <button className="btn btn-outline-secondary btn-sm w-100"
            onClick={() => { setSearch(''); setStatus(''); setCategory(''); }}>
            Clear
          </button>
        </div>
      </div>

      {loading && <p className="text-muted">Loading...</p>}

      {!loading && (
        <div className="table-responsive">
          <table className="table table-sm table-bordered table-hover">
            <thead className="table-dark">
              <tr>
                <th>#</th><th>Name</th><th>Phone</th><th>Source</th>
                <th>Category</th><th>Priority</th><th>🤖 AI Summary</th>
                <th>Status</th><th>Follow-up</th><th>Created</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {enquiries.length === 0 && (
                <tr><td colSpan="11" className="text-center text-muted py-3">No records found.</td></tr>
              )}
              {enquiries.map((e, i) => (
                <tr key={e.id}>
                  <td>{i + 1}</td>
                  <td>
                    <strong>{e.customer_name}</strong>
                    <div className="small text-muted">{e.email}</div>
                  </td>
                  <td className="small">{e.phone}</td>
                  <td className="small">{e.source}</td>
                  <td><span className="badge bg-dark">{e.category}</span></td>
                  <td><span className={`badge bg-${PRI[e.priority]||'secondary'}`}>{e.priority}</span></td>
                  <td style={{ maxWidth: '200px' }}>
                    {e.ai_summary ? (
                      <span className="small text-muted" title={e.ai_summary}>
                        {e.ai_summary.length > 60 ? e.ai_summary.slice(0, 60) + '…' : e.ai_summary}
                      </span>
                    ) : <span className="small text-danger">—</span>}
                  </td>
                  <td><span className={`badge bg-${BADGE[e.status]||'secondary'}`}>{e.status}</span></td>
                  <td className="small">{e.follow_up_date || '—'}</td>
                  <td className="small text-muted">{e.created_at}</td>
                  <td>
                    <button className="btn btn-outline-primary btn-sm me-1"
                      onClick={() => navigate(`/edit/${e.id}`)}>Edit</button>
                    <button className="btn btn-outline-danger btn-sm"
                      onClick={() => deleteEnquiry(e.id)}>Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
