"use strict";
/* =================== NeuralFoil B: the new NeuralFoil ===================
   The bounded release built from the 2026 validation study. Same eight shipped
   NeuralFoil 0.3.3 networks, exact tensors; what is new is everything around
   them, each choice grounded in the study's measurements (wind-tunnel
   comparisons for the core selection; the atlas for the guard thresholds):

   1. The core prediction is the arithmetic mean of all eight model sizes.
      Chosen on 106 measured subcritical points: it ties the classic xlarge on
      Harris (15.05 vs 14.95 counts, point protocol), improves TN 1546 drag by
      21 percent (11.4 vs 14.4 counts), and slightly improves lift.
   2. Every force and moment coefficient carries its 8-network disagreement
      band (p10 to p90), a fabrication-free measured lower-bound indicator of
      error. It is shown as an
      indicator, never as statistical coverage: the study's registered conformal
      bound came out uninformative and no spread scale factor transfers across
      facilities, so no coverage guarantee is claimed.
   3. A verdict engine checks every query against the measured failure map
      (the 312,795-condition atlas plus more than 600 digitized measured
      points from four wind-tunnel reports) and says
      in words when a number should not be trusted, including the two measured
      confidence blindspots the classic score cannot see.
   4. Nothing else is changed. The five attempted transonic recalibrations and
      both lift-break repairs FAILED their held-out tests and are therefore not
      shipped. Honesty about that is the feature.

   This file needs the page globals of NeuralFoil Studio (index.html) and the
   weight binaries in nfweights/. All aerodynamic formulas mirror
   aerosandbox 4.2.10 KulfanAirfoil.get_aero_from_neuralfoil exactly; the port
   is self-tested on load against 40 Python reference runs (nfweights/ref.json).
   No em dash appears anywhere in this file by request of the site owner. */

(() => {
const SIZE_ORDER = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"];
const CT = 1e4; /* drag counts per unit CD */

/* ---------------------------------------------------------------- content */
const EVAL_NOTE = "Protocol: point-by-point mean absolute error on measured subcritical data, " +
  "Harris TM-81927 fig. 8 (NACA 0012, 14 measured points at M up to 0.55 spanning Re 3.0e6 to 9.0e6 with both fixed and free transition, " +
  "while every candidate's predictions were run identically at Re 3.0e6, fixed transition 0.05, n_crit 9, so the absolute level in that column " +
  "is dominated by condition mismatch and only the between-row comparison is meaningful), " +
  "TN 1546 drag (free transition, n_crit 6, Re(M), strictly below each point's critical Mach, M up to 0.50, 48 points), " +
  "TN 1546 lift (32 points) and Ferri WR-L143 lift (Re 3.8e5, 12 points). " +
  "Absolute levels include facility effects; the fair comparison is between rows. " +
  "The study's convention-matched plateau gates (1.3 and 0.5 counts on Harris) remain the absolute-accuracy reference.";
const EVAL_ROWS = [
  ["classic xlarge", 14.95, 14.41, 0.03, 0.10],
  ["mean of 8 (the new core)", 15.05, 11.38, 0.02, 0.08],
  ["median of 8", 15.12, 13.08, 0.03, 0.08],
  ["trimmed mean", 15.07, 12.12, 0.02, 0.09],
  ["confidence-weighted", 15.05, 11.38, 0.02, 0.08],
];
const REGISTRY = [
  ["Transonic drag-rise magnitude", "2 to 8x too shallow near onset, 1.4 to 4.4x too steep later, roughly 30x too steep deep",
   "Five closed forms plus similarity scaling all failed holdout or cross-validation",
   "Red no-trust zone above each airfoil's critical Mach, with the measured error sizes quoted; the failed refits are documented, not shipped"],
  ["Drag-divergence onset", "0.029 average Mach error on both holdout sets", "No fix needed: verified good; the attempted recalibration made it worse and was rejected",
   "Displayed with its verified accuracy of about 0.03 in Mach, and used as the guard boundary"],
  ["Low Reynolds number", "At Re 50,000, 94 percent of atlas conditions disagree by more than 20 counts", "Not repairable by post-processing",
   "Verdict turns red below Re 150,000 and cautions below 500,000"],
  ["High angle of attack", "Median 8-net disagreement 80 counts at 16 degrees", "Same",
   "Caution outside alpha -4 to +10, red beyond -8 to +14, hard red past 20 (post-stall analytic blend)"],
  ["Thickness extremes", "U-shaped disagreement, floor at 9 to 12 percent t/c", "Same",
   "Caution outside 6 to 15 percent, red past 21 percent"],
  ["Answers where XFOIL diverges", "12 percent of a stratified sample; disagreement 1.8x higher there", "Cannot be removed",
   "The disagreement band on every number flags exactly these regions"],
  ["Confidence never sees Mach", "Structural: cannot flag transonic error", "Unfixable without retraining",
   "The verdict engine checks Mach explicitly against each airfoil's own critical Mach"],
  ["Confidence blindspot", "7.4 percent of atlas conditions pair confidence above 0.90 with disagreement above 50 counts", "Mitigation only",
   "A dedicated guard fires on exactly that pairing and says to trust the disagreement, not the confidence"],
  ["Registered conformal bound", "567 counts, declared uninformative", "No fix with current data",
   "No fake guarantees: bands are labeled a measured lower-bound indicator, never coverage"],
  ["Lift-break timing", "Model cuts lift 19 to 32 percent where measurement still rises 19 to 23 percent", "Two one-parameter repairs failed validation",
   "CL flagged above drag-divergence Mach + 0.04 with the measured mismatch quoted"],
  ["Subcritical lift level at low Re", "CL error up to 0.143 at Re 0.38e6, alpha +2", "Core-model error, unreachable from any layer",
   "Covered by the low-Reynolds verdict"],
  ["Lift thickness bias", "Signed +0.03 to +0.07 on thick 16-series sections", "Same physics as the thickness U", "Covered by the thickness verdict"],
  ["Geometry-input noise floor", "Median 0.4, worst 11.1 counts at scan-level coordinate noise", "User-side",
   "Loaded-coordinate airfoils get an advisory: smooth or refit before trusting fine differences"],
  ["Moment coefficient uncertainty", "p90 spread across sizes is about 18 percent of a typical cambered CM", "Never scored against experiment (out of scope)",
   "CM always carries its spread and an unvalidated-against-experiment note"],
  ["Positive audits", "0 impossible outputs in 2,160 conditions; smoothness kinks at most 0.09 counts; transition handling clean; subsonic gates 1.3 and 0.5 counts",
   "No fix needed", "The unchanged core carries these clean bills over verbatim"],
];
const STUDY_LINKS = [
  ["study/data/research-answer.md", "The answer to the research question, parts 1 to 9, with the complete inaccuracy registry"],
  ["study/data/master-dataset.csv", "Every Harris and Ferri experimental point with provenance and uncertainty"],
  ["study/data/everything-we-did.md", "The full study log"],
  ["study/docs/protocol-deviations.md", "Pre-registration deviations and amendments"],
];

/* ------------------------------------------------------------- weights IO */
let NETS = null, DMEAN = null, DICOV = null, REF = null;
let loadPromise = null, loadState = "idle", loadMsg = "";
function nfbLoad() {
  if (loadPromise) return loadPromise;
  loadState = "loading";
  loadPromise = (async () => {
    const man = await (await fetch("nfweights/manifest.json")).json();
    const names = SIZE_ORDER.map(s => "nn-" + s).concat(["scaled_input_distribution"]);
    const bufs = {};
    let got = 0;
    await Promise.all(names.map(async n => {
      const r = await fetch("nfweights/" + man[n].file);
      if (!r.ok) throw new Error("fetch failed: " + man[n].file);
      bufs[n] = new Float32Array(await r.arrayBuffer());
      got++; loadMsg = "loading the eight networks: " + got + "/" + names.length;
      nfbStatus();
    }));
    const tens = (n, want) => {
      const t = man[n].tensors.find(x => x.name === want);
      const len = t.shape.reduce((a, b) => a * b, 1);
      return bufs[n].subarray(t.offset, t.offset + len);
    };
    NETS = {};
    for (const s of SIZE_ORDER) {
      const n = "nn-" + s, ts = man[n].tensors;
      const idx = [...new Set(ts.map(t => +t.name.split(".")[1]))].sort((a, b) => a - b);
      NETS[s] = idx.map(i => {
        const w = ts.find(t => t.name === "net." + i + ".weight");
        return { rows: w.shape[0], cols: w.shape[1],
                 w: tens(n, "net." + i + ".weight"), b: tens(n, "net." + i + ".bias") };
      });
    }
    DMEAN = tens("scaled_input_distribution", "mean_inputs_scaled");
    DICOV = tens("scaled_input_distribution", "inv_cov_inputs_scaled");
    try { REF = await (await fetch("nfweights/ref.json")).json(); } catch (e) { REF = null; }
    loadState = "ready";
    loadMsg = selfTest();
    nfbCache = {}; sweepCache = {};
    nfbStatus();
    if (state.tab === "nfb" || state.tab === "vs") renderAll();
  })();
  loadPromise.catch(e => { loadState = "error"; loadMsg = "network load failed: " + e.message + " (revisit the tab to retry)"; loadPromise = null; nfbStatus(); });
  return loadPromise;
}

/* ------------------------------------------------ per-network evaluation */
function netEval(layers, x) {
  let v = x;
  for (let L = 0; L < layers.length; L++) {
    const lay = layers[L], rows = lay.rows, cols = lay.cols, w = lay.w, b = lay.b;
    const out = new Float64Array(rows);
    for (let r = 0; r < rows; r++) {
      let s = b[r];
      const off = r * cols;
      for (let c = 0; c < cols; c++) s += w[off + c] * v[c];
      out[r] = L < layers.length - 1 ? s / (1 + Math.exp(-s)) : s;
    }
    v = out;
  }
  return v;
}
function mahal(x) {
  let s = 0;
  for (let i = 0; i < 25; i++) {
    const di = x[i] - DMEAN[i];
    let t = 0;
    for (let j = 0; j < 25; j++) t += DICOV[i * 25 + j] * (x[j] - DMEAN[j]);
    s += di * t;
  }
  return s;
}
/* raw net outputs with flipped-evaluation symmetry averaging; mirrors
   neuralfoil.get_aero_from_kulfan_parameters and the page's verified port */
function rawN(layers, kp, alphaDeg, Re, nCrit, xtrU, xtrL) {
  const x = new Float64Array(25);
  for (let i = 0; i < 8; i++) x[i] = kp.upper[i];
  for (let i = 0; i < 8; i++) x[8 + i] = kp.lower[i];
  x[16] = kp.le; x[17] = kp.te * 50;
  x[18] = Math.sin(2 * alphaDeg * NFD2R);
  x[19] = Math.cos(alphaDeg * NFD2R);
  x[20] = 1 - x[19] * x[19];
  x[21] = (Math.log(Re) - 12.5) / 3.5;
  x[22] = (nCrit - 9) / 4.5;
  x[23] = xtrU; x[24] = xtrL;
  const y = netEval(layers, x);
  y[0] -= mahal(x) / 50;
  const xf = new Float64Array(25);
  for (let i = 0; i < 8; i++) { xf[i] = -x[8 + i]; xf[8 + i] = -x[i]; }
  xf[16] = -x[16]; xf[17] = x[17];
  xf[18] = -x[18]; xf[19] = x[19]; xf[20] = x[20]; xf[21] = x[21]; xf[22] = x[22];
  xf[23] = x[24]; xf[24] = x[23];
  const yf = netEval(layers, xf);
  yf[0] -= mahal(xf) / 50;
  const yu = Float64Array.from(yf);
  yu[1] = -yf[1]; yu[3] = -yf[3];
  yu[4] = yf[5]; yu[5] = yf[4];
  const NB = 32;
  for (let k = 0; k < 2 * NB; k++) { yu[6 + k] = yf[6 + 3 * NB + k]; yu[6 + 3 * NB + k] = yf[6 + k]; }
  for (let k = 0; k < NB; k++) { yu[6 + 2 * NB + k] = -yf[6 + 5 * NB + k]; yu[6 + 5 * NB + k] = -yf[6 + 2 * NB + k]; }
  const g = new Float64Array(198);
  for (let k = 0; k < 198; k++) g[k] = (y[k] + yu[k]) / 2;
  g[0] = 1 / (1 + Math.exp(-Math.max(-700, Math.min(700, g[0]))));
  g[4] = Math.min(1, Math.max(0, g[4]));
  g[5] = Math.min(1, Math.max(0, g[5]));
  const ueU = new Float64Array(NB), ueL = new Float64Array(NB);
  for (let k = 0; k < NB; k++) { ueU[k] = g[6 + 2 * NB + k]; ueL[k] = g[6 + 5 * NB + k]; }
  return { conf: g[0], CL: g[1] / 2, CD: Math.exp((g[2] - 2) * 2), CM: g[3] / 20,
           TopXtr: g[4], BotXtr: g[5], ueU, ueL };
}
/* incompressible section state: post-stall blend applied, Mach not yet */
function sectionRaw(layers, kp, alphaDeg, Re, nCrit, xtrU, xtrL) {
  const al = ((alphaDeg + 180) % 360 + 360) % 360 - 180;
  const r = rawN(layers, kp, al, Re, nCrit, xtrU, xtrL);
  const sina = Math.sin(al * NFD2R), cosa = Math.cos(al * NFD2R);
  const Cd90 = 2.08 + 8.36e-2 * cosa + 4.06e-1 * cosa * cosa;
  const CN = Cd90 * sina;
  const CTf = (9.00e-2 - 1.78e-1 * cosa - 2.98e-1 * Math.pow(cosa, 3)) * sina * sina;
  const CLsep = CN * cosa + CTf * sina;
  const CDsep = CN * sina - CTf * cosa;
  const isSep = nfSoftmaxN([al - 20, -20 - al], 1) / 3;
  const w = 0.5 + 0.5 * Math.tanh(isSep);
  const CL0 = CLsep * w + r.CL * (1 - w);
  const CD0 = Math.exp(Math.log(CDsep + 0.074 / Math.pow(Re, 0.2)) * w + Math.log(r.CD) * (1 - w));
  const CM0 = 0 * w + r.CM * (1 - w);
  const TopXtr = (0.5 - 0.5 * Math.tanh(10 * sina)) * w + r.TopXtr * (1 - w);
  const BotXtr = (0.5 + 0.5 * Math.tanh(10 * sina)) * w + r.BotXtr * (1 - w);
  const cps = [];
  for (let k = 0; k < 32; k++) { cps.push(1 - r.ueU[k] * r.ueU[k]); cps.push(1 - r.ueL[k] * r.ueL[k]); }
  let Cpmin0 = nfSoftminN(cps, 0.01);
  Cpmin0 = nfBlend(isSep, -1 - 0.5 * sina * sina, Cpmin0);
  Cpmin0 = nfSoftminN([Cpmin0, 0], 0.001);
  const machCrit = Math.pow(1.011571026701678 - Cpmin0
    + 0.6582431351007195 * Math.pow(-Cpmin0, 0.6724789439840343), -0.5504677038358711);
  const machDD = machCrit + Math.pow(0.1 / 320, 1 / 3);
  return { conf: r.conf, CL0, CD0, CM0, TopXtr, BotXtr, Cpmin0, machCrit, machDD, sina, cosa, isSep };
}
/* the exact compressibility chain, steps 2 to 5 of the shipped code */
function machChain(s, mach, tOverC) {
  const b2 = 1 - mach * mach;
  const beta = Math.sqrt(nfSoftmaxN([b2, -b2], 0.5));
  let CL = s.CL0 / beta;
  let CM = s.CM0 / beta;
  const Cpmin = s.Cpmin0 / beta;
  const buffet = nfBlend(50 * (mach - (s.machDD + 0.04)), nfBlend((mach - 1) / 0.1, 1, 0.5), 1);
  const cla = nfBlend((mach - 1) / 0.1, 4 / (2 * Math.PI), 1);
  CL = CL * buffet * cla;
  let CDw = 0;
  if (mach >= s.machCrit) {
    if (mach < s.machDD) CDw = 80 * Math.pow(mach - s.machCrit, 4);
    else if (mach < 1.1) {
      const xa = s.machDD, xb = 1.1;
      const fa = 80 * Math.pow(0.1 / 320, 4 / 3), fb = 0.8 * tOverC;
      const dfa = 0.1, dfb = -0.8 * tOverC * 8;
      const t = (mach - xa) / (xb - xa);
      const bb = 0.5 + 0.5 * Math.cos(Math.PI * t);
      CDw = bb * ((mach - xa) * dfa + fa) + (1 - bb) * ((mach - xb) * dfb + fb);
    } else CDw = nfBlend(8 * 2 * (mach - 1.1) / (1.2 - 0.8), 0.8 * 0.8 * tOverC, 1.2 * 0.8 * tOverC);
  }
  const CD = s.CD0 + CDw;
  const shift = nfSoftmaxN([s.isSep, (mach - (s.machDD + 0.06)) / 0.06], 0.1);
  CM = CM + nfBlend(shift, -0.25 * s.cosa * CL - 0.25 * s.sina * CD, 0);
  return { CL, CD, CM, Cpmin, CDwave: CDw };
}

/* ------------------------------------------------------------- ensemble */
function pctl(sorted, q) {
  const h = (sorted.length - 1) * q, lo = Math.floor(h);
  return lo + 1 < sorted.length ? sorted[lo] + (sorted[lo + 1] - sorted[lo]) * (h - lo) : sorted[lo];
}
function agg(vals) {
  const v = vals.slice().sort((a, b) => a - b);
  return { mean: vals.reduce((a, b) => a + b, 0) / vals.length,
           lo: pctl(v, 0.10), hi: pctl(v, 0.90) };
}
let nfbCache = {}, sweepCache = {};
function fitFor() {
  const k = FOIL.file;
  if (!fitFor.c) fitFor.c = {};
  if (!fitFor.c[k]) fitFor.c[k] = nfFitKulfan(FOIL.pts);
  return fitFor.c[k];
}
function tcFor() { return stats2For(FOIL).t / 100; }
/* full 8-net evaluation of one condition in the user frame */
function ensemblePoint(alpha, Re, mach) {
  const fit = fitFor();
  const key = [FOIL.file, alpha, Re, mach, state.ncrit, state.xtrU, state.xtrL].join("|");
  if (nfbCache[key]) return nfbCache[key];
  const tc = tcFor();
  const per = {};
  for (const s of SIZE_ORDER) {
    const sr = sectionRaw(NETS[s], fit.kp, alpha + fit.dAlpha, Re / fit.scale, state.ncrit, state.xtrU, state.xtrL);
    const m = machChain(sr, mach, tc);
    per[s] = { CL: m.CL, CD: m.CD, CM: m.CM + (-m.CL * fit.xqc + m.CD * fit.yqc),
               conf: sr.conf, TopXtr: sr.TopXtr, BotXtr: sr.BotXtr,
               machCrit: sr.machCrit, machDD: sr.machDD, Cpmin: m.Cpmin };
  }
  const out = { per, tc };
  for (const k of ["CL", "CD", "CM", "conf", "TopXtr", "BotXtr", "machCrit", "machDD", "Cpmin"])
    out[k] = agg(SIZE_ORDER.map(s => per[s][k]));
  out.classic = per.xlarge;
  const keys = Object.keys(nfbCache);
  if (keys.length > 60) delete nfbCache[keys[0]];
  nfbCache[key] = out;
  return out;
}

/* --------------------------------------------------------- verdict engine */
const LVL = { 0: "in the validated envelope", 1: "reduced trust", 2: "do not trust" };
function verdicts(alpha, Re, mach, out) {
  const f = [];
  const spread = (out.CD.hi - out.CD.lo) * CT;
  const mc = out.machCrit.mean, mdd = out.machDD.mean, tc = out.tc, cf = out.conf.mean;
  const add = (coef, lvl, why) => f.push({ coef, lvl, why });
  if (Re < 1.5e5) add("all", 2, "Low-Reynolds regime. At Re 50,000, 94 percent of the 312,795-condition atlas shows 8-net disagreement above 20 counts, falling monotonically as Re rises; the measured trust map bottoms out here.");
  else if (Re < 5e5) add("all", 1, "Below Re 500,000 the atlas shows elevated disagreement. The validated tight-agreement zone starts near Re 200,000 and only inside the benign alpha band.");
  if (Math.abs(alpha) > 20) add("all", 2, "Post-stall region: the analytic 360-degree blend takes over here and the study holds no validation data for it.");
  else if (alpha < -8 || alpha > 14) add("all", 2, "Far from the atlas alpha floor: median 8-net disagreement reaches 80 counts by 16 degrees.");
  else if (alpha < -4 || alpha > 10) add("all", 1, "Outside the atlas alpha comfort band (best agreement at 1 to 3 degrees).");
  if (tc > 0.21) add("all", 2, "Very thick section, far outside the atlas thickness U (floor at 9 to 12 percent t/c).");
  else if (tc < 0.06 || tc > 0.15) add("all", 1, "Thickness away from the atlas U floor at 9 to 12 percent t/c.");
  if (mach > 0.94) add("all", 2, "Beyond the highest experimentally compared Mach in the study (0.94)" + (mach > 1 ? "; the supersonic side is an analytic patch with no experimental comparison at all" : "") + ".");
  if (mach >= mc) add("CD", 2, "Above this airfoil's critical Mach. Measured drag-rise magnitude errors run 2 to 8x near onset and the shipped shape is orders of magnitude too steep by M 0.90. All five recalibration attempts failed their held-out tests, so this zone is displayed, never trusted.");
  else if (mach >= mc - 0.03) add("CD", 1, "Inside the drag-rise onset window. The onset location itself is verified to about 0.03 in Mach on holdout data; the magnitude beyond it is not.");
  if (mach >= mdd + 0.04) add("CL", 2, "The lift-break factor engages here, tied to drag divergence. Measurement shows the two decouple: lift was still rising 19 to 23 percent where the model already cuts 19 to 32 percent. Both one-parameter repairs failed validation.");
  if (cf < 0.3) add("all", 2, "NeuralFoil's own analysis confidence is very low here.");
  else if (cf < 0.6) add("all", 1, "NeuralFoil's own analysis confidence is low here.");
  if (cf > 0.9 && spread > 50) add("all", 1, "The measured confidence blindspot: 7.4 percent of atlas conditions pair confidence above 0.90 with disagreement above 50 counts, concentrated at thick sections, low Reynolds and high alpha. Trust the disagreement, not the confidence.");
  if (spread > 50) add("CD", 2, "8-net disagreement above 50 counts. Ensemble spread is a fabrication-free measured lower-bound indicator of true error.");
  else if (spread > 20) add("CD", 1, "8-net disagreement above 20 counts, a measured lower-bound indicator of true error.");
  const worst = coef => f.filter(x => x.coef === "all" || x.coef === coef)
    .reduce((m, x) => Math.max(m, x.lvl), 0);
  return { fired: f, CL: worst("CL"), CD: worst("CD"), CM: worst("CM"),
           overall: f.reduce((m, x) => Math.max(m, x.lvl), 0), spread };
}

/* ------------------------------------------------------------- self test */
function selfTest() {
  if (!REF) return "networks loaded; reference file missing, port self-test skipped";
  let dCL = 0, dCD = 0, dCM = 0, dMC = 0, n = 0;
  REF.conds.forEach((c, i) => {
    for (const s of SIZE_ORDER) {
      const sr = sectionRaw(NETS[s], REF.kp, c.alpha, c.Re, c.n_crit, c.xtr_upper, c.xtr_lower);
      const m = machChain(sr, c.mach, REF.t_over_c);
      const r = REF.results[i][s];
      dCL = Math.max(dCL, Math.abs(m.CL - r.CL));
      dCD = Math.max(dCD, Math.abs(m.CD - r.CD));
      dCM = Math.max(dCM, Math.abs(m.CM - r.CM));
      dMC = Math.max(dMC, Math.abs(sr.machCrit - r.mach_crit));
      n++;
    }
  });
  const ok = dCD * CT < 0.5 && dCL < 5e-3 && dMC < 5e-3;
  return (ok ? "port verified: " : "PORT CHECK FAILED: ") + n + " reference runs vs Python, worst |dCL| " +
    dCL.toExponential(1) + ", |dCD| " + (dCD * CT).toFixed(3) + " counts, |dCM| " + dCM.toExponential(1) +
    ", |d mach_crit| " + dMC.toExponential(1);
}

/* ---------------------------------------------------------------- charts */
function themeC() {
  return { ink: cssVar("--ink") || "#222", muted: cssVar("--muted") || "#777",
           line: cssVar("--line") || "#ccc", good: cssVar("--good") || "#1baf7a",
           warn: cssVar("--warn") || "#b1741f", bad: cssVar("--bad") || "#d63a3a",
           acc: cssVar("--cand") || "#2a78d6" };
}
function drawChart(cv, spec) {
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth || 460, H = designH(cv, 240);
  cv.width = W * dpr; cv.height = H * dpr;
  cv.style.height = H + "px";
  const g = cv.getContext("2d");
  g.scale(dpr, dpr);
  const C = themeC();
  const ml = 46, mr = 10, mt = 18, mb = 30;
  const px = x => ml + (x - spec.x0) / (spec.x1 - spec.x0) * (W - ml - mr);
  const py = y => H - mb - (y - spec.y0) / (spec.y1 - spec.y0) * (H - mt - mb);
  g.clearRect(0, 0, W, H);
  (spec.regions || []).forEach(r => {
    g.fillStyle = r.color;
    const a = Math.max(spec.x0, r.from), b = Math.min(spec.x1, r.to);
    if (b > a) g.fillRect(px(a), mt, px(b) - px(a), H - mt - mb);
  });
  g.strokeStyle = C.line; g.fillStyle = C.muted; g.font = "11px system-ui,sans-serif"; g.lineWidth = 1;
  g.strokeRect(ml, mt, W - ml - mr, H - mt - mb);
  const xt = spec.xticks || 5, yt = spec.yticks || 4;
  for (let i = 0; i <= xt; i++) {
    const x = spec.x0 + (spec.x1 - spec.x0) * i / xt;
    g.textAlign = "center";
    g.fillText((spec.xfmt || (v => v.toFixed(1)))(x), px(x), H - mb + 14);
  }
  for (let i = 0; i <= yt; i++) {
    const y = spec.y0 + (spec.y1 - spec.y0) * i / yt;
    g.textAlign = "right";
    g.fillText((spec.yfmt || (v => v.toFixed(2)))(y), ml - 5, py(y) + 4);
    g.strokeStyle = C.line; g.globalAlpha = 0.4;
    g.beginPath(); g.moveTo(ml, py(y)); g.lineTo(W - mr, py(y)); g.stroke();
    g.globalAlpha = 1;
  }
  if (spec.band) {
    g.fillStyle = spec.bandColor || C.acc; g.globalAlpha = 0.18;
    g.beginPath();
    spec.band.forEach((p, i) => { const yy = Math.max(spec.y0, Math.min(spec.y1, p[1])); i ? g.lineTo(px(p[0]), py(yy)) : g.moveTo(px(p[0]), py(yy)); });
    for (let i = spec.band.length - 1; i >= 0; i--) { const p = spec.band[i]; const yy = Math.max(spec.y0, Math.min(spec.y1, p[2])); g.lineTo(px(p[0]), py(yy)); }
    g.closePath(); g.fill(); g.globalAlpha = 1;
  }
  (spec.series || []).forEach(sr => {
    g.strokeStyle = sr.color; g.lineWidth = sr.width || 1.8;
    g.setLineDash(sr.dash || []);
    g.beginPath();
    let started = false;
    sr.pts.forEach(p => {
      if (p[1] < spec.y0 - (spec.y1 - spec.y0) || p[1] > spec.y1 + (spec.y1 - spec.y0)) { started = false; return; }
      const yy = Math.max(spec.y0, Math.min(spec.y1, p[1]));
      started ? g.lineTo(px(p[0]), py(yy)) : g.moveTo(px(p[0]), py(yy));
      started = true;
    });
    g.stroke(); g.setLineDash([]);
  });
  (spec.vlines || []).forEach(v => {
    if (v.x < spec.x0 || v.x > spec.x1) return;
    g.strokeStyle = v.color; g.setLineDash([4, 3]); g.lineWidth = 1;
    g.beginPath(); g.moveTo(px(v.x), mt); g.lineTo(px(v.x), H - mb); g.stroke();
    g.setLineDash([]);
    g.fillStyle = v.color; g.textAlign = "left"; g.fillText(v.label, px(v.x) + 3, mt + 11);
  });
  (spec.markers || []).forEach(m => {
    g.fillStyle = m.color;
    g.beginPath(); g.arc(px(m.x), py(Math.max(spec.y0, Math.min(spec.y1, m.y))), 3.5, 0, 7); g.fill();
  });
  g.fillStyle = C.ink; g.textAlign = "left"; g.font = "600 12px system-ui,sans-serif";
  g.fillText(spec.title, ml, 12);
  g.fillStyle = C.muted; g.font = "11px system-ui,sans-serif"; g.textAlign = "center";
  g.fillText(spec.xlabel, ml + (W - ml - mr) / 2, H - 4);
}

/* --------------------------------------------------------------- UI state */
const nfbUI = { alpha: 3, re: 1e6, mach: 0.3 };
let sweepToken = 0;

function chip(lvl) {
  const C = themeC();
  const col = lvl === 0 ? C.good : lvl === 1 ? C.warn : C.bad;
  return '<span style="display:inline-block;padding:2px 9px;border-radius:99px;border:1px solid ' + col +
    ';color:' + col + ';font-size:11.5px;font-weight:600">' + LVL[lvl] + "</span>";
}
function fmtBand(a, f) { return f(a.lo) + " to " + f(a.hi); }

function nfbStatus() {
  const el = $("nfbStatus");
  if (el) el.textContent = loadState === "ready" ? loadMsg :
    loadState === "loading" ? (loadMsg || "loading the eight networks (7.7 MB, one time)...") :
    loadState === "error" ? loadMsg : "";
  const el2 = $("vsStatus");
  if (el2) el2.textContent = el ? el.textContent : "";
}

function renderNFB() {
  nfbStatus();
  if (loadState !== "ready") { nfbLoad(); return; }
  const a = nfbUI.alpha, Re = nfbUI.re, M = nfbUI.mach;
  const out = ensemblePoint(a, Re, M);
  const v = verdicts(a, Re, M, out);
  const C = themeC();
  $("nfbFoil").textContent = FOIL.name + "  (t/c " + (out.tc * 100).toFixed(1) + " percent)";
  const f3 = x => x.toFixed(3), f4 = x => x.toFixed(4);
  const card = (name, sym, ag, lvl, cls, extra) =>
    '<div class="card" style="flex:1;min-width:210px"><div style="display:flex;justify-content:space-between;align-items:center">' +
    "<b>" + name + "</b>" + chip(lvl) + "</div>" +
    '<div style="font-size:26px;font-weight:700;margin:4px 0 0">' + sym + "</div>" +
    '<div style="color:var(--muted);font-size:12.5px">8-net band: ' + cls + "</div>" +
    '<div style="color:var(--muted);font-size:12.5px">classic xlarge: ' + extra + "</div></div>";
  $("nfbCards").innerHTML =
    card("Lift", f3(out.CL.mean), out.CL, v.CL, fmtBand(out.CL, f3), f3(out.classic.CL)) +
    card("Drag", f4(out.CD.mean) + ' <span style="font-size:13px;color:var(--muted)">(' + (out.CD.mean * CT).toFixed(1) + " counts)</span>",
         out.CD, v.CD, fmtBand(out.CD, f4) + " (" + v.spread.toFixed(1) + " counts wide)", f4(out.classic.CD)) +
    card("Moment", f4(out.CM.mean), out.CM, v.CM, fmtBand(out.CM, f4), f4(out.classic.CM)) +
    '<div class="card" style="flex:1;min-width:210px"><b>Mach map</b>' +
    '<div style="font-size:13.5px;margin-top:4px">critical Mach <b>' + f3(out.machCrit.mean) + "</b> (band " + fmtBand(out.machCrit, f3) + ")<br>" +
    "drag divergence <b>" + f3(out.machDD.mean) + "</b> (band " + fmtBand(out.machDD, f3) + ")<br>" +
    'onset verified to about 0.03 in Mach on holdout data; the magnitude above it is a measured no-trust zone</div></div>' +
    '<div class="card" style="flex:1;min-width:210px"><b>State</b>' +
    '<div style="font-size:13.5px;margin-top:4px">confidence (mean of 8): <b>' + out.conf.mean.toFixed(2) + "</b> (band " + fmtBand(out.conf, x => x.toFixed(2)) + ")<br>" +
    "transition top " + out.TopXtr.mean.toFixed(2) + " / bottom " + out.BotXtr.mean.toFixed(2) + "<br>" +
    "Cpmin " + out.Cpmin.mean.toFixed(2) + "</div></div>";
  const geomNote = FOIL.file && FOIL.file.indexOf("user-") === 0 ?
    '<div style="margin-top:6px;color:var(--warn)">Loaded coordinates: digitized geometry carries a measured noise floor of median 0.4 and worst 11 counts. Smooth or refit before trusting fine differences.</div>' : "";
  $("nfbWhy").innerHTML = "<b>Why these verdicts</b>" + (v.fired.length === 0 ?
    '<div style="margin-top:6px;color:var(--good)">No trust rule fired. This condition sits inside the envelope where the study found its best agreement with experiment (down to one or two counts under convention-matched conditions).</div>' :
    '<ul style="margin:6px 0 0;padding-left:18px">' + v.fired.map(x =>
      '<li style="margin:4px 0"><span style="color:' + (x.lvl === 2 ? C.bad : C.warn) + ';font-weight:600">' +
      (x.coef === "all" ? "all outputs" : x.coef) + "</span>: " + x.why + "</li>").join("") + "</ul>") +
    '<div style="margin-top:6px;color:var(--muted);font-size:12.5px">CM note: the p90 moment spread across sizes is about 18 percent of a typical cambered CM, and CM was never scored against experiment in the study.</div>' + geomNote;
  scheduleSweep();
}
function scheduleSweep() {
  const token = ++sweepToken;
  const key = [FOIL.file, nfbUI.re, nfbUI.mach, state.ncrit, state.xtrU, state.xtrL].join("|");
  if (sweepCache[key]) { drawAlphaCharts(sweepCache[key]); return; }
  const alphas = []; for (let x = -10; x <= 20.01; x += 1) alphas.push(x);
  const rows = [];
  const step = i => {
    if (token !== sweepToken) return;
    if (i >= alphas.length) {
      sweepCache[key] = rows;
      const kk = Object.keys(sweepCache);
      if (kk.length > 12) delete sweepCache[kk[0]];
      drawAlphaCharts(rows); return;
    }
    rows.push([alphas[i], ensemblePoint(alphas[i], nfbUI.re, nfbUI.mach)]);
    setTimeout(() => step(i + 1), 0);
  };
  step(0);
}
function drawAlphaCharts(rows) {
  const C = themeC();
  const cl = rows.map(r => [r[0], r[1].CL.mean]), clb = rows.map(r => [r[0], r[1].CL.lo, r[1].CL.hi]);
  const clc = rows.map(r => [r[0], r[1].classic.CL]);
  const cd = rows.map(r => [r[0], r[1].CD.mean * CT]), cdb = rows.map(r => [r[0], r[1].CD.lo * CT, r[1].CD.hi * CT]);
  const cdc = rows.map(r => [r[0], r[1].classic.CD * CT]);
  const cur = ensemblePoint(nfbUI.alpha, nfbUI.re, nfbUI.mach);
  drawChart($("nfbClA"), { title: "CL vs alpha, band = 8-net disagreement", xlabel: "alpha, degrees",
    x0: -10, x1: 20, y0: Math.min(...clb.map(p => p[1])) - 0.1, y1: Math.max(...clb.map(p => p[2])) + 0.1,
    xfmt: v => v.toFixed(0), band: clb, bandColor: C.acc,
    series: [{ pts: clc, color: C.muted, dash: [5, 4], width: 1.2 }, { pts: cl, color: C.acc }],
    markers: [{ x: nfbUI.alpha, y: cur.CL.mean, color: C.ink }] });
  const cdmax = Math.min(Math.max(...cdb.map(p => p[2])) + 20, 1500);
  drawChart($("nfbCdA"), { title: "CD vs alpha, drag counts", xlabel: "alpha, degrees",
    x0: -10, x1: 20, y0: 0, y1: cdmax, xfmt: v => v.toFixed(0), yfmt: v => v.toFixed(0),
    band: cdb, bandColor: C.acc,
    series: [{ pts: cdc, color: C.muted, dash: [5, 4], width: 1.2 }, { pts: cd, color: C.acc }],
    markers: [{ x: nfbUI.alpha, y: cur.CD.mean * CT, color: C.ink }] });
}

function renderVS() {
  nfbStatus();
  if (loadState !== "ready") { nfbLoad(); return; }
  const C = themeC();
  const a = nfbUI.alpha, Re = nfbUI.re;
  $("vsCond").textContent = FOIL.name + " at alpha " + a.toFixed(1) + " degrees, Re " +
    (Re >= 1e6 ? (Re / 1e6).toFixed(1) + "M" : (Re / 1e3).toFixed(0) + "k") +
    " (set on the New NeuralFoil tab), n_crit " + state.ncrit;
  const fit = fitFor(), tc = tcFor();
  const per = {};
  for (const s of SIZE_ORDER)
    per[s] = sectionRaw(NETS[s], fit.kp, a + fit.dAlpha, Re / fit.scale, state.ncrit, state.xtrU, state.xtrL);
  const machs = []; for (let m = 0.30; m <= 1.051; m += 0.01) machs.push(+m.toFixed(3));
  const rows = machs.map(m => {
    const vals = SIZE_ORDER.map(s => {
      const r = machChain(per[s], m, tc);
      return { CL: r.CL, CD: r.CD };
    });
    return { m, CD: agg(vals.map(v => v.CD)), CL: agg(vals.map(v => v.CL)),
             cCD: vals[5].CD, cCL: vals[5].CL };
  });
  const mc = agg(SIZE_ORDER.map(s => per[s].machCrit)).mean;
  const mdd = agg(SIZE_ORDER.map(s => per[s].machDD)).mean;
  const cdmax = Math.min(rows.find(r => r.m >= Math.min(mc + 0.12, 1.0)).CD.hi * CT * 1.3 + 30, 900);
  drawChart($("vsCdM"), { title: "Drag vs Mach: classic line, new band, measured no-trust zone shaded",
    xlabel: "Mach", x0: 0.30, x1: 1.05, y0: 0, y1: cdmax, xfmt: v => v.toFixed(2), yfmt: v => v.toFixed(0),
    regions: [{ from: mc, to: 1.05, color: "rgba(214,58,58,0.10)" }],
    band: rows.map(r => [r.m, r.CD.lo * CT, r.CD.hi * CT]), bandColor: C.acc,
    series: [{ pts: rows.map(r => [r.m, r.cCD * CT]), color: C.muted, dash: [5, 4], width: 1.2 },
             { pts: rows.map(r => [r.m, r.CD.mean * CT]), color: C.acc }],
    vlines: [{ x: mc, color: C.bad, label: "M_crit" }, { x: mdd, color: C.warn, label: "M_dd" }] });
  const clv = rows.flatMap(r => [r.CL.lo, r.CL.hi, r.cCL]);
  drawChart($("vsClM"), { title: "Lift vs Mach: the flagged lift-break region shaded",
    xlabel: "Mach", x0: 0.30, x1: 1.05, y0: Math.min(...clv) - 0.05, y1: Math.max(...clv) + 0.05,
    xfmt: v => v.toFixed(2),
    regions: [{ from: mdd + 0.04, to: 1.05, color: "rgba(177,116,31,0.12)" }],
    band: rows.map(r => [r.m, r.CL.lo, r.CL.hi]), bandColor: C.acc,
    series: [{ pts: rows.map(r => [r.m, r.cCL]), color: C.muted, dash: [5, 4], width: 1.2 },
             { pts: rows.map(r => [r.m, r.CL.mean]), color: C.acc }],
    vlines: [{ x: mdd + 0.04, color: C.warn, label: "lift-break onset" }] });
}

/* ------------------------------------------------------------ build panels */
function buildUI() {
  const tabs = $("tabs");
  const bNew = document.createElement("button");
  bNew.dataset.tab = "nfb"; bNew.textContent = "New NeuralFoil";
  const bVs = document.createElement("button");
  bVs.dataset.tab = "vs"; bVs.textContent = "New vs Classic";
  tabs.insertBefore(bVs, tabs.firstChild);
  tabs.insertBefore(bNew, tabs.firstChild);
  [bNew, bVs].forEach(b => b.addEventListener("click", () => selectTab(b.dataset.tab)));
  TAB_CHARTS.nfb = []; TAB_CHARTS.vs = [];

  const parent = $("p-flow").parentNode;
  const pn = document.createElement("section");
  pn.className = "panel"; pn.id = "p-nfb";
  pn.innerHTML =
    '<div class="card"><b>NeuralFoil B: the new NeuralFoil.</b> ' +
    "Same eight shipped 0.3.3 networks, exact tensors; new everything around them, each choice grounded in the study's measurements: " +
    "wind-tunnel comparisons chose the core, and the 312,795-condition atlas set the guard thresholds. " +
    "The prediction is the mean of all eight model sizes (ties the classic on Harris, 21 percent better drag on TN 1546, slightly better lift). " +
    "Every force and moment coefficient carries its 8-network disagreement band, a fabrication-free measured lower-bound indicator of error, and a verdict from the study's " +
    "measured failure map that says in words when not to trust it. It works on any airfoil in the search bar above, your own coordinate file, or a NACA design from the Geometry tab. " +
    'n_crit and forced trips come from the analysis-conditions panel in the toolbar. <span id="nfbStatus" style="color:var(--muted)"></span></div>' +
    '<div class="card" style="display:flex;gap:18px;flex-wrap:wrap;align-items:center">' +
    '<b id="nfbFoil"></b>' +
    '<label style="font-size:13px">alpha <input id="nfbA" type="range" min="-10" max="20" step="0.5" value="3" style="vertical-align:middle;width:130px"> <span id="nfbAv">3.0</span> deg</label>' +
    '<label style="font-size:13px">Mach <input id="nfbM" type="range" min="0" max="1.05" step="0.01" value="0.3" style="vertical-align:middle;width:130px"> <span id="nfbMv">0.30</span></label>' +
    '<label style="font-size:13px">Re <input id="nfbR" type="range" min="4" max="8" step="0.05" value="6" style="vertical-align:middle;width:130px"> <span id="nfbRv">1.0M</span></label></div>' +
    '<div id="nfbCards" style="display:flex;gap:12px;flex-wrap:wrap;margin-top:10px"></div>' +
    '<div id="nfbWhy" class="card" style="margin-top:10px"></div>' +
    '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:10px">' +
    '<canvas id="nfbClA" height="240" style="flex:1;min-width:320px"></canvas>' +
    '<canvas id="nfbCdA" height="240" style="flex:1;min-width:320px"></canvas></div>' +
    '<p class="note" style="margin-top:10px">Bands are the p10 to p90 disagreement of the eight networks: a measured lower bound on error, not a coverage guarantee. ' +
    "The study's registered conformal bound was honestly uninformative (567 counts) and no spread scale factor transfers between wind tunnels, so this page refuses to fake one. " +
    'Dashed lines are the classic single-network NeuralFoil. Full evidence: see New vs Classic and the <a href="study/data/research-answer.md">study answer document</a>.</p>';
  parent.appendChild(pn);

  const pv = document.createElement("section");
  pv.className = "panel"; pv.id = "p-vs";
  const evalTable = '<table class="t"><tr><th>Core candidate</th><th>Harris CD, counts</th><th>TN 1546 CD, counts</th><th>TN 1546 CL</th><th>Ferri CL</th></tr>' +
    EVAL_ROWS.map(r => "<tr" + (r[0].indexOf("new core") >= 0 ? ' style="font-weight:700"' : "") + "><td>" + r[0] + "</td><td>" + r[1].toFixed(2) +
      "</td><td>" + r[2].toFixed(2) + "</td><td>" + r[3].toFixed(2) + "</td><td>" + r[4].toFixed(2) + "</td></tr>").join("") + "</table>";
  const regTable = '<table class="t"><tr><th>#</th><th>Inaccuracy found</th><th>Measured size</th><th>Can it be fixed?</th><th>What the new NeuralFoil does</th></tr>' +
    REGISTRY.map((r, i) => "<tr><td>" + (i + 1) + "</td><td><b>" + r[0] + "</b></td><td>" + r[1] + "</td><td>" + r[2] + "</td><td>" + r[3] + "</td></tr>").join("") + "</table>";
  pv.innerHTML =
    '<div class="card"><b>What actually changed, and what honestly could not.</b><br>' +
    'The 2026 validation study measured NeuralFoil against wind-tunnel experiment across four reports, more than 600 digitized measured points, ' +
    "312,795 atlas conditions and all eight model sizes, then tried to repair every defect it found. " +
    "<b>Changed and shipped:</b> the core prediction is now the mean of all eight networks (ties or beats the classic on every measured group: equal within 0.1 counts on Harris, better everywhere else); every force and moment coefficient carries its 8-net disagreement band; " +
    "a verdict engine guards the measured failure regions, including the two confidence blindspots and the transonic zone the classic confidence score structurally cannot see. " +
    "<b>Tried, failed honestly, not shipped:</b> five transonic drag-rise recalibrations (the selected one was 78 percent worse on the Harris holdout), " +
    "a transonic-similarity scaling, and two lift-break timing repairs. Their failure is the study's central result: " +
    "the remaining errors live in the networks' Mach-blind training data, and the honest fix is displayed bounds and guards now, Mach-aware retraining later.</div>" +
    '<div class="card" style="margin-top:10px"><b>Live comparison at the current conditions</b> <span id="vsCond" style="color:var(--muted);font-size:12.5px"></span> <span id="vsStatus" style="color:var(--muted)"></span>' +
    '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:8px">' +
    '<canvas id="vsCdM" height="250" style="flex:1;min-width:320px"></canvas>' +
    '<canvas id="vsClM" height="250" style="flex:1;min-width:320px"></canvas></div>' +
    '<p class="note">Dashed: classic single-network NeuralFoil 0.3.3 xlarge. Solid with band: the new mean-of-8 with its disagreement band. ' +
    "The red zone starts at the airfoil's own critical Mach: onset location verified to about 0.03 in Mach, magnitude above it measured wrong by 2 to 8x near onset. " +
    "The two curves use identical physics formulas; the new one differs by the ensemble core, the band, and the honesty about where neither can be trusted.</p></div>" +
    '<div class="card" style="margin-top:10px"><b>How the new core was chosen: measured, not assumed</b><br>' +
    '<span style="color:var(--muted);font-size:12.5px">' + EVAL_NOTE + "</span>" + evalTable + "</div>" +
    '<div class="card" style="margin-top:10px"><b>Every inaccuracy the study found, and what this release does about each</b>' + regTable +
    '<p class="note">Sizes and verdicts are quoted verbatim from the study answer document, parts 1 to 9.</p></div>' +
    '<div class="card" style="margin-top:10px"><b>Read the evidence</b><ul style="margin:6px 0 0;padding-left:18px">' +
    STUDY_LINKS.map(l => '<li><a href="' + l[0] + '">' + l[0] + "</a>: " + l[1] + "</li>").join("") + "</ul></div>";
  parent.appendChild(pv);

  $("nfbA").addEventListener("input", () => { nfbUI.alpha = +$("nfbA").value; $("nfbAv").textContent = nfbUI.alpha.toFixed(1); renderNFB(); });
  $("nfbM").addEventListener("input", () => { nfbUI.mach = +$("nfbM").value; $("nfbMv").textContent = nfbUI.mach.toFixed(2); renderNFB(); });
  $("nfbR").addEventListener("input", () => { nfbUI.re = Math.pow(10, +$("nfbR").value);
    $("nfbRv").textContent = nfbUI.re >= 1e6 ? (nfbUI.re / 1e6).toFixed(1) + "M" : (nfbUI.re / 1e3).toFixed(0) + "k"; renderNFB(); });

  const about = $("p-about");
  if (about) {
    const d = document.createElement("div");
    d.className = "card";
    d.innerHTML = "<b>About the new NeuralFoil (2026 release of this site).</b> " +
      "The validation study this site was built around is complete. Its final answer document, including the honest negative results and the " +
      "15-entry inaccuracy registry, lives at <a href='study/data/research-answer.md'>study/data/research-answer.md</a>. " +
      "The New NeuralFoil tab is the study's product: the same networks, wrapped in the measured trust map. The New vs Classic tab shows exactly what changed and why. " +
      "Everything that was on this site before is still here, unchanged, on the other tabs.";
    about.insertBefore(d, about.firstChild);
  }
}

/* ------------------------------------------------------------ page wiring */
const origRenderAll = renderAll;
renderAll = function () {
  origRenderAll();
  if (state.tab === "nfb") renderNFB();
  else if (state.tab === "vs") renderVS();
};
const origRefreshRun = refreshRun;
refreshRun = function () {
  origRefreshRun();
  fitFor.c = {}; nfbCache = {}; sweepCache = {};
  ++sweepToken; /* kill any in-flight alpha sweep so it cannot cache mixed-condition rows */
  if (state.tab === "nfb" || state.tab === "vs") renderAll();
};
window.addEventListener("resize", () => {
  if (state.tab === "nfb") renderNFB();
  else if (state.tab === "vs") renderVS();
});
buildUI();
window.NFB = { load: nfbLoad, point: ensemblePoint, verdicts, SIZE_ORDER };
/* the page's own deep-link parser ran before this script and does not know the
   new tabs, so restore them from the hash here; bare visits land on the flagship */
const hashTab = location.hash.match(/^#(?:(nfb|vs)$|.*\btab=(nfb|vs)\b)/);
if (!location.hash) selectTab("nfb");
else if (hashTab) selectTab(hashTab[1] || hashTab[2]);
})();
