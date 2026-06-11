// Összesített eredménytáblázat – minden számla egy sor, kattintható sorok
import React, { useState } from 'react';
import StatusBadge from './StatusBadge.jsx';
import InvoiceDetail from './InvoiceDetail.jsx';
import { formatAmount } from '../utils/formatters.js';

/**
 * Props:
 *   results – InvoiceResult objektumok tömbje
 */
function ResultTable({ results = [] }) {
  // Megnyitott részletező panel azonosítója
  const [openFileId, setOpenFileId] = useState(null);
  // Státusz szerinti szűrő
  const [filterStatus, setFilterStatus] = useState('all');

  const filtered = filterStatus === 'all'
    ? results
    : results.filter((r) => r.status === filterStatus);

  // Összesítő adatok számítása
  const totalGross = results.reduce(
    (sum, r) => sum + (r.invoice_data?.gross_amount || 0), 0
  );
  const errorCount = results.filter((r) => r.status === 'error').length;
  const warningCount = results.filter((r) => r.status === 'warning').length;

  const toggleDetail = (fileId) => {
    setOpenFileId((prev) => (prev === fileId ? null : fileId));
  };

  return (
    <div>
      {/* Összesítő sor */}
      <div className="flex flex-wrap gap-4 mb-4 text-sm text-gray-600">
        <span>Összesen: <strong>{results.length}</strong> számla</span>
        <span>Bruttó összeg: <strong>{formatAmount(totalGross)} Ft</strong></span>
        {errorCount > 0 && (
          <span className="text-red-600">❌ Hibás: <strong>{errorCount}</strong></span>
        )}
        {warningCount > 0 && (
          <span className="text-yellow-600">⚠️ Figyelmeztetés: <strong>{warningCount}</strong></span>
        )}
      </div>

      {/* Szűrő */}
      <div className="flex gap-2 mb-3">
        {['all', 'ok', 'warning', 'error'].map((s) => (
          <button
            key={s}
            onClick={() => setFilterStatus(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors
              ${filterStatus === s
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'}`}
          >
            {s === 'all' ? 'Összes' : s === 'ok' ? 'Rendben' : s === 'warning' ? 'Figyelmeztetés' : 'Hiba'}
          </button>
        ))}
      </div>

      {/* Táblázat */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-100 text-gray-600 text-left">
              <th className="px-3 py-2 font-medium">Fájlnév</th>
              <th className="px-3 py-2 font-medium">Eladó</th>
              <th className="px-3 py-2 font-medium text-right">Bruttó összeg</th>
              <th className="px-3 py-2 font-medium">Pénznem</th>
              <th className="px-3 py-2 font-medium">Státusz</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((result) => (
              <React.Fragment key={result.file_id}>
                <tr
                  onClick={() => toggleDetail(result.file_id)}
                  className="border-t border-gray-100 hover:bg-blue-50 cursor-pointer transition-colors"
                >
                  <td className="px-3 py-2 text-blue-700 underline">{result.file_name}</td>
                  <td className="px-3 py-2 text-gray-700">
                    {result.invoice_data?.supplier_name || '–'}
                  </td>
                  <td className="px-3 py-2 text-right text-gray-800 font-mono">
                    {formatAmount(result.invoice_data?.gross_amount)}
                  </td>
                  <td className="px-3 py-2 text-gray-600">
                    {result.invoice_data?.currency || '–'}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={result.status} />
                  </td>
                </tr>
                {/* Részletes panel – accordion stílusban */}
                {openFileId === result.file_id && (
                  <tr>
                    <td colSpan={5} className="bg-gray-50 border-t border-blue-100">
                      <InvoiceDetail result={result} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="text-center text-gray-400 py-6">Nincs megjeleníthető eredmény.</p>
        )}
      </div>
    </div>
  );
}

export default ResultTable;
