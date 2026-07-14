/**
 * REDIST_DIAG
 * UDF-safe diagnostics for REDIST_WEIGHTS.
 * Usage: replace REDIST_WEIGHTS(...) in a cell with REDIST_DIAG(...)
 * It spills a key/value table explaining what the function is seeing.
 */
function REDIST_DIAG(elimParty, aliveSetStr, aecRow, applyCalibration, seatState, aecRowParty) {
  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];

  const elim = String(elimParty ?? "").trim().toUpperCase();
  const aliveArrRaw = String(aliveSetStr ?? "");
  const aliveArr = aliveArrRaw
    .split("+")
    .map(x => String(x).trim().toUpperCase())
    .filter(p => PARTIES.includes(p));

  const alive = new Set(aliveArr);

  let base = aecRow;
  if (Array.isArray(base) && Array.isArray(base[0])) base = base[0];
  base = PARTIES.map((_, i) => Number(base?.[i]) || 0);

  const PARAMS = GET_PARAMS_UDF();
  const wantCal = (applyCalibration === true || String(applyCalibration).trim().toUpperCase() === "TRUE");
  const state = String(seatState || "NAT").trim().toUpperCase();
  const rowParty = String(aecRowParty ?? "").trim().toUpperCase();

  // supported/missing (by base > 0 on alive)
  const supported = [];
  const missing = [];
  for (let i = 0; i < 6; i++) {
    if (!alive.has(PARTIES[i])) continue;
    (base[i] > 0 ? supported : missing).push(i);
  }

  const aliveKey = aliveArr.slice().sort().join("+");
  const postKey = `${elim}|${aliveKey}`;
  const postObj = PARAMS?.POSTERIOR_SCENARIOS?.[postKey] || null;

  // baseline lookup
  const baseMap = PARAMS?.baselines?.LNP_TO_ON || null;
  const baseON = baseMap ? (baseMap[state] ?? baseMap["NAT"]) : null;

  // Decide which branch *would* fire
  let branch = "UNKNOWN";
  const caseA_ok =
    rowParty === elim &&
    supported.length === alive.size &&
    base.some(v => v > 0);

  const baseline_ok =
    elim === "LNP" &&
    alive.has("ALP") &&
    alive.has("ON") &&
    isFinite(baseON);

  if (caseA_ok) branch = "A: AEC_FULL_COVER";
  else if (baseline_ok) branch = "B: STATE_BASELINE";
  else if (postObj) branch = "C: POSTERIOR";
  else if (PARAMS?.ideology?.[elim]) branch = "D: IDEOLOGY";
  else branch = "E: UNIFORM";

  // helper pretty
  const fmtArr = (arr) => arr.map(i => PARTIES[i]).join(",");

  // spill as key/value rows
  return [
    ["branch", branch],
    ["elim", elim],
    ["aliveSetStr_raw", aliveArrRaw],
    ["aliveArr_parsed", aliveArr.join("+")],
    ["alive_has_ON", String(alive.has("ON"))],
    ["seatState", state],
    ["aecRowParty_arg", rowParty],
    ["aecRow_sum", base.reduce((a,b)=>a+b,0)],
    ["aecRow_values", JSON.stringify(base)],
    ["supported_idxs", supported.join(",")],
    ["supported_parties", fmtArr(supported)],
    ["missing_idxs", missing.join(",")],
    ["missing_parties", fmtArr(missing)],
    ["caseA_ok", String(caseA_ok)],
    ["baseline_map_exists", String(!!baseMap)],
    ["baseline_baseON", String(baseON)],
    ["baseline_ok", String(baseline_ok)],
    ["postKey", postKey],
    ["postObj_exists", String(!!postObj)],
    ["postObj_preview", postObj ? JSON.stringify(postObj) : ""],
    ["wantCal", String(wantCal)],
    ["ideology_exists", String(!!PARAMS?.ideology?.[elim])]
  ];
}
