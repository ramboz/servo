// Pure-logic tests for capture_lib.mjs (servo design-eval) — no browser.
//
// Covers the chrome-crop clip geometry (spike finding #1) and the CLI arg /
// screen / viewport resolution that capture.mjs delegates here. capture.mjs
// itself stays browser-only and unimportable (top-level Playwright launch); the
// load-bearing arithmetic lives here where it can be checked deterministically.
//
//   node --test skills/design-eval/test_capture_lib.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { parseFlag, resolveViewport, findScreen, computeClip } from './capture_lib.mjs';

test('parseFlag reads the value after a flag', () => {
  assert.equal(parseFlag(['--screen', 'home', '--out', 'a.png'], '--screen'), 'home');
  assert.equal(parseFlag(['--screen', 'home', '--out', 'a.png'], '--out'), 'a.png');
});

test('parseFlag returns undefined for an absent flag', () => {
  assert.equal(parseFlag(['--refs'], '--screen'), undefined);
});

test('resolveViewport falls back to the phone default', () => {
  assert.deepEqual(resolveViewport({}), { width: 392, height: 812, deviceScaleFactor: 2 });
  assert.deepEqual(resolveViewport(undefined), { width: 392, height: 812, deviceScaleFactor: 2 });
});

test('resolveViewport honours an explicit viewport', () => {
  const vp = { width: 100, height: 200, deviceScaleFactor: 1 };
  assert.deepEqual(resolveViewport({ viewport: vp }), vp);
});

test('findScreen matches by id and misses cleanly', () => {
  const screens = [{ id: 'home' }, { id: 'settings' }];
  assert.equal(findScreen(screens, 'settings').id, 'settings');
  assert.equal(findScreen(screens, 'nope'), undefined);
  assert.equal(findScreen(undefined, 'home'), undefined);
});

test('computeClip insets the box by every crop side', () => {
  const box = { x: 100, y: 200, width: 400, height: 800 };
  const crop = { top: 47, right: 9, bottom: 33, left: 9 };
  assert.deepEqual(computeClip(box, crop), {
    x: 109,          // 100 + 9
    y: 247,          // 200 + 47
    width: 382,      // 400 - 9 - 9
    height: 720,     // 800 - 47 - 33
  });
});

test('computeClip with no crop is the identity box', () => {
  const box = { x: 5, y: 6, width: 10, height: 20 };
  assert.deepEqual(computeClip(box, undefined), { x: 5, y: 6, width: 10, height: 20 });
  assert.deepEqual(computeClip(box, {}), { x: 5, y: 6, width: 10, height: 20 });
});

test('computeClip treats missing individual sides as zero', () => {
  const box = { x: 0, y: 0, width: 100, height: 100 };
  // only a top inset — the other three default to 0
  assert.deepEqual(computeClip(box, { top: 20 }), { x: 0, y: 20, width: 100, height: 80 });
});

test('computeClip throws a named error when the box is null', () => {
  assert.throws(() => computeClip(null, {}), /no bounding box/);
});

test('computeClip throws when crop insets exceed the box', () => {
  const box = { x: 0, y: 0, width: 20, height: 20 };
  assert.throws(() => computeClip(box, { left: 15, right: 15 }), /crop insets exceed/);
});
