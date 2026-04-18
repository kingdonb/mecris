import React from 'react';
import './ReviewPump.css';

interface LanguageStat {
  name: string;
  current: number;
  tomorrow: number;
  next_7_days: number;
  pump_multiplier: number;
  safebuf: number;
  has_goal: boolean;
}

interface ReviewPumpProps {
  stat: LanguageStat;
  onMultiplierChange: (name: string, multiplier: number) => void;
  disabled?: boolean;
}

const ReviewPump: React.FC<ReviewPumpProps> = ({ stat, onMultiplierChange, disabled }) => {
  const multipliers = [1, 2, 3, 4, 5, 6, 7, 10];
  const accentColor = stat.name.toUpperCase() === 'ARABIC' ? '#FFD600' : 
                     stat.name.toUpperCase() === 'GREEK' ? '#00E5FF' : '#FFFFFF';

  const leverName = (m: number) => {
    switch (Math.floor(m)) {
      case 1: return "Maintenance";
      case 2: return "Steady";
      case 3: return "Brisk";
      case 4: return "Aggressive";
      case 5: return "High Pressure";
      case 6: return "Very High";
      case 7: return "The Blitz";
      case 10: return "System Overdrive";
      default: return "Custom";
    }
  };

  const getClearanceDays = (m: number) => {
    switch (Math.floor(m)) {
      case 1: return null;
      case 2: return 14;
      case 3: return 10;
      case 4: return 7;
      case 5: return 5;
      case 6: return 3;
      case 7: return 2;
      case 10: return 1;
      default: return null;
    }
  };

  const calculateTargetFlow = (m: number, current: number, tomorrow: number) => {
    const days = getClearanceDays(m);
    if (days === null) return tomorrow;
    return Math.ceil(tomorrow + (current / days));
  };

  const targetFlow = calculateTargetFlow(stat.pump_multiplier, stat.current, stat.tomorrow);
  const remaining = stat.target_flow_rate;

  return (
    <div className={`review-pump-card ${!stat.has_goal ? 'no-goal' : ''} ${stat.goal_met ? 'goal-met' : ''}`} style={{ borderColor: `${accentColor}4d` }}>
      <div className="review-pump-header">
        <div className="review-pump-title-group">
          <div className="pump-name-row">
            <span className="review-pump-name" style={{ color: accentColor }}>{stat.name.toUpperCase()}</span>
            {!stat.has_goal && <span className="no-goal-badge">NO GOAL</span>}
            {stat.goal_met && <span className="goal-met-badge">GOAL MET</span>}
          </div>
          <div className="review-pump-debt">DEBT: {stat.current} {stat.name.toUpperCase() === 'ARABIC' ? 'CARDS' : 'PTS'}</div>
        </div>
        <div className="lever-badge" style={{ backgroundColor: `${accentColor}1a`, color: accentColor }}>
          {leverName(stat.pump_multiplier).toUpperCase()}
        </div>
      </div>

      <div className="review-pump-forecast">
        <div className="forecast-item">
          <span className="forecast-label">TOMORROW</span>
          <span className="forecast-value">+{stat.tomorrow}</span>
        </div>
        <div className="forecast-item text-right">
          <span className="forecast-label">7 DAY</span>
          <span className="forecast-value">+{stat.next_7_days}</span>
        </div>
      </div>

      <div className="pressure-gauge">
        <div className="gauge-background">
            <div className="gauge-marker" style={{ left: `${Math.min((stat.absolute_target > 0 ? (stat.daily_completions / stat.absolute_target) : 1) * 100, 100)}%` }} />
        </div>
        <div className="gauge-content">
          <div className="target-flow-group">
            <span className="gauge-label">PROGRESS: {stat.daily_completions} / {stat.absolute_target}</span>
            <span className="target-flow-value" style={{ color: accentColor }}>{remaining}</span>
            {remaining > 0 ? <span className="remaining-label">REMAINING TODAY</span> : <span className="remaining-label success">GOAL SATISFIED</span>}
          </div>
          <div className="runway-group">
            <span className="gauge-label">RUNWAY</span>
            <span className="runway-value" style={{ color: stat.safebuf < 3 ? '#FF1744' : '#00C853' }}>{stat.safebuf}D</span>
          </div>
        </div>
      </div>

      <div className="multiplier-selector">
        <span className="selector-label">SHIFT LEVER</span>
        <div className="multiplier-grid">
          {multipliers.map((m) => (
            <button
              key={m}
              className={`multiplier-btn ${stat.pump_multiplier === m ? 'active' : ''}`}
              style={stat.pump_multiplier === m ? { backgroundColor: accentColor } : {}}
              onClick={() => onMultiplierChange(stat.name, m)}
              disabled={disabled}
            >
              {m}x
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ReviewPump;
