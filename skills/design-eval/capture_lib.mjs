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

// --------------------------------------------------------------------------- //
// Attestation channel (spec 026-03 / ADR-0031)
// --------------------------------------------------------------------------- //
// These live here, not in capture.mjs, because capture.mjs imports Playwright at
// module load and cannot be unit tested — so a guard written there would ship
// with a ticked checkbox and no coverage. Pure functions; the node suite tests
// them directly.

/** The namespaced sentinel. Parsed by marker, never positionally. */
export const ATTEST_MARKER = '##servo-capture:';

/**
 * Build the single attestation line. `engine` is null when identity could not be
 * attested; `error` then carries a short reason so "A5 false / no accessor" is
 * distinguishable from "the accessor threw".
 */
export function attestationLine({ engine = null, version = null, transport = 'bundled', error = null }) {
  return ATTEST_MARKER + JSON.stringify({ engine, version, transport, error });
}

/**
 * Call an engine-identity thunk and NEVER let its failure escape.
 *
 * The load-bearing guarantee (026-03 AC1b): capture.mjs has exactly one `try`
 * whose `catch` sets `process.exitCode = 2`, which `capture_app` maps to an
 * EnvError — so an accessor that throws would turn a SUCCESSFUL screenshot into
 * no score and no ledger row, making provenance load-bearing. This returns a
 * null-engine payload instead, and never touches process.exitCode.
 */
export function safeAttest(getVersion, transport = 'bundled') {
  try {
    const info = getVersion();
    if (!info || typeof info.version !== 'string' || !info.version) {
      return { engine: null, version: null, transport, error: 'no-accessor' };
    }
    return { engine: info.engine || 'chromium', version: info.version, transport, error: null };
  } catch (err) {
    return {
      engine: null,
      version: null,
      transport,
      error: `accessor-threw: ${(err && err.message) || err}`.slice(0, 120),
    };
  }
}

/** Extract the attestation from captured stdout: FIRST marker line, never _extract_json. */
export function parseAttestation(stdout) {
  for (const line of String(stdout || '').split('\n')) {
    const idx = line.indexOf(ATTEST_MARKER);
    if (idx === -1) continue;              // adopter's own logging — discarded, not a failure
    try {
      return JSON.parse(line.slice(idx + ATTEST_MARKER.length));
    } catch {
      return null;                          // malformed -> not_attested, never fatal
    }
  }
  return null;
}
