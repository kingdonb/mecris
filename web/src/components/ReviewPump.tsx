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
    if (m <= 1.0) return "Steady";
    if (m <= 2.0) return "Laminar";
    if (m <= 4.0) return "Turbulent";
    if (m <= 7.0) return "The Blitz";
    return "Canonical";
  };

  const calculateTargetFlow = (m: number, current: number, tomorrow: number) => {
    // Simplified version of the Android calculator logic
    const base = Math.max(current / 30, tomorrow);
    return Math.ceil(base * m);
  };

  const targetFlow = calculateTargetFlow(stat.pump_multiplier, stat.current, stat.tomorrow);

  return (
    <div className={`review-pump-card ${!stat.has_goal ? 'no-goal' : ''}`} style={{ borderColor: `${accentColor}4d` }}>
      <div className="review-pump-header">
        <div className="review-pump-title-group">
          <span className="review-pump-name" style={{ color: accentColor }}>{stat.name.toUpperCase()}</span>
          {!stat.has_goal && <span className="no-goal-badge">NO GOAL</span>}
          <div className="review-pump-debt">DEBT: {stat.current} CARDS</div>
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
            <div className="gauge-marker" style={{ left: `${Math.min(targetFlow / 10, 90)}%` }} />
        </div>
        <div className="gauge-content">
          <div className="target-flow-group">
            <span className="gauge-label">TARGET FLOW</span>
            <span className="target-flow-value" style={{ color: accentColor }}>{targetFlow}</span>
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
