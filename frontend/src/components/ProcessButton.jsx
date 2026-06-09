// Feldolgozás indítása gomb – betöltési állapottal
import React from 'react';
import LoadingSpinner from './LoadingSpinner.jsx';

/**
 * Props:
 *   onClick  – gombnyomás callback
 *   disabled – letiltja a gombot
 *   loading  – betöltési animációt mutat
 */
function ProcessButton({ onClick, disabled = false, loading = false }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        flex items-center gap-2 px-6 py-2.5 rounded-lg font-semibold text-white transition-colors
        ${disabled || loading
          ? 'bg-gray-300 cursor-not-allowed'
          : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'}
      `}
    >
      {loading ? (
        <>
          <LoadingSpinner size="sm" />
          Feldolgozás...
        </>
      ) : (
        <>
          <span>⚙️</span>
          Feldolgozás indítása
        </>
      )}
    </button>
  );
}

export default ProcessButton;
