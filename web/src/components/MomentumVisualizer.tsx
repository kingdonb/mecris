import React from 'react';
import './MomentumVisualizer.css';

interface MomentumVisualizerProps {
  momentum: number;
  isAllClear?: boolean;
}

const MomentumVisualizer: React.FC<MomentumVisualizerProps> = ({ momentum, isAllClear }) => {
  const isStable = momentum > 0.5;
  
  // Color palette for the "Neural Link" aesthetic
  const baseColor = isAllClear ? '#FFD600' : (isStable ? '#00C853' : '#FF1744');
  const glowColor = isAllClear ? '#FFA000' : (isStable ? '#00E676' : '#D50000');

  return (
    <div className={`momentum-wrapper ${isAllClear ? 'all-clear' : ''}`}>
      <div className="momentum-glow" style={{ backgroundColor: glowColor }} />
      <div className="momentum-orb">
        <div 
          className="orb-layer layer-1" 
          style={{ background: `radial-gradient(circle at 30% 30%, ${baseColor} 0%, transparent 70%)` }} 
        />
        <div 
          className="orb-layer layer-2" 
          style={{ background: `linear-gradient(135deg, ${glowColor}33 0%, transparent 100%)` }} 
        />
        <div className="orb-core" style={{ backgroundColor: baseColor }} />
      </div>
      {isAllClear && <div className="majesty-rings">
          <div className="ring ring-1" />
          <div className="ring ring-2" />
      </div>}
    </div>
  );
};

export default MomentumVisualizer;
