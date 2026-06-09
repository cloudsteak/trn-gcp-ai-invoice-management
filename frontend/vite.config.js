import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite konfiguráció – React plugin és backend proxy beállítása
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Fejlesztői proxy – API kérések átirányítása a backend felé
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
