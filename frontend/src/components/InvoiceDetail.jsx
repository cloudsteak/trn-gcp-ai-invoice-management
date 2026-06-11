// Részletes számla riport panel – kinyert adatok és Gemini értékelés
import React from 'react';
import StatusBadge from './StatusBadge.jsx';
import { formatAmount, formatDate, formatTaxId } from '../utils/formatters.js';

/**
 * Props:
 *   result – egyetlen InvoiceResult objektum
 */
function InvoiceDetail({ result }) {
  const inv = result.invoice_data;

  return (
    <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Bal panel: Kinyert számlaadat */}
      <div>
        <h3 className="font-semibold text-gray-700 mb-3 text-sm uppercase tracking-wide">
          Kinyert adatok
        </h3>

        <dl className="space-y-1.5 text-sm">
          <DataRow label="Eladó neve" value={inv?.supplier_name} />
          <DataRow label="Eladó adószáma" value={formatTaxId(inv?.supplier_tax_id)} />
          <DataRow label="Eladó címe" value={inv?.supplier_address} />
          <DataRow label="Vevő neve" value={inv?.buyer_name} />
          <DataRow label="Vevő adószáma" value={formatTaxId(inv?.buyer_tax_id)} />
          <DataRow label="Számlaszám" value={inv?.invoice_number} />
          <DataRow label="Számla kelte" value={formatDate(inv?.invoice_date)} />
          <DataRow label="Fizetési határidő" value={formatDate(inv?.due_date)} />
          <DataRow label="Teljesítés dátuma" value={formatDate(inv?.completion_date)} />
          <DataRow label="Nettó összeg" value={formatAmount(inv?.net_amount)} />
          <DataRow label="ÁFA összeg" value={formatAmount(inv?.vat_amount)} />
          <DataRow label="Bruttó összeg" value={formatAmount(inv?.gross_amount)} bold />
          <DataRow label="Pénznem" value={inv?.currency} />
        </dl>

        {/* Tételsorok táblázata */}
        {inv?.line_items?.length > 0 && (
          <div className="mt-4">
            <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Tételsorok</h4>
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-gray-100 text-left">
                  <th className="px-2 py-1">Leírás</th>
                  <th className="px-2 py-1 text-right">Mennyiség</th>
                  <th className="px-2 py-1 text-right">Egységár</th>
                  <th className="px-2 py-1 text-right">Összeg</th>
                </tr>
              </thead>
              <tbody>
                {inv.line_items.map((item, idx) => (
                  <tr key={idx} className="border-t border-gray-100">
                    <td className="px-2 py-1">{item.description || '–'}</td>
                    <td className="px-2 py-1 text-right">{item.quantity ?? '–'}</td>
                    <td className="px-2 py-1 text-right">{formatAmount(item.unit_price)}</td>
                    <td className="px-2 py-1 text-right">{formatAmount(item.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Jobb panel: Gemini validáció és könyvelői értékelés */}
      <div>
        <h3 className="font-semibold text-gray-700 mb-3 text-sm uppercase tracking-wide">
          Könyvelői értékelés
        </h3>

        {/* Validációs hibák listája */}
        {result.issues?.length > 0 && (
          <div className="space-y-2 mb-4">
            {result.issues.map((issue, idx) => (
              <div
                key={idx}
                className={`rounded-lg p-3 text-sm border ${
                  issue.severity === 'error'
                    ? 'bg-red-50 border-red-200 text-red-800'
                    : issue.severity === 'warning'
                    ? 'bg-yellow-50 border-yellow-200 text-yellow-800'
                    : 'bg-green-50 border-green-200 text-green-800'
                }`}
              >
                <div className="flex items-start gap-2">
                  <StatusBadge status={issue.severity} iconOnly />
                  <div>
                    <p className="font-medium">{issue.message}</p>
                    {issue.suggestion && (
                      <p className="text-xs mt-0.5 opacity-80">{issue.suggestion}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Gemini könyvelői szöveg */}
        {result.gemini_summary && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <h4 className="text-xs font-semibold text-blue-700 uppercase mb-1">
              Gemini összefoglaló
            </h4>
            <p className="text-sm text-blue-900 leading-relaxed">
              {result.gemini_summary}
            </p>
          </div>
        )}

        {/* Feldolgozási idő */}
        {result.processing_time_ms && (
          <p className="text-xs text-gray-400 mt-3">
            Feldolgozási idő: {result.processing_time_ms} ms
          </p>
        )}
      </div>
    </div>
  );
}

// Belső segédkomponens – adat sor a részletes panelben
function DataRow({ label, value, bold = false }) {
  return (
    <div className="flex gap-2">
      <dt className="text-gray-500 w-40 shrink-0">{label}:</dt>
      <dd className={`text-gray-800 ${bold ? 'font-semibold' : ''}`}>
        {value || <span className="text-gray-300">–</span>}
      </dd>
    </div>
  );
}

export default InvoiceDetail;
