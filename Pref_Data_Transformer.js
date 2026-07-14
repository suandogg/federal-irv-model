/**
 * TRANSFORM_SEAT_PREF_FLOWS_TO_LONG
 *
 * Reads "SEAT PREF FLOWS" wide-format sheet and emits long-format rows:
 *   Seat | Eliminated | AliveSet | Recipient | Votes | Share
 *
 * Assumptions (based on your latest note):
 * - Party block headers are merged in ROW 1 (ALP/LNP/GRN/ON/IND/OTH)
 * - Column subheaders like "Votes to GRN", "% to GRN" live in ROW 3
 * - Data starts on ROW 4
 * - "Division" column exists (seat name)
 *
 * AliveSet is defined empirically: recipients with Votes > 0 in that block.
 */

function TRANSFORM_SEAT_PREF_FLOWS_TO_LONG() {
  const ss = SpreadsheetApp.getActive();
  const src = ss.getSheetByName('SEAT PREF FLOWS');
  if (!src) throw new Error('SEAT PREF FLOWS sheet not found');

  const PARTY_HEADER_ROW = 1; // merged party headers
  const SUBHEADER_ROW = 3;    // "Votes to X" lives here
  const DATA_START_ROW = 4;   // first data row

  const PARTIES = ['ALP', 'LNP', 'GRN', 'ON', 'IND', 'OTH'];
  const OUT_SHEET = 'SEAT_PREF_FLOWS_LONG';

  const lastRow = src.getLastRow();
  const lastCol = src.getLastColumn();
  if (lastRow < DATA_START_ROW) throw new Error('No data rows found');

  // --- Read headers ---
  const partyHeaderRaw = src.getRange(PARTY_HEADER_ROW, 1, 1, lastCol).getDisplayValues()[0];
  const subHeaderRaw = src.getRange(SUBHEADER_ROW, 1, 1, lastCol).getDisplayValues()[0];

  // Forward-fill merged party headers across columns
  const ownerByCol = Array(lastCol).fill('');
  let currentOwner = '';
  for (let c = 0; c < lastCol; c++) {
    const v = String(partyHeaderRaw[c] || '').trim();
    if (v) currentOwner = v;
    ownerByCol[c] = currentOwner; // may still be ''
  }

  // Normalize helper
  const norm = (s) => String(s || '')
    .trim()
    .toUpperCase()
    .replace(/\u00A0/g, ' ');

  // Find seat column (Division / Seat / Electorate)
  const seatCol = subHeaderRaw.findIndex(h => {
    const nh = norm(h).replace(/\s+/g, '');
    return nh === 'DIVISION' || nh === 'SEAT' || nh === 'ELECTORATE';
  });
  if (seatCol === -1) {
    throw new Error('Seat column not found (looked for Division / Seat / Electorate in row 3)');
  }

  // Build mapping: eliminatedParty -> recipientParty -> colIndex
  // We ONLY take columns inside the eliminated party's block (ownerByCol)
  // and ONLY where subheader matches "Votes to XXX" or "Votes XXX" patterns.
  const voteColsByElim = {};
  PARTIES.forEach(p => voteColsByElim[p] = {});

  for (let c = 0; c < lastCol; c++) {
    const owner = norm(ownerByCol[c]);
    const sh = String(subHeaderRaw[c] || '').trim();

    if (!PARTIES.includes(owner)) continue;

    // Match:
    // "Votes to GRN"
    // "Votes GRN" (your sheet has at least one "Votes LNP" style)
    let m = sh.match(/^Votes\s+(?:to\s+)?(ALP|LNP|GRN|ON|IND|OTH)$/i);
    if (!m) continue;

    const recipient = norm(m[1]);
    if (!PARTIES.includes(recipient)) continue;

    // We allow flows to any recipient (including ALP in LNP block etc.)
    voteColsByElim[owner][recipient] = c;
  }

  // --- Read data ---
  const data = src.getRange(DATA_START_ROW, 1, lastRow - DATA_START_ROW + 1, lastCol).getValues();

  const out = [[
    'Seat',
    'Eliminated',
    'AliveSet',
    'Recipient',
    'Votes',
    'Share'
  ]];

  // Main loop
  for (let r = 0; r < data.length; r++) {
    const row = data[r];
    const seat = row[seatCol];
    if (!seat) continue;

    for (const elim of PARTIES) {
      const cols = voteColsByElim[elim];
      const recipients = Object.keys(cols);
      if (!recipients.length) continue;

      // Collect positive flows only
      let total = 0;
      const flows = [];
      for (const rec of recipients) {
        const v = Number(row[cols[rec]]) || 0;
        if (v > 0) {
          flows.push([rec, v]);
          total += v;
        }
      }

      // If nothing distributed in this block for this seat, skip
      if (total <= 0 || flows.length === 0) continue;

      // AliveSet = recipients with votes > 0 (sorted for stable scenario keys)
      const aliveSetArr = flows.map(x => x[0]).sort();
      const aliveSet = aliveSetArr.join('|');

      // Output one row per recipient
      for (const [rec, v] of flows) {
        out.push([
          seat,
          elim,
          aliveSet,
          rec,
          v,
          v / total
        ]);
      }
    }
  }

  // --- Write output ---
  let outSheet = ss.getSheetByName(OUT_SHEET);
  if (!outSheet) outSheet = ss.insertSheet(OUT_SHEET);
  outSheet.clear();
  outSheet.getRange(1, 1, out.length, out[0].length).setValues(out);
  outSheet.setFrozenRows(1);
  outSheet.autoResizeColumns(1, 6);
}
