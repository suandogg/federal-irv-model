function LOAD_SIPHON_TABLE() {
  const ss = SpreadsheetApp.getActive();
  const sh = ss.getSheetByName("SIPHON");
  if (!sh) return {}; // optional

  const values = sh.getDataRange().getValues();
  if (values.length < 2) return {};

  const headers = values[0].map(h => String(h).trim().toUpperCase());
  const idx = {};
  headers.forEach((h, i) => { idx[h] = i; });

  const out = {};
  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    const entrant = String(row[idx["ENTRANT"]] ?? "").trim().toUpperCase();
    if (!entrant) continue;

    out[entrant] = {};
    for (const party of ["ALP","LNP","GRN","ON","IND","OTH"]) {
      const c = idx[party];
      if (c == null) continue;
      const v = Number(row[c]) || 0;
      out[entrant][party] = v;
    }
  }
  return out;
}
