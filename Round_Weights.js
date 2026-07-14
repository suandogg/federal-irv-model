/**
 * ROUND_WEIGHTS
 * Wrapper to ensure REDIST_WEIGHTS is executed ONCE per round
 * and spills across 6 columns.
 *
 * Returns: 1×6 row vector
 */
function ROUND_WEIGHTS(elimParty, aliveSetStr, aecRow, applyCalibration) {
  const res = REDIST_WEIGHTS(elimParty, aliveSetStr, aecRow, applyCalibration);
  if (!res || !res[0]) return [[0,0,0,0,0,0]];
  return [res[0]]; // force 1×6 spill
}
