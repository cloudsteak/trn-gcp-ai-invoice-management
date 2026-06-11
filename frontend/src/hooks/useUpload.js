// Fájlfeltöltés állapotkezelő hook
import { useState } from 'react';

/**
 * Feltöltött fájlok listájának kezelése.
 * A fájlok azonosítója a backend által visszaadott file_id.
 */
export function useUpload() {
  const [uploadedFiles, setUploadedFiles] = useState([]);

  // Új fájlok hozzáadása a listához (feltöltés után hívandó)
  const addFiles = (newFiles) => {
    setUploadedFiles((prev) => [...prev, ...newFiles]);
  };

  // Egyedi fájl eltávolítása az azonosítója alapján
  const removeFile = (fileId) => {
    setUploadedFiles((prev) => prev.filter((f) => f.file_id !== fileId));
  };

  // Összes fájl törlése
  const clearFiles = () => {
    setUploadedFiles([]);
  };

  return { uploadedFiles, addFiles, removeFile, clearFiles };
}
