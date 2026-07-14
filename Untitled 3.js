/**
 * DEBUG_REDIST_TRACE
 *
 * Put in a spare cell like:
 * =DEBUG_REDIST_TRACE("IND","ALP+ON", <aecRowRange>, TRUE, "WA", "IND")
 *
 * It returns a 2-column table: [label, value]
 * so you can see which path is actually being used.
 */
function DEBUG_REDIST_TRACE(elimParty, aliveSetStr, aecRow, applyCalibration, seatState, aecRowParty) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];

  const elim = String(elimParty ?? "").trim().toUpperCase();
  const aliveArr = String(aliveSetStr ?? "")
    .split("+")
    .map(x => String(x).trim().toUpperCase())
    .filter(p => PARTIES.includes(p));

  if (!PARTIES.includes(elim) || aliveArr.length === 0) {
    return [["error", "bad inputs"]];
  }

  const alive = new Set(aliveArr);

  let base = aecRow;
  if (Array.isArray(base) && Array.isArray(base[0])) base = base[0];
  base = PARTIES.map((_, i) => Number(base?.[i]) || 0);

  const PARAMS = GET_PARAMS_UDF(); // will throw if cache missing — that’s good
  const S = PARAMS?.scalars || {};
  const wantCal = (applyCalibration === true || String(applyCalibration).trim().toUpperCase() === "TRUE");
  const state = String(seatState || "NAT").trim().toUpperCase();

  const rowParty = String(aecRowParty || "").trim().toUpperCase();
  const rowPartyOk = (!rowParty || rowParty === elim);

  const clamp01 = x => Math.max(0, Math.min(1, Number(x) || 0));

  const normaliseAlive = v => {
    let s = 0;
    const out = v.slice();
    for (let i = 0; i < 6; i++) {
      if (alive.has(PARTIES[i])) s += out[i];
      else out[i] = 0;
    }
    if (s > 0) {
      for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) out[i] /= s;
      return out;
    }
    const u = Array(6).fill(0);
    for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) u[i] = 1 / aliveArr.length;
    return u;
  };

  const vecToPct = v => PARTIES.map((p, i) => `${p}:${(100 * (v[i] || 0)).toFixed(2)}%`).join("  ");

  // Partition alive recipients into supported vs missing in the AEC row
  const supported = [];
  const missing = [];
  for (let i = 0; i < 6; i++) {
    if (!alive.has(PARTIES[i])) continue;
    (base[i] > 0 ? supported : missing).push(i);
  }

  const totalRow = base.reduce((a,b)=>a+b,0);
  const aliveMass = base.reduce((a,b,i)=> alive.has(PARTIES[i]) ? a+b : a, 0);

  const aecUsable = rowPartyOk && aliveMass > 0;
  const aecProj = aecUsable ? normaliseAlive(base) : null;
  const coverage = totalRow > 0 ? aliveMass / totalRow : 0;

  const aecPerfectMatch = aecUsable && missing.length === 0 && coverage >= 0.999;
  const aecIncompleteForAlive = aecUsable && missing.length > 0;

  const aliveSortedKey = aliveArr.slice().sort().join("+");
  const postKey = `${elim}|${aliveSortedKey}`;
  const postObj = PARAMS?.POSTERIOR_SCENARIOS?.[postKey] || null;

  const ide = PARAMS?.ideology?.[elim] || null;

  // Baseline trigger (important!)
  const baselineActive = (elim === "LNP" && alive.has("ALP") && alive.has("ON") &&
                          isFinite(PARAMS?.baselines?.LNP_TO_ON?.[state] ?? PARAMS?.baselines?.LNP_TO_ON?.NAT));

  // Anchor resolver (same logic as your weights UDF)
  const resolveAnchorW_ = () => {
    if (aecIncompleteForAlive) {
      let w = clamp01(S.AEC_ANCHOR_WHEN_MISS ?? 0.4);
      const cap = clamp01(S.AEC_MISMATCH_MAX ?? 0.55);
      w = Math.min(w, Math.min(cap, 0.999999));
      return w;
    }
    return clamp01((coverage - 0.5) / 0.4);
  };

  // Decide which path WILL be used (in order)
  let path = "UNKNOWN";
  if (aecPerfectMatch) path = "AEC_PERFECT_MATCH";
  else if (baselineActive) path = "BASELINE_LNP_TO_ON (not relevant unless elim=LNP)";
  else if (postObj) path = "POSTERIOR_SCENARIO";
  else if (aecIncompleteForAlive && ide) path = "IDEOLOGY (AEC_INCOMPLETE)";
  else if (aecUsable) path = "AEC_FALLBACK";
  else if (ide) path = "IDEOLOGY_FALLBACK";
  else path = "UNIFORM_FALLBACK";

  // Return diagnostics
  const out = [];
  out.push(["elim", elim]);
  out.push(["aliveSet (raw)", String(aliveSetStr)]);
  out.push(["aliveSet (sorted key)", aliveSortedKey]);
  out.push(["aecRowParty arg", rowParty || "(blank)"]);
  out.push(["rowPartyOk", String(rowPartyOk)]);
  out.push(["aecUsable", String(aecUsable)]);
  out.push(["coverage (aliveMass/totalRow)", coverage.toFixed(4)]);
  out.push(["missing alive parties in AEC row", missing.map(i=>PARTIES[i]).join(", ") || "(none)"]);
  out.push(["supported alive parties in AEC row", supported.map(i=>PARTIES[i]).join(", ") || "(none)"]);
  out.push(["aecPerfectMatch", String(aecPerfectMatch)]);
  out.push(["aecIncompleteForAlive", String(aecIncompleteForAlive)]);
  out.push(["posterior key looked up", postKey]);
  out.push(["posterior exists", String(!!postObj)]);
  out.push(["ideology exists for elim", String(!!ide)]);
  out.push(["wantCal", String(wantCal)]);
  out.push(["resolved AEC anchor w", resolveAnchorW_().toFixed(4)]);
  out.push(["AEC projected over alive", aecProj ? vecToPct(aecProj) : "(none)"]);
  out.push(["PATH USED (expected)", path]);

  return out;
}
