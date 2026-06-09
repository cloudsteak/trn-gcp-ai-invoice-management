// Drag-and-drop feltöltési terület – react-dropzone alapú
import React from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadFiles } from '../services/api.js';

// Engedélyezett fájltípusok MIME type alapján
const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
};

const MAX_FILE_SIZE_MB = Number(import.meta.env.VITE_MAX_FILE_SIZE_MB) || 20;

/**
 * Fájlfeltöltési zóna komponens.
 * Támogatja a drag-and-drop és kattintásos fájlkiválasztást.
 *
 * Props:
 *   onFilesAdded(uploadedFiles) – sikeres feltöltés után hívódik meg
 *   disabled – letiltja a zónát feldolgozás alatt
 */
function UploadZone({ onFilesAdded, disabled = false }) {
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState(null);

  const onDrop = React.useCallback(
    async (acceptedFiles) => {
      if (!acceptedFiles.length) return;
      setError(null);
      setUploading(true);
      try {
        // Fájlok feltöltése a backendre
        const result = await uploadFiles(acceptedFiles);
        onFilesAdded(result.files);
      } catch (err) {
        setError('Feltöltési hiba: ' + (err.message || 'Ismeretlen hiba'));
      } finally {
        setUploading(false);
      }
    },
    [onFilesAdded]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_FILE_SIZE_MB * 1024 * 1024,
    disabled: disabled || uploading,
  });

  return (
    <div>
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:border-blue-400'}
          ${(disabled || uploading) ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <input {...getInputProps()} />
        <div className="text-4xl mb-3">📂</div>
        {isDragActive ? (
          <p className="text-blue-600 font-medium">Ejtsd ide a fájlokat...</p>
        ) : (
          <>
            <p className="text-gray-700 font-medium">
              Húzd ide a számlákat, vagy kattints a kiválasztáshoz
            </p>
            <p className="text-gray-400 text-sm mt-1">
              PDF, JPG, JPEG, PNG – maximum {MAX_FILE_SIZE_MB} MB fájlonként
            </p>
          </>
        )}
        {uploading && (
          <p className="text-blue-500 mt-2 text-sm">Feltöltés folyamatban...</p>
        )}
      </div>
      {error && (
        <p className="text-red-600 text-sm mt-2">{error}</p>
      )}
    </div>
  );
}

export default UploadZone;
