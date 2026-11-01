// Backend API hívások – axios alapú HTTP kliens
import axios from 'axios';
// CSAK AZ API-NÉZET MIATT – a lenti interceptor ezt a naplót tölti
import { logCall } from './callLog.js';

// Backend alap URL – fejlesztésben proxy, production-ban a Cloud Run URL
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 60000, // 60 másodperc timeout (nagy fájlok esetén)
});

// --- CSAK AZ API-NÉZET MIATT ---
// A withoutApiCalls végéig minden csak az oktatási panelt táplálja.
// A kérést nem írja át, a szerver válaszát a hívó ugyanúgy kapja meg.
function requestPath(config) {
  const url = config?.url || '';
  if (url.startsWith('http')) {
    try {
      const parsed = new URL(url);
      return parsed.pathname + parsed.search;
    } catch {
      return url;
    }
  }
  return url;
}

function clipValue(value, depth = 0) {
  if (typeof value === 'string') {
    if (value.length <= 4000) return value;
    return `${value.slice(0, 4000)}\n… (${value.length} karakterből az első 4000 látható)`;
  }
  if (typeof Blob !== 'undefined' && value instanceof Blob) {
    return {
      blob: true,
      size: value.size,
      type: value.type || 'application/octet-stream',
    };
  }
  if (depth > 6) return '…';
  if (Array.isArray(value)) {
    const sliced = value.slice(0, 20).map((item) => clipValue(item, depth + 1));
    if (value.length > 20) sliced.push(`… +${value.length - 20} elem`);
    return sliced;
  }
  if (value && typeof value === 'object') {
    const copy = {};
    Object.entries(value).forEach(([key, item]) => {
      copy[key] = clipValue(item, depth + 1);
    });
    return copy;
  }
  return value ?? null;
}

function describeRequestBody(data) {
  if (data == null || data === '') return null;
  if (typeof FormData !== 'undefined' && data instanceof FormData) {
    const parts = [];
    data.forEach((value, field) => {
      if (typeof File !== 'undefined' && value instanceof File) {
        parts.push({
          field,
          file_name: value.name,
          mime_type: value.type,
          size_bytes: value.size,
        });
      } else {
        parts.push({ field, value: clipValue(String(value)) });
      }
    });
    return { multipart: parts };
  }
  return clipValue(data);
}

function stripAiTraces(data) {
  if (!data || typeof data !== 'object' || (typeof Blob !== 'undefined' && data instanceof Blob)) {
    return data;
  }
  if (Array.isArray(data)) return data.map(stripAiTraces);
  const copy = { ...data };
  if (Array.isArray(copy.results)) {
    copy.results = copy.results.map((result) => {
      if (!result || typeof result !== 'object' || !('api_calls' in result)) return result;
      const count = Array.isArray(result.api_calls) ? result.api_calls.length : 0;
      const rest = { ...result };
      delete rest.api_calls;
      return {
        ...rest,
        api_calls: `(${count} hívás a DOCAI és az AI model listában)`,
      };
    });
  }
  return copy;
}

function errorMessage(error) {
  if (!error) return null;
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail != null) {
    try {
      return JSON.stringify(detail);
    } catch {
      return error.message || 'Hálózati hiba';
    }
  }
  return error.message || 'Hálózati hiba';
}

function pollStatusOf(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  return typeof body.status === 'string' ? body.status : null;
}

function logFromAxios(config, response, error) {
  if (!config) return;
  const started = config.metadata?.startedAt ?? performance.now();
  const durationMs = Math.max(0, Math.round(performance.now() - started));
  const method = (config.method || 'get').toUpperCase();
  const path = requestPath(config);
  const httpStatus = response?.status ?? 0;
  const rawBody = response ? response.data : undefined;
  const responseBody = rawBody === undefined
    ? (error ? { error: errorMessage(error) } : null)
    : clipValue(stripAiTraces(rawBody));
  const pollStatus = pollStatusOf(rawBody);
  const operation = `${method} ${path}`;
  const beOk = httpStatus >= 200 && httpStatus < 400;

  logCall({
    id: crypto.randomUUID(),
    at: config.metadata?.startedIso || new Date().toISOString(),
    layer: 'fe',
    service: 'Frontend',
    operation,
    method,
    path,
    status: 'ok',
    httpStatus: null,
    durationMs: null,
    requestBody: describeRequestBody(config.data),
    responseBody: null,
    error: null,
    fileName: null,
    pollStatus,
  });

  logCall({
    id: crypto.randomUUID(),
    at: new Date().toISOString(),
    layer: 'be',
    service: 'Backend',
    operation,
    method,
    path,
    status: beOk ? 'ok' : 'error',
    httpStatus: httpStatus || null,
    durationMs,
    requestBody: null,
    responseBody,
    error: errorMessage(error),
    fileName: null,
    pollStatus,
  });
}

client.interceptors.request.use((config) => {
  config.metadata = {
    startedAt: performance.now(),
    startedIso: new Date().toISOString(),
  };
  return config;
});

client.interceptors.response.use(
  (response) => {
    logFromAxios(response.config, response, null);
    return response;
  },
  (error) => {
    logFromAxios(error.config, error.response, error);
    return Promise.reject(error);
  }
);

// CSAK AZ API-NÉZET MIATT – az export body-ból kiveszi a hívásnaplót, hogy ne menjen vissza a szerverre
function withoutApiCalls(results) {
  return results.map((result) => {
    if (!result || typeof result !== 'object') return result;
    const rest = { ...result };
    delete rest.api_calls;
    return rest;
  });
}
// --- API-NÉZET VÉGE ---

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
 * Feltöltött fájlok törlése a szerverről (feldolgozás előtt).
 *
 * @param {string[]} fileIds – UUID azonosítók tömbje
 */
export async function deleteUploadedFiles(fileIds) {
  const response = await client.post('/api/upload/delete', { file_ids: fileIds });
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
 * Export letöltése – job_id vagy közvetlenül a frontend eredménylistából.
 *
 * @param {'pdf'|'xlsx'|'csv'|'xlsx-accounting'} format
 * @param {{ jobId?: string, results?: object[] }} options
 */
export async function downloadExport(format, { jobId, results } = {}) {
  // withoutApiCalls: CSAK AZ API-NÉZET MIATT, az export tartalma ettől nem változik
  const body = results?.length ? { results: withoutApiCalls(results) } : { job_id: jobId };

  const response = await client.post(
    `/api/export/${format}`,
    body,
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
