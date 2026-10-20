import type { SubscriptionPlanValue } from './types'

export function isSubscriptionRequiredError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    (error as { code?: string }).code === 'seller_subscription_required'
  )
}

export const SUBSCRIPTION_PLAN_LABELS: Record<SubscriptionPlanValue, string> = {
  monthly: 'Monthly',
  semiannual: 'Semi-annual',
  annual: 'Annual',
}
