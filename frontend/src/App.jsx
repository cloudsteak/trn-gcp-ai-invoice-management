// Főalkalmazás komponens – az oldalfelépítés és állapotkezelés összefogója
import React, { useState } from 'react';
import UploadZone from './components/UploadZone.jsx';
import FileList from './components/FileList.jsx';
import ProcessButton from './components/ProcessButton.jsx';
import ResultTable from './components/ResultTable.jsx';
import ExportBar from './components/ExportBar.jsx';
import LoadingSpinner from './components/LoadingSpinner.jsx';
import { useProcessing } from './hooks/useProcessing.js';
import { useUpload } from './hooks/useUpload.js';
import { deleteUploadedFiles } from './services/api.js';

function App() {
  const { uploadedFiles, addFiles, removeFile, clearFiles } = useUpload();
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState(null);

  const {
    status,
    results,
    progress,
    jobId,
    startProcessing,
  } = useProcessing();

  const isProcessing = status === 'processing';
  const hasResults = results.length > 0;

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
      <header className="bg-blue-700 text-white shadow-md">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center gap-3">
          <span className="text-2xl">📄</span>
          <h1 className="text-xl font-bold tracking-tight">
            Intelligens Számlafeldolgozó
          </h1>
          <span className="text-blue-300 text-sm ml-auto">
            Google Cloud Document AI + Gemini
          </span>
        </div>
      </header>

      {/* Fő tartalom */}
      <main className="max-w-6xl mx-auto px-4 py-8 space-y-6">
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
              <ResultTable results={results} />
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

      {/* Lábléc */}
      <footer className="text-center text-gray-400 text-xs py-6">
        Intelligens Számlafeldolgozó – GCP AI Demo &copy; {new Date().getFullYear()}
      </footer>
    </div>
  );
}

export default App;
