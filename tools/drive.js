// 驾驶测试：油门加速 / 手刹漂移 / 复位 / 手机宽度触屏
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
  const browser = await puppeteer.launch({
    executablePath: findBrowser(),
    headless: 'new',
    args: ['--use-angle=default', '--autoplay-policy=no-user-gesture-required'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('[pageerror] ' + e.message));

  const url = 'http://127.0.0.1:8166/?pose=coast&q=medium';
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction('window.__state && window.__state.ready', { timeout: 90000 });
  // 点击“进入驾驶”启动
  await page.evaluate('document.getElementById("btnStart").click()');
  await new Promise(r => setTimeout(r, 800));

  // —— 直线加速 8 秒 ——
  await page.keyboard.down('KeyW');
  const speeds = [];
  for (let i = 0; i < 8; i++) {
    await new Promise(r => setTimeout(r, 1000));
    const s = await page.evaluate('window.__state.speed');
    speeds.push(Math.round(s));
  }
  await page.keyboard.up('KeyW');
  const st1 = await page.evaluate('window.__state');
  console.log('加速曲线 km/h:', speeds.join(' → '));
  console.log(`终速 ${Math.round(st1.speed)} km/h, fps=${st1.fps.toFixed(1)}, surface=${st1.surface}, gear=${st1.gear}`);
  await page.screenshot({ path: path.join(__dirname, '..', 'shots', 'drive_fast.png') });

  // —— 手刹漂移 ——
  await page.keyboard.down('KeyW');
  await page.keyboard.down('KeyA');
  await page.keyboard.down('Space');
  await new Promise(r => setTimeout(r, 2500));
  await page.keyboard.up('Space');
  await page.keyboard.up('KeyA');
  const st2 = await page.evaluate('window.__state');
  console.log(`漂移: drift=${st2.drift.toFixed(2)}, speed=${Math.round(st2.speed)} km/h`);
  await page.screenshot({ path: path.join(__dirname, '..', 'shots', 'drive_drift.png') });
  await page.keyboard.up('KeyW');

  // —— R 复位 ——
  await page.keyboard.press('KeyR');
  await new Promise(r => setTimeout(r, 700));
  const st3 = await page.evaluate('window.__state');
  console.log(`复位后 pos=(${st3.x | 0}, ${st3.z | 0}) surface=${st3.surface}`);

  // —— 手机宽度 + 触屏 UI（全新页面，从头就是手机视口）——
  const mp = await browser.newPage();
  await mp.setViewport({ width: 390, height: 844, hasTouch: true, isMobile: true });
  const merrs = [];
  mp.on('pageerror', e => merrs.push(e.message));
  await mp.goto('http://127.0.0.1:8166/?pose=spawn&q=medium', { waitUntil: 'domcontentloaded' });
  await mp.waitForFunction('window.__state && window.__state.ready', { timeout: 90000 });
  await mp.evaluate('document.getElementById("btnStart").click()');
  await mp.touchscreen.tap(340, 700);
  await mp.keyboard.down('KeyW');
  await new Promise(r => setTimeout(r, 2500));
  await mp.keyboard.up('KeyW');
  const touchVisible = await mp.evaluate(
    'getComputedStyle(document.getElementById("touchUI")).display !== "none"');
  const mst = await mp.evaluate('window.__state');
  await mp.screenshot({ path: path.join(__dirname, '..', 'shots', 'drive_mobile.png') });
  console.log('触屏UI可见:', touchVisible, ' 手机端speed=', Math.round(mst.speed), 'km/h fps=', mst.fps.toFixed(1), ' 页面错误:', merrs.length ? merrs.slice(0, 3) : 'none');

  console.log('console errors:', errors.length ? errors.slice(0, 8) : 'none');
  await browser.close();
})();
