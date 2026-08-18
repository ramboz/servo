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
 */
export function computeClip(box, crop) {
  const c = crop || {};
  const left = c.left || 0;
  const top = c.top || 0;
  const right = c.right || 0;
  const bottom = c.bottom || 0;
  return {
    x: box.x + left,
    y: box.y + top,
    width: box.width - left - right,
    height: box.height - top - bottom,
  };
}
