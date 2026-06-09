// Főalkalmazás komponens – az oldalfelépítés és állapotkezelés összefogója
import React from 'react';
import UploadZone from './components/UploadZone.jsx';
import FileList from './components/FileList.jsx';
import ProcessButton from './components/ProcessButton.jsx';
import ResultTable from './components/ResultTable.jsx';
import ExportBar from './components/ExportBar.jsx';
import LoadingSpinner from './components/LoadingSpinner.jsx';
import { useProcessing } from './hooks/useProcessing.js';
import { useUpload } from './hooks/useUpload.js';

function App() {
  // Fájlfeltöltés állapotkezelése
  const { uploadedFiles, addFiles, removeFile } = useUpload();

  // Feldolgozás állapotkezelése
  const {
    status,
    results,
    progress,
    jobId,
    startProcessing,
  } = useProcessing();

  // Feldolgozás indítása a feltöltött fájlok azonosítóival
  const handleProcess = () => {
    const fileIds = uploadedFiles.map((f) => f.file_id);
    startProcessing(fileIds);
  };

  const isProcessing = status === 'uploading' || status === 'processing';
  const isDone = status === 'done';

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
                disabled={isProcessing}
              />
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

        {/* Feldolgozás közbeni animáció */}
        {isProcessing && (
          <section className="flex flex-col items-center py-8">
            <LoadingSpinner />
            <p className="text-gray-600 mt-3">
              Feldolgozás: {progress}...
            </p>
          </section>
        )}

        {/* Eredmény táblázat */}
        {isDone && results.length > 0 && (
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">
              Feldolgozási eredmények
            </h2>
            <ResultTable results={results} />
          </section>
        )}

        {/* Export gombok */}
        {isDone && results.length > 0 && (
          <section className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <ExportBar jobId={jobId} />
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
