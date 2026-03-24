/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        gemini: {
          dark: '#131314',
          sidebar: '#1e1f20',
          input: '#282a2c',
          text: '#e3e3e3',
          border: '#333537',
          hover: '#333537',
          primary: '#8ab4f8'
        }
      },
      fontFamily: {
        sans: ['"Google Sans"', 'Inter', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        shuffle: {
          '0%, 100%': { transform: 'translate(0, 0) rotate(0deg)' },
          '25%': { transform: 'translate(1px, -1px) rotate(8deg)' },
          '50%': { transform: 'translate(-1px, 1px) rotate(-8deg)' },
          '75%': { transform: 'translate(1px, 1px) rotate(4deg)' },
        }
      },
      animation: {
        'dice-shuffle': 'shuffle 0.5s ease-in-out infinite',
      }
    },
  },
  plugins: [],
}
