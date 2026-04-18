import React, { useState, useEffect } from 'react';
import MomentumVisualizer from './components/MomentumVisualizer';
import Odometer from './components/Odometer';
import ReviewPump from './components/ReviewPump';
import './Dashboard.css';

interface DashboardProps {
  userToken?: string;
}

const Dashboard: React.FC<DashboardProps> = ({ userToken }) => {
  const [momentum, setMomentum] = useState(0.8);
  const [budget, setBudget] = useState(20.91);
  const [distance, setDistance] = useState(1.5);
  const [languageStats, setLanguageStats] = useState([
    {
      name: 'Arabic',
      current: 1762,
      tomorrow: 45,
      next_7_days: 315,
      pump_multiplier: 2.0,
      safebuf: 10,
      has_goal: true
    },
    {
      name: 'Greek',
      current: 0,
      tomorrow: 28,
      next_7_days: 196,
      pump_multiplier: 7.0,
      safebuf: 22,
      has_goal: true
    }
  ]);
  const [syncStatus, setSyncStatus] = useState('Ready');
  const [lastSync, setLastSync] = useState('22:01');

  const handleMultiplierChange = (name: string, multiplier: number) => {
    setLanguageStats(prev => prev.map(s => 
      s.name === name ? { ...s, pump_multiplier: multiplier } : s
    ));
    // TODO: API Call
  };

  const handleForceSync = () => {
    setSyncStatus('Syncing...');
    setTimeout(() => {
      setSyncStatus('Success');
      setLastSync(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    }, 2000);
  };

  return (
    <div className="dashboard-root">
      <header className="dashboard-header">
        <h1>MECRIS NEURAL LINK</h1>
        <div className="header-actions">
          <button className="icon-btn">👤</button>
          <button className="icon-btn">⚙️</button>
          <button className="icon-btn" onClick={handleForceSync}>🔄</button>
        </div>
      </header>

      <main className="dashboard-content">
        <section className="momentum-section">
          <div className="section-label">SYSTEM MOMENTUM</div>
          <div className="momentum-viz-wrapper">
            <MomentumVisualizer momentum={momentum} />
            <div className="momentum-status">
              <span className="status-label">STABLE</span>
              <span className="sessions-label">1 SESSION DETECTED</span>
            </div>
          </div>
        </section>

        <section className="sync-info">
            <span className="cloud-badge">HOME: ONLINE</span>
            <span className="sync-text">CLOUD SYNC: {syncStatus} ({lastSync})</span>
            <button className="text-sync-btn" onClick={handleForceSync}>FORCE SYNC</button>
        </section>

        <section className="odometer-section">
          <Odometer value={budget} label="VIRTUAL BUDGET" />
          <Odometer value={distance} label="TODAY'S DISTANCE" symbol="" suffix="MI" digitColor="#00E5FF" digits={4} />
        </section>

        <section className="review-pump-section">
          <div className="section-label">LANGUAGE LIABILITIES (THE REVIEW PUMP)</div>
          <div className="review-pump-list">
            {languageStats.map(stat => (
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
