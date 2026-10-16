import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Under jsdom the global URL is jsdom's, which node:fs rejects, so tests work with plain paths.
const here = path.dirname(fileURLToPath(String(import.meta.url)))

/** Absolute path of a file in the repository root (the folder that contains web/). */
export function repoPath(...parts: string[]): string {
  return path.resolve(here, '../../..', ...parts)
}
