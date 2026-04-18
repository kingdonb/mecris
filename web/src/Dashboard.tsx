import React, { useState, useEffect, useCallback } from 'react';
import MomentumVisualizer from './components/MomentumVisualizer';
import Odometer from './components/Odometer';
import ReviewPump from './components/ReviewPump';
import type { AggregateStatusResponse, LanguageStat } from './types/mecris';
import './Dashboard.css';

interface DashboardProps {
  userToken?: string;
}

const Dashboard: React.FC<DashboardProps> = ({ userToken }) => {
  const [data, setData] = useState<AggregateStatusResponse | null>(null);
  const [languages, setLanguages] = useState<LanguageStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<'Home' | 'Akamai' | 'Fermyon'>('Home');
  const [baseUrl, setBaseUrl] = useState('http://localhost:8000');

  const fetchWithTimeout = async (url: string, options: RequestInit, timeout = 3000) => {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(id);
      return response;
    } catch (e) {
      clearTimeout(id);
      throw e;
    }
  };

  const discoverBackend = useCallback(async () => {
    const headers: Record<string, string> = {};
    if (userToken) headers['Authorization'] = `Bearer ${userToken}`;

    const probes = [
      { name: 'Home', url: 'http://localhost:8000' },
      { name: 'Akamai', url: 'https://394b84e7-760c-4336-975b-653c17fdb446.fwf.app' },
      { name: 'Fermyon', url: 'https://mecris-sync-v2-r0r86pso.fermyon.app' }
    ];

    let bestUrl = 'https://mecris-sync-v2-r0r86pso.fermyon.app'; // Default
    let found = false;

    for (const probe of probes) {
      console.log(`PROBING ${probe.name}: ${probe.url}...`);
      try {
        const resp = await fetchWithTimeout(`${probe.url}/health`, { method: 'GET', headers });
        if (resp.ok) {
          console.log(`✅ ${probe.name} is ONLINE`);
          if (!found) {
            setProvider(probe.name as any);
            setBaseUrl(probe.url);
            bestUrl = probe.url;
            found = true;
          }
        } else {
          console.error(`❌ ${probe.name} returned ${resp.status}`);
        }
      } catch (e: any) {
        console.warn(`⚠️ ${probe.name} is OFFLINE: ${e.message}`);
      }
    }

    return bestUrl;
  }, [userToken]);


  const refreshData = useCallback(async (currentUrl?: string) => {
    const url = currentUrl || baseUrl;
    try {
      const headers: Record<string, string> = {};
      if (userToken) headers['Authorization'] = `Bearer ${userToken}`;

      const [aggResp, langResp] = await Promise.all([
        fetch(`${url}/aggregate-status?full=true`, { headers }),
        fetch(`${url}/languages`, { headers })
      ]);

      if (!aggResp.ok || !langResp.ok) throw new Error('API Failure');

      const aggData = await aggResp.json();
      const langData = await langResp.json();

      setData(aggData);
      setLanguages(langData.languages);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [baseUrl, userToken]);

  useEffect(() => {
    const init = async () => {
      const url = await discoverBackend();
      refreshData(url);
    };
    init();
    const interval = setInterval(() => refreshData(), 30000);
    return () => clearInterval(interval);
  }, [discoverBackend, refreshData]);

  const handleMultiplierChange = async (name: string, multiplier: number) => {
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (userToken) headers['Authorization'] = `Bearer ${userToken}`;

      await fetch(`${baseUrl}/languages/multiplier`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name: name.toLowerCase(), multiplier })
      });
      refreshData();
    } catch (e) {
      console.error("Multiplier update failed", e);
    }
  };

  const handleManualSync = async () => {
    try {
      const headers: Record<string, string> = {};
      if (userToken) headers['Authorization'] = `Bearer ${userToken}`;
      await fetch(`${baseUrl}/internal/cloud-sync`, { method: 'POST', headers });
      refreshData();
    } catch (e) {
      console.error("Manual sync failed", e);
    }
  };

  if (loading) return <div className="loading-screen">SYNCING NEURAL LINK...</div>;

  const momentum = data?.all_clear ? 1.0 : 0.6;

  return (
    <div className="dashboard-root">
      <header className="dashboard-header">
        <div className="header-left">
          <h1>MECRIS NEURAL LINK</h1>
          <span className={`provider-badge ${provider.toLowerCase()}`}>{provider.toUpperCase()}</span>
        </div>
        <div className="header-actions">
          <button className="icon-btn" title="Refresh" onClick={() => refreshData()}>🔄</button>
        </div>
      </header>

      <main className="dashboard-content">
        {error && <div className="error-banner">CONNECTION INTERRUPTED: {error}</div>}

        <section className="pulse-matrix">
            <div className="section-label">SYSTEM PULSE</div>
            <div className="pulse-grid">
                {data?.system_pulse?.modalities.map(m => (
                    <div key={m.role} className="pulse-item">
                        <span className={`status-led ${m.status}`} />
                        <span className="modality-name">{m.role.replace('_', ' ').toUpperCase()}</span>
                        <span className="last-seen">{m.minutes_since}m</span>
                    </div>
                ))}
            </div>
        </section>

        <section className="momentum-section">
          <div className="section-label">SYSTEM MOMENTUM</div>
          <div className="momentum-viz-wrapper">
            <MomentumVisualizer momentum={momentum} />
            <div className="momentum-status">
              <span className={`status-label ${data?.all_clear ? 'all-clear' : ''}`}>
                {data?.all_clear ? 'MAJESTY CAKE' : 'STABLE'}
              </span>
              <span className="sessions-label">{data?.score} GOALS SATISFIED</span>
            </div>
          </div>
        </section>

        <div className="manual-trigger-zone">
            <button className="trigger-btn" onClick={handleManualSync}>
                TRIGGER CLOUD RECONCILIATION
            </button>
            <p className="trigger-hint">Forces Fermyon/Akamai to scrape Clozemaster & update Beeminder</p>
        </div>

        <section className="odometer-section">
          <Odometer value={0} label="VIRTUAL BUDGET" symbol="$" digitColor="#FFD600" />
          <Odometer value={0} label="TODAY'S DISTANCE" symbol="" suffix="MI" digitColor="#00E5FF" digits={4} />
        </section>

        <section className="review-pump-section">
          <div className="section-label">LANGUAGE LIABILITIES (THE REVIEW PUMP)</div>
          <div className="review-pump-list">
            {languages.map(stat => (
              <ReviewPump 
                key={stat.name} 
                stat={stat} 
                onMultiplierChange={handleMultiplierChange} 
              />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
};

export default Dashboard;
