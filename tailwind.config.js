/** Config Tailwind (v3) pour générer un CSS figé et rapide (sans runtime navigateur).
 *  Build : npx tailwindcss@3 -c tailwind.config.js -i static/src/input.css \
 *          -o static/vendor/tailwind.built.css --minify
 */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
      colors: { lpm: { light: "#0196F2", DEFAULT: "#0073DE", dark: "#0057CA" } },
      boxShadow: { card: "0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06)" },
    },
  },
  // Les classes de couleur construites dynamiquement dans les templates
  // (ex. bg-{{ status_color }}-50) ne sont pas vues par le scanner : on les
  // force ici pour ne rien casser.
  safelist: [
    {
      pattern:
        /^(bg|text|border|ring|from|to)-(slate|gray|zinc|neutral|stone|emerald|green|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|red|orange|amber|yellow|lime)-(50|100|200|300|400|500|600|700|800|900)$/,
    },
  ],
};
