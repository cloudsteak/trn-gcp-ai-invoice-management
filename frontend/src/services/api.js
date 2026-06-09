// Backend API hívások – axios alapú HTTP kliens
import axios from 'axios';

// Backend alap URL – fejlesztésben proxy, production-ban a Cloud Run URL
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 60000, // 60 másodperc timeout (nagy fájlok esetén)
});

/**
 * Fájlok feltöltése a backendre (multipart/form-data).
 *
 * @param {File[]} files – böngészős File objektumok tömbje
 * @returns {{ files: UploadedFile[] }}
 */
export async function uploadFiles(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  const response = await client.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

/**
 * Batch feldolgozás indítása a feltöltött fájlok azonosítóival.
 *
 * @param {string[]} fileIds – UUID azonosítók tömbje
 * @returns {{ job_id: string, status: string }}
 */
export async function startProcessing(fileIds) {
  const response = await client.post('/api/process', { file_ids: fileIds });
  return response.data;
}

/**
 * Feldolgozási job aktuális státuszának lekérdezése.
 *
 * @param {string} jobId – a job egyedi azonosítója
 * @returns {{ status: string, results: InvoiceResult[], progress: string }}
 */
export async function getProcessingStatus(jobId) {
  const response = await client.get(`/api/process/${jobId}`);
  return response.data;
}

/**
 * Export letöltése és automatikus mentés a böngészőben.
 *
 * @param {string} jobId – a job azonosítója
 * @param {'pdf'|'xlsx'|'csv'|'xlsx-accounting'} format – export formátum
 */
export async function downloadExport(jobId, format) {
  const response = await client.post(
    `/api/export/${format}`,
    { job_id: jobId },
    { responseType: 'blob' }
  );

  // Fájlnév kinyerése a Content-Disposition fejlécből, vagy alapértelmezett
  const disposition = response.headers['content-disposition'] || '';
  const fileNameMatch = disposition.match(/filename=([^;]+)/);
  const fileName = fileNameMatch
    ? fileNameMatch[1].trim()
    : `szamlak_export.${format.replace('xlsx-accounting', 'xlsx')}`;

  // Letöltés elindítása virtuális link segítségével
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', fileName);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
