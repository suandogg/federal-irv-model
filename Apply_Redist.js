function APPLY_REDIST(votesRow, elimParty, weightsRow, aliveSetStr) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];

  // ---- coerce rows ----
  let v = Array.isArray(votesRow[0]) ? votesRow[0] : votesRow;
  let w = Array.isArray(weightsRow[0]) ? weightsRow[0] : weightsRow;

  v = PARTIES.map((_, i) => Number(v[i]) || 0);
  w = PARTIES.map((_, i) => Number(w[i]) || 0);

  // ---- alive set ----
  const alive = new Set(
    String(aliveSetStr || "")
      .split("+")
      .map(s => s.trim())
      .filter(Boolean)
  );

  // ---- eliminated index ----
  const e = PARTIES.indexOf(String(elimParty).trim());
  if (e < 0) throw new Error("Invalid elimParty: " + elimParty);

  const elimVotes = v[e];

  // ---- zero everyone not alive (including past eliminations) ----
  const next = v.map((val, i) =>
    alive.has(PARTIES[i]) ? val : 0
  );

  // ---- redistribute ----
  for (let i = 0; i < 6; i++) {
    if (alive.has(PARTIES[i])) {
      next[i] += elimVotes * w[i];
    }
  }

  return [next];
}
