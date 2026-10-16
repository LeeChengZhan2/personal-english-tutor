// Word-level diff for the proofreading marks: what you wrote, with deletions struck through in red and
// insertions in blue pencil. Ported from the original app (app/index.html, diffParts/proof).

export type DiffPart = { same: string } | { del: string; ins: string }

export type Segment =
  | { kind: 'same'; text: string }
  /** `del` and `ins` are trimmed; `lead`/`space` mean whitespace came before/after the change. */
  | { kind: 'change'; del: string; ins: string; lead: boolean; space: boolean }

/** Above this many token pairs the diff is skipped (it would take too long for very long messages). */
export const MAX_CELLS = 360_000

export function tokens(t: string): string[] {
  return String(t || '').match(/\s+|[\p{L}\p{N}'’_-]+|[^\s\p{L}\p{N}]/gu) ?? []
}

/** Longest-common-subsequence diff over tokens; runs of changes are grouped, and a space between two
 * changes joins them. Null when either side is empty or the texts are too long. */
export function diffParts(a: string, b: string): DiffPart[] | null {
  const A = tokens(a)
  const B = tokens(b)
  const n = A.length
  const m = B.length
  if (!n || !m || n * m > MAX_CELLS) return null
  const W = m + 1
  const L = new Uint16Array((n + 1) * W)
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      L[i * W + j] = A[i] === B[j] ? L[(i + 1) * W + j + 1]! + 1 : Math.max(L[(i + 1) * W + j]!, L[i * W + j + 1]!)
    }
  }
  const ops: ['=' | '-' | '+', string][] = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (A[i] === B[j]) {
      ops.push(['=', A[i]!])
      i++
      j++
    } else if (L[(i + 1) * W + j]! >= L[i * W + j + 1]!) {
      ops.push(['-', A[i++]!])
    } else {
      ops.push(['+', B[j++]!])
    }
  }
  while (i < n) ops.push(['-', A[i++]!])
  while (j < m) ops.push(['+', B[j++]!])

  const parts: DiffPart[] = []
  let cur: { del: string; ins: string } | null = null
  for (let k = 0; k < ops.length; k++) {
    const [op, t] = ops[k]!
    if (op === '=') {
      const next = ops[k + 1]
      const between = cur !== null && /^\s+$/.test(t) && next !== undefined && next[0] !== '='
      if (between && cur) {
        cur.del += t
        cur.ins += t
        continue
      }
      if (cur) {
        parts.push(cur)
        cur = null
      }
      parts.push({ same: t })
    } else {
      cur ??= { del: '', ins: '' }
      if (op === '-') cur.del += t
      else cur.ins += t
    }
  }
  if (cur) parts.push(cur)
  return parts
}

/** Segments ready to render as text, <del> and <ins>. Null when there is nothing to mark up (see diffParts):
 * show the original text then, never the corrected one as if the learner had typed it. */
export function proofSegments(from: string, to: string): Segment[] | null {
  const parts = diffParts(from, to)
  if (!parts) return null
  return parts.map((p) =>
    'same' in p
      ? { kind: 'same', text: p.same }
      : {
          kind: 'change',
          del: p.del.trim(),
          ins: p.ins.trim(),
          lead: /^\s/.test(p.del) || /^\s/.test(p.ins),
          space: /\s$/.test(p.del) || /\s$/.test(p.ins),
        },
  )
}

/** Whether a change needs a space before it: the original had one there and the text before doesn't end with one. */
export function needsLeadSpace(segments: Segment[], index: number): boolean {
  const s = segments[index]
  if (!s || s.kind !== 'change' || !s.lead || index === 0) return false
  const prev = segments[index - 1]!
  return prev.kind === 'same' ? !/\s$/.test(prev.text) : !prev.space
}

/** True when two different texts are too long to mark up (ProofText then shows the original). */
export function tooLongToMark(from: string, to: string): boolean {
  return Boolean(from && to && from !== to && proofSegments(from, to) === null)
}

/** True when the two texts differ in anything but whitespace. */
export function hasChanges(segments: Segment[]): boolean {
  return segments.some((s) => s.kind === 'change' && (s.del !== '' || s.ins !== ''))
}
