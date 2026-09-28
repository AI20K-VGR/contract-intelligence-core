#!/usr/bin/env node
/**
 * Smoke test for the ported html2pptx.js (HTML slide -> pptxgenjs slide).
 * Run: node harness/plugins/hs/skills/document-skills/tests/html2pptx-smoke.test.cjs
 *
 * The full render needs playwright (+chromium), sharp, and pptxgenjs — a heavy
 * runtime the harness core does not carry. So the STRUCTURAL guards always run
 * (syntax, export contract, declared deps); the FUNCTIONAL render runs only when
 * those deps are installed. The functional skip is reported loudly, never silent —
 * a green here without the functional line means deps were absent, not that nothing
 * was checked.
 */
const { execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const SCRIPT = path.join(__dirname, '..', 'scripts', 'html2pptx.js');
const PKG = path.join(__dirname, '..', 'scripts', 'package.json');
const SCRIPTS_DIR = path.join(__dirname, '..', 'scripts');

let passed = 0;
let failed = 0;
async function check(name, fn) {
  try {
    await fn();
    console.log(`  ✓ ${name}`);
    passed++;
  } catch (err) {
    console.error(`  ✗ ${name}\n      ${err.message}`);
    failed++;
  }
}
function assert(cond, msg) {
  if (!cond) throw new Error(msg || 'assertion failed');
}

function depsPresent() {
  for (const d of ['playwright', 'sharp', 'pptxgenjs']) {
    try {
      require.resolve(d, { paths: [SCRIPTS_DIR, __dirname] });
    } catch {
      return false;
    }
  }
  return true;
}

(async () => {
  console.log('html2pptx structural guards');

  await check('script file exists', () => assert(fs.existsSync(SCRIPT), 'html2pptx.js missing'));

  await check('syntax is valid (node --check)', () => {
    execFileSync(process.execPath, ['--check', SCRIPT], { stdio: 'pipe' });
  });

  await check('exports the html2pptx function', () => {
    const src = fs.readFileSync(SCRIPT, 'utf-8');
    assert(/module\.exports\s*=\s*html2pptx/.test(src), 'no `module.exports = html2pptx`');
  });

  await check('package.json declares the runtime deps', () => {
    const pkg = JSON.parse(fs.readFileSync(PKG, 'utf-8'));
    const deps = pkg.dependencies || {};
    for (const d of ['playwright', 'sharp', 'pptxgenjs']) {
      assert(deps[d], `dependency '${d}' not declared in package.json`);
    }
  });

  await check('no upstream brand in the script', () => {
    const src = fs.readFileSync(SCRIPT, 'utf-8').toLowerCase();
    assert(!src.includes('claudekit') && !src.includes('.claude/'), 'upstream brand survived');
  });

  if (depsPresent()) {
    await check('renders a tiny HTML slide to a valid .pptx (functional)', async () => {
      const os = require('os');
      const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'h2p-'));
      const html = path.join(tmp, 'slide.html');
      const out = path.join(tmp, 'out.pptx');
      fs.writeFileSync(
        html,
        '<html><body style="width:720pt;height:405pt;margin:0">' +
          '<div style="position:absolute;left:50pt;top:50pt">Hi</div></body></html>'
      );
      const pptxgen = require(require.resolve('pptxgenjs', { paths: [SCRIPTS_DIR] }));
      const html2pptx = require(SCRIPT);
      const pptx = new pptxgen();
      pptx.defineLayout({ name: 'C', width: 10, height: 5.625 });
      pptx.layout = 'C';
      await html2pptx(html, pptx);
      await pptx.writeFile({ fileName: out });
      const buf = fs.readFileSync(out);
      assert(buf.slice(0, 2).toString() === 'PK', 'output is not a zip/OOXML container');
      fs.rmSync(tmp, { recursive: true, force: true });
    });
  } else {
    console.log(
      '  ⚠ functional render SKIPPED — playwright/sharp/pptxgenjs not installed ' +
        '(run `npm install` in scripts/ to enable). Structural guards above still ran.'
    );
  }

  console.log(`\nResults: ${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
})();
