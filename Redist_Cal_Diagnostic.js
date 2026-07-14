function REDIST_DIAGNOSTIC(elimParty, aliveSetStr, aecRow, applyCalibration) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];
  const elim = String(elimParty).trim().toUpperCase();

  const aliveArr = String(aliveSetStr)
    .split("+")
    .map(s => s.trim().toUpperCase())
    .filter(p => PARTIES.includes(p));

  if (!PARTIES.includes(elim) || aliveArr.length === 0) return "BAD_INPUT";

  let base = aecRow;
  if (Array.isArray(base) && Array.isArray(base[0])) base = base[0];
  base = PARTIES.map((_, i) => Number(base?.[i]) || 0);

  const P = GET_PARAMS();
  const wantCal = (applyCalibration === true || String(applyCalibration).toUpperCase() === "TRUE");

  // AEC support
  const alive = new Set(aliveArr);
  const aecSupported = aliveArr.filter(p => base[PARTIES.indexOf(p)] > 0);

  if (aecSupported.length < 2) return "NO_CAL: AEC_SUPPORT<2";
  if (aecSupported.length === aliveArr.length) return "NO_CAL: AEC_COVERS_ALL";

  const aliveKey = aliveArr.slice().sort().join("+");
  const postFull = P.POSTERIOR_SCENARIOS?.[`${elim}|${aliveKey}`];
  if (!postFull) return "NO_CAL: NO_POSTERIOR_FULL";

  const subsetKey = `${elim}|${aecSupported.slice().sort().join("+")}`;
  const postSub = P.POSTERIOR_SCENARIOS?.[subsetKey];
  if (!postSub) return "NO_CAL: NO_POSTERIOR_SUBSET";

  // Compare AEC vs posterior on supported subset
  let aecSum = 0, postSum = 0;
  for (const p of aecSupported) {
    aecSum += base[PARTIES.indexOf(p)];
    postSum += Number(postSub[p]) || 0;
  }
  if (aecSum <= 0 || postSum <= 0) return "NO_CAL: DEGENERATE";

  let maxAbs = 0;
  for (const p of aecSupported) {
    const i = PARTIES.indexOf(p);
    const a = base[i] / aecSum;
    const q = (Number(postSub[p]) || 0) / postSum;
    maxAbs = Math.max(maxAbs, Math.abs(a - q));
  }

  if (maxAbs < 0.05) return `NO_CAL: WEAK_DIFF (${(maxAbs*100).toFixed(1)}pp)`;
  return wantCal
    ? `CAL_APPLIED (${aecSupported.join("+")})`
    : `CAL_CANDIDATE (${aecSupported.join("+")})`;
}

