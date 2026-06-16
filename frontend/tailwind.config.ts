import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#f7f8fb",
        foreground: "#17202a",
        muted: "#667085",
        line: "#d7dce5",
        panel: "#ffffff",
        accent: "#0f766e",
        ink: "#202939",
        warning: "#a15c07",
        danger: "#b42318"
      },
      boxShadow: {
        soft: "0 16px 40px rgba(28, 39, 49, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
