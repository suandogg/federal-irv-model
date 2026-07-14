function BUILD_SCENARIO_STATS() {
  const ss = SpreadsheetApp.getActive();
  const src = ss.getSheetByName('SEAT_PREF_FLOWS_LONG');
  if (!src) throw new Error('SEAT_PREF_FLOWS_LONG not found');

  const data = src.getDataRange().getValues();
  const headers = data[0];

  const idx = {};
  headers.forEach((h, i) => idx[h] = i);

  const REQUIRED = ['Seat','Eliminated','AliveSet','Recipient','Votes'];
  REQUIRED.forEach(h => {
    if (!(h in idx)) throw new Error(`Missing column: ${h}`);
  });

  // --- aggregate ---
  const agg = {};
  const seatsByScenario = {};

  for (let r = 1; r < data.length; r++) {
    const row = data[r];

    const seat = row[idx.Seat];
    const elim = row[idx.Eliminated];
    const alive = row[idx.AliveSet];
    const rec = row[idx.Recipient];
    const votes = Number(row[idx.Votes]) || 0;

    if (!seat || !elim || !alive || !rec || votes <= 0) continue;

    const scenarioKey = `${elim}→${alive}`;
    const cellKey = `${scenarioKey}|${rec}`;

    if (!agg[cellKey]) {
      agg[cellKey] = {
        Eliminated: elim,
        AliveSet: alive,
        Recipient: rec,
        Votes: 0,
        ScenarioKey: scenarioKey
      };
    }

    agg[cellKey].Votes += votes;

    if (!seatsByScenario[scenarioKey]) {
      seatsByScenario[scenarioKey] = new Set();
    }
    seatsByScenario[scenarioKey].add(seat);
  }

  // --- compute scenario totals ---
  const scenarioTotals = {};
  Object.values(agg).forEach(o => {
    scenarioTotals[o.ScenarioKey] =
      (scenarioTotals[o.ScenarioKey] || 0) + o.Votes;
  });

  // --- output ---
  const out = [[
    'Eliminated',
    'AliveSet',
    'Recipient',
    'Votes',
    'ScenarioTotal',
    'Share',
    'Seats'
  ]];

  Object.values(agg)
    .sort((a,b) =>
      a.ScenarioKey.localeCompare(b.ScenarioKey) ||
      a.Recipient.localeCompare(b.Recipient)
    )
    .forEach(o => {
      const total = scenarioTotals[o.ScenarioKey];
      out.push([
        o.Eliminated,
        o.AliveSet,
        o.Recipient,
        o.Votes,
        total,
        o.Votes / total,
        seatsByScenario[o.ScenarioKey].size
      ]);
    });

  let sh = ss.getSheetByName('SCENARIO_STATS');
  if (!sh) sh = ss.insertSheet('SCENARIO_STATS');
  else sh.clear();

  sh.getRange(1,1,out.length,out[0].length).setValues(out);
  sh.setFrozenRows(1);
}
