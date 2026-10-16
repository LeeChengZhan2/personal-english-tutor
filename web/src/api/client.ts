import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

/** The API's response and request bodies (generated from the server's OpenAPI schema). */
export type Schemas = components['schemas']

/** Every failed request becomes one of these: the server's {code, message}, or code "offline". */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  get offline(): boolean {
    return this.code === 'offline'
  }
}

export const api = createClient<paths>({ baseUrl: '/' })

interface FetchResult {
  data?: unknown
  error?: unknown
  response: Response
}

/** The data of a request, or an ApiError. Aborted requests rethrow the AbortError untouched. */
export async function unwrap<R extends FetchResult>(request: Promise<R>): Promise<NonNullable<R['data']>> {
  let result: R
  try {
    result = await request
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, 'offline', "Can't reach the app's server. Is it still running?")
  }
  const { data, error, response } = result
  if (!response.ok || error !== undefined) {
    if (response.status === 502 || response.status === 504 || response.status === 0) {
      // the dev proxy answers 502/504 when the Python server is down
      const proxyDown = !response.headers.get('content-type')?.includes('application/json')
      if (proxyDown) throw new ApiError(0, 'offline', "Can't reach the app's server. Is it still running?")
    }
    const body = (error ?? {}) as { code?: string; message?: string; details?: unknown }
    throw new ApiError(response.status, body.code ?? 'http_error', body.message ?? `Request failed (${response.status}).`, body.details)
  }
  return data as NonNullable<R['data']>
}
