import { useEffect, useMemo, useState } from 'react'
import type { SubscriptionStatusPayload } from '../lib/types'

export type RemainingTime = {
  days: number
  hours: number
  minutes: number
  seconds: number
}

export function countdownFor(payload: SubscriptionStatusPayload): RemainingTime {
  const totalSeconds = Math.max(
    0,
    Math.floor(
      (new Date(payload.expires_at ?? 0).getTime() - Date.now()) / 1000,
    ),
  )
  return {
    days: Math.floor(totalSeconds / 86_400),
    hours: Math.floor((totalSeconds % 86_400) / 3_600),
    minutes: Math.floor((totalSeconds % 3_600) / 60),
    seconds: totalSeconds % 60,
  }
}

// ── Display-only countdown: never used for authorization ──
export function useSubscriptionCountdown(
  payload: SubscriptionStatusPayload | undefined,
): { remaining: RemainingTime | null; expiringSoon: boolean } {
  const [, setTick] = useState(0)

  useEffect(() => {
    if (!payload || payload.status !== 'active') return
    const intervalId = window.setInterval(() => setTick((t) => t + 1), 1000)
    return () => window.clearInterval(intervalId)
  }, [payload])

  return useMemo(() => {
    if (!payload || payload.status !== 'active' || !payload.expires_at) {
      return { remaining: null, expiringSoon: false }
    }
    const remaining = countdownFor(payload)
    return {
      remaining,
      expiringSoon: remaining.days < 3,
    }
  }, [payload])
}
