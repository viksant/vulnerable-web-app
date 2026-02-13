import forms from "@tailwindcss/forms";

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    borderRadius: {
      none: "0px",
      full: "9999px",
    },
    extend: {
      colors: {
        neo: {
          bg: "#FFFDF5",
          fg: "#000000",
          accent: "#FF6B6B",
          secondary: "#FFD93D",
          muted: "#C4B5FD",
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', "sans-serif"],
      },
      boxShadow: {
        "neo-sm": "4px 4px 0px 0px #000",
        "neo-md": "8px 8px 0px 0px #000",
        "neo-lg": "12px 12px 0px 0px #000",
        "neo-xl": "16px 16px 0px 0px #000",
        "neo-white": "8px 8px 0px 0px #fff",
        none: "none",
      },
      borderWidth: {
        DEFAULT: "2px",
        2: "2px",
        4: "4px",
        8: "8px",
      },
      animation: {
        "spin-slow": "spin 10s linear infinite",
        "bounce-slow": "bounce 3s infinite",
      },
    },
  },
  plugins: [forms],
};
