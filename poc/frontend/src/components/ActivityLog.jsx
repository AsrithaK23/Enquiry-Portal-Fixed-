import React from 'react';

export default function ActivityLog({ logs = [] }) {
  if (!logs.length) return <p className="text-muted small">No activity yet.</p>;

  return (
    <ul className="list-group list-group-flush">
      {logs.map((log) => (
        <li key={log.id} className="list-group-item px-0 py-1">
          <small className="text-muted me-2">{log.created_at}</small>
          <span className="small">{log.action}</span>
        </li>
      ))}
    </ul>
  );
}
