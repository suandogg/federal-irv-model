/**
 * REDIST_WEIGHTS — Robust AEC + Posterior + Ideology, with missing-alive protection
 *
 * FIX INCLUDED (IMPORTANT):
 *   The LNP → (ALP, ON) baseline is now ONLY applied when alive set is exactly ALP+ON.
 *   Previously it fired whenever ALP & ON were present (even if GRN/OTH were also alive),
 *   which hard-forced LNP prefs to split only ALP/ON and starved GRN/OTH entirely.
 *
 * Everything else is preserved from your "previous script":
 *  - AEC perfect match short-circuit
 *  - AEC-missing regime: AEC_ANCHOR_WHEN_MISS capped by AEC_MISMATCH_MAX, never to 1
 *  - Posterior path with robust parsing + key variants
 *  - Protected entry mass to missing alive (POST_ENTRY_FLOOR / POST_ENTRY_STRENGTH)
 *  - No posterior path: ideology first + protected entry + optional weak AEC anchor
 *  - Supported-only calibration
 */
function REDIST_WEIGHTS(elimParty, aliveSetStr, aecRow, applyCalibration, seatState, aecRowParty) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];

  /* =============================
   * 0) Inputs + normalisation
   * ============================= */
  const elim = String(elimParty ?? "").trim().toUpperCase();

  const aliveArr = String(aliveSetStr ?? "")
    .split("+")
    .map(x => String(x).trim().toUpperCase())
    .filter(p => PARTIES.includes(p));
    const alive = new Set(aliveArr);


  if (!PARTIES.includes(elim) || aliveArr.length === 0) {
    throw new Error("REDIST_WEIGHTS: bad inputs");
  }

  let base = aecRow;
  if (Array.isArray(base) && Array.isArray(base[0])) base = base[0];
  base = PARTIES.map((_, i) => Number(base?.[i]) || 0);

  const PARAMS = GET_PARAMS_UDF();
  const S = PARAMS?.scalars || {};

  const wantCal =
    (applyCalibration === true) ||
    (String(applyCalibration).trim().toUpperCase() === "TRUE");

  const state = String(seatState || "NAT").trim().toUpperCase();

  const rowParty = String(aecRowParty || "").trim().toUpperCase();
  const rowPartyOk = (!rowParty || rowParty === elim);

  /* =============================
   * Helpers
   * ============================= */
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
    // last resort: uniform across alive
    const u = Array(6).fill(0);
    const n = aliveArr.length;
    for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) u[i] = 1 / n;
    return u;
  };

  // Parse posterior numbers robustly: "27.29%", 27.29, 0.2729
  const parseShare_ = v => {
    if (v == null) return 0;
    if (typeof v === "number") {
      if (!isFinite(v) || v <= 0) return 0;
      return (v > 1.5 ? v / 100 : v);
    }
    const s = String(v).trim();
    if (!s) return 0;

    if (s.endsWith("%")) {
      const n = Number(s.slice(0, -1).trim());
      if (!isFinite(n) || n <= 0) return 0;
      return n / 100;
    }
    const n = Number(s);
    if (!isFinite(n) || n <= 0) return 0;
    return (n > 1.5 ? n / 100 : n);
  };

  // Posterior object key variants: fixes "One Nation"/"ONP"/etc
  const readPosteriorShare_ = (obj, party) => {
    if (!obj) return 0;

    const keys = [
      party,
      party.trim(),
      party.toLowerCase(),
      party.toUpperCase(),
      party.replace(/\s+/g,""),
      party.toLowerCase().replace(/\s+/g,""),
      party.toUpperCase().replace(/\s+/g,"")
    ];

    if (party === "ON")  keys.push("One Nation","ONE NATION","OneNation","ONP","PHON");
    if (party === "LNP") keys.push("LIB","LIB/NAT","LIBNAT","COAL");
    if (party === "GRN") keys.push("GREENS");
    if (party === "OTH") keys.push("OTHER","OTHERS");

    for (const k of keys) {
      if (k == null) continue;
      const kk = String(k);
      if (kk in obj) {
        const val = parseShare_(obj[kk]);
        if (val > 0) return val;
      }
      const kt = kk.trim();
      if (kt && (kt in obj)) {
        const val = parseShare_(obj[kt]);
        if (val > 0) return val;
      }
    }
    return 0;
  };

  // Used for the "supported-only calibration" step
  const calibrateSupportedOnly_ = (vector, supportedIdxs, targetAEC, frozenMissingMass) => {
    const eps = 1e-12;

    let aS = 0;
    for (const i of supportedIdxs) aS += targetAEC[i];

    let vS = 0;
    for (const i of supportedIdxs) vS += vector[i];

    if (!(aS > 0) || !(vS > 0)) return vector;

    const cal = vector.slice();
    for (const i of supportedIdxs) {
      const a = Math.max(targetAEC[i] / aS, eps);
      const q = Math.max(vector[i] / vS, eps);
      cal[i] *= Math.exp(Math.log(a) - Math.log(q));
    }

    let supSum = 0;
    for (const i of supportedIdxs) supSum += cal[i];

    const out = Array(6).fill(0);
    for (let i = 0; i < 6; i++) out[i] = cal[i];

    const rem = 1 - frozenMissingMass;
    if (supSum > 0 && rem > 0) {
      for (const i of supportedIdxs) out[i] = rem * (cal[i] / supSum);
    }

    return normaliseAlive(out);
  };

  /* =============================
   * 1) Partition alive vs AEC
   * ============================= */
  const supported = [];
  const missing = [];
  for (let i = 0; i < 6; i++) {
    if (!alive.has(PARTIES[i])) continue;
    (base[i] > 0 ? supported : missing).push(i);
  }

  const totalRow  = base.reduce((a,b)=>a+b,0);

  let aliveMass = 0;
  for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) aliveMass += base[i];

  const aecUsable = rowPartyOk && (aliveMass > 0);
  const aecProj   = aecUsable ? normaliseAlive(base) : null;
  const coverage  = (totalRow > 0) ? (aliveMass / totalRow) : 0;

  const aecPerfectMatch =
    aecUsable &&
    (missing.length === 0) &&
    (coverage >= 0.999);

  const aecIncompleteForAlive = aecUsable && (missing.length > 0);

  /* =============================
   * 2) Special ON 2CP override
   * ============================= */
  const aliveIsALP_LNP = (alive.size === 2 && alive.has("ALP") && alive.has("LNP"));
  const forcePosteriorON2CP = (elim === "ON" && aliveIsALP_LNP);

  /* =============================
   * A) Immediate AEC return
   * ============================= */
  if (aecPerfectMatch && !forcePosteriorON2CP) {
    return [aecProj];
  }

  /* =============================
   * B) State baseline (LNP → ALP+ON) — FIXED
   * =============================
   * Previously: triggered whenever alive had ALP and ON (even with GRN/OTH alive)
   * Now: only trigger when alive set is EXACTLY {ALP, ON}
   */
  const aliveIsALP_ON = (alive.size === 2 && alive.has("ALP") && alive.has("ON"));
  if (elim === "LNP" && aliveIsALP_ON) {
    const pON = PARAMS?.baselines?.LNP_TO_ON?.[state] ?? PARAMS?.baselines?.LNP_TO_ON?.NAT;
    if (isFinite(pON)) {
      const out = Array(6).fill(0);
      out[PARTIES.indexOf("ON")]  = Number(pON);
      out[PARTIES.indexOf("ALP")] = 1 - Number(pON);
      return [normaliseAlive(out)];
    }
  }

  /* =============================
   * Anchor weight resolver
   * ============================= */
  const resolveAnchorW_ = () => {
    if (forcePosteriorON2CP) {
      return clamp01(S.AEC_2CP_ANCHOR_ON ?? 0.15);
    }

    if (aecIncompleteForAlive) {
      let w = clamp01(S.AEC_ANCHOR_WHEN_MISS ?? 0.4);
      const cap = clamp01(S.AEC_MISMATCH_MAX ?? 0.55);
      w = Math.min(w, Math.min(cap, 0.999999));
      return w;
    }

    return clamp01((coverage - 0.5) / 0.4);
  };

  /* =============================
   * Protected entry mass allocator (WITH and WITHOUT posterior)
   * ============================= */
  const applyProtectedEntryToMissing_ = (priorVec, missingIdxs, supportedIdxs) => {
    if (!missingIdxs.length) return priorVec;

    const floor = clamp01(S.POST_ENTRY_FLOOR ?? 0);
    const strength = clamp01(S.POST_ENTRY_STRENGTH ?? 0.45);

    let curMissing = 0;
    for (const i of missingIdxs) curMissing += priorVec[i];

    let reserveMass = Math.max(floor, strength * curMissing);
    reserveMass = Math.min(reserveMass, 0.95);

    if (!supportedIdxs.length) return priorVec;

    const out = Array(6).fill(0);

    if (curMissing > 0) {
      for (const i of missingIdxs) out[i] = reserveMass * (priorVec[i] / curMissing);
    } else {
      for (const i of missingIdxs) out[i] = reserveMass / missingIdxs.length;
    }

    const rem = 1 - reserveMass;
    let curSupported = 0;
    for (const i of supportedIdxs) curSupported += priorVec[i];

    if (curSupported > 0 && rem > 0) {
      for (const i of supportedIdxs) out[i] = rem * (priorVec[i] / curSupported);
    } else {
      for (const i of supportedIdxs) out[i] = rem / supportedIdxs.length;
    }

    return normaliseAlive(out);
  };

  /* =============================
   * C) Posterior path
   * ============================= */
  const postKey = `${elim}|${aliveArr.slice().sort().join("+")}`;
  const postObj = PARAMS?.POSTERIOR_SCENARIOS?.[postKey];

  if (postObj) {
    const post = Array(6).fill(0);
    let postSum = 0;

    for (let i = 0; i < 6; i++) {
      if (!alive.has(PARTIES[i])) continue;
      post[i] = readPosteriorShare_(postObj, PARTIES[i]);
      postSum += post[i];
    }
    if (postSum > 0) {
      for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) post[i] /= postSum;
    }

    let postSide = normaliseAlive(post.slice());

    if (missing.length > 0) {
      postSide = applyProtectedEntryToMissing_(postSide, missing, supported);

      if (wantCal && supported.length >= 2 && aecUsable) {
        let missMass = 0;
        for (const i of missing) missMass += postSide[i];
        postSide = calibrateSupportedOnly_(postSide, supported, base, clamp01(missMass));
      }
    }

    if (aecUsable && aecProj) {
      const w = resolveAnchorW_();
      const blended = Array(6).fill(0);
      for (let i = 0; i < 6; i++) blended[i] = w * aecProj[i] + (1 - w) * postSide[i];
      return [normaliseAlive(blended)];
    }

    return [normaliseAlive(postSide)];
  }

  /* =============================
   * D) No posterior
   * ============================= */
  const ide = PARAMS?.ideology?.[elim] || null;

  if (aecIncompleteForAlive) {
    const prior = Array(6).fill(0);

    if (ide) {
      for (let i = 0; i < 6; i++) {
        if (!alive.has(PARTIES[i])) continue;
        prior[i] = Number(ide[PARTIES[i]]) || 0;
      }
    } else {
      for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) prior[i] = 1;
    }

    let priorSide = normaliseAlive(prior);

    // critical: inject reserve mass so missing-alive can’t be starved
    priorSide = applyProtectedEntryToMissing_(priorSide, missing, supported);

    if (wantCal && supported.length >= 2 && aecUsable) {
      let missMass = 0;
      for (const i of missing) missMass += priorSide[i];
      priorSide = calibrateSupportedOnly_(priorSide, supported, base, clamp01(missMass));
    }

    if (aecUsable && aecProj) {
      const w = resolveAnchorW_();
      const blended = Array(6).fill(0);
      for (let i = 0; i < 6; i++) blended[i] = w * aecProj[i] + (1 - w) * priorSide[i];
      return [normaliseAlive(blended)];
    }

    return [normaliseAlive(priorSide)];
  }

  if (aecUsable && aecProj) return [aecProj];

  if (ide) {
    const out = Array(6).fill(0);
    for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) out[i] = Number(ide[PARTIES[i]]) || 0;
    return [normaliseAlive(out)];
  }

  return [normaliseAlive(Array(6).fill(1))];
}
