// Főalkalmazás komponens – az oldalfelépítés és állapotkezelés összefogója
import React, { useEffect, useState } from 'react'; // useEffect: CSAK AZ API-NÉZET MIATT
import UploadZone from './components/UploadZone.jsx';
import FileList from './components/FileList.jsx';
import ProcessButton from './components/ProcessButton.jsx';
import ResultTable from './components/ResultTable.jsx';
import ExportBar from './components/ExportBar.jsx';
import LoadingSpinner from './components/LoadingSpinner.jsx';
import DocumentPreview from './components/DocumentPreview.jsx';
import ApiTracePanel, { ApiTraceToggle } from './components/ApiTracePanel.jsx'; // CSAK AZ API-NÉZET MIATT
import { useProcessing } from './hooks/useProcessing.js';
import { useUpload } from './hooks/useUpload.js';
import { useCallLog } from './hooks/useCallLog.js'; // CSAK AZ API-NÉZET MIATT
import { deleteUploadedFiles } from './services/api.js';

// CSAK AZ API-NÉZET MIATT – megjegyzi, hogy a híváspanel nyitva volt-e
const TRACE_STORAGE_KEY = 'showApiCalls';

function App() {
  const { uploadedFiles, addFiles, removeFile, clearFiles } = useUpload();
  // CSAK AZ API-NÉZET MIATT – a panel nyitva/zárva állapota és a rögzített hívások
  const apiCalls = useCallLog();
  const [showApiCalls, setShowApiCalls] = useState(
    () => sessionStorage.getItem(TRACE_STORAGE_KEY) === '1'
  );
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState(null);
  const [previewFileId, setPreviewFileId] = useState(null);

  // CSAK AZ API-NÉZET MIATT
  useEffect(() => {
    sessionStorage.setItem(TRACE_STORAGE_KEY, showApiCalls ? '1' : '0');
  }, [showApiCalls]);

  const {
    status,
    results,
    progress,
    jobId,
    startProcessing,
  } = useProcessing();

  const isProcessing = status === 'processing';
  const hasResults = results.length > 0;
  const previewFile = uploadedFiles.find((file) => file.file_id === previewFileId) || null;
  const canPreview = (fileId) => uploadedFiles.some(
    (file) => file.file_id === fileId && file.previewUrl
  );

  const handleProcess = () => {
    startProcessing(uploadedFiles.map((f) => f.file_id));
  };

  const handleClearAll = async () => {
    if (!uploadedFiles.length || isProcessing) return;
    setClearError(null);
    setClearing(true);
    try {
      await deleteUploadedFiles(uploadedFiles.map((f) => f.file_id));
      clearFiles();
    } catch (err) {
      setClearError('Törlési hiba: ' + (err.message || 'Ismeretlen hiba'));
    } finally {
      setClearing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Fejléc */}
      {/* sticky fejléc: CSAK AZ API-NÉZET MIATT, hogy a híváspanel alatta maradjon */}
      <header className="bg-blue-700 text-white shadow-md sticky top-0 z-30">
        <div className={`mx-auto px-4 h-16 flex items-center gap-3 ${showApiCalls ? 'max-w-none' : 'max-w-6xl'}`}>
          <span className="text-2xl shrink-0" aria-hidden="true">📄</span>
          <h1 className="text-xl font-bold tracking-tight truncate">
            Intelligens Számlafeldolgozó
          </h1>
          <div className="ml-auto flex items-center gap-4 shrink-0">
            {/* CSAK AZ API-NÉZET MIATT – kikapcsolva a panel nem látszik */}
            <ApiTraceToggle
              pressed={showApiCalls}
              count={apiCalls.length}
              onToggle={() => setShowApiCalls((open) => !open)}
            />
            <span className="text-blue-200 text-sm hidden lg:inline">
              Google Cloud Document AI + Gemini
            </span>
          </div>
        </div>
      </header>

      {/* CSAK AZ API-NÉZET MIATT – nyitott panelnél a lista a tartalom mellé kerül */}
      <div className={showApiCalls ? 'flex flex-col lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(320px,440px)]' : ''}>
      {/* Fő tartalom. Az order-* osztály CSAK AZ API-NÉZET MIATT van itt, nyitott panelnél. */}
      <main className={`px-4 py-8 space-y-6 ${showApiCalls ? 'order-2 lg:order-1 w-full min-w-0' : 'mx-auto max-w-6xl'}`}>
        {/* Feltöltési szekció */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            Számlák feltöltése
          </h2>
          <UploadZone onFilesAdded={addFiles} disabled={isProcessing} />
          {uploadedFiles.length > 0 && (
            <div className="mt-4">
              <FileList
                files={uploadedFiles}
                onRemove={removeFile}
                onClearAll={handleClearAll}
                onPreview={setPreviewFileId}
                disabled={isProcessing}
                clearing={clearing}
              />
              {clearError && (
                <p className="text-red-600 text-sm mt-2">{clearError}</p>
              )}
            </div>
          )}
          <div className="mt-4 flex justify-end">
            <ProcessButton
              onClick={handleProcess}
              disabled={uploadedFiles.length === 0 || isProcessing}
              loading={isProcessing}
            />
          </div>
        </section>

        {/* Feldolgozás közben + eredmények folyamatos megjelenítése */}
        {(isProcessing || hasResults) && (
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4 gap-4">
              <h2 className="text-lg font-semibold text-gray-800">
                Feldolgozási eredmények
              </h2>
              {isProcessing && (
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <LoadingSpinner size="sm" />
                  <span>Feldolgozás: {progress}</span>
                </div>
              )}
            </div>
            {hasResults ? (
              <ResultTable
                results={results}
                onPreview={setPreviewFileId}
                canPreview={canPreview}
              />
            ) : (
              <p className="text-gray-500 text-sm text-center py-6">
                Az első számla feldolgozása folyamatban...
              </p>
            )}
          </section>
        )}

        {/* Export – ha van legalább egy eredmény és nincs folyamatban feldolgozás */}
        {hasResults && !isProcessing && (
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <ExportBar results={results} jobId={jobId} />
          </section>
        )}
      </main>

      {/* CSAK AZ API-NÉZET MIATT */}
      {showApiCalls && <ApiTracePanel calls={apiCalls} />}
      </div>

      {previewFile?.previewUrl && (
        <DocumentPreview
          fileName={previewFile.file_name}
          url={previewFile.previewUrl}
          mimeType={previewFile.previewType}
          onClose={() => setPreviewFileId(null)}
        />
      )}

      {/* Lábléc */}
      <footer className="text-center text-gray-400 text-xs py-6">
        Intelligens Számlafeldolgozó – GCP AI Demo &copy; {new Date().getFullYear()}
      </footer>
    </div>
  );
}

export default App;
