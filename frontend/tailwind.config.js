/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Primary palette
        "primary": "#89ceff",
        "primary-container": "#0ea5e9",
        "on-primary": "#00344d",
        "on-primary-container": "#003751",
        "primary-fixed": "#c9e6ff",
        "primary-fixed-dim": "#89ceff",
        "on-primary-fixed": "#001e2f",
        "on-primary-fixed-variant": "#004c6e",
        "inverse-primary": "#006591",
        
        // Secondary palette
        "secondary": "#4edea3",
        "secondary-container": "#00a572",
        "on-secondary": "#003824",
        "on-secondary-container": "#00311f",
        "secondary-fixed": "#6ffbbe",
        "secondary-fixed-dim": "#4edea3",
        "on-secondary-fixed": "#002113",
        "on-secondary-fixed-variant": "#005236",
        
        // Tertiary palette
        "tertiary": "#ffb2b7",
        "tertiary-container": "#ff697b",
        "on-tertiary": "#67001b",
        "on-tertiary-container": "#6c001d",
        "tertiary-fixed": "#ffdadb",
        "tertiary-fixed-dim": "#ffb2b7",
        "on-tertiary-fixed": "#40000d",
        "on-tertiary-fixed-variant": "#92002a",
        
        // Error palette
        "error": "#ffb4ab",
        "error-container": "#93000a",
        "on-error": "#690005",
        "on-error-container": "#ffdad6",
        
        // Surface palette
        "surface": "#0b1326",
        "surface-dim": "#0b1326",
        "surface-bright": "#31394d",
        "surface-container-lowest": "#060e20",
        "surface-container-low": "#131b2e",
        "surface-container": "#171f33",
        "surface-container-high": "#222a3d",
        "surface-container-highest": "#2d3449",
        "surface-variant": "#2d3449",
        "on-surface": "#dae2fd",
        "on-surface-variant": "#bec8d2",
        "inverse-surface": "#dae2fd",
        "inverse-on-surface": "#283044",
        
        // Outline
        "outline": "#88929b",
        "outline-variant": "#3e4850",
        
        // Background
        "background": "#0b1326",
        "on-background": "#dae2fd",
        
        // Surface tint
        "surface-tint": "#89ceff",
      },
      fontFamily: {
        "sans": ["Inter", "system-ui", "sans-serif"],
        "mono": ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
        "headline": ["Inter", "system-ui", "sans-serif"],
        "label": ["JetBrains Mono", "monospace"],
      },
      fontSize: {
        "headline-lg": ["32px", { lineHeight: "40px", letterSpacing: "-0.02em", fontWeight: "700" }],
        "headline-md": ["24px", { lineHeight: "32px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "body-lg": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "body-md": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "label-md": ["12px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "500" }],
        "label-sm": ["10px", { lineHeight: "14px", fontWeight: "500" }],
      },
      spacing: {
        "xs": "4px",
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "xl": "48px",
        "gutter": "24px",
        "margin": "32px",
      },
      borderRadius: {
        "DEFAULT": "0.125rem",
        "lg": "0.25rem",
        "xl": "0.5rem",
        "full": "0.75rem",
      },
      animation: {
        "pulse-ring": "pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "scanline": "scanline 8s linear infinite",
        "blink": "blink 1s infinite",
      },
      keyframes: {
        "pulse-ring": {
          "0%": { transform: "scale(0.95)", opacity: "0.5" },
          "50%": { transform: "scale(1.05)", opacity: "0.2" },
          "100%": { transform: "scale(0.95)", opacity: "0.5" },
        },
        "scanline": {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        "blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
      },
    },
  },
  plugins: [],
}
