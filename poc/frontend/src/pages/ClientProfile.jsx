import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import API from '../api/axios';

const PRI   = { High:'danger', Medium:'warning', Low:'success' };
const BADGE = { New:'primary','In Discussion':'warning',Quoted:'secondary',Closed:'success',Dropped:'danger' };

export default function ClientProfile() {
  const { id }   = useParams();
  const navigate = useNavigate();
  const [data,  setData]  = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    API.get(`/api/clients/${id}/enquiries`)
      .then(r => setData(r.data))
      .catch(() => setError('Could not load client profile.'));
  }, [id]);

  if (error) return <div className="alert alert-danger mt-3">{error}</div>;
  if (!data)  return <p className="mt-3 text-muted">Loading...</p>;

  const { client, enquiries } = data;

  const total     = enquiries.length;
  const closed    = enquiries.filter(e => e.status === 'Closed').length;
  const dropped   = enquiries.filter(e => e.status === 'Dropped').length;
  const highCount = enquiries.filter(e => e.priority === 'High').length;

  const categories = {};
  enquiries.forEach(e => {
    categories[e.category] = (categories[e.category] || 0) + 1;
  });
  const topCategory = Object.entries(categories).sort((a,b) => b[1]-a[1])[0]?.[0] || '—';

  const conversionRate = total > 0 ? Math.round((closed / total) * 100) : 0;

  let behaviourTag = 'Regular client';
  let behaviourColor = 'secondary';
  if (highCount >= 2)          { behaviourTag = '🔥 Frequently urgent';    behaviourColor = 'danger';  }
  else if (dropped > total/2)  { behaviourTag = '⚠️ High drop rate';       behaviourColor = 'warning'; }
  else if (conversionRate > 60){ behaviourTag = '✅ High conversion';      behaviourColor = 'success'; }
  else if (total >= 5)         { behaviourTag = '⭐ Frequent client';      behaviourColor = 'primary'; }

  return (
    <div>
      <button className="btn btn-sm btn-secondary mb-3"
        onClick={() => navigate('/clients')}>← Back to Clients</button>

      <div className="row g-3">

        <div className="col-md-4">

          <div className="card mb-3">
            <div className="card-header bg-dark text-white py-2"><strong>Client Profile</strong></div>
            <div className="card-body">
              <div className="d-flex align-items-center gap-3 mb-3">
                <div style={{
                  width:52, height:52, borderRadius:'50%',
                  background:'#0d6efd', color:'#fff',
                  display:'grid', placeItems:'center',
                  fontSize:20, fontWeight:700, flexShrink:0
                }}>
                  {client.name[0].toUpperCase()}
                </div>
                <div>
                  <div className="fw-bold fs-6">{client.name}</div>
                  <div className="small text-muted">{client.company || 'No company'}</div>
                  <span className={`badge bg-${behaviourColor} mt-1`}>{behaviourTag}</span>
                </div>
              </div>
              <table className="table table-sm table-bordered mb-0">
                <tbody>
                  <tr><th>Email</th> <td>{client.email}</td></tr>
                  <tr><th>Phone</th> <td>{client.phone || '—'}</td></tr>
                  <tr><th>Client ID</th><td>#{client.id}</td></tr>
                  <tr><th>Since</th> <td>{client.created_at}</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="card mb-3">
            <div className="card-header bg-info text-white py-2"><strong>🤖 Behaviour Summary</strong></div>
            <div className="card-body p-2">
              <table className="table table-sm mb-0">
                <tbody>
                  <tr><td>Total enquiries</td><td><strong>{total}</strong></td></tr>
                  <tr><td>Closed deals</td><td><strong className="text-success">{closed}</strong></td></tr>
                  <tr><td>Dropped</td><td><strong className="text-danger">{dropped}</strong></td></tr>
                  <tr><td>Urgent requests</td><td><strong className="text-danger">{highCount}</strong></td></tr>
                  <tr>
                    <td>Conversion rate</td>
                    <td>
                      <strong>{conversionRate}%</strong>
                      <div className="progress mt-1" style={{height:5}}>
                        <div className="progress-bar bg-success" style={{width:`${conversionRate}%`}}/>
                      </div>
                    </td>
                  </tr>
                  <tr><td>Top service needed</td><td><span className="badge bg-dark">{topCategory}</span></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <div className="card-header py-2"><strong>Category Breakdown</strong></div>
            <div className="card-body p-2">
              {Object.entries(categories).map(([cat, count]) => (
                <div key={cat} className="d-flex justify-content-between align-items-center mb-1">
                  <span className="small">{cat}</span>
                  <span className="badge bg-dark">{count}</span>
                </div>
              ))}
              {Object.keys(categories).length === 0 &&
                <p className="small text-muted mb-0">No data</p>}
            </div>
          </div>
        </div>

        <div className="col-md-8">
          <div className="card">
            <div className="card-header py-2 d-flex justify-content-between align-items-center">
              <strong>All Enquiries ({total})</strong>
            </div>
            <div className="card-body p-0">
              {enquiries.length === 0 ? (
                <p className="text-muted p-3 mb-0">No enquiries yet.</p>
              ) : (
                <table className="table table-sm table-hover table-bordered mb-0">
                  <thead className="table-dark">
                    <tr>
                      <th>#ID</th><th>Description</th><th>Category</th>
                      <th>Priority</th><th>Status</th><th>Date</th><th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {enquiries.map(e => (
                      <tr key={e.id}>
                        <td className="fw-bold">#{e.id}</td>
                        <td className="small" style={{maxWidth:180}}>
                          {e.ai_summary || e.description.slice(0,60) + '…'}
                        </td>
                        <td><span className="badge bg-dark">{e.category}</span></td>
                        <td><span className={`badge bg-${PRI[e.priority]||'secondary'}`}>{e.priority}</span></td>
                        <td><span className={`badge bg-${BADGE[e.status]||'secondary'}`}>{e.status}</span></td>
                        <td className="small text-muted">{e.created_at}</td>
                        <td>
                          <Link to={`/edit/${e.id}`} className="btn btn-outline-primary btn-sm">Open</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
