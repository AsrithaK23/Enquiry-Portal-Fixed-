import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api/axios';

export default function ClientList() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    API.get('/api/clients')
      .then(r => setClients(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h5 className="mb-3">All Clients ({clients.length})</h5>
      {loading && <p className="text-muted">Loading...</p>}
      {!loading && (
        <table className="table table-sm table-bordered table-hover">
          <thead className="table-dark">
            <tr>
              <th>#</th><th>Name</th><th>Email</th>
              <th>Phone</th><th>Company</th>
              <th>Total Enquiries</th><th>Joined</th><th></th>
            </tr>
          </thead>
          <tbody>
            {clients.length === 0 && (
              <tr><td colSpan="8" className="text-center text-muted">
                No clients yet. They appear when a client registers or submits via chatbot/email.
              </td></tr>
            )}
            {clients.map((c) => (
              <tr key={c.id}>
                <td>#{c.id}</td>
                <td><strong>{c.name}</strong></td>
                <td className="small">{c.email}</td>
                <td className="small">{c.phone || '—'}</td>
                <td className="small">{c.company || '—'}</td>
                <td><span className="badge bg-primary">{c.enquiry_count || 0}</span></td>
                <td className="small text-muted">{c.created_at}</td>
                <td>
                  <button className="btn btn-outline-info btn-sm"
                    onClick={() => navigate(`/clients/${c.id}`)}>
                    View History
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
