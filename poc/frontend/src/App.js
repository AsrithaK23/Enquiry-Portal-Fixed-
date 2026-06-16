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
              <Route path="/"          element={<Navigate to="/dashboard"/>}/>
              <Route path="/dashboard" element={<Dashboard/>}/>
              <Route path="/enquiries" element={<EnquiryList/>}/>
              <Route path="/add"       element={<AddEnquiry/>}/>
              <Route path="/edit/:id"  element={<EditEnquiry/>}/>
              <Route path="/clients"   element={<ClientList/>}/>
              <Route path="/clients/:id" element={<ClientProfile/>}/>
              <Route path="*"          element={<Navigate to="/dashboard"/>}/>
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
  const a = p => pathname === p ? 'nav-link active fw-semibold text-white' : 'nav-link text-white-50';

  return (
    <>
      <nav className="navbar navbar-dark bg-primary px-4 py-2">
        <span className="navbar-brand fw-bold">📋 Enquiry Portal</span>

        {user.role === 'admin' && (
          <div className="navbar-nav d-flex flex-row ms-3 gap-1">
            <Link className={a('/dashboard')} to="/dashboard">Dashboard</Link>
            <Link className={a('/enquiries')} to="/enquiries">All Enquiries</Link>
            <Link className={a('/clients')}   to="/clients">Clients</Link>
            <Link className={a('/add')}       to="/add">+ New</Link>
          </div>
        )}

        {user.role === 'client' && (
          <div className="navbar-nav d-flex flex-row ms-3">
            <Link className={a('/chat')} to="/chat">💬 My Enquiries</Link>
          </div>
        )}

        <div className="ms-auto d-flex align-items-center gap-3">
          <span className="text-white-50 small">
            {user.role === 'admin' ? '🔑 Admin' : '👤 Client'} — {user.name}
          </span>
          <button className="btn btn-outline-light btn-sm" onClick={onLogout}>Logout</button>
        </div>
      </nav>

      <div className="container-fluid mt-3 px-4">
        {children}
      </div>
    </>
  );
}
