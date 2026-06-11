// Feldolgozás állapotkezelő hook – fájlonként sorban, eredmény azonnal megjelenik
import { useState, useRef, useCallback } from 'react';
import { startProcessing as apiStartProcessing, getProcessingStatus } from '../services/api.js';

const POLL_INTERVAL_MS = 1500;
// Szünet két fájl között – Document AI kvóta pihenő
const BETWEEN_FILES_MS = 3000;
// 3 fájl után hosszabb szünet (GCP processzor rate limit)
const QUOTA_PAUSE_EVERY = 3;
const QUOTA_PAUSE_MS = 12000;
// DocAI átmeneti hiba – egy újrapróba a következő fájl előtt
const DOCai_RETRY_WAIT_MS = 15000;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function isDocaiTransientFailure(result) {
  if (!result || result.status === 'ok' || result.status === 'warning') return false;
  return (result.issues || []).some((issue) =>
    (issue.message || '').includes('Document AI átmeneti')
  );
}

async function waitForJob(jobId) {
  while (true) {
    const data = await getProcessingStatus(jobId);
    if (data.status === 'done' || data.status === 'error') {
      return data;
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

async function processOneFile(fileId) {
  const { job_id } = await apiStartProcessing([fileId]);
  const jobData = await waitForJob(job_id);
  if (jobData.status === 'error') {
    throw new Error('Feldolgozási hiba a szerveren');
  }
  return jobData.results?.[0] ?? null;
}

export function useProcessing() {
  const [state, setState] = useState({
    jobId: null,
    status: 'idle',
    results: [],
    progress: '0/0',
    currentIndex: 0,
  });

  const runningRef = useRef(false);

  const startProcessing = useCallback(async (fileIds) => {
    if (!fileIds.length || runningRef.current) return;

    runningRef.current = true;
    const total = fileIds.length;
    const accumulated = [];

    setState({
      jobId: null,
      status: 'processing',
      results: [],
      progress: `0/${total}`,
      currentIndex: 0,
    });

    try {
      for (let i = 0; i < total; i++) {
        const fileId = fileIds[i];

        setState((prev) => ({
          ...prev,
          currentIndex: i + 1,
          progress: `${i}/${total}`,
        }));

        let result = await processOneFile(fileId);

        // DocAI átmeneti hiba – egyszer újrapróbáljuk hosszabb várakozás után
        if (isDocaiTransientFailure(result)) {
          setState((prev) => ({
            ...prev,
            progress: `${i}/${total} (újrapróba...)`,
          }));
          await sleep(DOCai_RETRY_WAIT_MS);
          result = await processOneFile(fileId);
        }

        if (result) {
          accumulated.push(result);
        }

        setState((prev) => ({
          ...prev,
          results: [...accumulated],
          progress: `${i + 1}/${total}`,
        }));

        if (i + 1 >= total) break;

        // Szünet a következő fájl előtt
        let pauseMs = BETWEEN_FILES_MS;
        if ((i + 1) % QUOTA_PAUSE_EVERY === 0) {
          pauseMs = QUOTA_PAUSE_MS;
        }
        await sleep(pauseMs);
      }

      setState((prev) => ({
        ...prev,
        status: 'done',
        progress: `${total}/${total}`,
      }));
    } catch (err) {
      console.error('Feldolgozási hiba:', err);
      setState((prev) => ({
        ...prev,
        status: accumulated.length ? 'done' : 'error',
        results: accumulated,
      }));
    } finally {
      runningRef.current = false;
    }
  }, []);

  return {
    ...state,
    startProcessing,
  };
}
