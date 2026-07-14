function POSTERIOR_WEIGHTS(elimParty, aliveSet) {
  const PARAMS = GET_PARAMS();
  const table = PARAMS.POSTERIOR_SCENARIOS;
  if (!table) return null;

  const elim = String(elimParty).trim().toUpperCase();
  const alive = String(aliveSet)
    .split(/[+,|/]/g)
    .map(s => s.trim().toUpperCase())
    .filter(Boolean)
    .sort()
    .join('+');

  const key = `${elim}|${alive}`;
  const row = table[key];
  if (!row) return null;

  const PARTIES = ["ALP","LNP","GRN","ON","IND","OTH"];
  const out = PARTIES.map(p => Number(row[p]) || 0);

  const s = out.reduce((a,b)=>a+b,0);
  if (s > 0) for (let i=0;i<6;i++) out[i] /= s;

  return [out];
}
