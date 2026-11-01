// Fájlfeltöltés állapotkezelő hook
import { useEffect, useRef, useState } from 'react';

function releasePreview(url, urls) {
  if (!url) return;
  URL.revokeObjectURL(url);
  urls.delete(url);
}

/**
 * Feltöltött fájlok listájának kezelése.
 * A fájlok azonosítója a backend által visszaadott file_id.
 * A localFile mezőből készült előnézeti cím a betekintőhöz kell,
 * és a szerver törlése után is a böngészőben marad.
 */
export function useUpload() {
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const filesRef = useRef(uploadedFiles);
  const urlsRef = useRef(new Set());
  filesRef.current = uploadedFiles;

  useEffect(() => () => {
    urlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    urlsRef.current.clear();
  }, []);

  // Új fájlok hozzáadása a listához (feltöltés után hívandó)
  const addFiles = (newFiles) => {
    const withPreview = newFiles.map((file) => {
      const localFile = file.localFile;
      const rest = { ...file };
      delete rest.localFile;
      if (!localFile) return rest;
      const previewUrl = URL.createObjectURL(localFile);
      urlsRef.current.add(previewUrl);
      return {
        ...rest,
        previewUrl,
        previewType: localFile.type || '',
      };
    });
    setUploadedFiles((prev) => [...prev, ...withPreview]);
  };

  // Egyedi fájl eltávolítása az azonosítója alapján
  const removeFile = (fileId) => {
    const target = filesRef.current.find((file) => file.file_id === fileId);
    releasePreview(target?.previewUrl, urlsRef.current);
    setUploadedFiles((prev) => prev.filter((file) => file.file_id !== fileId));
  };

  // Összes fájl törlése
  const clearFiles = () => {
    filesRef.current.forEach((file) => releasePreview(file.previewUrl, urlsRef.current));
    setUploadedFiles([]);
  };

  return { uploadedFiles, addFiles, removeFile, clearFiles };
}
