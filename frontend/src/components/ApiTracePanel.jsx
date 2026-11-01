// CSAK AZ API-NÉZET MIATT – ez az egész fájl.
// Az oktatási panel: kapcsoló, szűrők, és a lenyitható kérés/válasz JSON.
// A számlafeldolgozás (feltöltés, eredmény, export) ezt a fájlt nem használja.
import React, { useEffect, useRef, useState } from 'react';
import { clearCallLog } from '../services/callLog.js';

const FILTERS = [
  { id: 'all', label: 'Mind' },
  { id: 'fe-be', label: 'FE ↔ BE' },
  { id: 'be-ai', label: 'BE ↔ AI' },
];

function formatTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('hu-HU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDuration(ms) {
  if (ms == null) return '';
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatJson(value) {
  if (value == null) return 'null';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function directionLabel(direction) {
  return direction === 'be-ai' ? 'BE → AI' : 'FE → BE';
}

function cardTitle(call) {
  if (call.direction === 'be-ai') {
    return `${call.service} · ${call.operation}`;
  }
  const repeats = call.pollCount > 1 ? ` × ${call.pollCount}` : '';
  return `${call.method} ${call.path}${repeats}`;
}

function accentClass(call) {
  if (call.status !== 'ok') return 'border-red-400';
  if (call.service === 'Document AI') return 'border-amber-400';
  if (call.service === 'Gemini') return 'border-violet-400';
  return 'border-sky-400';
}

function badgeClass(call) {
  if (call.direction === 'be-ai') return 'bg-violet-100 text-violet-800';
  return 'bg-sky-100 text-sky-800';
}

export function ApiTraceToggle({ pressed, count, onToggle }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
        pressed ? 'bg-white text-blue-800' : 'bg-blue-800/50 text-blue-50 hover:bg-blue-800'
      }`}
    >
      <span
        className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors ${
          pressed ? 'bg-blue-600' : 'bg-blue-950/50'
        }`}
        aria-hidden="true"
      >
        <span
          className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
            pressed ? 'translate-x-4' : 'translate-x-0'
          }`}
        />
      </span>
      API hívások
      {count > 0 && (
        <span className={`rounded-full px-1.5 text-xs tabular-nums ${
          pressed ? 'bg-blue-100 text-blue-800' : 'bg-blue-950/40 text-white'
        }`}
        >
          {count}
        </span>
      )}
    </button>
  );
}

function callJson(call) {
  return {
    direction: directionLabel(call.direction),
    service: call.service,
    operation: call.operation,
    status: call.httpStatus || call.status,
    duration_ms: call.durationMs,
    request: call.requestBody,
    response: call.responseBody,
    error: call.error,
  };
}

function JsonBlock({ title, value }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
        {title}
      </p>
      <pre className="text-xs leading-relaxed overflow-auto max-h-72 bg-gray-900 text-gray-100 rounded-lg p-3 whitespace-pre-wrap break-words">
        {formatJson(value)}
      </pre>
    </div>
  );
}

function ApiTracePanel({ calls }) {
  const [filter, setFilter] = useState('all');
  const [openId, setOpenId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const listRef = useRef(null);
  const stickRef = useRef(true);
  const copyTimer = useRef(null);

  const visible = filter === 'all' ? calls : calls.filter((call) => call.direction === filter);
  const visibleCount = visible.length;
  const lastCallId = visible[visibleCount - 1]?.id ?? '';

  useEffect(() => () => window.clearTimeout(copyTimer.current), []);

  useEffect(() => {
    const el = listRef.current;
    if (!el || !stickRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [visibleCount, lastCallId]);

  const handleScroll = () => {
    const el = listRef.current;
    if (!el) return;
    stickRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
  };

  const toggleCall = (callId) => {
    stickRef.current = false;
    setOpenId((current) => (current === callId ? null : callId));
  };

  useEffect(() => {
    if (!openId || !listRef.current) return;
    const card = listRef.current.querySelector(`[data-call-id="${openId}"]`);
    if (!card) return;
    const list = listRef.current;
    const listRect = list.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    if (cardRect.top < listRect.top) {
      list.scrollTop -= listRect.top - cardRect.top;
    } else if (cardRect.bottom > listRect.bottom) {
      list.scrollTop += cardRect.bottom - listRect.bottom;
    }
  }, [openId]);

  const copyCall = async (call) => {
    const text = formatJson(callJson(call));
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(call.id);
      window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(
        () => setCopiedId((current) => (current === call.id ? null : current)),
        1500
      );
    } catch {
      setCopiedId(null);
    }
  };

  return (
    <aside
      className="order-1 lg:order-2 flex flex-col min-h-0 overflow-hidden bg-white border-b lg:border-b-0 lg:border-l border-gray-200 lg:sticky lg:top-16 lg:self-start lg:h-[calc(100vh-4rem)] max-lg:max-h-[50vh]"
      aria-label="API hívások"
    >
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">API hívások</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Frontend ↔ Backend és Backend ↔ AI
            </p>
          </div>
          <button
            type="button"
            onClick={clearCallLog}
            disabled={calls.length === 0}
            className="text-xs font-medium text-gray-500 hover:text-gray-800 disabled:opacity-40 disabled:hover:text-gray-500"
          >
            Törlés
          </button>
        </div>
        <div className="flex gap-1 mt-3" role="tablist" aria-label="Hívások szűrése">
          {FILTERS.map((item) => {
            const count = item.id === 'all'
              ? calls.length
              : calls.filter((call) => call.direction === item.id).length;
            const active = filter === item.id;
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setFilter(item.id)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  active ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {item.label}
                <span className="ml-1 tabular-nums opacity-70">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div ref={listRef} onScroll={handleScroll} className="flex-1 min-h-0 overflow-y-auto px-3 py-3 space-y-2">
        {visible.length === 0 ? (
          <p className="text-sm text-gray-500 leading-relaxed px-1 py-6 text-center">
            Még nincs rögzített hívás. Tölts fel egy számlát, vagy indítsd a feldolgozást.
            A feltöltés, a státuszlekérdezés, a Document AI és a Gemini hívások itt jelennek meg.
          </p>
        ) : (
          visible.map((call) => {
            const open = openId === call.id;
            const attempt = call.requestBody?.attempt;
            return (
              <article
                key={call.id}
                data-call-id={call.id}
                className={`rounded-lg border border-gray-200 border-l-4 bg-gray-50 ${accentClass(call)}`}
              >
                <div className="px-3 py-2">
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="text-gray-400 tabular-nums">{formatTime(call.at)}</span>
                    <span className={`rounded px-1.5 py-0.5 font-semibold ${badgeClass(call)}`}>
                      {directionLabel(call.direction)}
                    </span>
                    <span className={`ml-auto font-medium ${call.status === 'ok' ? 'text-emerald-700' : 'text-red-600'}`}>
                      {call.httpStatus || (call.status === 'ok' ? 'OK' : 'HIBA')}
                    </span>
                  </div>
                  <p className="mt-1 text-sm font-medium text-gray-900 break-all">
                    {cardTitle(call)}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    {formatDuration(call.durationMs)}
                    {call.fileName ? ` · ${call.fileName}` : ''}
                    {attempt > 1 ? ` · kísérlet ${attempt}` : ''}
                    {call.pollCount > 1 ? ' · folyamatban, ismétlődő lekérdezés' : ''}
                  </p>
                </div>
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => toggleCall(call.id)}
                  className="w-full flex items-center justify-between gap-2 px-3 py-1.5 border-t border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-100"
                >
                  <span>{open ? 'JSON bezárása' : 'JSON lenyitása'}</span>
                  <span
                    aria-hidden="true"
                    className={`inline-block h-1.5 w-1.5 border-r-2 border-b-2 border-current transition-transform ${
                      open ? '-translate-y-px rotate-[225deg]' : 'translate-y-px rotate-45'
                    }`}
                  />
                </button>
                {open && (
                  <div className="px-3 pb-3 space-y-3 border-t border-gray-200 pt-3">
                    <JsonBlock title="Kérés" value={call.requestBody} />
                    <JsonBlock title="Válasz" value={call.responseBody} />
                    <button
                      type="button"
                      onClick={() => copyCall(call)}
                      className="text-xs font-medium text-blue-700 hover:text-blue-900"
                    >
                      {copiedId === call.id ? 'Másolva' : 'JSON másolása'}
                    </button>
                  </div>
                )}
              </article>
            );
          })
        )}
      </div>
    </aside>
  );
}

export default ApiTracePanel;
