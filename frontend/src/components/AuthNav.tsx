'use client';

import Link from 'next/link';
import { useSyncExternalStore } from 'react';
import { clearToken, getToken } from '@/lib/api';

function subscribeToAuthChanges(callback: () => void) {
  window.addEventListener('storage', callback);
  return () => window.removeEventListener('storage', callback);
}

function getClientAuthSnapshot() {
  return Boolean(getToken());
}

function getServerAuthSnapshot() {
  return false;
}

export default function AuthNav() {
  const loggedIn = useSyncExternalStore(
    subscribeToAuthChanges,
    getClientAuthSnapshot,
    getServerAuthSnapshot
  );

  const logout = () => {
    clearToken();
    window.location.href = '/login';
  };

  return (
    <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
      {loggedIn ? (
        <>
          <Link href="/personas" style={{ textDecoration: 'none', color: 'inherit', fontWeight: 'bold' }}>
            Personas
          </Link>
          <Link href="/settings" style={{ textDecoration: 'none', color: 'inherit', fontWeight: 'bold' }}>
            SMTP Settings
          </Link>
          <Link href="/campaigns/new" className="btn">
            + New Campaign
          </Link>
          <button className="link-button" type="button" onClick={logout}>
            Log out
          </button>
        </>
      ) : (
        <Link href="/login" className="btn">
          Log in
        </Link>
      )}
    </nav>
  );
}
