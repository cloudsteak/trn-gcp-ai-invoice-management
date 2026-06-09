// Feltöltött fájlok listája státusz ikonokkal
import React from 'react';

/**
 * A feltöltött fájlok táblázatos megjelenítése.
 *
 * Props:
 *   files    – feltöltött fájlok tömbje { file_id, file_name, status, size? }
 *   onRemove(fileId) – fájl törlésének callback-je
 *   disabled – letiltja a törlést feldolgozás alatt
 */
function FileList({ files = [], onRemove, disabled = false }) {
  if (!files.length) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100 text-gray-600 text-left">
            <th className="px-3 py-2 font-medium">Fájlnév</th>
            <th className="px-3 py-2 font-medium">Státusz</th>
            <th className="px-3 py-2 font-medium w-12"></th>
          </tr>
        </thead>
        <tbody>
          {files.map((file) => (
            <tr key={file.file_id} className="border-t border-gray-100 hover:bg-gray-50">
              <td className="px-3 py-2 text-gray-800">{file.file_name}</td>
              <td className="px-3 py-2">
                {/* Státusz ikon megjelenítése */}
                <StatusIcon status={file.status} />
              </td>
              <td className="px-3 py-2">
                {!disabled && (
                  <button
                    onClick={() => onRemove(file.file_id)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                    title="Fájl eltávolítása"
                  >
                    ✕
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Belső segédkomponens – státusz szöveg és ikon
function StatusIcon({ status }) {
  const map = {
    uploaded: { icon: '📁', label: 'Feltöltve', color: 'text-gray-500' },
    processing: { icon: '⏳', label: 'Feldolgozás alatt', color: 'text-blue-500' },
    ok: { icon: '✅', label: 'Rendben', color: 'text-green-600' },
    warning: { icon: '⚠️', label: 'Figyelmeztetés', color: 'text-yellow-600' },
    error: { icon: '❌', label: 'Hiba', color: 'text-red-600' },
  };
  const entry = map[status] || { icon: '❓', label: status, color: 'text-gray-400' };
  return (
    <span className={`flex items-center gap-1 ${entry.color}`}>
      {entry.icon} {entry.label}
    </span>
  );
}

export default FileList;
