/** @type {import('tailwindcss').Config} */
export default {
  content: ['./web/index.html', './web/src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        // Brand palette — matched against 21m.art screenshots
        bg: {
          DEFAULT: '#1f1f1f',
          soft: '#2a2a2a',
          deep: '#171717',
        },
        accent: {
          DEFAULT: '#f7931a',   // Bitcoin orange
          hover: '#ffa940',
          mute: '#c47615',
        },
        ink: {
          DEFAULT: '#ffffff',
          soft: '#d0d0d0',
          mute: '#9a9a9a',
        },
        line: '#3a3a3a',
        success: '#43b65b',     // BuhoGO green
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif',
        ],
      },
      letterSpacing: {
        headline: '0.08em',
      },
      borderRadius: {
        card: '0.5rem',
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(247, 147, 26, 0.3), 0 8px 24px -8px rgba(247, 147, 26, 0.4)',
      },
    },
  },
  plugins: [],
}
