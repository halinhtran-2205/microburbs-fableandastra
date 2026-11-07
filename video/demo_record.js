// Record demo.mp4: drive the real report.html in Chromium, timed to the voice lines.
// Usage: node demo_record.js <fontsDir> <voiceDir> <framesDir>
// Writes frames (jpeg) + frames.json and lines.json (line start times) into framesDir.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const [fontsDir, voiceDir, framesDir] = process.argv.slice(2);
const ROOT = path.join(__dirname, '..');
const LINES = JSON.parse(fs.readFileSync(path.join(voiceDir, 'demo_lines.json'), 'utf8'));
const GAP = 0.4;
const sleep = ms => new Promise(r => setTimeout(r, ms));

// real output from our own runs, shown in the terminal scene
const holdout = fs.readFileSync(path.join(ROOT, 'log_2026-03-01.txt'), 'utf8').split('\n');
const pick = name => holdout.find(l => l.startsWith(name + ' ')).trim().split(/\s+/);
const holdout2 = fs.readFileSync(path.join(ROOT, 'log_2025-09-01.txt'), 'utf8').split('\n');
const pick2 = name => holdout2.find(l => l.startsWith(name + ' ')).trim().split(/\s+/);
const fmtRow = (label, r) => `${label.padEnd(30)}${String(+r[1]).padStart(6)}   ${(r[2] * 100).toFixed(1).padStart(5)}%   $${Math.round(+r[3]).toLocaleString('en-AU').padStart(7)}`;
const csvHead = fs.readFileSync(path.join(ROOT, 'valuation_fableandastra.csv'), 'utf8').split('\n').slice(0, 3);
const csvRows = fs.readFileSync(path.join(ROOT, 'valuation_fableandastra.csv'), 'utf8').trim().split('\n').length;

(async () => {
  fs.mkdirSync(framesDir, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 810 }, deviceScaleFactor: 4 / 3 });
  const page = await ctx.newPage();
  page.on('pageerror', e => console.error('PAGE ERROR', e.message));
  await page.goto('file://' + path.join(ROOT, 'report.html'));
  await page.addStyleTag({ content: `
    @font-face{font-family:Fraunces;font-weight:700;src:url(file://${fontsDir}/fraunces/files/fraunces-latin-700-normal.woff2)}
    @font-face{font-family:Fraunces;font-style:italic;font-weight:600 700;src:url(file://${fontsDir}/fraunces/files/fraunces-latin-700-italic.woff2)}
    @font-face{font-family:Inter;font-weight:400;src:url(file://${fontsDir}/inter/files/inter-latin-400-normal.woff2)}
    @font-face{font-family:Inter;font-weight:500;src:url(file://${fontsDir}/inter/files/inter-latin-500-normal.woff2)}
    @font-face{font-family:Inter;font-weight:600;src:url(file://${fontsDir}/inter/files/inter-latin-600-normal.woff2)}
    @font-face{font-family:Inter;font-weight:700;src:url(file://${fontsDir}/inter/files/inter-latin-700-normal.woff2)}
    #dcap{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);max-width:1180px;background:rgba(8,12,20,.86);color:#fff;
      font:700 25px/1.35 Inter,sans-serif;padding:12px 26px;border-radius:14px;z-index:200;text-align:center;opacity:0;transition:opacity .25s;
      box-shadow:0 8px 30px rgba(0,0,0,.35)}
    #dcur{position:fixed;left:0;top:0;width:22px;height:22px;z-index:300;pointer-events:none;transform:translate(-3px,-2px)}
    #dcur.clk::after{content:"";position:absolute;left:-14px;top:-14px;width:48px;height:48px;border-radius:50%;border:3px solid #3d8bff;animation:rip .5s ease-out forwards}
    @keyframes rip{from{transform:scale(.3);opacity:1}to{transform:scale(1.2);opacity:0}}
    .dov{position:fixed;inset:0;z-index:150;display:flex;align-items:center;justify-content:center;flex-direction:column;
      background:radial-gradient(circle at 50% 45%,#0e2350 0%,#04070e 70%);color:#fff;transition:opacity .8s;text-align:center}
    .dov .b{font-family:Fraunces,serif;font-weight:700;font-size:92px;letter-spacing:-.01em}
    .dov .s{font-family:Fraunces,serif;font-style:italic;font-size:46px;color:#9cc8ff;margin-top:10px;text-shadow:0 0 30px rgba(90,160,255,.8)}
    .dov .m{font:600 18px Inter,sans-serif;color:#8b94a3;margin-top:40px;letter-spacing:.14em;text-transform:uppercase}
    #dterm{position:fixed;inset:0;z-index:150;background:radial-gradient(circle at 50% 40%,#0c1a38,#04070e 75%);display:flex;align-items:center;justify-content:center;transition:opacity .6s}
    #dterm .w{width:1120px;background:#0b1020;border:1px solid #24304a;border-radius:14px;box-shadow:0 30px 80px rgba(0,0,0,.6),0 0 60px rgba(61,139,255,.15);overflow:hidden}
    #dterm .bar{height:38px;background:#141b2e;display:flex;align-items:center;gap:8px;padding:0 16px;color:#7d8696;font:500 14px Inter,sans-serif}
    #dterm .bar i{width:12px;height:12px;border-radius:50%;background:#ff5f57}#dterm .bar i:nth-child(2){background:#febc2e}#dterm .bar i:nth-child(3){background:#28c840}
    #dterm pre{margin:0;padding:22px 26px;min-height:520px;font:17px/1.6 "DejaVu Sans Mono",monospace;color:#cfd8e6;white-space:pre}
    #dterm .p{color:#5aa0ff}#dterm .ok{color:#3ddc97}#dterm .hl{background:rgba(61,139,255,.22);color:#fff}
  `});
  await page.evaluate(() => { document.documentElement.dataset.theme = 'dark';
    document.querySelectorAll('#data .story').forEach((x, i) => x.id = 'story' + (i + 1));
    const c = document.createElement('div'); c.id = 'dcap'; document.body.appendChild(c);
    const k = document.createElement('div'); k.id = 'dcur'; k.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M3 2l7 19 2.6-7.4L20 11z" fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/></svg>'; document.body.appendChild(k);
    document.addEventListener('mousemove', e => { k.style.left = e.clientX + 'px'; k.style.top = e.clientY + 'px'; });
    const o = document.createElement('div'); o.className = 'dov'; o.id = 'dintro';
    o.innerHTML = '<div class="m" style="margin:0 0 24px">Microburbs Hackathon · Task 5 · Demo</div><div class="b">Every Flat, Priced</div><div class="s">Team FableAndAstra</div>'; document.body.appendChild(o); });
  await page.evaluate(() => document.fonts.ready);
  await page.mouse.move(1300, 700);
  await sleep(500);

  // ---- screencast
  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  cdp.on('Page.screencastFrame', async f => {
    const file = `f${String(frames.length).padStart(5, '0')}.jpg`;
    fs.writeFileSync(path.join(framesDir, file), Buffer.from(f.data, 'base64'));
    frames.push([file, f.metadata.timestamp]);
    try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) {}
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  // keep frames flowing even when nothing moves
  await page.evaluate(() => { const d = document.createElement('div'); d.style.cssText = 'position:fixed;left:0;top:0;width:1px;height:1px;opacity:.01;z-index:999';
    document.body.appendChild(d); let n = 0; (function tick(){ d.style.background = (n++ % 2) ? '#000' : '#010101'; requestAnimationFrame(tick); })(); });
  await sleep(600);

  // ---- helpers
  const cap = text => page.evaluate(t => { const c = document.getElementById('dcap'); c.textContent = t; c.style.opacity = t ? 1 : 0; }, text);
  async function center(sel, nth = 0){ const h = (await page.$$(sel))[nth]; const b = await h.boundingBox(); return [b.x + b.width / 2, b.y + b.height / 2]; }
  async function moveTo(sel, nth = 0, steps = 28){ const [x, y] = await center(sel, nth); await page.mouse.move(x, y, { steps }); return [x, y]; }
  async function click(sel, nth = 0){ const [x, y] = await moveTo(sel, nth); await sleep(150);
    await page.evaluate(() => { const k = document.getElementById('dcur'); k.classList.remove('clk'); void k.offsetWidth; k.classList.add('clk'); });
    await page.mouse.click(x, y); }
  const scrollTo = (sel, off = 74) => page.evaluate(([s, o]) => { const el = document.querySelector(s);
    window.scrollTo({ top: el.getBoundingClientRect().top + scrollY - o, behavior: 'smooth' }); }, [sel, off]);
  const term = async (html) => page.evaluate(h => { document.querySelector('#dterm pre').innerHTML = h; }, html);
  async function typeCmd(prefix, cmd, ms = 38){ for (let i = 1; i <= cmd.length; i++) { await term(prefix + `<span class="p">$</span> ${cmd.slice(0, i)}█`); await sleep(ms); }
    return prefix + `<span class="p">$</span> ${cmd}\n`; }

  let termText = '';
  const ACT = {
    intro1: async () => {},
    intro2: async () => { await page.evaluate(() => { const o = document.getElementById('dintro'); o.style.opacity = 0; setTimeout(() => o.remove(), 900);
      document.querySelectorAll('.kpi [data-count]').forEach(el => countUp(el)); }); },
    run1: async () => { await page.evaluate(() => { const t = document.createElement('div'); t.id = 'dterm'; t.style.opacity = 0;
        t.innerHTML = '<div class="w"><div class="bar"><i></i><i></i><i></i><span style="margin-left:10px">microburbs-fableandastra</span></div><pre></pre></div>';
        document.body.appendChild(t); requestAnimationFrame(() => t.style.opacity = 1); });
      await sleep(400); termText = await typeCmd('', 'python model.py --holdout 2026-03-01'); await term(termText); },
    run2: async () => { termText += '<span style="color:#7d8696">  train: sales from 2010 to 28 Feb 2026 · test: 930 sales, 1 Mar to 31 Aug 2026</span>\n';
      await term(termText); await sleep(1600); termText += '<span style="color:#7d8696">  building price index, look-back clues, LightGBM x3 ...</span>\n'; await term(termText); },
    run3: async () => { termText += `\n${'method'.padEnd(30)}${'sales'.padStart(6)}   within 10%   typical miss\n`;
      termText += `<span class="hl">${fmtRow('our model', pick('model'))}</span>\n${fmtRow('last sale + price index', pick('last_sale_indexed'))}\n${fmtRow('suburb + bedroom median', pick('suburb_bedroom_median'))}\n\n`;
      await term(termText); },
    run3b: async () => { termText = await typeCmd(termText, 'python model.py --holdout 2025-09-01', 30);
      termText += '<span style="color:#7d8696">  train: sales from 2010 to 31 Aug 2025 · test: 2,068 sales, 1 Sep 2025 to 31 Aug 2026</span>\n';
      await term(termText); await sleep(900); termText += `<span class="hl">${fmtRow('our model', pick2('model'))}</span>\n\n`; await term(termText); },
    run4: async () => { termText = await typeCmd(termText, 'python model.py --final fableandastra', 30);
      termText += '<span class="ok">wrote valuation_fableandastra.csv</span>\n'; await term(termText); await sleep(500);
      termText = await typeCmd(termText, 'head -3 valuation_fableandastra.csv; wc -l < valuation_fableandastra.csv', 22);
      termText += csvHead.join('\n') + `\n${csvRows}   <span class="ok">(header + 181,711 flats)</span>\n`; await term(termText); },
    data1: async () => { await page.evaluate(() => { const t = document.getElementById('dterm'); t.style.opacity = 0; setTimeout(() => t.remove(), 700); });
      await sleep(300); await scrollTo('#data'); },
    data2: async () => { await scrollTo('#story1', 90); await sleep(1300); await moveTo('#cSold .hrow', 1); },
    data3: async () => { await scrollTo('#story2', 90); await sleep(1400); await moveTo('#cBeds div', 18); await sleep(900); await moveTo('#cBeds div', 3, 20); },
    data4: async () => { await scrollTo('#story4', 90); await sleep(1500); await moveTo('#cIdx svg', 0); await sleep(700); await click('#idxSeg [data-v="month"]'); },
    data5: async () => { await scrollTo('#story5', 90); await sleep(1300); await moveTo('#cAnch .hrow', 0); },
    ins0: async () => { await scrollTo('#insights'); await sleep(1300); await moveTo('.ins', 0); await sleep(1600); await moveTo('.ins', 1, 20); await sleep(2200); await moveTo('.ins', 2, 20); },
    ins1: async () => { await scrollTo('#ladder', 150); await sleep(1300); await moveTo('#ladder .hrow', 20); },
    ins2: async () => { await click('#bedSeg [data-b="b2"]'); },
    ins3: async () => { await click('#sortSeg [data-s="growth"]'); },
    mod1: async () => { await scrollTo('#model'); await sleep(1200); await moveTo('.flow .st', 3, 40); },
    mod2: async () => { await scrollTo('#tl', 260); await sleep(1300); await click('#splitSeg [data-c="2025-09-01"]'); await sleep(1800); await moveTo('#tl .tr'); },
    mod3: async () => { await scrollTo('#cWin', 230); await sleep(1300); await moveTo('#cWin .vbar', 1); },
    res1: async () => { await scrollTo('#results'); await sleep(1200); await moveTo('.met', 0); await sleep(1500); await moveTo('.met', 1, 20); },
    res1b: async () => { await moveTo('.met', 2, 25); },
    res2: async () => { await scrollTo('#cRes', 260); await sleep(900); await click('#resSeg [data-v="hist"]'); await sleep(1900); await click('#resSeg [data-v="price"]'); },
    res3: async () => { await click('#resSeg [data-v="dir"]'); },
    look1: async () => { await scrollTo('#lookup'); },
    look2: async () => { await moveTo('#fSub'); await sleep(200); await page.selectOption('#fSub', 'Zetland'); await page.dispatchEvent('#fSub', 'change'); await sleep(700); await click('#fSize [data-v="l"]'); },
    look2b: async () => { await click('#fTier [data-v="2"]'); },
    look3: async () => { await scrollTo('#lkList', 300); await sleep(900); await click('#lkList .lkr', 0); await sleep(1200); await moveTo('#bcard .bed', 1); },
    look4: async () => { await scrollTo('#bcard .sales', 120); await sleep(1500); await moveTo('#bcard .sale .gap', 2); },
    look5: async () => { await scrollTo('#lookup', 74); await sleep(900); await click('#fSize [data-v=""]'); await page.selectOption('#fSub', ''); await page.dispatchEvent('#fSub', 'change'); await sleep(300); await click('#q'); await page.keyboard.type('Harris Street', { delay: 70 }); await sleep(400); await scrollTo('#lkList', 300); await sleep(800); await click('#lkList .lkr', 0); },
    end1: async () => { await scrollTo('#conclusion'); await sleep(1300); await moveTo('.modelline span', 0); },
    end2: async () => { await page.evaluate(() => { const o = document.createElement('div'); o.className = 'dov'; o.style.opacity = 0;
      o.innerHTML = '<div class="b">FableAndAstra</div><div class="s">Every flat, priced.</div><div class="m">github.com/halinhtran-2205/microburbs-fableandastra</div>';
      document.body.appendChild(o); requestAnimationFrame(() => o.style.opacity = 1); }); },
  };

  const t0 = Date.now() / 1000, starts = [];
  for (const L of LINES) {
    const start = Date.now() / 1000; starts.push({ id: L.id, start });
    await cap(L.caption);
    const act = ACT[L.id]();
    await sleep(L.dur * 1000);
    await act;
    await cap('');
    const left = start + L.dur + GAP - Date.now() / 1000;
    if (left > 0) await sleep(left * 1000);
    console.log(L.id, 'done at', (Date.now() / 1000 - t0).toFixed(1));
  }
  await sleep(1000);
  await cdp.send('Page.stopScreencast');
  fs.writeFileSync(path.join(framesDir, 'frames.json'), JSON.stringify(frames));
  fs.writeFileSync(path.join(framesDir, 'lines.json'), JSON.stringify(starts));
  console.log('frames', frames.length);
  await browser.close();
})();
