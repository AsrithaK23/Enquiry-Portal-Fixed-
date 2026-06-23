import React, { useState } from 'react';
import API from '../api/axios';

const PRI = { High: 'danger', Medium: 'warning', Low: 'success' };

export default function Automation() {
  const [limit, setLimit] = useState(10);
  const [markSeen, setMarkSeen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function syncEmail() {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const response = await API.post('/api/automation/email/sync', {
        limit: Number(limit),
        mark_seen: markSeen,
      });
      setResult(response.data);
    } catch (e) {
      setError(e.response?.data?.error || 'Email sync failed. Check backend email settings.');
    } finally {
      setLoading(false);
    }
  }

  // Helper function to render reply status badge
  const renderReplyStatus = (status) => {
    const statusMap = {
      'auto_sent': { 
        className: 'badge bg-success', 
        label: '✅ Auto-Sent' 
      },
      'pending_manual': { 
        className: 'badge bg-warning text-dark', 
        label: '⏳ Manual Review' 
      },
      'send_failed': { 
        className: 'badge bg-danger', 
        label: '❌ Failed' 
      }
    };
    
    const defaultStatus = { 
      className: 'badge bg-secondary', 
      label: status || 'Unknown' 
    };
    
    const { className, label } = statusMap[status] || defaultStatus;
    return <span className={className}>{label}</span>;
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 className="mb-0">Workflow Automation</h5>
      </div>

      {error && <div className="alert alert-danger py-2">{error}</div>}
      {error.includes('not configured') && (
        <div className="alert alert-info py-2 small">
          Create a <code>.env</code> file in <code>poc/backend</code> using <code>.env.example</code>, then restart the backend.
          For Gmail, use an app password instead of your normal account password.
        </div>
      )}

      <div className="card mb-3">
        <div className="card-header py-2"><strong>Email Intake</strong></div>
        <div className="card-body">
          <div className="row g-3 align-items-end">
            <div className="col-md-3">
              <label className="form-label form-label-sm">Unread email limit</label>
              <input
                type="number"
                min="1"
                max="50"
                className="form-control form-control-sm"
                value={limit}
                onChange={e => setLimit(e.target.value)}
              />
            </div>
            <div className="col-md-4">
              <div className="form-check">
                <input
                  id="markSeen"
                  type="checkbox"
                  className="form-check-input"
                  checked={markSeen}
                  onChange={e => setMarkSeen(e.target.checked)}
                />
                <label htmlFor="markSeen" className="form-check-label small">
                  Mark imported emails as read
                </label>
              </div>
            </div>
            <div className="col-md-3">
              <button className="btn btn-primary btn-sm" onClick={syncEmail} disabled={loading}>
                {loading ? 'Syncing...' : 'Sync Unread Email'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {result && (
        <div className="card">
          <div className="card-header py-2">
            <strong>Imported {result.synced || result.imported_count}</strong>
            <span className="small text-muted ms-2">Skipped {result.skipped || result.skipped_count} duplicates</span>
          </div>
          <div className="card-body p-0">
            <table className="table table-sm table-hover mb-0">
              <thead className="table-light">
                <tr>
                  <th>Client</th>
                  <th>Subject</th>
                  <th>Category</th>
                  <th>Priority</th>
                  <th>AI Summary</th>
                  <th>Draft Response</th>
                  <th>Reply Status</th> {/* New column */}
                </tr>
              </thead>
              <tbody>
                {(!result.imported || result.imported.length === 0) && (
                  <tr><td colSpan="7" className="text-center text-muted">No unread emails imported.</td></tr>
                )}
                {(result.imported || []).map(item => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.customer_name}</strong>
                      <div className="small text-muted">{item.email}</div>
                    </td>
                    <td className="small">{item.inbound_subject}</td>
                    <td><span className="badge bg-dark">{item.category}</span></td>
                    <td><span className={`badge bg-${PRI[item.priority] || 'secondary'}`}>{item.priority}</span></td>
                    <td className="small text-muted">{item.ai_summary}</td>
                    <td className="small" style={{ maxWidth: '280px', whiteSpace: 'pre-wrap' }}>
                      {item.suggested_response}
                    </td>
                    <td>{renderReplyStatus(item.reply_status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}