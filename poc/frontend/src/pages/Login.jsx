import React, { useState, useMemo } from 'react';
import API from '../api/axios';

const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$/;

export default function Login({ onLogin }) {
  const [isSignUp,      setIsSignUp]      = useState(false);
  const [name,          setName]          = useState('');
  const [email,         setEmail]         = useState('');
  const [password,      setPassword]      = useState('');
  const [role,          setRole]          = useState('client');
  const [challenge,     setChallenge]     = useState('');
  const [otp,           setOtp]           = useState('');
  const [showPassword,  setShowPassword]  = useState(false);
  const [error,         setError]         = useState('');
  const [loading,       setLoading]       = useState(false);

  const passwordCriteria = useMemo(() => [
    { id: 'len',   label: 'At least 8 characters',       met: password.length >= 8 },
    { id: 'upper', label: '1 uppercase letter (A-Z)',    met: /[A-Z]/.test(password) },
    { id: 'lower', label: '1 lowercase letter (a-z)',    met: /[a-z]/.test(password) },
    { id: 'num',   label: '1 number (0-9)',              met: /[0-9]/.test(password) },
    { id: 'spec',  label: '1 special character (!@#$..)', met: /[^A-Za-z0-9]/.test(password) },
  ], [password]);

  const metCount = passwordCriteria.filter(c => c.met).length;
  const isPasswordValid = metCount === 5;

  const strength = useMemo(() => {
    if (!password) return { label: '', percent: 0, color: '#e0e0e0' };
    if (metCount <= 2) return { label: 'Weak', percent: 25, color: '#e74c3c' };
    if (metCount === 3) return { label: 'Fair', percent: 50, color: '#f39c12' };
    if (metCount === 4) return { label: 'Good', percent: 75, color: '#3498db' };
    return { label: 'Strong', percent: 100, color: '#27ae60' };
  }, [password, metCount]);

  async function handleLogin(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await API.post('/api/auth/login', { email: email.trim(), password, role });
      setChallenge(res.data.challenge);
    } catch (err) {
      setError(err.response?.data?.error || (err.response ? 'Login failed. Please try again.' : 'Could not reach the server at localhost:5000. Start the backend and try again.'));
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOtp(e) {
    e.preventDefault();
    setError(''); setLoading(true);
    try {
      const res = await API.post('/api/auth/verify-otp', { challenge, otp: otp.trim() });
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('user', JSON.stringify(res.data.user));
      onLogin(res.data.user);
    } catch (err) {
      setError(err.response?.data?.error || (err.response ? 'Verification failed. Please try again.' : 'Could not reach the server at localhost:5000. Start the backend and try again.'));
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    setError('');

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !EMAIL_REGEX.test(trimmedEmail)) {
      setError('Please enter a valid email address (e.g. name@example.com or user@domain.in).');
      return;
    }

    if (!isPasswordValid) {
      if (password.length < 8) {
        setError('Password must be at least 8 characters long.');
      } else if (!/[A-Z]/.test(password)) {
        setError('Password must contain at least one uppercase letter (A-Z).');
      } else if (!/[a-z]/.test(password)) {
        setError('Password must contain at least one lowercase letter (a-z).');
      } else if (!/[0-9]/.test(password)) {
        setError('Password must contain at least one number (0-9).');
      } else {
        setError('Password must contain at least one special character (e.g. !@#$%^&*).');
      }
      return;
    }

    setLoading(true);
    try {
      const res = await API.post('/api/auth/register', { name: name.trim(), email: trimmedEmail, password });
      setChallenge(res.data.challenge);
    } catch (err) {
      setError(err.response?.data?.error || (err.response ? 'Registration failed. Please check your details and try again.' : 'Could not reach the server at localhost:5000. Start the backend and try again.'));
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
            <h2 style={S.heading}>{challenge ? 'Verify your email' : isSignUp ? 'Create Account' : 'Welcome Back'}</h2>
            <p style={S.subheading}>
              {challenge ? `Enter the 6-digit code sent to ${email.trim()}` : isSignUp ? 'Sign up to raise and track your enquiries' : 'Log in to your account'}
            </p>

            {error && <div style={S.error}>{error}</div>}

            <form onSubmit={challenge ? handleVerifyOtp : (isSignUp ? handleRegister : handleLogin)}>
              {!isSignUp && !challenge && (
                <div style={S.field}>
                  <label style={S.label}>I am a</label>
                  <select className="ep-input" style={S.input} value={role} onChange={e => setRole(e.target.value)}>
                    <option value="client">Client</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
              )}
              {challenge ? (
                <div style={S.field}>
                  <label style={S.label}>Verification code</label>
                  <input className="ep-input" style={S.input} inputMode="numeric" autoComplete="one-time-code"
                    value={otp} onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    required minLength={6} maxLength={6} placeholder="6-digit code" />
                  <div style={S.otpHint}>If no code arrives, check the address. A valid format doesn’t guarantee the mailbox exists.</div>
                  <button type="button" onClick={() => { setChallenge(''); setOtp(''); setError(''); }} style={{ ...S.switchBtn, color: '#6c63ff', border: 0, padding: '8px 0' }}>{isSignUp ? 'Back to sign up' : 'Back to login'}</button>
                </div>
              ) : <>
              {isSignUp && (
                <div style={S.field}>
                  <label style={S.label}>Full Name</label>
                  <input className="ep-input" style={S.input} value={name}
                    onChange={e => setName(e.target.value)} required placeholder="e.g. Rahul Sharma"/>
                </div>
              )}

              <div style={S.field}>
                <label style={S.label}>Email Address</label>
                <input className="ep-input" style={S.input} type="email" value={email}
                  onChange={e => setEmail(e.target.value)} required placeholder="you@example.com"/>
              </div>

              <div style={S.field}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label style={S.label}>Password</label>
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#6c63ff',
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: 'pointer',
                      padding: 0,
                      marginBottom: 6,
                    }}
                  >
                    {showPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
                <input
                  className="ep-input"
                  style={S.input}
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  placeholder={isSignUp ? 'Min. 8 characters with upper, number, symbol' : '********'}
                />

                {isSignUp && (
                  <div style={{ marginTop: 7 }}>
                    <div style={{
                      height: 4,
                      width: '100%',
                      background: '#ede7dd',
                      borderRadius: 4,
                      overflow: 'hidden',
                      marginBottom: 5,
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${strength.percent}%`,
                        background: strength.color,
                        transition: 'all 0.3s ease',
                      }} />
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 6 }}>
                      <span style={{ color: '#8882a4' }}>Password Strength:</span>
                      <strong style={{ color: strength.color }}>{strength.label || 'Required'}</strong>
                    </div>

                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: '3px 6px',
                      fontSize: 10.5,
                      background: '#f8f4ec',
                      padding: '7px 10px',
                      borderRadius: 8,
                      border: '1px solid #ece4d7',
                    }}>
                      {passwordCriteria.map(c => (
                        <div key={c.id} style={{
                          color: c.met ? '#27ae60' : '#888195',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                          fontWeight: c.met ? 600 : 400,
                        }}>
                          <span>{c.met ? '✓' : '○'}</span>
                          <span>{c.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {!isSignUp && (
                <div style={S.demoBox}>
                  <strong>Admin demo:</strong> admin@portal.com / admin123<br />
                  <span>Two-step verification: password, then a code sent to your email.</span>
                </div>
              )}
              {isSignUp && <div style={S.twoStepNote}>Verify the email code to create your account and sign in.</div>}
              </>}

              <button type="submit" style={S.submitBtn} disabled={loading}>
              {loading ? 'Please wait...' : challenge ? 'Verify and continue' : (isSignUp ? 'Create Account' : 'Continue to email verification')}
              </button>
            </form>
          </div>
        </div>

        {/* RIGHT: switch panel */}
        <div style={{ ...S.right, ...(isSignUp ? S.rightSignUp : {}) }}>
          <div key={isSignUp ? 'right-su' : 'right-si'} className="ep-fade">
            <h1 style={S.getStarted}>{isSignUp ? 'Welcome!' : 'Hello!'}</h1>
            {challenge ? <p style={S.rightText}>Check your inbox for your one time verification code.</p> : <>
              <p style={S.rightText}>{isSignUp ? 'Already have an account?' : "Don't have an account yet?"}</p>
              <button type="button" style={S.switchBtn} onClick={() => { setError(''); setChallenge(''); setOtp(''); setIsSignUp(!isSignUp); }}>
                {isSignUp ? 'Log in' : 'Sign up'}
              </button>
            </>}
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
    display: 'flex', width: '100%', maxWidth: 840, minHeight: 540,
    borderRadius: 24, overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,.12)',
    background: '#fdf6ec', flexWrap: 'wrap',
  },
  left: {
    flex: '1 1 360px', padding: '34px 42px', display: 'flex', flexDirection: 'column',
    justifyContent: 'center', position: 'relative',
  },
  brand: {
    position: 'absolute', top: 22, left: 42, fontWeight: 700, color: '#6c63ff', fontSize: 15,
  },
  heading: { color: '#6c63ff', fontWeight: 800, fontSize: 26, marginBottom: 4 },
  subheading: { color: '#9089b5', fontSize: 13, marginBottom: 18 },
  error: {
    background: '#fde2e2', color: '#c0392b', borderRadius: 8, padding: '8px 12px',
    fontSize: 13, marginBottom: 14,
  },
  field: { marginBottom: 13 },
  label: { display: 'block', fontSize: 12, fontWeight: 700, color: '#6c63ff', marginBottom: 5 },
  input: {
    width: '100%', padding: '10px 14px', borderRadius: 10,
    border: '1.5px solid #e6dfd3', background: '#fffdf9',
    fontSize: 14, color: '#444', transition: 'all .15s',
  },
  demoBox: {
    background: '#fff3e0', color: '#a3700a', borderRadius: 8, padding: '8px 12px',
    fontSize: 12, marginBottom: 16,
  },
  twoStepNote: { color: '#6c63ff', fontSize: 12, margin: '-4px 0 14px', lineHeight: 1.5 },
  otpHint: { color: '#777', fontSize: 11, marginTop: 6, lineHeight: 1.4 },
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
