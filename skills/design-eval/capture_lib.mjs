// Pure, browser-free helpers for capture.mjs (servo design-eval).
//
// Extracted so the load-bearing geometry — chrome-crop clip math (spike
// finding #1) — and the CLI arg/screen resolution can be unit-tested with
// plain node, without launching Playwright. capture.mjs imports these; it owns
// all the browser side effects, this file owns none.

/** Read a `--flag <value>` pair from an argv slice; undefined if absent. */
export function parseFlag(argv, name) {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : undefined;
}

/** Resolve the capture viewport, falling back to the phone default. */
export function resolveViewport(config) {
  return (config && config.viewport) || { width: 392, height: 812, deviceScaleFactor: 2 };
}

/** Find a screen by id; undefined if the config has no such screen. */
export function findScreen(screens, id) {
  return (screens || []).find((s) => s.id === id);
}

/**
 * Inset an element's bounding box by the per-side crop, stripping device
 * chrome (bezel + status bar + home indicator) so a full-bleed PWA compares
 * fairly against a phone-framed mockup. Missing insets default to 0.
 *
 * Throws a named error rather than producing a garbage clip when the box is
 * absent (Playwright's `boundingBox()` returns null for an off-screen or
 * zero-area element) or when the crop insets exceed the box (a
 * negative-dimension clip crashes `page.screenshot` with a cryptic message far
 * from the real cause).
 */
export function computeClip(box, crop) {
  if (!box || typeof box.width !== 'number' || typeof box.height !== 'number') {
    throw new Error('computeClip: no bounding box (element off-screen or zero-area?)');
  }
  const c = crop || {};
  const left = c.left || 0;
  const top = c.top || 0;
  const right = c.right || 0;
  const bottom = c.bottom || 0;
  const width = box.width - left - right;
  const height = box.height - top - bottom;
  if (width <= 0 || height <= 0) {
    throw new Error(
      `computeClip: crop insets exceed the box (${box.width}x${box.height} → ${width}x${height})`,
    );
  }
  return { x: box.x + left, y: box.y + top, width, height };
}
