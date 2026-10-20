import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { apiFetch } from '../../lib/api'
import { formatDate, formatMoney } from '../../lib/format'
import { useSubscriptionCountdown } from '../../lib/subscriptionCountdown'
import type {
  SubscriptionPayment,
  SubscriptionPlanValue,
  SubscriptionStatusPayload,
} from '../../lib/types'

const PLAN_LABELS: Record<SubscriptionPlanValue, string> = {
  monthly: 'Monthly',
  semiannual: 'Semi-annual',
  annual: 'Annual',
}

type CheckoutPhase = 'idle' | 'pending' | 'succeeded' | 'failed'

export function SubscriptionPage() {
  const { hasRole } = useAuth()
  const queryClient = useQueryClient()
  const [phase, setPhase] = useState<CheckoutPhase>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [checkoutPaymentId, setCheckoutPaymentId] = useState<string | null>(null)

  // Periodic refetch (15 min while active) + window-focus refetch keep the
  // server as the only source of truth for selling rights. The visible
  // countdown is display-only and ticks locally.
  const statusQuery = useQuery({
    queryKey: ['mp-subscription-status'],
    queryFn: () => apiFetch<SubscriptionStatusPayload>('/marketplace/subscription/'),
    refetchInterval: ({ state }) =>
      state.data?.status === 'active' ? 15 * 60 * 1000 : false,
    retry: false,
  })
  const payload = statusQuery.data

  const paymentQuery = useQuery({
    queryKey: ['mp-subscription-payment', checkoutPaymentId],
    queryFn: () =>
      apiFetch<SubscriptionPayment>(
        `/marketplace/subscription/payments/${checkoutPaymentId}/`,
      ),
    enabled: checkoutPaymentId !== null,
    refetchInterval: 2_500,
    retry: false,
  })

  function invalidateStatus(): void {
    void queryClient.invalidateQueries({ queryKey: ['mp-subscription-status'] })
  }

  const checkoutMutation = useMutation({
    mutationFn: (plan: SubscriptionPlanValue) =>
      apiFetch<SubscriptionPayment>('/marketplace/subscription/checkout/', {
        method: 'POST',
        body: { plan },
      }),
    onMutate: () => {
      setPhase('pending')
      setMessage('Starting checkout…')
    },
    onSuccess: (payment) => {
      setCheckoutPaymentId(payment.id)
      setMessage(
        'Checkout created. Complete the payment with your provider; the STAR ' +
          'server confirms the outcome before any selling right is granted.',
      )
    },
    onError: (error) => {
      setPhase('failed')
      setMessage(
        error instanceof Error && error.message
          ? error.message
          : 'Could not start the checkout. Try again.',
      )
    },
  })

  useEffect(() => {
    const payment = paymentQuery.data
    if (!payment) return
    if (payment.status === 'succeeded') {
      setPhase('succeeded')
      setMessage('Payment confirmed. Your seller subscription is active.')
      setCheckoutPaymentId(null)
      invalidateStatus()
    } else if (payment.status === 'failed' || payment.status === 'cancelled') {
      setPhase('failed')
      setMessage(
        payment.status === 'cancelled'
          ? 'Checkout cancelled. No payment was confirmed.'
          : `Payment rejected: ${payment.failure_reason || 'declined by provider'}`,
      )
      setCheckoutPaymentId(null)
      invalidateStatus()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paymentQuery.data])

  if (!hasRole('supplier')) {
    return (
      <div className="page">
        <div className="state-block state-block--error" role="alert">
          <h3 className="state-block__title">Become a seller on STAR Marketplace</h3>
          <p className="state-block__message">
            Selling requires the supplier role plus an active seller subscription.
            Contact your administrator to be granted the supplier role.
          </p>
          <Link to="/marketplace" className="btn btn--secondary btn--sm">
            Back to marketplace
          </Link>
        </div>
      </div>
    )
  }

  if (statusQuery.isPending) {
    return (
      <div className="page">
        <div className="page-loading" role="status">
          <Spinner size="md" label="Loading your subscription…" />
        </div>
      </div>
    )
  }

  if (statusQuery.isError) {
    return (
      <div className="page">
        <ErrorState
          message={
            statusQuery.error instanceof Error
              ? statusQuery.error.message
              : 'Could not load your subscription.'
          }
          onRetry={() => void statusQuery.refetch()}
        />
      </div>
    )
  }

  const plans = payload?.plans ?? []
  const active = payload?.status === 'active'

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Become a seller on STAR Marketplace</h1>
          <p className="page__subtitle">
            An active subscription lets you publish equipment, manage prices and
            photos, and follow buyer orders. Prices are fixed by the server.
          </p>
        </div>
        <Link to="/supplier" className="btn btn--secondary btn--sm">
          Supplier workspace
        </Link>
      </header>

      {message && (
        <p
          className={phase === 'succeeded' ? 'form-alert form-alert--success' : 'form-alert'}
          role="alert"
        >
          {message}
        </p>
      )}
      {checkoutMutation.isPending && (
        <div className="page-loading" role="status">
          <Spinner size="sm" />
          <span>Starting checkout…</span>
        </div>
      )}

      <StatusCard payload={payload} />

      <Card title="Plans">
        <p className="field__hint">
          Amounts are in CFA francs (whole units). The monthly plan starts at{' '}
          {formatMoney(2500, 'FCFA')} for a user's very first month only.
        </p>
        <div className="form-grid">
          {plans.map((plan) => (
            <div className="subscription-plan" key={plan.plan}>
              <strong>{PLAN_LABELS[plan.plan]}</strong>
              <p className="subscription-plan__price">
                {formatMoney(plan.price_fcfa, 'FCFA')}
              </p>
              <p className="field__hint">{plan.duration_months} month(s)</p>
              <Button
                variant={active && plan.plan === payload?.plan ? 'ghost' : 'secondary'}
                loading={checkoutMutation.isPending}
                onClick={() => checkoutMutation.mutate(plan.plan)}
              >
                {active && plan.plan === payload?.plan
                  ? 'Renew this plan'
                  : active
                    ? 'Switch & subscribe'
                    : 'Subscribe'}
              </Button>
            </div>
          ))}
        </div>
        <p className="field__hint">
          The subscription is manual: it never auto-renews. A failed or cancelled
          payment never grants selling rights — only a server-verified payment does.
        </p>
      </Card>
    </div>
  )
}

function StatusCard({ payload }: { payload: SubscriptionStatusPayload | undefined }) {
  const { remaining, expiringSoon } = useSubscriptionCountdown(payload)

  if (!payload) return null

  if (payload.status === 'expired' || payload.status === 'cancelled') {
    return (
      <Card title="Subscription">
        <Badge tone="danger">Your seller subscription has expired</Badge>
        <p className="field__hint">
          Ended on {formatDate(payload.expires_at)}. Your existing listings have
          been retained but are hidden from public buyers until you renew, and new
          listings cannot be published in the meantime.
        </p>
      </Card>
    )
  }

  if (payload.status === 'active') {
    const countdown = remaining
      ? `${remaining.days}d ${remaining.hours}h ${remaining.minutes}m ${remaining.seconds}s`
      : '—'
    return (
      <Card title="Subscription">
        <div className="badge-row">
          <Badge tone="success">Active</Badge>
          {expiringSoon && <Badge tone="warning">Expiring soon</Badge>}
        </div>
        <dl className="definition-list">
          <dt>Plan</dt>
          <dd>
            {payload.plan ? PLAN_LABELS[payload.plan] : '—'} ({formatMoney(payload.amount_fcfa, 'FCFA')} per
            period)
          </dd>
          <dt>Started</dt>
          <dd>{formatDate(payload.starts_at)}</dd>
          <dt>Expires</dt>
          <dd>
            {formatDate(payload.expires_at)} · remaining {countdown}
          </dd>
        </dl>
        <p className="field__hint">
          Listings stay visible to buyers while the subscription is active.
          Renewal keeps any remaining paid time.
        </p>
      </Card>
    )
  }

  return (
    <Card title="Subscription">
      <Badge tone={payload.status === 'pending' ? 'warning' : payload.status === 'failed' ? 'danger' : 'neutral'}>
        {payload.status === 'none' ? 'No subscription yet' : payload.status}
      </Badge>
      {payload.status === 'pending' && (
        <p className="field__hint">
          A checkout is waiting for payment confirmation — it will show here once
          confirmed. Nothing is granted until the server verifies the payment.
        </p>
      )}
      {payload.status === 'failed' && (
        <p className="field__hint">
          The last payment attempt failed. You can try any plan again at any time.
        </p>
      )}
    </Card>
  )
}
