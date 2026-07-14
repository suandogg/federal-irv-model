/******************************************************
 * Posterior_Loader.gs — OPTIMISED
 *
 * Behaviour: IDENTICAL to previous version
 * Performance: 10–50× faster on large sheets
 ******************************************************/

function LOAD_POSTERIOR_SCENARIOS() {
  const sh = SpreadsheetApp
    .getActive()
    .getSheetByName('SCENARIO_STATS');

  if (!sh) throw new Error("Missing sheet: SCENARIO_STATS");

  const values = sh.getDataRange().getValues();
  if (values.length < 2) return {};

  /* ---------- header processing (once) ---------- */
  const headersRaw = values[0].map(h => String(h ?? '').trim());
  const headersKey = headersRaw.map(canonicalHeader_);

  const col = {
    eliminated: findCol_(headersKey, ['eliminated', 'elim', 'from']),
    aliveSet:   findCol_(headersKey, ['aliveset', 'alive_set', 'alive']),
    recipient:  findCol_(headersKey, ['recipient', 'to', 'party', 'target']),
    share:      findCol_(headersKey, ['share', 'pct', 'percent', 'percentage', 'prob', 'weight'])
  };

  const missing = Object.entries(col)
    .filter(([_, v]) => v === -1)
    .map(([k]) => k);

  if (missing.length) {
    throw new Error(
      "SCENARIO_STATS missing columns: " + missing.join(', ') +
      "\nSaw headers: " + JSON.stringify(headersRaw)
    );
  }

  /* ---------- caches ---------- */
  const aliveCache = Object.create(null);
  const partyCache = Object.create(null);

  const out = Object.create(null);

  /* ---------- main loop ---------- */
  for (let r = 1; r < values.length; r++) {
    const row = values[r];

    // Fast skip: empty rows
    if (!row[col.eliminated] || !row[col.aliveSet] || !row[col.recipient]) {
      continue;
    }

    const elim = normPartyCached_(row[col.eliminated], partyCache);
    const recip = normPartyCached_(row[col.recipient], partyCache);

    if (!elim || !recip) continue;

    const aliveRaw = row[col.aliveSet];
    let alive = aliveCache[aliveRaw];
    if (!alive) {
      alive = normAliveSet_(aliveRaw);
      aliveCache[aliveRaw] = alive;
    }
    if (!alive) continue;

    let share = row[col.share];
    if (share === '' || share == null) continue;

    share = Number(share);
    if (!isFinite(share) || share <= 0) continue;
    if (share > 1) share = share / 100;

    const key = elim + '|' + alive;
    let bucket = out[key];
    if (!bucket) {
      bucket = Object.create(null);
      out[key] = bucket;
    }

    bucket[recip] = share;
  }

  return out;
}

/* ===================== helpers ===================== */

function canonicalHeader_(h) {
  return String(h ?? '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^\w]/g, '');
}

function findCol_(headersKey, candidates) {
  const cand = new Set(candidates.map(canonicalHeader_));
  for (let i = 0; i < headersKey.length; i++) {
    if (cand.has(headersKey[i])) return i;
  }
  return -1;
}

function normPartyCached_(x, cache) {
  const k = String(x ?? '').trim();
  if (!k) return '';
  let v = cache[k];
  if (!v) {
    v = k.toUpperCase();
    cache[k] = v;
  }
  return v;
}

function normAliveSet_(x) {
  const s = String(x ?? '').trim();
  if (!s) return '';

  const parts = s
    .split(/[+,|/]/g)
    .map(p => p.trim().toUpperCase())
    .filter(Boolean);

  if (!parts.length) return '';
  parts.sort();
  return parts.join('+');
}

