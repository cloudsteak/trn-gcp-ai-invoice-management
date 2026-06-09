// Feldolgozás állapotkezelő hook – polling mechanizmussal
import { useState, useRef, useCallback } from 'react';
import { startProcessing as apiStartProcessing, getProcessingStatus } from '../services/api.js';

// Polling intervallum milliszekundumban
const POLL_INTERVAL_MS = 2000;

/**
 * A feldolgozás teljes állapotát kezeli:
 * - Feldolgozás indítása
 * - Státusz lekérdezése 2 másodpercenként
 * - Eredmények tárolása
 */
export function useProcessing() {
  const [state, setState] = useState({
    files: [],           // Feltöltött fájlok listája
    jobId: null,         // Aktuális job azonosítója
    status: 'idle',      // idle | uploading | processing | done | error
    results: [],         // InvoiceResult lista
    progress: '0/0',     // Feldolgozás előrehaladása
  });

  // Polling timer referencia a leállításhoz
  const pollTimer = useRef(null);

  // Polling leállítása
  const stopPolling = () => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  };

  // Feldolgozási státusz lekérdezése
  const pollStatus = useCallback(async (jobId) => {
    try {
      const data = await getProcessingStatus(jobId);

      setState((prev) => ({
        ...prev,
        status: data.status,
        results: data.results || [],
        progress: data.progress || '0/0',
      }));

      // Ha kész vagy hiba, leállítjuk a pollingot
      if (data.status === 'done' || data.status === 'error') {
        stopPolling();
      }
    } catch (err) {
      console.error('Státusz lekérdezési hiba:', err);
      setState((prev) => ({ ...prev, status: 'error' }));
      stopPolling();
    }
  }, []);

  // Feldolgozás indítása
  const startProcessing = useCallback(async (fileIds) => {
    if (!fileIds.length) return;

    setState((prev) => ({ ...prev, status: 'processing', results: [], progress: '0/0' }));
    stopPolling();

    try {
      const { job_id } = await apiStartProcessing(fileIds);

      setState((prev) => ({ ...prev, jobId: job_id }));

      // 2 másodpercenkénti polling indítása
      pollTimer.current = setInterval(() => pollStatus(job_id), POLL_INTERVAL_MS);
    } catch (err) {
      console.error('Feldolgozás indítási hiba:', err);
      setState((prev) => ({ ...prev, status: 'error' }));
    }
  }, [pollStatus]);

  return {
    ...state,
    startProcessing,
  };
}
