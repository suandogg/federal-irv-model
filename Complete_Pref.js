/**
* COMPLETE_PREF(baseMatrixRange)
* baseMatrixRange: N×N range of direct first-preference flows (rows = source, cols = destination), e.g. K4:P9.
* Returns an N×N matrix C whose j-th column gives the total
* probability that each source eventually lands at destination j
* after any sequence of eliminations among the other parties
* (absorbing Markov chain closure).
*
* Cells may be 0 or blank; blanks are treated as 0.
*/
function COMPLETE_PREF(baseMatrixRange) {
 if (!baseMatrixRange || !baseMatrixRange.length || !baseMatrixRange[0].length) {
   throw new Error('COMPLETE_PREF: provide an N×N range (e.g. K4:P9).');
 }
 // Convert to numeric matrix, blank->0
 const P = baseMatrixRange.map(row => row.map(x => (x === '' || x == null) ? 0 : Number(x)));
 const n = P.length;
 if (P.some(r => r.length !== n)) throw new Error('COMPLETE_PREF: range must be square.');


 // Utility: matrix ops
 const eye = (m) => Array.from({length:m}, (_,i)=>Array.from({length:m},(_,j)=> i===j?1:0));
 const submatrix = (A, rows, cols) => rows.map(i => cols.map(j => A[i][j]));
 const matAdd = (A,B, sgn=1) => A.map((r,i)=>r.map((v,j)=>v + sgn*B[i][j]));
 const matMul = (A,B) => {
   const m=A.length, k=A[0].length, n=B[0].length;
   const C=Array.from({length:m},()=>Array(n).fill(0));
   for (let i=0;i<m;i++) for (let t=0;t<k;t++) {
     const a=A[i][t];
     if (a!==0) for (let j=0;j<n;j++) C[i][j]+=a*B[t][j];
   }
   return C;
 };
 const inv = (A) => { // Gauss-Jordan
   const n = A.length;
   const M = A.map(r=>r.slice());
   const I = eye(n);
   for (let i=0;i<n;i++){
     // pivot
     let p=i; for(let r=i+1;r<n;r++) if(Math.abs(M[r][i])>Math.abs(M[p][i])) p=r;
     if (Math.abs(M[p][i])<1e-12) throw new Error('COMPLETE_PREF: singular (I-R) for some destination.');
     if (p!==i){ [M[i],M[p]]=[M[p],M[i]]; [I[i],I[p]]=[I[p],I[i]]; }
     const d=M[i][i];
     for(let j=0;j<n;j++){ M[i][j]/=d; I[i][j]/=d; }
     for(let r=0;r<n;r++) if(r!==i){
       const f=M[r][i];
       if (f!==0) for (let j=0;j<n;j++){ M[r][j]-=f*M[i][j]; I[r][j]-=f*I[i][j]; }
     }
   }
   return I;
 };


 // Build completed matrix C (n×n)
 const C = Array.from({length:n}, ()=>Array(n).fill(0));


 for (let dest=0; dest<n; dest++) {
   // indices of "other" states (alive set excluding the destination)
   const others = Array.from({length:n},(_,i)=>i).filter(i=>i!==dest);


   // R = P[others, others]
   const R = submatrix(P, others, others);


   // d = P[others, dest]  (column vector)
   const d = others.map(i => [P[i][dest]]);


   // Fundamental matrix: (I - R)^-1
   const I = eye(others.length);
   const F = inv(matAdd(I, R, -1)); // (I - R)^{-1}


   // c = F * d  (absorption probabilities into dest from each "other" source)
   const c = matMul(F, d).map(v => v[0]);


   // place into column dest of C
   others.forEach((i, k) => { C[i][dest] = c[k]; });
   // and C[dest][dest] = 0 by definition (a party doesn’t “flow” to itself)
 }


 // Return as a 2D array to Sheets
 return C;
}
