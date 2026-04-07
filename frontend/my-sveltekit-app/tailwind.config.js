// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Oxford University Blue Color Palette
        oxford: {
          // Primary Oxford Blue
          blue: '#002147',
          // Lighter variants for UI elements
          '50': '#f0f4f8',
          '100': '#d9e2ec',
          '200': '#bcccdc',
          '300': '#9fb3c8',
          '400': '#829ab1',
          '500': '#627d98',
          '600': '#486581',
          '700': '#334e68',
          '800': '#243b53',
          '900': '#002147',
          // Darker variants for depth
          '950': '#001122',
          '975': '#000b11'
        },
        // Supporting colors that work well with Oxford Blue
        accent: {
          gold: '#FFD700',      // Classic academic gold
          silver: '#C0C0C0',    // Silver for secondary accents
          cream: '#F5F5DC',     // Warm neutral
          pearl: '#F8F8FF'      // Light neutral
        },
        // Status colors that complement Oxford Blue
        status: {
          success: '#10b981',   // Green that works with blue
          warning: '#f59e0b',   // Amber/orange
          error: '#ef4444',     // Red
          info: '#3b82f6'       // Complementary blue
        }
      },
      fontFamily: {
        // Oxford-style typography
        serif: ['Georgia', 'Times New Roman', 'serif'],
        sans: ['Inter', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['Menlo', 'Monaco', 'Consolas', 'monospace']
      },
      boxShadow: {
        'oxford': '0 4px 14px 0 rgba(0, 33, 71, 0.15)',
        'oxford-lg': '0 10px 25px 0 rgba(0, 33, 71, 0.25)',
        'oxford-xl': '0 20px 40px 0 rgba(0, 33, 71, 0.35)'
      },
      backgroundImage: {
        'oxford-gradient': 'linear-gradient(135deg, #002147 0%, #334e68 100%)',
        'oxford-gradient-light': 'linear-gradient(135deg, #f0f4f8 0%, #d9e2ec 100%)'
      }
    },
  },
  plugins: [],
}
