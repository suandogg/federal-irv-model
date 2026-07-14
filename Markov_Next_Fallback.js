/**
 * MARKOV_NEXT_FALLBACK — Structure-preserving, NATIONAL posteriors only
 *
 * Preference order:
 *   1) AEC evidence (partial allowed; reserve mass if alive=0 exists)
 *   2) National posterior scenarios: ELIM|ALIVESET  (no class)
 *   3) Ideology + existing smoothing/caps/tilts (unchanged)
 *
 * Geography/class are intentionally NOT USED here.
 * geographyStr is kept only for signature compatibility with Sheets.
 */

function MARKOV_NEXT_FALLBACK(
  prevRow,
  elimIndex,
  baseMatrix,
  aliveMaskRow,
  completedMatrix,
  MIN_LEFT_WHEN_LEFT_ELIM,          // kept for compatibility; not used here
  MIN_RIGHT_WHEN_RIGHT_ELIM,        // kept for compatibility; not used here
  MIN_LNP_OVER_ON_WHEN_ALP_ELIM,    // kept for compatibility; not used here
  MIN_GRN_OVER_LNP_WHEN_ALP_ELIM,   // kept for compatibility; not used here
  geographyStr,                     // kept for compatibility; NOT USED
  primariesRow,
  PARAMS
) {
  /* ===================== helpers ===================== */

  function toNum(x) { var v = Number(x); return isFinite(v) ? v : 0; }
  function clamp(x, lo, hi) { return x < lo ? lo : (x > hi ? hi : x); }
  function safeLog(x) { return Math.log(Math.max(x, 1e-12)); }

  function asRow6(r) {
    var out = [0,0,0,0,0,0];
    if (!Array.isArray(r)) return out;
    if (Array.isArray(r[0])) r = r[0];
    for (var i = 0; i < 6; i++) out[i] = toNum(r[i]);
    return out;
  }

  function asMatrix6(m) {
    var out = [];
    for (var i = 0; i < 6; i++) {
      var row = (m && m[i]) ? m[i] : [];
      var nr = [];
      for (var j = 0; j < 6; j++) nr.push(toNum(row[j]));
      out.push(nr);
    }
    return out;
  }

  function normaliseOverRecipients(w, recipients) {
    var s = 0, i;
    for (i = 0; i < recipients.length; i++) s += w[recipients[i]];
    if (s <= 0) {
      var u = recipients.length ? 1 / recipients.length : 0;
      for (i = 0; i < recipients.length; i++) w[recipients[i]] = u;
      for (i = 0; i < 6; i++) if (recipients.indexOf(i) === -1) w[i] = 0;
      return w;
    }
    for (i = 0; i < recipients.length; i++) w[recipients[i]] /= s;
    for (i = 0; i < 6; i++) if (recipients.indexOf(i) === -1) w[i] = 0;
    return w;
  }

  function softmaxScores(scores, recipients) {
    var maxS = -1e99, i, r;
    for (i = 0; i < recipients.length; i++) {
      r = recipients[i];
      if (scores[r] > maxS) maxS = scores[r];
    }
    var exps = {}, tot = 0;
    for (i = 0; i < recipients.length; i++) {
      r = recipients[i];
      var e = Math.exp(scores[r] - maxS);
      exps[r] = e; tot += e;
    }
    var out = [0,0,0,0,0,0];
    if (tot <= 0) {
      var u = recipients.length ? 1 / recipients.length : 0;
      for (i = 0; i < recipients.length; i++) out[recipients[i]] = u;
      return out;
    }
    for (i = 0; i < recipients.length; i++) out[recipients[i]] = exps[recipients[i]] / tot;
    return out;
  }

  // Parties (index convention must match your matrices)
  var ALP = 0, LNP = 1, GRN = 2, ON = 3, IND = 4, OTH = 5;
  var PARTY_KEYS = ["ALP","LNP","GRN","ON","IND","OTH"];

  function isMajor(p) { return p === ALP || p === LNP; }
  function isMajorPairOnly(recipientsArr) {
    if (recipientsArr.length !== 2) return false;
    var a = recipientsArr[0], b = recipientsArr[1];
    return (a === ALP && b === LNP) || (a === LNP && b === ALP);
  }

  function scalar(key, fallback) {
    // keep existing behaviour: if PARAMS.scalars not present, use fallback
    if (!PARAMS || !PARAMS.scalars) return fallback;
    var v = toNum(PARAMS.scalars[key]);
    return isFinite(v) ? v : fallback;
  }

  function ideologyRow(elimPartyKey) {
    if (!PARAMS || !PARAMS.ideology) return null;
    return PARAMS.ideology[elimPartyKey] || null;
  }

  function upliftForMinor(minorKey) {
    if (!PARAMS || !PARAMS.finalTwoUplift) return 0;
    var v = PARAMS.finalTwoUplift[minorKey];
    if (v && typeof v === "object") return toNum(v.Uplift);
    return toNum(v);
  }

  function canonicalAliveKeyFromRecipients(recipientsArr) {
    var parts = [];
    for (var i = 0; i < recipientsArr.length; i++) parts.push(PARTY_KEYS[recipientsArr[i]]);
    parts.sort();
    return parts.join('+');
  }

  // NATIONAL posterior only: key = ELIM|ALIVESET
  function posteriorScenarioPrior(elimPartyIndex, recipientsArr) {
    if (!PARAMS || !PARAMS.POSTERIOR_SCENARIOS) return null;

    var elimKey = PARTY_KEYS[elimPartyIndex];
    function canonicalAliveKeyIncludingElim(elimKey, recipientsArr) {
  var parts = [elimKey];
  for (var i = 0; i < recipientsArr.length; i++) parts.push(PARTY_KEYS[recipientsArr[i]]);
  parts.sort();
  return parts.join('+');
}

var aliveKeyExcl = canonicalAliveKeyFromRecipients(recipientsArr);
var aliveKeyIncl = canonicalAliveKeyIncludingElim(elimKey, recipientsArr);

// try both conventions
var obj =
  PARAMS.POSTERIOR_SCENARIOS[elimKey + "|" + aliveKeyIncl + "|" + classKey] ||
  PARAMS.POSTERIOR_SCENARIOS[elimKey + "|" + aliveKeyExcl + "|" + classKey] ||
  null;

if (!obj) return null;


    var row = [0,0,0,0,0,0];
    for (var i = 0; i < recipientsArr.length; i++) {
      var r = recipientsArr[i];
      var partyKey = PARTY_KEYS[r];
      row[r] = toNum(obj[partyKey]);
    }
    row = normaliseOverRecipients(row, recipientsArr);
    return row;
  }

  /* ===================== scalars ===================== */

  var SMOOTH_LAMBDA = scalar("SMOOTH_LAMBDA", 0.10);

  var MAJOR_PAIR_MAX = scalar("MAJOR_PAIR_MAX", 0.85);
  var THREE_WAY_MAX  = scalar("THREE_WAY_MAX",  0.80);
  var IND_OTH_MAX    = scalar("IND_OTH_MAX",    0.75);

  var PRIMARY_TILT_K   = scalar("PRIMARY_TILT_K",   0.20);
  var PRIMARY_TILT_MAX = scalar("PRIMARY_TILT_MAX", 0.03);

  var IND_OTH_WEAK_TILT_K   = scalar("IND_OTH_WEAK_TILT_K",   0.30);
  var IND_OTH_WEAK_TILT_MAX = scalar("IND_OTH_WEAK_TILT_MAX", 0.02);

  var AEC_PRIOR_BLEND = scalar("AEC_PRIOR_BLEND", 0.70);

  var RESERVE_MASS_WHEN_ALIVE_ZERO = scalar("RESERVE_MASS_WHEN_ALIVE_ZERO", 0.12);
  var MIN_SUPPORT = scalar("MIN_SUPPORT", 0.005);

  var FINAL_TWO_UPLIFT_MAX = scalar("FINAL_TWO_UPLIFT_MAX", 0.12);

  /* ===================== inputs ===================== */

  var prev = asRow6(prevRow);

  var aliveMask = [0,0,0,0,0,0];

// Build alive mask strictly:
//  - eliminated party is NEVER alive
//  - only numeric >0 values count as alive
var rawMask = asRow6(aliveMaskRow);
for (var i0 = 0; i0 < 6; i0++) {
  if (i0 === eRow) {
    aliveMask[i0] = 0;
  } else {
    aliveMask[i0] = (Number(rawMask[i0]) > 0) ? 1 : 0;
  }
}

  var base = asMatrix6(baseMatrix);
  var comp = asMatrix6(completedMatrix);

  var eRow = Math.max(0, Math.min(5, toNum(elimIndex) - 1));

  function alive(j) { return aliveMask[j] === 1 && j !== eRow; }

  var recipients = [];
  for (var j0 = 0; j0 < 6; j0++) if (alive(j0)) recipients.push(j0);

  var prim = asRow6(primariesRow);

  var next = prev.slice();
  next[eRow] = 0;
  if (recipients.length === 0) return [next];

  /* ===============================
   * 1) Evidence-first (with reserve if alive=0 exists)
   * =============================== */

  var evidence = [0,0,0,0,0,0];
  var observedSum = 0;

  for (var rix = 0; rix < recipients.length; rix++) {
    var r = recipients[rix];
    var v = base[eRow][r];
    if (v > 0) { evidence[r] = v; observedSum += v; }
  }

  var hasAliveZero = false;
  for (var rix2 = 0; rix2 < recipients.length; rix2++) {
    var rr = recipients[rix2];
    if (base[eRow][rr] === 0) { hasAliveZero = true; break; }
  }

  var remaining = clamp(1 - observedSum, 0, 1);

  if (remaining <= 1e-9 && hasAliveZero) {
    var reserve = clamp(RESERVE_MASS_WHEN_ALIVE_ZERO, 0, 0.40);
    var evPos = evidence.slice();
    evPos = normaliseOverRecipients(evPos, recipients);
    for (var i1 = 0; i1 < recipients.length; i1++) {
      var r1 = recipients[i1];
      evidence[r1] = (1 - reserve) * evPos[r1];
    }
    observedSum = 1 - reserve;
    remaining = reserve;
  }

  /* ===============================
   * 2) Priors (posterior-first)
   * =============================== */

  function applyMinSupportFloor(row, recipientsArr) {
    var out = row.slice();
    for (var i = 0; i < recipientsArr.length; i++) {
      var r = recipientsArr[i];
      if (out[r] <= 0) out[r] = MIN_SUPPORT;
    }
    return normaliseOverRecipients(out, recipientsArr);
  }

  function ideologyPrior(elimParty, recipientsArr) {
    var out = [0,0,0,0,0,0];
    var elimKey = PARTY_KEYS[elimParty];
    var rowObj = ideologyRow(elimKey);

    if (rowObj) {
      out[ALP] = toNum(rowObj.ALP);
      out[LNP] = toNum(rowObj.LNP);
      out[GRN] = toNum(rowObj.GRN);
      out[ON]  = toNum(rowObj.ON);
      out[IND] = toNum(rowObj.IND);
      out[OTH] = toNum(rowObj.OTH);
    } else {
      for (var i = 0; i < recipientsArr.length; i++) out[recipientsArr[i]] = 1;
    }

    out = normaliseOverRecipients(out, recipientsArr);
    return applyMinSupportFloor(out, recipientsArr);
  }

  function conditionalAecPrior(elimParty, recipientsArr) {
    var out = [0,0,0,0,0,0], s = 0;
    for (var i = 0; i < recipientsArr.length; i++) {
      var r = recipientsArr[i];
      var v = base[elimParty][r];
      if (v > 0) { out[r] = v; s += v; }
    }
    if (s <= 0) return null;
    out = normaliseOverRecipients(out, recipientsArr);
    return applyMinSupportFloor(out, recipientsArr);
  }

  function blendRows(a, b, w, recipientsArr) {
    var ww = clamp(toNum(w), 0, 1);
    var out = [0,0,0,0,0,0];
    for (var i = 0; i < recipientsArr.length; i++) {
      var r = recipientsArr[i];
      out[r] = (1 - ww) * a[r] + ww * b[r];
    }
    out = normaliseOverRecipients(out, recipientsArr);
    return applyMinSupportFloor(out, recipientsArr);
  }

  function applyBoundedMajorPrimaryTilt(priorRow, recipientsArr, elimParty) {
    if (!isMajorPairOnly(recipientsArr)) return priorRow;
    if (elimParty === IND || elimParty === OTH) return priorRow;

    var delta = clamp(PRIMARY_TILT_K * (prim[ALP] - prim[LNP]),
                      -PRIMARY_TILT_MAX, PRIMARY_TILT_MAX);

    var out = [0,0,0,0,0,0];
    out[ALP] = clamp(priorRow[ALP] + delta, 0, 1);
    out[LNP] = 1 - out[ALP];
    return applyMinSupportFloor(out, recipientsArr);
  }

  function applyWeakGrnOnTiltForIndOth(priorRow, recipientsArr, elimParty) {
    if (!(elimParty === IND || elimParty === OTH)) return priorRow;
    if (!isMajorPairOnly(recipientsArr)) return priorRow;

    var delta = clamp(IND_OTH_WEAK_TILT_K * (prim[GRN] - prim[ON]),
                      -IND_OTH_WEAK_TILT_MAX, IND_OTH_WEAK_TILT_MAX);

    var out = [0,0,0,0,0,0];
    out[ALP] = clamp(priorRow[ALP] + delta, 0, 1);
    out[LNP] = 1 - out[ALP];
    return applyMinSupportFloor(out, recipientsArr);
  }

  function applyFinalTwoUplift(priorRow, recipientsArr) {
    if (recipientsArr.length !== 2) return priorRow;
    var a = recipientsArr[0], b = recipientsArr[1];
    var major = null, minor = null;

    if (isMajor(a) && !isMajor(b)) { major = a; minor = b; }
    else if (isMajor(b) && !isMajor(a)) { major = b; minor = a; }
    else return priorRow;

    var minorKey = PARTY_KEYS[minor];
    var uplift = clamp(upliftForMinor(minorKey), 0, FINAL_TWO_UPLIFT_MAX);
    if (uplift <= 0) return priorRow;

    var out = priorRow.slice();
    var d = Math.min(uplift, out[major]);
    out[major] -= d;
    out[minor] += d;
    return applyMinSupportFloor(out, recipientsArr);
  }

  function applyWeakSmoothing(priorRow, recipientsArr, lambda) {
    var lam = clamp(toNum(lambda), 0, 1);
    if (lam <= 0) return priorRow;

    var smooth = [0,0,0,0,0,0], have = false;
    for (var i = 0; i < recipientsArr.length; i++) {
      var r = recipientsArr[i];
      var v = comp[eRow][r];
      if (v > 0) { smooth[r] = v; have = true; }
    }
    if (!have) return priorRow;

    smooth = normaliseOverRecipients(smooth, recipientsArr);
    smooth = applyMinSupportFloor(smooth, recipientsArr);

    return blendRows(priorRow, smooth, lam, recipientsArr);
  }

  // --- Posterior-first prior (national; no class) ---
  var prior = posteriorScenarioPrior(eRow, recipients);

  // safe flag (never referenced before assignment)
  var usedPosterior = (prior !== null);

  if (!prior) {
    var priorIdeo = ideologyPrior(eRow, recipients);
    var priorAec  = conditionalAecPrior(eRow, recipients);
    prior = priorIdeo;
    if (priorAec) prior = blendRows(priorIdeo, priorAec, AEC_PRIOR_BLEND, recipients);

    // keep all the existing downstream adjustments
    prior = applyBoundedMajorPrimaryTilt(prior, recipients, eRow);
    prior = applyWeakGrnOnTiltForIndOth(prior, recipients, eRow);
    prior = applyFinalTwoUplift(prior, recipients);
    prior = applyWeakSmoothing(prior, recipients, SMOOTH_LAMBDA);
  } else {
    // posterior path keeps the same stabilisers
    prior = applyMinSupportFloor(prior, recipients);
    prior = applyWeakSmoothing(prior, recipients, SMOOTH_LAMBDA);
  }

  /* ===============================
   * 3) Combine evidence + remainder * prior
   * =============================== */

  var combined = [0,0,0,0,0,0];
  for (var i3 = 0; i3 < recipients.length; i3++) {
    var rr3 = recipients[i3];
    combined[rr3] = evidence[rr3] + remaining * prior[rr3];
  }
  combined = normaliseOverRecipients(combined, recipients);
  combined = applyMinSupportFloor(combined, recipients);

  /* ===============================
   * 4) Caps with evidence floors (unchanged)
   * =============================== */

  function capMaxForScenario(elimParty, recipientsArr) {
    var cap = (recipientsArr.length === 2) ? MAJOR_PAIR_MAX : THREE_WAY_MAX;
    if (elimParty === IND || elimParty === OTH) cap = Math.min(cap, IND_OTH_MAX);
    return cap;
  }

  function capRedistributeWithEvidenceFloor(w, recipientsArr, capMax) {
    var out = w.slice();
    for (var iter = 0; iter < 10; iter++) {
      var excess = 0, headroom = 0;

      for (var i = 0; i < recipientsArr.length; i++) {
        var r = recipientsArr[i];
        var mx = Math.max(capMax, evidence[r]);
        if (out[r] > mx) excess += (out[r] - mx);
      }
      if (excess <= 1e-12) break;

      for (var j = 0; j < recipientsArr.length; j++) {
        var r2 = recipientsArr[j];
        var mx2 = Math.max(capMax, evidence[r2]);
        if (out[r2] < mx2) headroom += (mx2 - out[r2]);
      }
      if (headroom <= 1e-12) break;

      for (var k = 0; k < recipientsArr.length; k++) {
        var r3 = recipientsArr[k];
        var mx3 = Math.max(capMax, evidence[r3]);
        if (out[r3] > mx3) out[r3] = mx3;
      }
      for (var m = 0; m < recipientsArr.length; m++) {
        var r4 = recipientsArr[m];
        var mx4 = Math.max(capMax, evidence[r4]);
        if (out[r4] < mx4) out[r4] += excess * ((mx4 - out[r4]) / headroom);
      }
    }
    out = normaliseOverRecipients(out, recipientsArr);
    return applyMinSupportFloor(out, recipientsArr);
  }

  combined = capRedistributeWithEvidenceFloor(
    combined,
    recipients,
    capMaxForScenario(eRow, recipients)
  );

  /* ===============================
   * 5) Apply redistribution
   * =============================== */

  var elimVotes = prev[eRow];
  for (var k1 = 0; k1 < 6; k1++) next[k1] += elimVotes * combined[k1];

  return [next];
}
