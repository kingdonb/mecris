import React from 'react';
import './MomentumVisualizer.css';

interface MomentumVisualizerProps {
  momentum: number;
  overrideColor?: string;
}

const MomentumVisualizer: React.FC<MomentumVisualizerProps> = ({ momentum, overrideColor }) => {
  const isStable = momentum > 0.5;
  const color1 = overrideColor || (isStable ? '#00C853' : '#FF1744');
  const color2 = overrideColor || (isStable ? '#2979FF' : '#FFEA00');

  const scale = 0.8 + momentum * 0.4;

  return (
    <div className="momentum-container" style={{ transform: `scale(${scale})` }}>
      <div 
        className="momentum-circle" 
        style={{ 
          background: `radial-gradient(circle, ${color1}cc 0%, ${color2}33 50%, transparent 100%)` 
        }} 
      />
    </div>
  );
};

export default MomentumVisualizer;
