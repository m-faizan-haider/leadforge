'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { authFetch, requireAuth } from '@/lib/api';

type Persona = {
  id: number;
  name: string;
  objective: string;
};

export default function NewCampaign() {
  const router = useRouter();
  const [niche, setNiche] = useState('Plumbers');
  const [location, setLocation] = useState('Dubai');
  const [maxLeads, setMaxLeads] = useState(10);
  const [loading, setLoading] = useState(false);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personaId, setPersonaId] = useState<number | ''>('');
  const [screenshotEnabled, setScreenshotEnabled] = useState(false);

  useEffect(() => {
    if (!requireAuth()) return;
    authFetch('/api/personas')
      .then(r => r.json())
      .then(d => {
        setPersonas(d);
        if (d.length > 0) setPersonaId(d[0].id);
      })
      .catch(e => console.error(e));
  }, []);

  const handleSubmit = async (e: React.MouseEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await authFetch('/api/campaigns', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          niche,
          location,
          max_leads: maxLeads,
          persona_id: personaId === '' ? null : personaId,
          screenshot_enabled: screenshotEnabled,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        router.push(`/campaigns/${data.campaign_id}`);
      } else {
        alert("Failed to start campaign");
      }
    } catch (e) {
      console.error(e);
      alert("Error starting campaign - is the python API server actively running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '3rem', maxWidth: '600px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '2rem', textAlign: 'center' }}>Launch New Campaign</h2>
      <div>
        <div className="input-group">
          <label>Target Niche</label>
          <input
            type="text"
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
            placeholder="e.g. Plumbers, Roofers, Dentists"
          />
        </div>

        <div className="input-group">
          <label>Location</label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Dubai, New York, London"
          />
        </div>

        <div className="input-group">
          <label>Max Leads to Scrape</label>
          <input
            type="number"
            value={maxLeads || ''}
            onChange={(e) => setMaxLeads(parseInt(e.target.value) || 0)}
            min="1"
            max="50"
          />
        </div>

        <div className="input-group">
          <label>Campaign Persona (Objective)</label>
          <select
            value={personaId}
            onChange={(e) => setPersonaId(parseInt(e.target.value) || '')}
            style={{ width: '100%', padding: '0.75rem', borderRadius: '4px', border: '1px solid #ccc', marginBottom: '1rem', background: '#fff' }}
          >
            <option value="" disabled>Select a Persona</option>
            {personas.map(p => (
              <option key={p.id} value={p.id}>{p.name} ({p.objective})</option>
            ))}
          </select>
        </div>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={screenshotEnabled}
            onChange={(e) => setScreenshotEnabled(e.target.checked)}
          />
          <span>Capture website screenshots</span>
        </label>

        <button
          onClick={handleSubmit}
          className="btn"
          style={{ width: '100%', marginTop: '1rem' }}
          disabled={loading}
        >
          {loading ? (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', justifyContent: 'center' }}>
              <div className="spinner"></div> Initiating Pipeline...
            </div>
          ) : 'Launch Scraper Engine'}
        </button>
      </div>
    </div>
  );
}
