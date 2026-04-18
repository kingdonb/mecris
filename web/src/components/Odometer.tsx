import React from 'react';
import './Odometer.css';

interface OdometerProps {
  value: number;
  label: string;
  symbol?: string;
  suffix?: string;
  digitColor?: string;
  digits?: number;
  decimalPlaces?: number;
}

const Odometer: React.FC<OdometerProps> = ({
  value,
  label,
  symbol = '$',
  suffix = '',
  digitColor = '#FFD600',
  digits = 7,
  decimalPlaces = 2
}) => {
  const formattedValue = value.toFixed(decimalPlaces).padStart(digits + (decimalPlaces > 0 ? 1 : 0), '0');

  return (
    <div className="odometer-container">
      <div className="odometer-label">{label}</div>
      <div className="odometer-frame">
        {symbol && <span className="odometer-symbol">{symbol}</span>}
        <div className="odometer-digits">
          {formattedValue.split('').map((char, index) => (
            <div 
              key={index} 
              className={`odometer-digit ${char === '.' ? 'odometer-decimal' : ''}`}
              style={{ color: char === '.' ? 'white' : digitColor }}
            >
              {char}
            </div>
          ))}
        </div>
        {suffix && <span className="odometer-suffix">{suffix}</span>}
      </div>
    </div>
  );
};

export default Odometer;
