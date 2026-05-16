'use client';

import { useState, useEffect } from 'react';
import { authFetch, requireAuth } from '@/lib/api';

type Persona = {
    id: number;
    name: string;
    objective: string;
    skills?: string;
};

export default function PersonasPage() {
    const [personas, setPersonas] = useState<Persona[]>([]);
    const [name, setName] = useState('');
    const [objective, setObjective] = useState('b2b_agency');
    const [skills, setSkills] = useState('');
    const [resumeText, setResumeText] = useState('');
    const [valueProp, setValueProp] = useState('');
    const [status, setStatus] = useState('');

    const fetchPersonas = async () => {
        try {
            const res = await authFetch('/api/personas');
            const data = await res.json();
            setPersonas(data);
        } catch (e) { console.error(e); }
    };

    useEffect(() => {
        if (!requireAuth()) return;
        void Promise.resolve().then(fetchPersonas);
    }, []);

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const res = await authFetch('/api/personas', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, objective, skills, resume_text: resumeText, value_proposition: valueProp })
            });

            if (res.ok) {
                setStatus('Persona Created!');
                setName('');
                setSkills('');
                setResumeText('');
                setValueProp('');
                fetchPersonas();
                setTimeout(() => setStatus(''), 3000);
            }
        } catch {
            setStatus('Error saving persona.');
        }
    };

    return (
        <div style={{ padding: '2rem' }}>
            <div className="glass-panel" style={{ maxWidth: '800px', margin: '0 auto', padding: '2rem' }}>
                <h2>🎭 Manage Your Outreach Personas</h2>
                <p style={{ color: '#666', marginBottom: '2rem' }}>
                    Create dynamic identities. Are you hunting for a job? Pitching freelance services? The AI will read your persona and completely alter the cold emails it generates perfectly for your specific playbook.
                </p>

                <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', borderBottom: '1px solid #ccc', paddingBottom: '2rem', marginBottom: '2rem' }}>
                    <div>
                        <label className="form-label">Persona Name</label>
                        <input className="form-input" type="text" value={name} onChange={e => setName(e.target.value)} required placeholder="e.g. LeadGen Expert or AI Engineer" />
                    </div>
                    
                    <div>
                        <label className="form-label">Objective playbook</label>
                        <select className="form-input" value={objective} onChange={e => setObjective(e.target.value)} required>
                            <option value="b2b_agency">B2B Agency / Sales</option>
                            <option value="freelance">Freelance Client Hunt</option>
                            <option value="job_hunt">Job / Internship Search</option>
                        </select>
                    </div>

                    <div>
                        <label className="form-label">Hard Skills (Comma separated)</label>
                        <input className="form-input" type="text" value={skills} onChange={e => setSkills(e.target.value)} placeholder="e.g. Python, React, Next.js" />
                    </div>

                    {objective === 'job_hunt' && (
                        <div>
                            <label className="form-label">Resume / Cover Letter Context</label>
                            <textarea className="form-input" rows={4} value={resumeText} onChange={e => setResumeText(e.target.value)} placeholder="Paste bullet points of your experience so the AI can weave it into the outreach..."></textarea>
                        </div>
                    )}

                    {(objective === 'b2b_agency' || objective === 'freelance') && (
                        <div>
                            <label className="form-label">Value Proposition (What do you sell?)</label>
                            <textarea className="form-input" rows={3} value={valueProp} onChange={e => setValueProp(e.target.value)} placeholder="e.g. We build high-converting mobile apps for local businesses."></textarea>
                        </div>
                    )}

                    <button type="submit" className="btn" style={{ width: '100%', fontSize: '1rem' }}>Create Persona</button>
                    {status && <p style={{ color: 'green', fontWeight: 'bold', textAlign: 'center' }}>{status}</p>}
                </form>

                <h3>Your Active Personas</h3>
                {personas.length === 0 ? <p>No personas created yet.</p> : (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        {personas.map(p => (
                            <div key={p.id} style={{ border: '1px solid #ddd', padding: '1rem', borderRadius: '8px', background: '#f9fafb' }}>
                                <h4 style={{ margin: '0 0 0.5rem 0' }}>{p.name}</h4>
                                <span className="badge high" style={{ marginBottom: '0.5rem', display: 'inline-block' }}>{p.objective}</span>
                                <p style={{ fontSize: '0.875rem', color: '#555' }}><strong>Skills:</strong> {p.skills}</p>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
