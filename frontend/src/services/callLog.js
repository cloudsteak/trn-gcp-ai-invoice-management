// CSAK AZ API-NÉZET MIATT – ez az egész fájl.
// Memóriában tartja a Frontend → Backend és Backend → AI hívásokat, amiket a panel kiír.
// A számlafeldolgozás eredményét nem módosítja.
const listeners = new Set();

let calls = [];
let seq = 0;

function emit() {
  listeners.forEach((listener) => listener());
}

function isRepeatPoll(previous, next) {
  return Boolean(
    previous
    && next
    && previous.direction === 'fe-be'
    && next.direction === 'fe-be'
    && previous.method === 'GET'
    && next.method === 'GET'
    && previous.path === next.path
    && previous.responseBody?.status === 'processing'
    && next.responseBody?.status === 'processing'
  );
}

export function getCalls() {
  return [...calls].sort((a, b) => {
    if (a.at === b.at) return a.seq - b.seq;
    return a.at < b.at ? -1 : 1;
  });
}

export function subscribeCallLog(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function clearCallLog() {
  calls = [];
  emit();
}

export function logCall(entry) {
  const previous = calls[calls.length - 1];
  if (previous && isRepeatPoll(previous, entry)) {
    calls = [
      ...calls.slice(0, -1),
      {
        ...previous,
        pollCount: (previous.pollCount || 1) + 1,
        durationMs: entry.durationMs,
        responseBody: entry.responseBody,
        httpStatus: entry.httpStatus,
        status: entry.status,
        error: entry.error,
      },
    ];
  } else {
    calls = [...calls, { pollCount: 1, ...entry, seq: ++seq }];
  }
  emit();
}

/**
 * A feldolgozás eredményében érkező Backend → AI hívások beillesztése.
 * Az időbélyeg a szerveré, így a pollok közé rendeződnek.
 */
export function logBackendAiCalls(fileName, apiCalls) {
  if (!apiCalls?.length) return;
  apiCalls.forEach((call) => {
    logCall({
      id: crypto.randomUUID(),
      at: call.occurred_at || new Date().toISOString(),
      direction: 'be-ai',
      service: call.service,
      operation: call.operation,
      method: call.request?.method || 'POST',
      path: call.request?.endpoint || call.operation,
      status: call.status === 'ok' ? 'ok' : 'error',
      httpStatus: null,
      durationMs: call.duration_ms ?? null,
      requestBody: call.request || null,
      responseBody: call.response || null,
      error: call.error || null,
      fileName: fileName || call.request?.file_name || null,
    });
  });
}
