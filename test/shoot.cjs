// Headless check + screenshots. Usage: node test/shoot.cjs <baseUrl> <outDir>
const puppeteer = require('/tmp/shotenv/node_modules/puppeteer-core');
const [,, base = 'http://localhost:8791/', outDir = '.'] = process.argv;
const wait = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const errs = [];
  const page = async (w, h, mobile) => {
    const p = await b.newPage();
    p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
    p.on('pageerror', e => errs.push('pageerror: ' + e.message));
    p.on('requestfailed', r => { if (!/fonts\.g/.test(r.url())) errs.push('reqfail: ' + r.url() + ' ' + r.failure()?.errorText); });
    p.on('response', r => { if (r.status() >= 400) errs.push('http ' + r.status() + ' ' + r.url()); });
    await p.setViewport({ width: w, height: h, deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile });
    return p;
  };
  const p = await page(1440, 1000, false);
  await p.goto(base, { waitUntil: 'networkidle2', timeout: 60000 }); await wait(1500);
  await p.screenshot({ path: outDir + '/screenshot-overview.png' });
  const info = {};
  for (const t of ['revival', 'import', 'closing', 'twins']) {
    await p.click(`#tabs button[data-tab="${t}"]`); await wait(400);
    info[t] = await p.evaluate(() => ({ count: document.querySelector('#count').textContent, first: document.querySelector('.lead h3')?.textContent }));
  }
  await p.click('#tabs button[data-tab="closing"]'); await wait(300);
  await p.click('.lead'); await wait(1800);
  await p.screenshot({ path: outDir + '/screenshot-lead.png' });
  info.detail = await p.evaluate(() => ({ title: document.querySelector('.d-title')?.textContent, srcs: [...document.querySelectorAll('.srcs a')].map(a => a.href) }));
  // status persistence
  await p.click('.tracker button[data-st="contacted"]'); await wait(200);
  info.stored = await p.evaluate(() => localStorage.getItem('provenance.v1'));
  await p.keyboard.press('Escape'); await wait(300);
  await p.click('.topnav button[data-view="map"]'); await wait(5000);
  await p.screenshot({ path: outDir + '/screenshot-map.png' });
  info.mapNote = await p.evaluate(() => document.querySelector('#map-note').textContent);
  await p.click('.topnav button[data-view="sources"]'); await wait(1200);
  await p.screenshot({ path: outDir + '/screenshot-sources.png', fullPage: false });
  info.sources = await p.evaluate(() => document.querySelectorAll('.srccard').length);
  await p.click('.topnav button[data-view="rules"]'); await wait(300);
  info.rules = await p.evaluate(() => document.querySelector('#rules h1')?.textContent);
  const m = await page(390, 844, true);
  await m.goto(base, { waitUntil: 'networkidle2', timeout: 60000 }); await wait(1500);
  await m.screenshot({ path: outDir + '/screenshot-mobile.png' });
  await m.evaluate(() => document.querySelector('.five li')?.click()); await wait(1500);
  await m.screenshot({ path: outDir + '/screenshot-mobile-lead.png' });
  console.log(JSON.stringify(info, null, 1));
  console.log('ERRORS:', errs.length ? errs.join('\n') : 'none');
  await b.close();
})();
