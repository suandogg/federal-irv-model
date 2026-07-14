/**
 * MARKOV_NEXT_FALLBACK_V2 (safe test)
 * Same signature as legacy: (prevRow, elimIndex, baseMatrix, aliveMaskRow, completedMatrix)
 * Fallback order: AEC evidence → posterior scenarios → ideology → uniform (last resort)
 */
function MARKOV_NEXT_FALLBACK_V2(prevRow, elimIndex, baseMatrix, aliveMaskRow, completedMatrix) {
  const PARTY_ORDER = ["ALP","LNP","GRN","ON","IND","OTH"]; // must match your matrix column order

  const votes = _as1d_(prevRow);
  const alive = _as1d_(aliveMaskRow);

  const elimI = _toIndex0_(elimIndex, votes.length); // accepts 1-based or 0-based
  const elimParty = PARTY_ORDER[elimI];

  const aliveSet = [];
  for (let i = 0; i < PARTY_ORDER.length; i++) if (_isAlive_(alive, i)) aliveSet.push(PARTY_ORDER[i]);
  const aliveKey = aliveSet.join("+");
  const posteriorKey = `${elimParty}|${aliveKey}`;

  const elimVotes = votes[elimI] || 0;
  if (elimVotes === 0) return votes; // nothing to move

  // --- weights ---
  const params = _GET_PARAMS_CACHED_(); // loads SCENARIO_AVGS + ideology once
  const recipients = [];
  for (let i = 0; i < PARTY_ORDER.length; i++) {
    if (i !== elimI && _isAlive_(alive, i)) recipients.push(i);
  }
  if (recipients.length === 0) return votes;

  const aec = _getAECWeights_(baseMatrix, elimI, recipients);
  const aecSum = _sumByIdx_(aec, recipients);

  let weights = new Array(PARTY_ORDER.length).fill(0);

  if (aecSum > 0) {
    // Use AEC evidence for what exists
    for (const j of recipients) weights[j] = aec[j] / aecSum;

    // If partial evidence, fill remainder from posterior → ideology
    const remainder = Math.max(0, 1 - aecSum);
    if (remainder > 1e-9) {
      const post = _getPosterior_(params, posteriorKey, PARTY_ORDER, recipients);
      const fill = post || _getIdeology_(params, elimParty, PARTY_ORDER, recipients);
      const fillSum = _sumByIdx_(fill, recipients);

      if (fillSum > 0) {
        for (const j of recipients) weights[j] = (aec[j] / aecSum) * (1 - remainder) + (fill[j] / fillSum) * remainder;
      }
    }
  } else {
    // No AEC evidence → posterior → ideology → uniform
    const post = _getPosterior_(params, posteriorKey, PARTY_ORDER, recipients);
    const fill = post || _getIdeology_(params, elimParty, PARTY_ORDER, recipients);
    const fillSum = _sumByIdx_(fill, recipients);

    if (fillSum > 0) {
      for (const j of recipients) weights[j] = fill[j] / fillSum;
    } else {
      const u = 1 / recipients.length;
      for (const j of recipients) weights[j] = u;
    }
  }

  // --- apply ---
  const out = votes.slice();
  out[elimI] = 0;
  for (const j of recipients) out[j] += elimVotes * (weights[j] || 0);

  return out;
}

/** --- helpers --- */

function _as1d_(x) {
  // Handles either [a,b,c] or [[a,b,c]] from Sheets
  if (Array.isArray(x) && Array.isArray(x[0])) return x[0].map(_toNum_);
  if (Array.isArray(x)) return x.map(_toNum_);
  return [];
}

function _toNum_(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function _isAlive_(aliveRow, i) {
  // alive mask sometimes comes as 1/0 or TRUE/FALSE
  const v = aliveRow[i];
  return v === true || v === 1 || v === "1" || v === "TRUE" || v === "true";
}

function _toIndex0_(elimIndex, n) {
  const k = Number(elimIndex);
  if (!Number.isFinite(k)) return 0;
  // If user passes 1..n, convert to 0..n-1; if already 0..n-1 keep it.
  if (k >= 1 && k <= n) return Math.floor(k - 1);
  if (k >= 0 && k < n) return Math.floor(k);
  return 0;
}

function _sumByIdx_(arr, idxs) {
  let s = 0;
  for (const i of idxs) s += (arr[i] || 0);
  return s;
}

function _getAECWeights_(baseMatrix, elimI, recipients) {
  // baseMatrix expected 6x6 (or bigger but with first 6 cols relevant)
  const M = baseMatrix;
  const row = (Array.isArray(M) && Array.isArray(M[elimI])) ? M[elimI] : [];
  const out = new Array(6).fill(0);
  for (const j of recipients) out[j] = _toNum_(row[j]);
  return out;
}

function _getPosterior_(params, key, PARTY_ORDER, recipients) {
  const out = new Array(PARTY_ORDER.length).fill(0);
  const table = params && params.POSTERIOR_SCENARIOS;
  const hit = table && table[key];
  if (!hit) return null;
  // hit assumed {ALP:0.3, LNP:0.4, ...}
  for (const j of recipients) {
    const p = PARTY_ORDER[j];
    out[j] = _toNum_(hit[p]);
  }
  return out;
}

function _getIdeology_(params, elimParty, PARTY_ORDER, recipients) {
  const out = new Array(PARTY_ORDER.length).fill(0);
  const ide = params && params.IDEOLOGY_PRIOR;
  const row = ide && ide[elimParty];
  if (!row) return out;
  for (const j of recipients) {
    const p = PARTY_ORDER[j];
    out[j] = _toNum_(row[p]);
  }
  return out;
}

/**
 * Global cached PARAMS getter.
 * Replace internals with your existing loaders:
 *  - LOAD_POSTERIOR_SCENARIOS()
 *  - LOAD_IDEOLOGY_PRIOR()
 */
function _GET_PARAMS_CACHED_() {
  if (globalThis.__IRV_PARAMS__) return globalThis.__IRV_PARAMS__;

  const PARAMS = {};
  // You will wire these into your real loaders
  PARAMS.POSTERIOR_SCENARIOS = (typeof LOAD_POSTERIOR_SCENARIOS === "function") ? LOAD_POSTERIOR_SCENARIOS() : {};
  PARAMS.IDEOLOGY_PRIOR      = (typeof LOAD_IDEOLOGY_PRIOR === "function") ? LOAD_IDEOLOGY_PRIOR() : {};

  globalThis.__IRV_PARAMS__ = PARAMS;
  return PARAMS;
}
