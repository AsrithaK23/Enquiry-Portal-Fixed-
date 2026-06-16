import React, { useState } from 'react';
import API from '../api/axios';

export default function Login({ onLogin }) {
  const [isSignUp, setIsSignUp] = useState(false);
  const [name,     setName]     = useState('');
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [role,     setRole]     = useState('client');
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  async function handleLogin(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await API.post('/api/auth/login', { email, password });
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('user', JSON.stringify(res.data.user));
      onLogin(res.data.user);
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await API.post('/api/auth/register', { name, email, password, role });
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('user', JSON.stringify(res.data.user));
      onLogin(res.data.user);
    } catch (err) {
      setError(err.response?.data?.error || 'Registration failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={S.page}>
      <style>{`
        @keyframes fadeIn { from {opacity:0; transform:translateY(8px);} to {opacity:1; transform:translateY(0);} }
        .ep-input:focus { outline:none; border-color:#6c63ff !important; box-shadow:0 0 0 3px rgba(108,99,255,.15); }
        .ep-fade { animation: fadeIn .35s ease; }
      `}</style>

      <div style={S.card}>
        {/* LEFT: form panel */}
        <div style={S.left}>
          <div style={S.brand}>Enquiry Portal</div>

          <div key={isSignUp ? 'su' : 'si'} className="ep-fade" style={{ width: '100%' }}>
            <h2 style={S.heading}>{isSignUp ? 'Create Account' : 'Welcome Back'}</h2>
            <p style={S.subheading}>
              {isSignUp ? 'Sign up to raise and track enquiries' : 'Log in to your account'}
            </p>

            {error && <div style={S.error}>{error}</div>}

            <form onSubmit={isSignUp ? handleRegister : handleLogin}>
              {isSignUp && (
                <div style={S.field}>
                  <label style={S.label}>Full Name</label>
                  <input className="ep-input" style={S.input} value={name}
                    onChange={e => setName(e.target.value)} required placeholder="e.g. Rahul Sharma"/>
                </div>
              )}

              <div style={S.field}>
                <label style={S.label}>Email</label>
                <input className="ep-input" style={S.input} type="email" value={email}
                  onChange={e => setEmail(e.target.value)} required placeholder="you@example.com"/>
              </div>

              <div style={S.field}>
                <label style={S.label}>Password</label>
                <input className="ep-input" style={S.input} type="password" value={password}
                  onChange={e => setPassword(e.target.value)} required placeholder="********"/>
              </div>

              {isSignUp && (
                <div style={S.field}>
                  <label style={S.label}>I am a</label>
                  <div style={S.roleRow}>
                    <button type="button"
                      style={role==='client' ? S.roleActive : S.roleBtn}
                      onClick={() => setRole('client')}>
                      Client
                    </button>
                    <button type="button"
                      style={role==='admin' ? S.roleActive : S.roleBtn}
                      onClick={() => setRole('admin')}>
                      Admin / Staff
                    </button>
                  </div>
                </div>
              )}

              {!isSignUp && (
                <div style={S.demoBox}>
                  <strong>Admin demo:</strong> admin@portal.com / admin123
                </div>
              )}

              <button type="submit" style={S.submitBtn} disabled={loading}>
                {loading ? 'Please wait...' : (isSignUp ? 'Sign up' : 'Log in')}
              </button>
            </form>
          </div>
        </div>

        {/* RIGHT: switch panel */}
        <div style={{ ...S.right, ...(isSignUp ? S.rightSignUp : {}) }}>
          <div key={isSignUp ? 'right-su' : 'right-si'} className="ep-fade">
            <h1 style={S.getStarted}>{isSignUp ? 'Welcome!' : 'Hello!'}</h1>
            <p style={S.rightText}>
              {isSignUp ? 'Already have an account?' : "Don't have an account yet?"}
            </p>
            <button style={S.switchBtn} onClick={() => { setError(''); setIsSignUp(!isSignUp); }}>
              {isSignUp ? 'Log in' : 'Sign up'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const S = {
  page: {
    minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: '#f0f2f5', fontFamily: "'Inter', system-ui, sans-serif", padding: 16,
  },
  card: {
    display: 'flex', width: '100%', maxWidth: 820, minHeight: 520,
    borderRadius: 24, overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,.12)',
    background: '#fdf6ec', flexWrap: 'wrap',
  },
  left: {
    flex: '1 1 360px', padding: '40px 44px', display: 'flex', flexDirection: 'column',
    justifyContent: 'center', position: 'relative',
  },
  brand: {
    position: 'absolute', top: 24, left: 44, fontWeight: 700, color: '#6c63ff', fontSize: 15,
  },
  heading: { color: '#6c63ff', fontWeight: 800, fontSize: 28, marginBottom: 4 },
  subheading: { color: '#9089b5', fontSize: 13, marginBottom: 22 },
  error: {
    background: '#fde2e2', color: '#c0392b', borderRadius: 8, padding: '8px 12px',
    fontSize: 13, marginBottom: 14,
  },
  field: { marginBottom: 14 },
  label: { display: 'block', fontSize: 12, fontWeight: 700, color: '#6c63ff', marginBottom: 6 },
  input: {
    width: '100%', padding: '11px 14px', borderRadius: 10,
    border: '1.5px solid #e6dfd3', background: '#fffdf9',
    fontSize: 14, color: '#444', transition: 'all .15s',
  },
  roleRow: { display: 'flex', gap: 10 },
  roleBtn: {
    flex: 1, padding: '10px 8px', borderRadius: 10, fontSize: 13, fontWeight: 600,
    border: '1.5px solid #e6dfd3', background: '#fffdf9', color: '#9089b5', cursor: 'pointer',
  },
  roleActive: {
    flex: 1, padding: '10px 8px', borderRadius: 10, fontSize: 13, fontWeight: 700,
    border: '1.5px solid #6c63ff', background: '#6c63ff', color: '#fff', cursor: 'pointer',
  },
  demoBox: {
    background: '#fff3e0', color: '#a3700a', borderRadius: 8, padding: '8px 12px',
    fontSize: 12, marginBottom: 16,
  },
  submitBtn: {
    width: '100%', padding: '13px', borderRadius: 12, border: 'none',
    background: '#7c75ff', color: '#fff', fontWeight: 700, fontSize: 15,
    cursor: 'pointer', boxShadow: '0 8px 20px rgba(124,117,255,.35)',
  },
  right: {
    flex: '1 1 260px', minHeight: 280,
    background: 'linear-gradient(135deg, #6c63ff 0%, #5347d6 100%)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexDirection: 'column', textAlign: 'center', padding: 40,
    borderRadius: '50% 0 0 50% / 60% 0 0 40%',
    transition: 'border-radius .3s',
  },
  rightSignUp: {
    borderRadius: '0 50% 50% 0 / 0 60% 40% 0',
  },
  getStarted: { color: '#ffb74d', fontWeight: 800, fontSize: 36, marginBottom: 14 },
  rightText: { color: 'rgba(255,255,255,.85)', fontSize: 13, marginBottom: 18 },
  switchBtn: {
    padding: '11px 32px', borderRadius: 30, border: '2px solid #ffb74d',
    background: 'transparent', color: '#ffb74d', fontWeight: 700, fontSize: 14,
    cursor: 'pointer',
  },
};
