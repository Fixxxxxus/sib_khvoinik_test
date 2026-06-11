// Конфиг для сборки статического CSS (standalone Tailwind CLI v3).
// Должен совпадать с inline-конфигом, который раньше жил в base.html.
// Пересборка после правок шаблонов:
//   tailwindcss -c tailwind.config.js -i tailwind.input.css -o static/css/tailwind.css --minify
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/app.js',
  ],
  theme: {
    extend: {
      colors: {
        brand: '#2D6A4F',
        brand2: '#40916C',
        accent: '#E9C46A',
      },
      boxShadow: {
        soft: '0 10px 30px rgba(0,0,0,0.08)',
        glow: '0 0 0 1px rgba(64,145,108,0.25), 0 20px 60px rgba(45,106,79,0.22)',
      },
    },
  },
};
