const RESPONSE_HEADERS = ['content-type', 'cache-control', 'retry-after', 'x-request-id']

type FetchInitWithDuplex = RequestInit & { duplex: 'half' }

export async function proxyBackend(request: Request, path: string): Promise<Response> {
  const baseUrl = process.env.TENNIX_BACKEND_URL
  if (!baseUrl) {
    return Response.json(
      { error: { code: 'internal_error', message: 'Backend URL is not configured', details: {} } },
      { status: 500 },
    )
  }

  const incoming = new URL(request.url)
  const target = new URL(path, baseUrl)
  target.search = incoming.search
  const headers = new Headers({
    'Content-Type': request.headers.get('content-type') ?? 'application/json',
  })
  const requestId = request.headers.get('x-request-id')
  if (requestId) headers.set('X-Request-ID', requestId)
  const accept = request.headers.get('accept')
  if (accept) headers.set('Accept', accept)
  const lastEventId = request.headers.get('last-event-id')
  if (lastEventId) headers.set('Last-Event-ID', lastEventId)

  let upstream: Response
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
      cache: 'no-store',
      duplex: 'half',
    } as FetchInitWithDuplex)
  } catch {
    return Response.json(
      { error: { code: 'internal_error', message: 'Backend is unavailable', details: {} } },
      { status: 502 },
    )
  }

  const responseHeaders = new Headers()
  for (const name of RESPONSE_HEADERS) {
    const value = upstream.headers.get(name)
    if (value) responseHeaders.set(name, value)
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders })
}
