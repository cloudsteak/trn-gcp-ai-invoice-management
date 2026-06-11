/** @type {import('tailwindcss').Config} */
export default {
  // Tartalom szkennelési útvonalak – csak a szükséges CSS kerül a buildbe
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      // Egyedi színek a státusz jelzőkhöz
      colors: {
        status: {
          ok: '#16a34a',       // Zöld – rendben
          warning: '#d97706',  // Sárga/narancs – figyelmeztetés
          error: '#dc2626',    // Piros – hiba
        },
      },
    },
  },
  plugins: [],
};
