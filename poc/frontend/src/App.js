import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import Login         from './pages/Login';
import Dashboard     from './pages/Dashboard';
import EnquiryList   from './pages/EnquiryList';
import AddEnquiry    from './pages/AddEnquiry';
import EditEnquiry   from './pages/EditEnquiry';
import ClientChatbot from './pages/ClientChatbot';
import ClientList    from './pages/ClientList';
import ClientProfile from './pages/ClientProfile';
import Automation    from './pages/Automation';
import API           from './api/axios';

API.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers['Authorization'] = `Bearer ${token}`;
  return cfg;
});

export default function App() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });

  function handleLogin(u) { setUser(u); }
  function handleLogout() {
    API.post('/api/auth/logout').catch(() => {});
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  }

  if (!user) return <Login onLogin={handleLogin}/>;

  return (
    <BrowserRouter>
      <AppShell user={user} onLogout={handleLogout}>
        <Routes>
          {user.role === 'admin' ? (
            <>
              <Route path="/"            element={<Navigate to="/dashboard"/>}/>
              <Route path="/dashboard"   element={<Dashboard/>}/>
              <Route path="/enquiries"   element={<EnquiryList/>}/>
              <Route path="/add"         element={<AddEnquiry/>}/>
              <Route path="/edit/:id"    element={<EditEnquiry/>}/>
              <Route path="/clients"     element={<ClientList/>}/>
              <Route path="/clients/:id" element={<ClientProfile/>}/>
              <Route path="/automation"  element={<Automation/>}/>
              <Route path="*"            element={<Navigate to="/dashboard"/>}/>
            </>
          ) : (
            <>
              <Route path="/"      element={<Navigate to="/chat"/>}/>
              <Route path="/chat"  element={<ClientChatbot user={user}/>}/>
              <Route path="*"      element={<Navigate to="/chat"/>}/>
            </>
          )}
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}

function AppShell({ user, onLogout, children }) {
  const { pathname } = useLocation();

  const navLinkStyle = (path) => {
    const active = pathname === path;
    return {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '7px 14px',
      borderRadius: '8px',
      fontSize: '0.875rem',
      fontWeight: active ? '600' : '500',
      color: active ? '#ffffff' : 'rgba(255, 255, 255, 0.78)',
      background: active ? 'rgba(255, 255, 255, 0.18)' : 'transparent',
      textDecoration: 'none',
      transition: 'all 0.15s ease',
    };
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc', display: 'flex', flexDirection: 'column' }}>
      <nav style={{
        background: 'linear-gradient(90deg, #3730a3 0%, #4f46e5 100%)',
        boxShadow: '0 2px 10px rgba(55, 48, 163, 0.15)',
        padding: '10px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
        position: 'sticky',
        top: 0,
        zIndex: 1000,
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: 34,
            height: 34,
            borderRadius: 8,
            background: 'rgba(255, 255, 255, 0.18)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 18,
          }}>
            📋
          </div>
          <div>
            <span style={{ fontWeight: 700, fontSize: '1.05rem', color: '#ffffff', letterSpacing: '-0.2px' }}>
              Enquiry Portal
            </span>
          </div>
        </div>

        {/* Navigation Links */}
        {user.role === 'admin' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
            <Link style={navLinkStyle('/dashboard')} to="/dashboard">📊 Dashboard</Link>
            <Link style={navLinkStyle('/enquiries')} to="/enquiries">📋 All Enquiries</Link>
            <Link style={navLinkStyle('/clients')} to="/clients">👥 Clients</Link>
            <Link style={navLinkStyle('/add')} to="/add">➕ New Enquiry</Link>
            <Link style={navLinkStyle('/automation')} to="/automation">📧 Email Automation</Link>
          </div>
        )}

        {user.role === 'client' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Link style={navLinkStyle('/chat')} to="/chat">💬 My Enquiries</Link>
          </div>
        )}

        {/* User profile & Logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '4px 12px 4px 6px',
            background: 'rgba(255, 255, 255, 0.12)',
            borderRadius: '20px',
            border: '1px solid rgba(255, 255, 255, 0.18)',
          }}>
            <div style={{
              width: 26,
              height: 26,
              borderRadius: '50%',
              background: user.role === 'admin' ? '#f59e0b' : '#38bdf8',
              color: '#ffffff',
              fontSize: '0.75rem',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {user.role === 'admin' ? 'A' : 'C'}
            </div>
            <span style={{ color: '#ffffff', fontSize: '0.825rem', fontWeight: 500 }}>
              {user.name}
            </span>
            <span style={{
              fontSize: '0.68rem',
              padding: '2px 7px',
              borderRadius: '10px',
              background: user.role === 'admin' ? 'rgba(245, 158, 11, 0.28)' : 'rgba(56, 189, 248, 0.28)',
              color: user.role === 'admin' ? '#fef3c7' : '#e0f2fe',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.3px',
            }}>
              {user.role}
            </span>
          </div>

          <button
            onClick={onLogout}
            style={{
              padding: '6px 14px',
              borderRadius: '8px',
              fontSize: '0.825rem',
              fontWeight: 500,
              color: '#ffffff',
              background: 'transparent',
              border: '1px solid rgba(255, 255, 255, 0.35)',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseOver={e => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.15)'}
            onMouseOut={e => e.currentTarget.style.background = 'transparent'}
          >
            Logout
          </button>
        </div>
      </nav>

      <main style={{ flex: 1, padding: '24px 32px' }}>
        {children}
      </main>
    </div>
  );
}