// 截图测试：node tools/shot.js [pose ...]（默认全套机位）
// 需先启动 tools/serve.js
const path = require('path');
const fs = require('fs');
const puppeteer = require('E:/ZCODE/node_modules/puppeteer-core');

function findBrowser() {
  const cands = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  ];
  for (const c of cands) if (fs.existsSync(c)) return c;
  throw new Error('no browser');
}

(async () => {
  const poses = process.argv.slice(2).length
    ? process.argv.slice(2)
    : ['spawn', 'city', 'coast', 'beach', 'hill', 'lighthouse', 'park'];
  const browser = await puppeteer.launch({
    executablePath: findBrowser(),
    headless: 'new',
    args: ['--use-angle=default', '--enable-unsafe-webgpu', '--window-size=1320,800'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('[pageerror] ' + e.message));
  fs.mkdirSync(path.join(__dirname, '..', 'shots'), { recursive: true });

  for (const pose of poses) {
    const orbit = pose.startsWith('orbit:') ? 'orbit=1&' : '';
    const p = pose.replace('orbit:', '');
    const url = `http://127.0.0.1:8166/?hud=0&${orbit}pose=${p}&q=high`;
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    try {
      await page.waitForFunction('window.__state && window.__state.ready', { timeout: 90000 });
      await new Promise(r => setTimeout(r, 2600));
      const st = await page.evaluate('window.__state');
      const file = path.join(__dirname, '..', 'shots', `shot_${p}.png`);
      await page.screenshot({ path: file });
      console.log(`OK ${p} fps=${st.fps.toFixed(1)} pos=(${st.x | 0},${st.z | 0}) surf=${st.surface}`);
    } catch (e) {
      console.log(`FAIL ${pose}: ${e.message.slice(0, 120)}`);
    }
  }
  console.log('console errors:', errors.length ? errors.slice(0, 8) : 'none');
  await browser.close();
})();
