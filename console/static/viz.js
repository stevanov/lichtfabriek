/* Lichtfabriek visualizer math — the JS mirror of kubusd/engine.py (V23).
 *
 * SINGLE SOURCE for the browser-side primitive math: the step editor's live
 * preview and the node-based parity test (tests/test_visualizer_parity.py)
 * both use this file, so the preview shows exactly what the Pi renders.
 *
 * Semantics (SPEC §C): `speed` is a uniform multiplier (1.0 = normal pace);
 * `offset` is a phase shift as a FRACTION of one animation cycle; the
 * strobe-family flash rate is capped < 3 Hz (V14); seeded primitives use the
 * same LCG as engine.py's _LCG class.
 */

const MAX_STROBE_HZ_JS = 1 / 3.0;
function rate(speed, base) { return base * Math.max(speed, 0.01); }
function periodOf(base, speed) { return Math.max(MAX_STROBE_HZ_JS, base / Math.max(speed, 0.01)); }
function strobeBase(t, base, speed) {
  const period = periodOf(base, speed); // < 3 Hz cap (V14)
  return (t % period) / period;
}
// `offset` is a fraction of one animation cycle (0..1)
const shift = (t, p, cycle) => t + (p.offset ?? 0) * cycle;
function hsv(h, s, v) {
  h = ((h % 1) + 1) % 1;
  const i = Math.floor(h * 6), f = h * 6 - i,
        p = v * (1 - s), q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
  return [[v,t,p],[q,v,p],[p,v,t],[p,q,v],[t,p,v],[v,p,q]][i % 6];
}
function bright(c, b) { return c.map(x => Math.min(1, Math.max(0, x * b))); }
function c01(c) { return [c[0]/255, c[1]/255, c[2]/255]; }

// same LCG as engine.py _LCG: x = (x*9301+49297) % 233280
function lcg(seed) {
  let x = (Math.floor(seed) * 9301 + 49297) % 233280;
  return () => { x = (x * 9301 + 49297) % 233280; return x / 233280.0; };
}

// ---- primitives: (t, params) -> [r,g,b] 0..1 ----
const PRIMS = {
  rainbow: (t,p) => { const c=1/rate(p.speed??1,0.5); const [r,g,b]=hsv(shift(t,p,c)*rate(p.speed??1,0.5)%1,1,1); return bright([r,g,b], p.brightness??1); },
  huesweep: (t,p) => { const c=1/rate(p.speed??1,0.2); const [r,g,b]=hsv(shift(t,p,c)*rate(p.speed??1,0.2)%1,1,1); return bright([r,g,b], p.brightness??1); },
  pulse: (t,p) => {
    const cols = p.colors||[[255,0,0],[0,255,0],[0,0,255]];
    const per = periodOf(1.0, p.speed??1);
    const ts = shift(t,p, cols.length*per);  // offset: full palette cycle
    const col = cols[Math.floor(ts/Math.max(per,0.01)) % cols.length];
    const ph = strobeBase(ts, 1.0, p.speed??1), amp = 0.5+0.5*Math.sin(ph*2*Math.PI);
    return bright(c01(col).map(x=>x*amp), p.brightness??1);
  },
  fade: (t,p) => {
    const cols = p.colors||[[255,0,0],[0,255,0],[0,0,255]];
    const cyc = 0.5/Math.max(p.speed??1,0.01);   // smooth blend: no clamp
    const ts = shift(t,p,cyc), ph=(ts%cyc)/cyc;
    const n=cols.length;
    const i=Math.floor(ph*n)%n, j=(i+1)%n, f=(ph*n)-i;
    const a=c01(cols[i]), b=c01(cols[j]);
    return bright([a[0]*(1-f)+b[0]*f, a[1]*(1-f)+b[1]*f, a[2]*(1-f)+b[2]*f], p.brightness??1);
  },
  chase: (t,p) => {
    const cyc = periodOf(0.8,p.speed??1);
    const on = strobeBase(shift(t,p,cyc),0.8,p.speed??1)<0.5;  // 1 blink/period (V14)
    const c = c01((p.colors||[[255,255,255]])[0]);
    return bright(c.map(x=>on?x:0), p.brightness??1);
  },
  holiday: (t,p) => {
    const cyc = 2*periodOf(1.0, p.speed??1);
    const r = lcg(p.seed??0);
    const sparkle = 0.7 + 0.3*r();               // mirrors engine.py
    const ph = strobeBase(shift(t,p,cyc)*0.5, 1.0, p.speed??1);
    const warm = 0.5+0.5*Math.sin(ph*2*Math.PI);
    return bright([warm*sparkle, warm*0.9*sparkle, warm*0.4*sparkle], p.brightness??1);
  },
  random: (t,p) => {
    const cyc = 0.5/Math.max(p.speed??1,0.01);   // no strobe clamp (color jumps)
    const ts = t + ((p.offset??0)%1)*cyc;
    const r = lcg((p.seed??0) + Math.floor(ts/Math.max(cyc,0.01)));
    return bright([r(),r(),r()], p.brightness??1);
  },
  fire: (t,p) => {
    const cyc = 0.3/Math.max(p.speed??1,0.01);   // smooth flicker: no clamp
    const ts = t + ((p.offset??0)%1)*cyc;
    const r = lcg((p.seed??0) + Math.floor(ts/Math.max(cyc,0.01)*10));
    const f=0.6+0.4*r();
    return bright([f, f*0.35, f*0.05], p.brightness??1);
  },
  sparkle: (t,p) => {
    const cyc = periodOf(0.7, p.speed??1);   // flash-like: strobe-capped
    const ts = t + ((p.offset??0)%1)*cyc;
    const r = lcg((p.seed??0) + Math.floor(ts/Math.max(cyc,0.01)));
    const pal = (p.colors && p.colors.length>=2) ? p.colors
      : [[255,255,255],[255,0,0],[0,0,255],[255,255,0],[0,255,0]];
    const on = r()<0.2;
    const c = c01(pal[Math.floor(r()*pal.length)%pal.length]);
    return bright(c.map(v=>on?v:0), p.brightness??1);
  },
  sine: (t,p) => {
    const cols=(p.colors && p.colors.length>=2)?p.colors:[[255,0,0],[0,0,255]];
    const c=1/rate(p.speed??1,0.4);
    const m=0.5+0.5*Math.sin(shift(t,p,c)*rate(p.speed??1,0.4)*2*Math.PI);
    const a=c01(cols[0]), b=c01(cols[1]);
    return bright([a[0]*(1-m)+b[0]*m, a[1]*(1-m)+b[1]*m, a[2]*(1-m)+b[2]*m], p.brightness??1);
  },
  strobe: (t,p) => {
    const cyc = periodOf(1.0, p.speed??1);
    const on = strobeBase(shift(t,p,cyc), 1.0, p.speed??1)<0.5;
    const c = c01((p.colors||[[255,255,255]])[0]);
    return bright(c.map(x=>on?x:0), p.brightness??1);
  },
  police: (t,p) => {
    const cols=p.colors||[[255,0,0],[0,0,255]];
    const c = cols[Math.floor(strobeBase(shift(t,p,periodOf(0.6,p.speed??1)),0.6,p.speed??1)*2)%cols.length];
    return bright(c01(c), p.brightness??1);
  },
  knight: (t,p) => {
    const on = strobeBase(shift(t,p,periodOf(0.8,p.speed??1)),0.8,p.speed??1)<0.25;
    const c = c01((p.colors||[[255,255,255]])[0]);
    return bright(c.map(x=>on?x:0), p.brightness??1);
  },
  static: (t,p) => bright(c01((p.colors||[[255,255,255]])[0]), p.brightness??0.5),
  off: () => [0,0,0],
};

// node (parity test) export; in the browser the consts are script-global
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { PRIMS, rate, periodOf, strobeBase, shift, bright, c01, hsv, lcg };
}
