import { ApiError, getAccessToken, getStoredRefreshToken, setAccessToken, storeRefreshToken } from './api'

// ── Authenticated file download (private storage has no public URLs) ──
async function refreshAccessToken(): Promise<string | null> {
  const stored = getStoredRefreshToken()
  if (!stored) return null
  try {
    const response = await fetch('/api/v1/auth/token/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: stored }),
    })
    if (!response.ok) return null
    const data = (await response.json()) as { access: string; refresh?: string }
    setAccessToken(data.access)
    if (data.refresh) storeRefreshToken(data.refresh)
    return data.access
  } catch {
    return null
  }
}

async function fetchBlob(path: string): Promise<Blob> {
  const doFetch = (token: string | null): Promise<Response> =>
    fetch(`/api/v1${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })

  let response = await doFetch(getAccessToken())
  if (response.status === 401) {
    const fresh = await refreshAccessToken()
    if (fresh) response = await doFetch(fresh)
  }

  if (!response.ok) {
    throw new ApiError(
      response.status === 410
        ? 'This file has expired and can no longer be downloaded.'
        : `Download failed with status ${response.status}.`,
      { code: response.status === 410 ? 'artifact_expired' : `http_${response.status}`, status: response.status },
    )
  }
  return response.blob()
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const blob = await fetchBlob(path)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
