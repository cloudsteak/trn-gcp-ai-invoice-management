// Export gombok sávja – PDF, XLSX, CSV és könyvelői adatlap letöltés
import React, { useState } from 'react';
import { downloadExport } from '../services/api.js';

/**
 * Props:
 *   jobId – az aktuális feldolgozási job azonosítója
 */
function ExportBar({ jobId }) {
  const [loading, setLoading] = useState(null); // Melyik export tölt éppen

  const handleExport = async (format) => {
    if (!jobId || loading) return;
    setLoading(format);
    try {
      await downloadExport(jobId, format);
    } catch (err) {
      alert('Letöltési hiba: ' + (err.message || 'Ismeretlen hiba'));
    } finally {
      setLoading(null);
    }
  };

  const buttonBase =
    'flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

  return (
    <div className="flex flex-wrap gap-3 items-center">
      <span className="text-sm text-gray-500 font-medium">Letöltés:</span>

      {/* PDF export */}
      <button
        onClick={() => handleExport('pdf')}
        disabled={!jobId || !!loading}
        className={`${buttonBase} bg-red-100 text-red-700 hover:bg-red-200`}
      >
        {loading === 'pdf' ? '⏳' : '📄'} PDF
      </button>

      {/* XLSX export */}
      <button
        onClick={() => handleExport('xlsx')}
        disabled={!jobId || !!loading}
        className={`${buttonBase} bg-green-100 text-green-700 hover:bg-green-200`}
      >
        {loading === 'xlsx' ? '⏳' : '📊'} XLSX
      </button>

      {/* CSV export */}
      <button
        onClick={() => handleExport('csv')}
        disabled={!jobId || !!loading}
        className={`${buttonBase} bg-gray-100 text-gray-700 hover:bg-gray-200`}
      >
        {loading === 'csv' ? '⏳' : '📋'} CSV
      </button>

      {/* Könyvelői adatlap – vizuálisan elkülönített, ez a fő könyvelési export */}
      <button
        onClick={() => handleExport('xlsx-accounting')}
        disabled={!jobId || !!loading}
        className={`${buttonBase} bg-blue-600 text-white hover:bg-blue-700 ml-2 shadow-sm`}
      >
        {loading === 'xlsx-accounting' ? '⏳' : '🧾'} Könyvelői adatlap
      </button>
    </div>
  );
}

export default ExportBar;
