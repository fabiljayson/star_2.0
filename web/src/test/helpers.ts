import { vi } from 'vitest'

export function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function emptyResponse(status = 204): Response {
  return new Response(null, { status })
}

export type FetchCall = { url: string; init?: RequestInit | undefined }

type Route = {
  match: (url: string) => boolean
  respond: (url: string, init?: RequestInit | undefined) => Response | Promise<Response>
}

export function stubFetch(): {
  on: (pattern: string | RegExp, respond: Route['respond']) => void
  calls: FetchCall[]
  fn: ReturnType<typeof vi.fn>
} {
  const routes: Route[] = []
  const calls: FetchCall[] = []

  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push({ url, init })
    const route = routes.find((candidate) => candidate.match(url))
    if (!route) {
      throw new Error(`Unexpected fetch: ${init?.method ?? 'GET'} ${url}`)
    }
    return route.respond(url, init)
  })

  vi.stubGlobal('fetch', fn)

  return {
    calls,
    fn,
    on(pattern, respond) {
      routes.push({
        match: (url) =>
          typeof pattern === 'string' ? url.includes(pattern) : pattern.test(url),
        respond,
      })
    },
  }
}
