/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: '#0b0e14',
        panel: '#121722',
        border: '#1f2733',
        accent: '#3b82f6',
        good: '#22c55e',
        warn: '#eab308',
        bad: '#ef4444',
      },
    },
  },
  plugins: [],
}
