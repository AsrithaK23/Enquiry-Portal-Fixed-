import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import API from '../api/axios';

const BADGE = { New: 'primary', 'In Discussion': 'warning', Quoted: 'secondary', Closed: 'success', Dropped: 'danger' };
const PRI = { High: 'danger', Medium: 'warning', Low: 'success' };

const CATEGORY_COLORS = ['#4f46e5', '#0284c7', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#64748b'];

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    API.get('/api/dashboard')
      .then(r => setData(r.data))
      .catch(() => setError('Cannot connect to backend. Is Flask running on port 5000?'));
  }, []);

  if (error) return <div className="alert alert-danger mt-3">{error}</div>;
  if (!data) return <p className="mt-4 text-muted text-center">Loading dashboard overview...</p>;

  const totalEnquiries = data.total || 0;

  const kpis = [
    {
      label: 'Total Enquiries',
      value: data.total,
      icon: '📁',
      bg: 'rgba(79, 70, 229, 0.1)',
      subtext: `Quoted: ${data.quoted} · Dropped: ${data.dropped}`,
    },
    {
      label: 'New Intake',
      value: data.new,
      icon: '✨',
      bg: 'rgba(2, 132, 199, 0.1)',
      subtext: 'Awaiting review or draft',
    },
    {
      label: 'In Discussion',
      value: data.in_discussion,
      icon: '💬',
      bg: 'rgba(217, 119, 6, 0.1)',
      subtext: 'Active conversation threads',
    },
    {
      label: 'Closed / Won',
      value: data.closed,
      icon: '✅',
      bg: 'rgba(22, 163, 74, 0.1)',
      subtext: 'Successfully resolved',
    },
    {
      label: 'Follow-ups Due',
      value: data.pending_followup,
      icon: '⏰',
      bg: 'rgba(225, 29, 72, 0.1)',
      subtext: data.pending_followup > 0 ? 'Requires attention today' : 'All caught up!',
    },
  ];

  return (
    <div style={{ maxWidth: 1280, margin: '0 auto' }}>
      {/* Top Header */}
      <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        <div>
          <h4 style={{ fontWeight: 700, color: '#1e293b', marginBottom: 2 }}>Dashboard Overview</h4>
          <p className="text-muted small mb-0">Track incoming client enquiries, discussion progress, and resolution status.</p>
        </div>
        <div className="d-flex gap-2">
          <Link to="/enquiries" className="btn btn-outline-secondary btn-sm" style={{ borderRadius: 8, fontWeight: 500 }}>
            View All Enquiries
          </Link>
          <Link to="/add" className="btn btn-primary btn-sm" style={{ borderRadius: 8, fontWeight: 500, background: '#4f46e5', borderColor: '#4f46e5' }}>
            + New Enquiry
          </Link>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="row g-3 mb-4">
        {kpis.map(kpi => (
          <div key={kpi.label} className="col-12 col-sm-6 col-xl">
            <div style={{
              background: '#ffffff',
              borderRadius: 12,
              border: '1px solid #e2e8f0',
              boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
              padding: '16px 18px',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                  {kpi.label}
                </span>
                <span style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: kpi.bg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 15,
                }}>
                  {kpi.icon}
                </span>
              </div>
              <div>
                <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#0f172a', lineHeight: 1.1 }}>
                  {kpi.value}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: 4 }}>
                  {kpi.subtext}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Middle Row: Category Distribution & Priority Health */}
      <div className="row g-3 mb-4">
        {/* Left: Category breakdown */}
        <div className="col-lg-7">
          <div style={{
            background: '#ffffff',
            borderRadius: 12,
            border: '1px solid #e2e8f0',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
            height: '100%',
            overflow: 'hidden',
          }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '0.92rem', color: '#1e293b' }}>Enquiries by Service Area</strong>
              <span className="badge bg-light text-muted border">
                {Object.keys(data.by_category || {}).length} categories
              </span>
            </div>
            <div style={{ padding: '18px 20px' }}>
              {Object.keys(data.by_category || {}).length === 0 ? (
                <p className="text-muted small mb-0 text-center py-3">No categorized enquiries found.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {Object.entries(data.by_category).map(([cat, count], idx) => {
                    const pct = totalEnquiries > 0 ? Math.round((count / totalEnquiries) * 100) : 0;
                    const color = CATEGORY_COLORS[idx % CATEGORY_COLORS.length];
                    return (
                      <div key={cat}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: 4 }}>
                          <span style={{ fontWeight: 500, color: '#334155' }}>{cat}</span>
                          <span style={{ color: '#64748b' }}>
                            <strong>{count}</strong> <span style={{ fontSize: '0.78rem' }}>({pct}%)</span>
                          </span>
                        </div>
                        <div style={{ height: 6, background: '#f1f5f9', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 4, transition: 'width 0.4s ease' }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Priority Breakdown & Automation Info */}
        <div className="col-lg-5">
          <div style={{
            background: '#ffffff',
            borderRadius: 12,
            border: '1px solid #e2e8f0',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            overflow: 'hidden',
          }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid #f1f5f9' }}>
              <strong style={{ fontSize: '0.92rem', color: '#1e293b' }}>Priority Distribution</strong>
            </div>
            <div style={{ padding: '18px 20px', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: 18 }}>
                {[
                  { level: 'High', color: '#ef4444', bg: '#fef2f2', border: '#fecaca', count: data.by_priority?.High || 0 },
                  { level: 'Medium', color: '#f59e0b', bg: '#fffbeb', border: '#fde68a', count: data.by_priority?.Medium || 0 },
                  { level: 'Low', color: '#10b981', bg: '#ecfdf5', border: '#a7f3d0', count: data.by_priority?.Low || 0 },
                ].map(p => (
                  <div key={p.level} style={{
                    background: p.bg,
                    border: `1px solid ${p.border}`,
                    borderRadius: 10,
                    padding: '12px 10px',
                    textAlign: 'center',
                  }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: p.color, textTransform: 'uppercase' }}>
                      {p.level}
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1e293b', marginTop: 2 }}>
                      {p.count}
                    </div>
                  </div>
                ))}
              </div>

              {/* Automation Status Card */}
              <div style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 10,
                padding: '12px 14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '1.25rem' }}>📧</span>
                  <div>
                    <div style={{ fontSize: '0.825rem', fontWeight: 600, color: '#1e293b' }}>Email Automation</div>
                    <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      {data.emails_synced} emails processed ({data.emails_today} today)
                    </div>
                  </div>
                </div>
                <Link to="/automation" className="btn btn-outline-primary btn-sm" style={{ fontSize: '0.78rem', borderRadius: 6 }}>
                  Sync Now
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom: Recent Enquiries Table */}
      <div style={{
        background: '#ffffff',
        borderRadius: 12,
        border: '1px solid #e2e8f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '14px 20px',
          borderBottom: '1px solid #f1f5f9',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <strong style={{ fontSize: '0.92rem', color: '#1e293b' }}>Recent Enquiries</strong>
            <span className="text-muted small ms-2">(latest 5)</span>
          </div>
          <Link to="/enquiries" style={{ fontSize: '0.825rem', color: '#4f46e5', textDecoration: 'none', fontWeight: 600 }}>
            View All Enquiries →
          </Link>
        </div>

        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0" style={{ fontSize: '0.875rem' }}>
            <thead style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
              <tr>
                <th style={{ padding: '10px 16px', color: '#64748b', fontWeight: 600, fontSize: '0.78rem' }}>ENQUIRY #</th>
                <th style={{ padding: '10px 16px', color: '#64748b', fontWeight: 600, fontSize: '0.78rem' }}>CUSTOMER</th>
                <th style={{ padding: '10px 16px', color: '#64748b', fontWeight: 600, fontSize: '0.78rem' }}>CATEGORY</th>
                <th style={{ padding: '10px 16px', color: '#64748b', fontWeight: 600, fontSize: '0.78rem' }}>PRIORITY</th>
                <th style={{ padding: '10px 16px', color: '#64748b', fontWeight: 600, fontSize: '0.78rem' }}>STATUS</th>
                <th style={{ padding: '10px 16px', color: '#64748b', fontWeight: 600, fontSize: '0.78rem' }}>DATE</th>
                <th style={{ padding: '10px 16px', width: '80px' }}></th>
              </tr>
            </thead>
            <tbody>
              {!data.recent || data.recent.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center text-muted py-4">No recent enquiries found.</td>
                </tr>
              ) : (
                data.recent.map(e => (
                  <tr key={e.id}>
                    <td style={{ padding: '12px 16px' }}>
                      <span className="badge bg-secondary font-monospace" style={{ fontSize: '0.8rem' }}>
                        #{e.id}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 600, color: '#1e293b' }}>{e.customer_name}</div>
                      <div className="small text-muted" style={{ fontSize: '0.78rem' }}>{e.email}</div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span className="badge bg-dark" style={{ fontWeight: 500, fontSize: '0.75rem' }}>{e.category}</span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span className={`badge bg-${PRI[e.priority] || 'secondary'}`} style={{ fontWeight: 500, fontSize: '0.75rem' }}>
                        {e.priority}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span className={`badge bg-${BADGE[e.status] || 'secondary'}`} style={{ fontWeight: 500, fontSize: '0.75rem' }}>
                        {e.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', color: '#64748b', fontSize: '0.825rem' }}>
                      {e.created_at}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <Link to={`/edit/${e.id}`} className="btn btn-outline-secondary btn-sm" style={{ fontSize: '0.75rem', padding: '3px 10px', borderRadius: 6 }}>
                        Edit
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
