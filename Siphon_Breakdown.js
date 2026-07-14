function REDIST_SIPHON_BREAKDOWN(elimParty, aliveSetStr, aecRow, applyCalibration) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];

  const elim = String(elimParty).trim().toUpperCase();
  if (!PARTIES.includes(elim)) return "BAD ELIM";

  const aliveArr = String(aliveSetStr)
    .split("+")
    .map(s => s.trim().toUpperCase())
    .filter(p => PARTIES.includes(p));

  if (aliveArr.length === 0) return "EMPTY ALIVESET";

  const alive = new Set(aliveArr);

  let base = aecRow;
  if (Array.isArray(base) && Array.isArray(base[0])) base = base[0];
  base = PARTIES.map((_, i) => Number(base?.[i]) || 0);

  const P = GET_PARAMS();
  const wantCal = (applyCalibration === true || String(applyCalibration).toUpperCase() === "TRUE");

  // ---------- identify AEC-supported ----------
  const supported = [];
  const missing = [];

  for (let i = 0; i < 6; i++) {
    if (!alive.has(PARTIES[i])) continue;
    if (base[i] > 0) supported.push(i);
    else missing.push(i);
  }

  // ---------- posterior ----------
  const aliveKey = aliveArr.slice().sort().join("+");
  const post = P.POSTERIOR_SCENARIOS?.[`${elim}|${aliveKey}`] || null;

  if (!post) return "NO POSTERIOR";

  const postVec = Array(6).fill(0);
  let postSum = 0;
  for (let i = 0; i < 6; i++) {
    if (!alive.has(PARTIES[i])) continue;
    const v = Number(post[PARTIES[i]]) || 0;
    postVec[i] = v;
    postSum += v;
  }
  if (postSum <= 0) return "POSTERIOR ZERO";

  for (let i = 0; i < 6; i++) postVec[i] /= postSum;

  // ---------- pre-siphon vector ----------
  let pre = Array(6).fill(0);

  if (supported.length >= 1) {
    // ratio-preserving + posterior-entry
    let aecSum = 0;
    for (const i of supported) aecSum += base[i];

    let missingMass = 0;
    for (const i of missing) missingMass += postVec[i];

    const remaining = 1 - missingMass;

    for (const i of supported) {
      pre[i] = (aecSum > 0 ? base[i] / aecSum : 0) * remaining;
    }
    for (const i of missing) pre[i] = postVec[i];
  } else {
    pre = postVec.slice();
  }

  // ---------- siphon ----------
  const siph = P.siphon || {};
  let entrant = null;

  if (missing.length === 1 && supported.length >= 2) {
    entrant = PARTIES[missing[0]];
  }

  if (!entrant || !siph[entrant]) {
    return `PRE: ${fmt(pre, alive)} | NO SIPHON`;
  }

  // donor shares
  const donorRow = siph[entrant];
  let dSum = 0;
  const donorShares = {};

  for (const i of supported) {
    const v = Number(donorRow[PARTIES[i]]) || 0;
    donorShares[i] = v;
    dSum += v;
  }

  if (dSum <= 0) {
    return `PRE: ${fmt(pre, alive)} | NO SIPHON`;
  }

  for (const i of supported) donorShares[i] /= dSum;

const m = pre[missing[0]]; // entrant mass
const postSiphon = pre.slice();

for (const i of supported) {
  postSiphon[i] -= m * donorShares[i];
}

// normalise
let s = 0;
for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) s += postSiphon[i];
for (let i = 0; i < 6; i++) if (alive.has(PARTIES[i])) postSiphon[i] /= s;

return (
  `PRE: ${fmt(pre, alive)} | ` +
  `SIPHON: ${entrant} ← ${fmtDonors(donorShares)} | ` +
  `POST: ${fmt(postSiphon, alive)}`
);
}

// ---------- helpers ----------
function fmt(vec, alive) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];
  return PARTIES
    .filter(p => alive.has(p))
    .map(p => `${p} ${(vec[PARTIES.indexOf(p)] * 100).toFixed(1)}`)
    .join(" | ");
}

function fmtDonors(ds) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];
  return Object.entries(ds)
    .map(([i,v]) => `${PARTIES[i]} ${(v*100).toFixed(1)}%`)
    .join(", ");
}
