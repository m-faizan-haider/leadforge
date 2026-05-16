'use client';
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { authFetch, requireAuth } from '@/lib/api';

type Lead = {
  id: number;
  business_name: string;
  phone?: string;
  website?: string;
  email?: string;
  opportunity_score: number;
  tech_stack?: string;
  status: string;
  email_draft?: string;
};

type CampaignData = {
  campaign: {
    id: number;
    name: string;
    niche: string;
    location: string;
    status: string;
  };
  leads: Lead[];
  leads_count: number;
};

function leadStatusLabel(status: string) {
  if (status === 'audited') return 'Audited';
  if (status === 'emailed') return 'In Sequence';
  if (status === 'site_blocked') return 'Blocked';
  if (status === 'replied') return 'Replied';
  return 'Skipped';
}

export default function CampaignView() {
  const params = useParams();
  const id = String(params.id);
  const [data, setData] = useState<CampaignData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedEmail, setSelectedEmail] = useState<string | null>(null);

  const fetchCampaign = useCallback(async () => {
    try {
      const res = await authFetch(`/api/campaigns/${id}`);
      if (res.ok) {
        const result = await res.json();
        setData(result);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  const handleSendBlast = async () => {
    if (!confirm('Are you sure you want to blast emails to all valid leads in this campaign?')) return;
    try {
      setLoading(true);
      const res = await authFetch(`/api/campaigns/${id}/send`, { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        alert(`Finished: Sent ${result.results?.success || 0} emails.`);
        fetchCampaign();
      } else {
        const err = await res.json();
        alert(`Failed to send blast: ${err.detail || 'Unknown error'}`);
      }
    } catch {
      alert('Error contacting API to send emails.');
    } finally {
      setLoading(false);
    }
  };

  const handleForceSequence = async () => {
    if (!confirm('This will skip the 3-5 day waiting safety mechanism and instantly send follow-up AI emails to anyone ready. Continue?')) return;
    try {
      setLoading(true);
      const res = await authFetch(`/api/campaigns/${id}/force_sequence`, { method: 'POST' });
      if (res.ok) {
        const result = await res.json();
        alert(`Finished: Sent ${result.results?.advanced || 0} follow-up sequences. Errors: ${result.results?.errors || 0}`);
        fetchCampaign();
      } else {
        const err = await res.json();
        alert(`Failed: ${err.detail || 'Unknown error. Make sure SMTP is set.'}`);
      }
    } catch {
      alert('Error contacting API.');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkReplied = async (leadId: number) => {
    try {
      const res = await authFetch(`/api/leads/${leadId}/replied`, { method: 'POST' });
      if (res.ok) fetchCampaign();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDownloadCsv = async () => {
    const res = await authFetch(`/api/campaigns/${id}/export`);
    if (!res.ok) {
      alert('Could not download CSV.');
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `LeadForge_campaign_${id}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (!requireAuth()) return;
    fetchCampaign();
  }, [fetchCampaign, id]);

  useEffect(() => {
    const status = data?.campaign?.status;
    if (status !== 'queued' && status !== 'running') return;
    const interval = setInterval(fetchCampaign, 5000);
    return () => clearInterval(interval);
  }, [data?.campaign?.status, fetchCampaign, id]);

  if (loading && !data) {
    return (
      <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
        <div className="spinner" style={{ margin: '0 auto', marginBottom: '1rem' }}></div>
        <h2>Loading Campaign Data...</h2>
      </div>
    );
  }

  if (!data) {
    return <div className="glass-panel" style={{ padding: '2rem' }}>Campaign not found.</div>;
  }

  const { campaign, leads, leads_count } = data;
  const isPolling = campaign.status === 'queued' || campaign.status === 'running';

  return (
    <div className="glass-panel" style={{ padding: '2rem' }}>
      <div className="header">
        <div>
          <h2>{campaign.name}</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Targeting: {campaign.niche} in {campaign.location}</p>
        </div>
        {isPolling && (
          <div className="status-indicator">
            <div className="spinner"></div>
            Scraping in progress... ({leads_count} Leads Extracted)
          </div>
        )}
        {!isPolling && leads.length > 0 && (
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn" onClick={handleDownloadCsv} style={{ background: 'transparent', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}>
              Download CSV
            </button>
            <button className="btn" onClick={handleSendBlast} style={{ background: 'var(--success-color)' }}>
              Start Email Sequence
            </button>
            <button className="btn" onClick={handleForceSequence} style={{ background: 'transparent', border: '1px solid var(--accent-color)', color: 'var(--accent-color)' }}>
              Force Sequence (Test)
            </button>
          </div>
        )}
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Business Name</th>
              <th>Website</th>
              <th>Opp. Score</th>
              <th>Tech</th>
              <th>Status</th>
              <th>AI Action</th>
            </tr>
          </thead>
          <tbody>
            {leads.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                  No leads processed yet. The campaign is currently scraping and enriching leads...
                </td>
              </tr>
            ) : (
              leads.map((lead) => (
                <tr key={lead.id}>
                  <td>
                    <strong>{lead.business_name}</strong><br />
                    <small style={{ color: 'var(--text-secondary)' }}>{lead.phone}</small>
                  </td>
                  <td>
                    {lead.website ? (
                      <a href={lead.website} target="_blank" rel="noopener noreferrer">Visit Site</a>
                    ) : <span style={{ color: 'var(--text-secondary)' }}>N/A</span>}
                    <br />
                    {lead.email && <small style={{ color: 'var(--accent-color)' }}>{lead.email}</small>}
                  </td>
                  <td>
                    {lead.opportunity_score > 0 ? (
                      <span className={`badge ${lead.opportunity_score >= 20 ? 'high' : lead.opportunity_score >= 10 ? 'medium' : 'low'}`}>
                        {lead.opportunity_score}/100
                      </span>
                    ) : (
                      <span className="badge low">0/100</span>
                    )}
                  </td>
                  <td>
                    {lead.tech_stack ? <span className="badge medium" style={{ background: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa' }}>{lead.tech_stack}</span> : '-'}
                  </td>
                  <td>
                    {leadStatusLabel(lead.status)}
                    {lead.status === 'emailed' && (
                      <div style={{ marginTop: '0.5rem' }}>
                        <button onClick={() => handleMarkReplied(lead.id)} style={{ fontSize: '10px', padding: '4px 6px', cursor: 'pointer', background: '#fee2e2', color: '#991b1b', border: 'none', borderRadius: '4px' }}>
                          Mark Replied
                        </button>
                      </div>
                    )}
                  </td>
                  <td>
                    {lead.email_draft ? (
                      <button
                        className="btn"
                        style={{ padding: '0.4rem 1rem', fontSize: '0.875rem', minWidth: 'auto' }}
                        onClick={() => setSelectedEmail(lead.email_draft ?? null)}
                      >
                        View AI Email
                      </button>
                    ) : (lead.status === 'skipped' || lead.status === 'site_blocked') ? (
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>N/A</span>
                    ) : (
                      <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Processing...</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedEmail && (
        <div className="modal-backdrop" onClick={() => setSelectedEmail(null)}>
          <div className="glass-panel modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelectedEmail(null)}>&times;</button>
            <h3 style={{ marginTop: '0' }}>Generated AI Cold Email</h3>
            <p style={{ color: 'var(--text-secondary)' }}>This email is personalized based on the weaknesses found on the lead website.</p>
            <div className="email-draft">
              {selectedEmail}
            </div>
            <div style={{ marginTop: '1.5rem', textAlign: 'right', display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button className="btn" style={{ background: 'transparent', border: '1px solid var(--border-color)', boxShadow: 'none' }} onClick={() => setSelectedEmail(null)}>Close</button>
              <button className="btn" onClick={() => {
                navigator.clipboard.writeText(selectedEmail);
                alert('Copied to clipboard!');
              }}>Copy to Clipboard</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
