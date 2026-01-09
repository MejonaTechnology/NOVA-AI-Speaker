/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'sci-base': '#020408', // Deep Void
        'sci-panel': 'rgba(10, 15, 30, 0.6)', // Glassmorphic Dark
        'sci-cyan': '#00F0FF', // Electric Cyan (Unchanged, it's perfect)
        'sci-accent': '#FF2A6D', // Neon Rose (High contrast against Cyan)
        'sci-dim': 'rgba(0, 240, 255, 0.05)',
        'sci-border': 'rgba(0, 240, 255, 0.2)' // Subtle Glow Border
      },
      fontFamily: {
        'sci': ['"Courier New"', 'monospace'], // Fallback for sci-fi look
        'mono': ['"Courier New"', 'monospace']
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan': 'scan 2s linear infinite'
      },
      keyframes: {
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' }
        }
      }
    },
  },
  plugins: [],
}
