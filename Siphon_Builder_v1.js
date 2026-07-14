function BUILD_SIPHON_FROM_POSTERIORS() {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];
  const P = GET_PARAMS();
  const post = P.POSTERIOR_SCENARIOS || {};

  // Accumulators: entrant -> donor -> sum, and entrant -> count
  const acc = {};
  const cnt = {};

  function parseAliveKey(key) {
    // key format: ELIM|ALP+GRN+LNP
    const parts = key.split("|");
    return { elim: parts[0], alive: (parts[1] || "").split("+").filter(Boolean) };
  }

  // Index keys by elim + aliveSet for fast lookup
  const byElimAlive = {};
  for (const k of Object.keys(post)) {
    const { elim, alive } = parseAliveKey(k);
    if (!elim || alive.length === 0) continue;
    const aliveKey = alive.slice().sort().join("+");
    byElimAlive[`${elim}|${aliveKey}`] = post[k];
  }

  // For each (elim, aliveSet-with-X) find matching (elim, aliveSet-without-X)
  for (const k of Object.keys(byElimAlive)) {
    const { elim, alive } = parseAliveKey(k);
    const aliveSet = alive.slice().sort();

    // try each possible entrant X in the set
    for (const X of aliveSet) {
      // Only build siphons for these entrants
      if (!["GRN","ON","IND","OTH"].includes(X)) continue;

      const without = aliveSet.filter(p => p !== X);
      if (without.length < 2) continue; // need ≥2 donors to be meaningful

      const kWithout = `${elim}|${without.join("+")}`;
      const postWithout = byElimAlive[kWithout];
      const postWith = byElimAlive[k];
      if (!postWithout || !postWith) continue;

      const pX = Number(postWith[X]) || 0;
      if (pX <= 0) continue;

      // compute donor siphon shares
      let sumS = 0;
      const s = {};
      for (const d of without) {
        const a = Number(postWithout[d]) || 0;
        const b = Number(postWith[d]) || 0;
        const sd = (a - b) / pX;
        s[d] = sd;
        sumS += sd;
      }

      // only accept if sane-ish (avoid noisy pairs)
      if (!(sumS > 0.7 && sumS < 1.3)) continue;

      if (!acc[X]) acc[X] = {};
      if (!cnt[X]) cnt[X] = 0;

      for (const d of without) {
        const v = Math.max(0, s[d] / sumS); // renormalise and clamp
        acc[X][d] = (acc[X][d] || 0) + v;
      }
      cnt[X] += 1;
    }
  }

  // Turn into averages
  const out = {};
  for (const X of Object.keys(acc)) {
    out[X] = {};
    const n = cnt[X] || 1;
    for (const d of PARTIES) {
      if (d === X) { out[X][d] = 0; continue; }
      out[X][d] = (acc[X][d] || 0) / n;
    }
    // normalise row to sum to 1 (excluding entrant)
    let s = 0;
    for (const d of PARTIES) if (d !== X) s += out[X][d];
    if (s > 0) for (const d of PARTIES) if (d !== X) out[X][d] /= s;
  }

  Logger.log(JSON.stringify({ samples: cnt, siphon: out }, null, 2));
  return out; // handy if you call it from a cell via custom function later
}
