import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import API from '../api/axios';

const BADGE = { New:'primary','In Discussion':'warning',Quoted:'secondary',Closed:'success',Dropped:'danger' };
const PRI = { High:'danger', Medium:'warning', Low:'success' };

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    API.get('/api/dashboard')
      .then(r => setData(r.data))
      .catch(() => setError('Cannot connect to backend. Is Flask running on port 5000?'));
  }, []);

  if (error) return <div className="alert alert-danger mt-3">{error}</div>;
  if (!data)  return <p className="mt-3 text-muted">Loading dashboard...</p>;

  return (
    <div>
      <h5 className="mb-3">Dashboard</h5>

      <div className="row g-3 mb-4">
        {[
          { label: 'Total Enquiries',    value: data.total,            color: 'primary' },
          { label: 'New',                value: data.new,              color: 'info'    },
          { label: 'In Discussion',      value: data.in_discussion,    color: 'warning' },
          { label: 'Quoted',             value: data.quoted,           color: 'secondary'},
          { label: 'Closed',             value: data.closed,           color: 'success' },
          { label: 'Dropped',            value: data.dropped,          color: 'danger'  },
          { label: 'Pending Follow-ups', value: data.pending_followup, color: 'dark'    },
        ].map(c => (
          <div key={c.label} className="col-6 col-md-3 col-xl-2">
            <div className={`card text-white bg-${c.color} h-100`}>
              <div className="card-body py-2 px-3">
                <div className="fs-2 fw-bold">{c.value}</div>
                <div className="small">{c.label}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="row mb-4">
        <div className="col-md-6">
          <div className="card">
            <div className="card-header py-2"><strong>By Category</strong></div>
            <div className="card-body p-2">
              <table className="table table-sm mb-0">
                <thead><tr><th>Category</th><th>Count</th></tr></thead>
                <tbody>
                  {Object.entries(data.by_category).map(([k, v]) => (
                    <tr key={k}><td>{k}</td><td><span className="badge bg-dark">{v}</span></td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div className="col-md-6">
          <div className="card">
            <div className="card-header py-2"><strong>By Priority</strong></div>
            <div className="card-body p-2">
              <table className="table table-sm mb-0">
                <thead><tr><th>Priority</th><th>Count</th></tr></thead>
                <tbody>
                  {Object.entries(data.by_priority).map(([k, v]) => (
                    <tr key={k}>
                      <td><span className={`badge bg-${PRI[k]||'secondary'}`}>{k}</span></td>
                      <td>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header py-2 d-flex justify-content-between align-items-center">
          <strong>Recent Enquiries</strong>
          <Link to="/enquiries" className="btn btn-sm btn-outline-primary">View All</Link>
        </div>
        <div className="card-body p-0">
          <table className="table table-sm table-hover mb-0">
            <thead className="table-light">
              <tr><th>Name</th><th>Category</th><th>Priority</th><th>Status</th><th>Date</th><th></th></tr>
            </thead>
            <tbody>
              {data.recent.map(e => (
                <tr key={e.id}>
                  <td>{e.customer_name}</td>
                  <td><span className="badge bg-dark">{e.category}</span></td>
                  <td><span className={`badge bg-${PRI[e.priority]||'secondary'}`}>{e.priority}</span></td>
                  <td><span className={`badge bg-${BADGE[e.status]||'secondary'} text-dark`}>{e.status}</span></td>
                  <td className="small text-muted">{e.created_at}</td>
                  <td><Link to={`/edit/${e.id}`} className="btn btn-xs btn-outline-secondary btn-sm">Edit</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
