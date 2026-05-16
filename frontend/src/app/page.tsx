'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { authFetch, requireAuth } from '@/lib/api';

type Campaign = {
  id: number;
  name: string;
  niche: string;
  location: string;
  status: string;
};

export default function Dashboard() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState('');

  const fetchCampaigns = async () => {
    try {
      // Connects to the local FastAPI backend
      const res = await authFetch('/api/campaigns');
      if (res.ok) {
        const data = await res.json();
        setCampaigns(data);
        setApiError('');
      }
    } catch {
      setApiError('Could not reach the API. Check that FastAPI is running and ALLOWED_ORIGINS includes this frontend URL.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!requireAuth()) return;
    fetchCampaigns();
    // Poll every 5 seconds for live updates
    const interval = setInterval(fetchCampaigns, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="glass-panel" style={{ padding: '2rem' }}>
      <h2>Recent Campaigns</h2>
      
      {loading && campaigns.length === 0 ? (
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <div className="spinner"></div>
          <p>Connecting to backend...</p>
        </div>
      ) : apiError ? (
        <p style={{ color: 'var(--warning-color)' }}>{apiError}</p>
      ) : campaigns.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)' }}>No campaigns found. Start by creating a new one!</p>
      ) : (
        <div className="grid">
          {campaigns.map((camp) => (
            <Link key={camp.id} href={`/campaigns/${camp.id}`} style={{ textDecoration: 'none' }}>
              <div className="card glass-panel">
                <h3 className="card-title">{camp.name}</h3>
                <div className="card-meta">
                  <span>Niche: <strong>{camp.niche}</strong></span>
                  <span>Location: <strong>{camp.location}</strong></span>
                </div>
                <div className="badge high" style={{ marginTop: '0.5rem', alignSelf: 'flex-start' }}>
                  Open Campaign &rarr;
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
