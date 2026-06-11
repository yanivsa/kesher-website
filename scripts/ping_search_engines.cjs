const https = require('https');

const SITEMAP_URL = 'https://kesher.saharoni.com/sitemap.xml';

const searchEngines = [
  { name: 'Google', url: `https://www.google.com/ping?sitemap=${encodeURIComponent(SITEMAP_URL)}` },
  { name: 'Bing', url: `https://www.bing.com/ping?sitemap=${encodeURIComponent(SITEMAP_URL)}` }
];

console.log(`Starting ping for sitemap: ${SITEMAP_URL}`);

searchEngines.forEach(engine => {
  https.get(engine.url, (res) => {
    if (res.statusCode >= 200 && res.statusCode < 300) {
      console.log(`✅ Successfully pinged ${engine.name}`);
    } else {
      console.log(`❌ Failed to ping ${engine.name}. Status code: ${res.statusCode}`);
    }
  }).on('error', (err) => {
    console.error(`❌ Error pinging ${engine.name}:`, err.message);
  });
});
