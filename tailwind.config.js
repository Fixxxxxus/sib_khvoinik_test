// Конфиг для сборки статического CSS (standalone Tailwind CLI v3).
// Должен совпадать с inline-конфигом, который раньше жил в base.html.
// Пересборка после правок шаблонов:
//   tailwindcss -c tailwind.config.js -i tailwind.input.css -o static/css/tailwind.css --minify
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/app.js',
    './static/js/landing-ozelenenie.js',
    './static/js/opt.js',
  ],
  theme: {
    extend: {
      colors: {
        brand: '#2D6A4F',
        brand2: '#40916C',
        accent: '#E9C46A',
        // Палитра посадочной «Озеленение · финал сезона» (правки маркетолога,
        // 10.09.2026). Используется ТОЛЬКО на этом лендинге: остальные страницы
        // сайта остаются на brand/brand2/accent.
        land: {
          bg: '#eef1ec',
          sheet: '#f3f5f1',
          card: '#ffffff',
          heading: '#16301a',
          text: '#3d4f42',
          muted: '#6b7b70',
          line: '#dde5da',
          green: '#2e7d32',
          'green-dark': '#1b5e20',
          'green-soft': '#e8f3e9',
        },
      },
      boxShadow: {
        soft: '0 10px 30px rgba(0,0,0,0.08)',
        glow: '0 0 0 1px rgba(64,145,108,0.25), 0 20px 60px rgba(45,106,79,0.22)',
      },
    },
  },
};
