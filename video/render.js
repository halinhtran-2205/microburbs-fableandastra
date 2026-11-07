// Render video/pitch.html frame by frame into an H.264 mp4 (silent; voice is added later).
// Usage: node render.js <fontsDir> <out.mp4> [fps] [--stills t1,t2,...]
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');

const [fontsDir, out, fpsArg, flag, stillsArg] = process.argv.slice(2);
const FPS = +(fpsArg || 30), DURATION = 44.5;

(async () => {
  const html = fs.readFileSync(path.join(__dirname, 'pitch.html'), 'utf8')
    .replace('/*DATA*/null', fs.readFileSync(path.join(__dirname, 'video_data.json'), 'utf8'))
    .replace('/*TIMING*/null', fs.readFileSync(path.join(__dirname, 'timing.json'), 'utf8'))
    .replaceAll('url(FONTS/', `url(file://${fontsDir}/`);
  const built = path.join(__dirname, 'pitch_built.html');
  fs.writeFileSync(built, html);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', e => console.error('PAGE ERROR', e.message));
  await page.goto('file://' + built);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);

  if (flag === '--stills') {
    for (const t of stillsArg.split(',').map(Number)) {
      await page.evaluate(t => window.render(t), t);
      await page.screenshot({ path: path.join(path.dirname(out), `still_${t}.png`) });
    }
    await browser.close();
    return;
  }

  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-movflags', '+faststart', out],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.round(DURATION * FPS);
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => window.render(t), i / FPS);
    const buf = await page.screenshot({ type: 'jpeg', quality: 94 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 150 === 0) console.log(`frame ${i}/${n}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  console.log('wrote', out);
})();
