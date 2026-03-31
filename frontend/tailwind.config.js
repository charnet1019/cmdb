/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design System Colors
        primary: {
          DEFAULT: '#005daa',
          container: '#0075d5',
        },
        secondary: {
          DEFAULT: '#6750A4',
          container: '#E8DEF8',
        },
        tertiary: {
          DEFAULT: '#934600',
        },
        surface: {
          DEFAULT: '#f7f9fc',
          container: {
            low: '#f2f4f7',
            lowest: '#ffffff',
            high: '#e6e8eb',
          }
        },
        outline: {
          DEFAULT: '#79747E',
          variant: '#CAC4D0',
        },
        error: {
          DEFAULT: '#B3261E',
          container: '#F9DEDC',
        },
        success: {
          DEFAULT: '#22c55e',
          container: '#dcfce7',
        },
        warning: {
          DEFAULT: '#f59e0b',
          container: '#fef3c7',
        },
      },
      fontFamily: {
        headline: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        'sm': '4px',
        'md': '8px',
        'lg': '12px',
        'xl': '16px',
        'full': '9999px',
      },
      boxShadow: {
        'sm': '0 1px 2px 0 rgb(0 0 0 / 0.05)',
        'md': '0 4px 6px -1px rgb(0 0 0 / 0.1)',
        'lg': '0 10px 15px -3px rgb(0 0 0 / 0.1)',
        'glass': '0 24px 48px -12px rgba(25, 28, 30, 0.04)',
      },
      backdropBlur: {
        'glass': '12px',
      },
    },
  },
  plugins: [],
}