// Számla betekintő – PDF, JPEG és PNG egy felugró ablakban
import React, { useEffect, useRef } from 'react';

function previewKind(fileName, mimeType) {
  const type = (mimeType || '').toLowerCase();
  const name = fileName || '';
  if (type === 'application/pdf' || /\.pdf$/i.test(name)) return 'pdf';
  if (type === 'image/jpeg' || type === 'image/jpg' || /\.jpe?g$/i.test(name)) return 'image';
  if (type === 'image/png' || /\.png$/i.test(name)) return 'image';
  return null;
}

/**
 * A böngészőben tartott fájl megjelenítése.
 * A PDF-et a böngésző saját nézője, a képet egy img elem mutatja.
 */
function DocumentPreview({ fileName, url, mimeType, onClose }) {
  const closeRef = useRef(null);
  const kind = previewKind(fileName, mimeType);

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={fileName}
        className="flex h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-gray-200 px-4 py-3">
          <h2 className="truncate text-sm font-semibold text-gray-900">{fileName}</h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900"
          >
            Bezárás
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col bg-gray-100">
          {kind === 'pdf' && (
            <iframe title={fileName} src={url} className="min-h-0 w-full flex-1 border-0" />
          )}
          {kind === 'image' && (
            <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-4">
              <img src={url} alt={fileName} className="max-h-full max-w-full object-contain" />
            </div>
          )}
          {kind == null && (
            <p className="px-6 py-10 text-center text-sm text-gray-500">
              Megtekintéshez PDF, JPEG vagy PNG fájl kell.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default DocumentPreview;
