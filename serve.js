// 本地静态服务器（正确 MIME，支持 ES modules / GLB）
const http = require('http'), fs = require('fs'), path = require('path');
const root = __dirname;
const mime = { html: 'text/html; charset=utf-8', js: 'text/javascript', mjs: 'text/javascript', css: 'text/css', json: 'application/json', png: 'image/png', ico: 'image/x-icon', glb: 'model/gltf-binary' };
http.createServer((req, res) => {
  const rel = decodeURIComponent(req.url.split('?')[0]).replace(/\\/g, '/').replace(/\.\.+/g, '');
  let p = path.resolve(root, '.' + rel);
  if (p !== root && !p.startsWith(root + path.sep)) { res.writeHead(403); res.end('403'); return; }
  if (!path.extname(p)) p = path.join(p, 'index.html');
  fs.readFile(p, (e, d) => {
    if (e) { res.writeHead(404); res.end('404'); return; }
    res.writeHead(200, { 'Content-Type': mime[p.split('.').pop()] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    res.end(d);
  });
}).listen(8166, () => console.log('serving on 8166'));
