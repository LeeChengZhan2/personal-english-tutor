export function tokens(t: string): string[]
export function diffParts(a: string, b: string): ({ same: string } | { del: string; ins: string })[] | null
export function legacyProofString(a: string, b: string): string | null
