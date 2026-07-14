function BUILD_SIPHON_FROM_POSTERIORS() {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];
  const P = GET_PARAMS();
  const post = P.POSTERIOR_SCENARIOS || {};

  // Accumulators: entrant -> donor -> sum, and entrant -> count
  const acc = {};
  const cnt = {};

  function parseKey(key) {
    // key format: ELIM|ALP+GRN+LNP
    const parts = key.split("|");
    return {
      elim: parts[0],
      alive: (parts[1] || "").split("+").filter(Boolean)
    };
  }

  // Iterate over all posterior scenarios
  for (const k of Object.keys(post)) {
    const { elim, alive } = parseKey(k);
    if (!elim || alive.length < 3) continue;

    const aliveSet = alive.slice().sort();
    const postWith = post[k];

    // Try each possible entrant X
    for (const X of aliveSet) {
      if (!["GRN","ON","IND","OTH"].includes(X)) continue;

      const donors = aliveSet.filter(p => p !== X);
      if (donors.length < 2) continue;

      const pX = Number(postWith[X]) || 0;
      if (pX <= 0 || pX >= 0.9) continue; // avoid degenerate cases

      // ---- derive "without X" by renormalising donors ----
      let donorSum = 0;
      const postWithout = {};

      for (const d of donors) {
        const v = Number(postWith[d]) || 0;
        postWithout[d] = v;
        donorSum += v;
      }
      if (donorSum <= 0) continue;

      for (const d of donors) {
        postWithout[d] /= donorSum;
      }

      // ---- donor-normalised siphon signal ----
      let sumSignal = 0;
      const signal = {};

      for (const d of donors) {
        const a = postWithout[d];                  // donor share without X
        const b = (Number(postWith[d]) || 0) / (1 - pX); // donor share if X removed

        if (a <= 0) {
          signal[d] = 0;
          continue;
        }

        const sd = Math.max(0, (a - b) / a); // FRACTION of donor lost
        signal[d] = sd;
        sumSignal += sd;
      }

      if (sumSignal <= 0) continue;

      // ---- accumulate ----
      if (!acc[X]) acc[X] = {};
      if (!cnt[X]) cnt[X] = 0;

      for (const d of donors) {
        const w = signal[d] / sumSignal;
        acc[X][d] = (acc[X][d] || 0) + w;
      }
      cnt[X] += 1;
    }
  }

  // ---- convert to averaged siphon rows ----
  const out = {};

  for (const X of Object.keys(acc)) {
    out[X] = {};
    const n = cnt[X] || 1;

    for (const d of PARTIES) {
      if (d === X) {
        out[X][d] = 0;
      } else {
        out[X][d] = (acc[X][d] || 0) / n;
      }
    }

    // normalise row to sum to 1 (excluding entrant)
    let s = 0;
    for (const d of PARTIES) if (d !== X) s += out[X][d];
    if (s > 0) {
      for (const d of PARTIES) if (d !== X) out[X][d] /= s;
    }
  }

  Logger.log(JSON.stringify({ samples: cnt, siphon: out }, null, 2));
  return out;
}
