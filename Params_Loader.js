/******************************************************
 * PARAMS_LOADER.gs — FAST + SAFE + DETERMINISTIC
 *
 * FIXES:
 * - PARAMS sheet read ONCE (no O(N×M) scans)
 * - UDFs NEVER touch sheets
 * - Manual rebuild only
 ******************************************************/

const PARAMS_CACHE_KEY = "IRV_PARAMS_SNAPSHOT_V1";

/* ============================
 * MENU
 * ============================ */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("IRV Model")
    .addItem("Rebuild PARAMS cache", "REBUILD_PARAMS_CACHE")
    .addItem("Clear PARAMS cache", "CLEAR_PARAMS_CACHE")
    .addToUi();
}

/* ============================
 * IDEOLOGY TABLE LOADER
 * ============================ */
function LOAD_IDEOLOGY_TABLE_() {
  const sh = SpreadsheetApp
    .getActive()
    .getSheetByName("IDEOLOGY");

  if (!sh) return {};

  const values = sh.getDataRange().getValues();
  if (values.length < 2) return {};

  const headers = values[0]
    .map(h => String(h).trim().toUpperCase());

  const out = Object.create(null);

  for (let r = 1; r < values.length; r++) {
    const elim = String(values[r][0] ?? "")
      .trim()
      .toUpperCase();

    if (!elim) continue;

    const row = Object.create(null);

    for (let c = 1; c < headers.length; c++) {
      const party = headers[c];
      const v = Number(values[r][c]);
      if (isFinite(v) && v > 0) {
        row[party] = v;
      }
    }

    out[elim] = row;
  }

  return out;
}

/* ============================
 * CACHE CONTROL
 * ============================ */
function REBUILD_PARAMS_CACHE() {
  console.time("PARAMS rebuild");

  const params = LOAD_PARAMS_FROM_SHEETS_();
  const json = JSON.stringify(params);

  CacheService.getScriptCache().put(PARAMS_CACHE_KEY, json, 21600);
  PropertiesService.getScriptProperties().setProperty(PARAMS_CACHE_KEY, json);

  console.timeEnd("PARAMS rebuild");
  SpreadsheetApp.getActive().toast("PARAMS cache rebuilt", "IRV Model", 3);
}

function CLEAR_PARAMS_CACHE() {
  CacheService.getScriptCache().remove(PARAMS_CACHE_KEY);
  PropertiesService.getScriptProperties().deleteProperty(PARAMS_CACHE_KEY);
  SpreadsheetApp.getActive().toast("PARAMS cache cleared", "IRV Model", 3);
}

/* ============================
 * UDF-SAFE ACCESSOR
 * ============================ */
function GET_PARAMS_UDF() {
  // 1) Script cache (fast, volatile)
  const cache = CacheService.getScriptCache().get(PARAMS_CACHE_KEY);
  if (cache) return JSON.parse(cache);

  // 2) Script properties (slow, persistent)
  const prop = PropertiesService.getScriptProperties().getProperty(PARAMS_CACHE_KEY);
  if (prop) {
    // rehydrate cache opportunistically
    CacheService.getScriptCache().put(PARAMS_CACHE_KEY, prop, 21600);
    return JSON.parse(prop);
  }

  // 3) Absolute last-resort fallback (SAFE, deterministic)
  //    This prevents sheet-wide failure during recalculation storms
  return {
    scalars: {
      AEC_PRIOR_BLEND: 0.7,
      K_DIRICHLET: 50,
      POSTERIOR_SHRINK_K: 30,
      SIPHON_STRENGTH: 0.35,
      SIPHON_DONOR_CAP: 0.25,
      POST_ENTRY_STRENGTH: 0.75,
      POST_ENTRY_FLOOR: 0.15,
      AEC_2CP_ANCHOR_ON: 0.15,
      AEC_BLEND_COV_MIN: 0.5,
      AEC_BLEND_COV_MAX: 0.9,
      AEC_BLEND_STRENGTH: 0.75,
      AEC_MISMATCH_MAX: 0.3,
      AEC_ANCHOR_WHEN_MISS: 0.4
    },
    baselines: {},
    POSTERIOR_SCENARIOS: {},
    siphon: {},
    ideology: {}
  };
}


/* ============================
 * PARAMS LOADER (FAST)
 * ============================ */
function LOAD_PARAMS_FROM_SHEETS_() {
  console.time("LOAD_PARAMS_FROM_SHEETS");

  const PARAMS = {};

  /* ---- Read PARAMS sheet ONCE ---- */
  const paramMap = LOAD_PARAM_MAP_();

  /* ---- Scalars ---- */
  PARAMS.scalars = {
    AEC_PRIOR_BLEND:      paramMap.AEC_PRIOR_BLEND ?? 0.7,
    K_DIRICHLET:          paramMap.K_DIRICHLET ?? 50,
    POSTERIOR_SHRINK_K:   paramMap.POSTERIOR_SHRINK_K ?? 30,
    SIPHON_STRENGTH:      paramMap.SIPHON_STRENGTH ?? 0.35,
    SIPHON_DONOR_CAP:     paramMap.SIPHON_DONOR_CAP ?? 0.25,

    POST_ENTRY_STRENGTH:  paramMap.POST_ENTRY_STRENGTH ?? 0.75,
    POST_ENTRY_FLOOR:     paramMap.POST_ENTRY_FLOOR ?? 0.15,

    AEC_2CP_ANCHOR_ON:    paramMap.AEC_2CP_ANCHOR_ON ?? 0.15,

    AEC_BLEND_COV_MIN:    paramMap.AEC_BLEND_COV_MIN ?? 0.5,
    AEC_BLEND_COV_MAX:    paramMap.AEC_BLEND_COV_MAX ?? 0.9,
    AEC_BLEND_STRENGTH:   paramMap.AEC_BLEND_STRENGTH ?? 0.75,
    AEC_MISMATCH_MAX:     paramMap.AEC_MISMATCH_MAX ?? 0.3,
    AEC_ANCHOR_WHEN_MISS: paramMap.AEC_ANCHOR_WHEN_MISS ?? 0.4
  };

  /* ---- Baselines ---- */
  PARAMS.baselines = {
    LNP_TO_ON: {
      NSW: 0.743, QLD: 0.733, VIC: 0.699,
      WA:  0.692, SA:  0.685, NT:  0.666,
      TAS: 0.592, NAT: 0.716
    }
  };

  /* ---- Heavy tables ---- */
  console.time("Posterior load");
  PARAMS.POSTERIOR_SCENARIOS = LOAD_POSTERIOR_SCENARIOS();
  console.timeEnd("Posterior load");

  console.time("Siphon load");
  PARAMS.siphon = LOAD_SIPHON_TABLE();
  console.timeEnd("Siphon load");

  console.time("Ideology load");
  PARAMS.ideology = LOAD_IDEOLOGY_TABLE_();
  console.timeEnd("Ideology load");

  console.timeEnd("LOAD_PARAMS_FROM_SHEETS");
  return PARAMS;
}

/* ============================
 * PARAM MAP (FAST)
 * ============================ */
function LOAD_PARAM_MAP_() {
  const sh = SpreadsheetApp.getActive().getSheetByName("PARAMS");
  if (!sh) return {};

  const values = sh.getRange(1, 1, sh.getLastRow(), 2).getValues();
  const map = Object.create(null);

  for (let i = 0; i < values.length; i++) {
    const k = String(values[i][0] ?? '').trim().toUpperCase();
    if (!k) continue;

    const v = Number(values[i][1]);
    if (isFinite(v)) map[k] = v;
  }
  return map;
}
