/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#131316',
        surface: '#1c1c22',
        surfaceLight: '#26262e',
        border: '#2e2e38',
        borderLight: '#3f3f4e',
        primary: '#3b82f6',
        primaryHover: '#2563eb',
        accent: '#10b981',
      }
    },
  },
  plugins: [],
}
