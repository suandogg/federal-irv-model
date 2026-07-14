/**
* MARKOV_REDIST_POSTERIOR
*
* LIVE redistribution wrapper.
*
* This function is the ACTIVE engine called by the sheet.
* It delegates all logic to MARKOV_NEXT_FALLBACK, which handles:
*  - Posterior scenarios
*  - AEC / ideology fallback
*  - Reserve mass
*  - Geography conditioning
*
* voteRow:          1×6 current vote shares
* eliminatedIndex:  1..6 index of eliminated party
* seatClass:        "InnerMetro" | "OuterMetro" | "Provincial" | "Rural"
* PARAMS:           global params object (must include POSTERIOR_SCENARIOS)
*
* Returns: [1×6 updated vote row]
*/
function MARKOV_REDIST_POSTERIOR(
 voteRow,
 eliminatedIndex,
 seatClass,
 PARAMS
) {
 // ---- normalise inputs ----
 const prev = Array.isArray(voteRow[0]) ? voteRow[0] : voteRow;
 const elimIndex = Number(eliminatedIndex);


 // ---- build alive mask from current votes ----
 const aliveMask = [];
 for (let i = 0; i < 6; i++) {
   aliveMask[i] =
     (i !== (elimIndex - 1) && Number(prev[i]) > 0)
       ? 1
       : 0;
 }


 // ---- dummy matrices (not used by posterior path) ----
 // Required only for signature compatibility
 const ZERO_ROW = [0,0,0,0,0,0];
 const ZERO_MATRIX = [
   ZERO_ROW, ZERO_ROW, ZERO_ROW,
   ZERO_ROW, ZERO_ROW, ZERO_ROW
 ];


 // ---- call the real engine ----
 return MARKOV_NEXT_FALLBACK(
   prev,                // prevRow
   elimIndex,           // eliminated index (1-based)
   ZERO_MATRIX,         // baseMatrix (unused for posterior)
   aliveMask,           // aliveMaskRow
   ZERO_MATRIX,         // completedMatrix
   null, null, null, null, // legacy unused args
   seatClass,           // geography / class
   prev,                // primaries (safe fallback)
   PARAMS               // params
 );
}
