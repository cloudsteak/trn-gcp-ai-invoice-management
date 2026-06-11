// Betöltési animáció komponens – feldolgozás közbeni megjelenítéshez
import React from 'react';

/**
 * Props:
 *   size – 'sm' | 'md' | 'lg' (alapértelmezett: 'md')
 */
function LoadingSpinner({ size = 'md' }) {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-2',
    lg: 'w-12 h-12 border-4',
  };

  return (
    <div
      className={`
        ${sizeClasses[size] || sizeClasses.md}
        rounded-full border-blue-200 border-t-blue-600
        animate-spin
      `}
      role="status"
      aria-label="Betöltés..."
    />
  );
}

export default LoadingSpinner;
