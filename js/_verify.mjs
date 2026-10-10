// 高度公式一致性校验辅助：在固定网格上采样 terrainH，输出 JSON 映射
// 由 tools/worldspec.py --verify 调用（cwd=项目根，node js _verify.mjs → 实际文件 js/_verify.mjs）
import { terrainH } from './height.js';

const pts = [];
for (let i = -13; i <= 13; i++) {
  for (let j = -13; j <= 13; j++) {
    pts.push([i * 100 + (i % 3 ? 37 : -21), j * 100 + (j % 2 ? 53 : -77)]);
  }
}
pts.push([0, 620], [-1040, 600], [1050, 60], [0, 830], [1300, 700], [720, 772], [-980, 380]);

const out = {};
for (const [x, z] of pts) out[x + ',' + z] = terrainH(x, z);
console.log(JSON.stringify(out));
