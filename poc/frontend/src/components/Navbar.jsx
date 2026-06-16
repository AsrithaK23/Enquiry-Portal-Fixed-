import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function Navbar() {
  const { pathname } = useLocation();
  const active = (path) => pathname === path ? 'nav-link active fw-semibold' : 'nav-link';

  return (
    <nav className="navbar navbar-expand navbar-dark bg-primary px-4 py-2">
      <span className="navbar-brand fw-bold">📋 Enquiry Portal</span>
      <div className="navbar-nav ms-3">
        <Link className={active('/dashboard')} to="/dashboard">Dashboard</Link>
        <Link className={active('/enquiries')} to="/enquiries">All Enquiries</Link>
        <Link className={active('/clients')} to="/clients">Clients</Link>
        <Link className={active('/add')}       to="/add">+ New Enquiry</Link>
      </div>
    </nav>
  );
}
