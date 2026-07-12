#!/usr/bin/env node
// Playwright capture runtime for a design-fidelity eval (servo design-eval).
// Copied into <target>/.servo/design-eval/ and run with that dir as cwd. Uses
// the *target's* Playwright (a project devDependency) — servo ships no browser.
//
//   node capture.mjs --refs                      render every screen's reference
//   node capture.mjs --screen <id> --out <path>  screenshot the app, seeded state
//
// References crop out device chrome (bezel + status bar + home indicator) so a
// full-bleed PWA compares fairly against a phone-framed mockup (spike finding #1).
import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const targetRoot = path.resolve(here, '..', '..'); // <target>/
const config = JSON.parse(fs.readFileSync(path.join(here, 'config.json'), 'utf8'));
const vp = config.viewport || { width: 392, height: 812, deviceScaleFactor: 2 };

const argv = process.argv.slice(2);
const flag = (name) => {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : undefined;
};
const wantRefs = argv.includes('--refs');
const fail = (msg) => {
  console.error(`capture: ${msg}`);
  process.exit(2);
};

const browser = await chromium.launch();
try {
  if (wantRefs) {
    for (const screen of config.screens) {
      const rs = screen.referenceSource;
      if (!rs) fail(`screen ${screen.id}: no referenceSource to render`);
      const page = await browser.newPage({ deviceScaleFactor: vp.deviceScaleFactor });
      await page.setViewportSize({ width: 1600, height: 1600 });
      await page.goto(pathToFileURL(path.resolve(targetRoot, rs.file)).href, {
        waitUntil: 'networkidle',
      });
      await page.waitForTimeout(rs.settleMs ?? 2500);
      const el = page.locator(rs.selector).first();
      if (!(await el.count())) fail(`screen ${screen.id}: selector not found: ${rs.selector}`);
      // Scroll the target into the viewport so its box stays within the screenshot
      // bitmap — mockups often lay several screens out in one gallery, past the fold.
      await el.scrollIntoViewIfNeeded();
      const box = await el.boundingBox();
      const c = rs.crop || {};
      const clip = {
        x: box.x + (c.left || 0),
        y: box.y + (c.top || 0),
        width: box.width - (c.left || 0) - (c.right || 0),
        height: box.height - (c.top || 0) - (c.bottom || 0),
      };
      const out = path.join(here, screen.reference);
      fs.mkdirSync(path.dirname(out), { recursive: true });
      await page.screenshot({ path: out, clip });
      await page.close();
      console.error(`ref ${screen.id} -> ${screen.reference}`);
    }
  } else {
    const id = flag('--screen');
    const out = flag('--out');
    if (!id || !out) fail('usage: --screen <id> --out <path>');
    const screen = config.screens.find((s) => s.id === id);
    if (!screen) fail(`unknown screen: ${id}`);
    const page = await browser.newPage({ deviceScaleFactor: vp.deviceScaleFactor });
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(config.app_url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(800);
    if (screen.setup) {
      // Per-screen setup seeds deterministic state + navigates (spike finding #2/#3).
      const mod = await import(pathToFileURL(path.join(here, screen.setup)).href);
      await mod.default(page, config);
    }
    await page.waitForTimeout(screen.settleMs ?? 400);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await page.screenshot({ path: out });
  }
} catch (err) {
  fail(String(err && err.message ? err.message : err));
} finally {
  await browser.close();
}
