function REDIST_SIPHON_DIAGNOSTIC(elimParty, aliveSetStr, aecRow) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];

  const elim = String(elimParty).trim().toUpperCase();
  if (!PARTIES.includes(elim)) return "";

  const aliveArr = String(aliveSetStr)
    .split("+")
    .map(s => s.trim().toUpperCase())
    .filter(p => PARTIES.includes(p));

  if (aliveArr.length === 0) return "";

  const alive = new Set(aliveArr);

  let base = aecRow;
  if (Array.isArray(base) && Array.isArray(base[0])) base = base[0];
  base = PARTIES.map((_, i) => Number(base?.[i]) || 0);

  const P = GET_PARAMS();
  const siph = P.siphon || {};

  // AEC-supported vs missing
  const supported = [];
  const missing = [];
  for (let i = 0; i < 6; i++) {
    if (!alive.has(PARTIES[i])) continue;
    if (base[i] > 0) supported.push(i);
    else missing.push(i);
  }

  if (supported.length < 2 || missing.length === 0) return "";

  const msgs = [];

  for (const eIdx of missing) {
    const entrant = PARTIES[eIdx];
    const row = siph[entrant];
    if (!row) continue;

    // donor weights
    let maxDonor = null;
    let maxVal = 0;

    for (const dIdx of supported) {
      const donor = PARTIES[dIdx];
      const v = Number(row[donor]) || 0;
      if (v > maxVal) {
        maxVal = v;
        maxDonor = donor;
      }
    }

    if (maxDonor && maxVal > 0) {
      msgs.push(`SIPHON APPLIED: ${entrant} \u2192 ${maxDonor}`);
    }
  }

  return msgs.join("; ");
}