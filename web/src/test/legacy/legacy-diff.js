// Verbatim copy of the original app's diff (app/index.html, lines 411-441), kept only to prove the
// TypeScript port in src/lib/diff.ts gives identical marks. Do not change.
/* eslint-disable */
export function tokens(t) { return String(t || "").match(/\s+|[\p{L}\p{N}'’_-]+|[^\s\p{L}\p{N}]/gu) || []; }
export function diffParts(a, b) {
  const A = tokens(a), B = tokens(b), n = A.length, m = B.length;
  if (!n || !m || n * m > 360000) return null;
  const W = m + 1, L = new Uint16Array((n + 1) * W);
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i * W + j] = A[i] === B[j] ? L[(i + 1) * W + j + 1] + 1 : Math.max(L[(i + 1) * W + j], L[i * W + j + 1]);
  const ops = []; let i = 0, j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) { ops.push(["=", A[i]]); i++; j++; }
    else if (L[(i + 1) * W + j] >= L[i * W + j + 1]) { ops.push(["-", A[i++]]); }
    else { ops.push(["+", B[j++]]); }
  }
  while (i < n) ops.push(["-", A[i++]]);
  while (j < m) ops.push(["+", B[j++]]);
  // group runs of changes; a space between two changes joins them
  const parts = []; let cur = null;
  for (let k = 0; k < ops.length; k++) {
    const [op, t] = ops[k];
    if (op === "=") {
      const between = cur && /^\s+$/.test(t) && ops[k + 1] && ops[k + 1][0] !== "=";
      if (between) { cur.del += t; cur.ins += t; continue; }
      if (cur) { parts.push(cur); cur = null; }
      parts.push({ same: t });
    } else {
      if (!cur) cur = { del: "", ins: "" };
      if (op === "-") cur.del += t; else cur.ins += t;
    }
  }
  if (cur) parts.push(cur);
  return parts;
}
// The rendering rules of the original proof() (lines 442-455), as a string: [-deleted-] {+inserted+}
export function legacyProofString(a, b) {
  const parts = diffParts(a, b);
  if (!parts) return null;
  let out = "";
  for (const p of parts) {
    if (p.same != null) { out += p.same; continue; }
    const d = p.del.trim(), n = p.ins.trim();
    if (d) out += `[-${d}-]`;
    if (d && n) out += " ";
    if (n) out += `{+${n}+}`;
    if (/\s$/.test(p.del) || /\s$/.test(p.ins)) out += " ";
  }
  return out;
}
