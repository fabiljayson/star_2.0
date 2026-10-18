import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { ApiError, apiFetch } from '../../lib/api'
import { downloadFile } from '../../lib/download'
import { formatDateTime, formatMoney } from '../../lib/format'
import type { Order, SupplierProfileValue } from '../../lib/types'
import { statusMeta } from '../../lib/status'

const REFUNDABLE = new Set(['paid', 'shipped', 'delivered'])
const DISPUTABLE = new Set(['paid', 'shipped', 'delivered'])

export function OrderDetailPage() {
  const { id = '' } = useParams()
  const { user, hasRole } = useAuth()
  const queryClient = useQueryClient()

  const [actionError, setActionError] = useState<string | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [refundReason, setRefundReason] = useState('')
  const [disputeText, setDisputeText] = useState('')
  const [evidenceBody, setEvidenceBody] = useState('')
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null)
  const [shipTracking, setShipTracking] = useState('')

  const isSupplier = hasRole('supplier')
  const isBuyer = hasRole('buyer')

  const orderQuery = useQuery({
    queryKey: ['mp-order', id],
    queryFn: () => apiFetch<Order>(`/marketplace/orders/${id}/`),
    enabled: Boolean(id),
  })
  const profileQuery = useQuery({
    queryKey: ['mp-supplier-profile'],
    queryFn: () => apiFetch<SupplierProfileValue>('/marketplace/supplier/profile/'),
    enabled: isSupplier,
    retry: false,
  })

  const invalidate = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['mp-order', id] })
    void queryClient.invalidateQueries({ queryKey: ['mp-orders'] })
    void queryClient.invalidateQueries({ queryKey: ['mp-cart'] })
  }
  const fail = (error: unknown): void =>
    setActionError(error instanceof ApiError ? error.message : 'The request failed.')

  const payMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/marketplace/orders/${id}/pay/`, {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      }),
    onSuccess: invalidate,
    onError: fail,
  })
  const simulateMutation = useMutation({
    mutationFn: (outcome: 'succeeded' | 'failed') =>
      apiFetch(
        `/marketplace/payments/${orderQuery.data?.payments.find((payment) => payment.status === 'pending')?.id}/simulate/`,
        { method: 'POST', body: { outcome } },
      ),
    onSuccess: invalidate,
    onError: fail,
  })
  const cancelMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/marketplace/orders/${id}/cancel/`, {
        method: 'POST',
        body: { reason: cancelReason },
      }),
    onSuccess: invalidate,
    onError: fail,
  })
  const refundRequestMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/marketplace/orders/${id}/refund-request/`, {
        method: 'POST',
        body: { reason: refundReason },
      }),
    onSuccess: () => {
      setRefundReason('')
      invalidate()
    },
    onError: fail,
  })
  const refundDecideMutation = useMutation({
    mutationFn: ({ refundId, approved }: { refundId: string; approved: boolean }) =>
      apiFetch(`/marketplace/refunds/${refundId}/decide/`, {
        method: 'POST',
        body: { approved, reason: '' },
      }),
    onSuccess: invalidate,
    onError: fail,
  })
  const shipMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/marketplace/orders/${id}/ship/`, {
        method: 'POST',
        body: { tracking_number: shipTracking },
      }),
    onSuccess: invalidate,
    onError: fail,
  })
  const deliverMutation = useMutation({
    mutationFn: () => apiFetch(`/marketplace/orders/${id}/deliver/`, { method: 'POST' }),
    onSuccess: invalidate,
    onError: fail,
  })
  const openDisputeMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/marketplace/orders/${id}/dispute/`, {
        method: 'POST',
        body: { description: disputeText },
      }),
    onSuccess: () => {
      setDisputeText('')
      invalidate()
    },
    onError: fail,
  })
  const addEvidenceMutation = useMutation({
    mutationFn: () => {
      const body = new FormData()
      body.append('body', evidenceBody)
      if (evidenceFile) body.append('file', evidenceFile)
      return apiFetch(
        `/marketplace/disputes/${orderQuery.data?.dispute?.id}/evidence/`,
        { method: 'POST', body },
      )
    },
    onSuccess: () => {
      setEvidenceBody('')
      setEvidenceFile(null)
      invalidate()
    },
    onError: fail,
  })
  const resolveDisputeMutation = useMutation({
    mutationFn: (resolution: 'buyer_favored' | 'supplier_favored') =>
      apiFetch(`/marketplace/disputes/${orderQuery.data?.dispute?.id}/resolve/`, {
        method: 'POST',
        body: { resolution, note: '' },
      }),
    onSuccess: invalidate,
    onError: fail,
  })

  if (orderQuery.isPending) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading order…" />
      </div>
    )
  }
  if (orderQuery.isError) {
    const err = orderQuery.error
    if (err instanceof ApiError && err.status === 404) {
      return (
        <div className="page">
          <div className="state-block state-block--error" role="alert">
            <h3 className="state-block__title">Order not found</h3>
            <p className="state-block__message">
              This order does not exist or is outside your access.
            </p>
            <Link to="/marketplace/orders" className="btn btn--secondary btn--sm">
              Back to orders
            </Link>
          </div>
        </div>
      )
    }
    return (
      <ErrorState
        message={err instanceof Error ? err.message : 'Could not load the order.'}
        onRetry={() => void orderQuery.refetch()}
      />
    )
  }

  const order = orderQuery.data
  const meta = statusMeta('order', order.status)
  const iAmOrderBuyer = Boolean(user && isBuyer && order.buyer === user.id)
  const buyerOk = iAmOrderBuyer
  const supplierProfile = profileQuery.data
  const iAmSupplier = Boolean(supplierProfile && order.supplier === supplierProfile.id)
  const isAdmin = Boolean(user?.is_platform_admin)

  const payments = order.payments
  const pendingPayment = payments.find((payment) => payment.status === 'pending')
  const succeededPayment = payments.find((payment) => payment.status === 'succeeded')
  const pendingRefund = order.refunds.find((refund) => refund.status === 'pending')
  const canPay =
    buyerOk && order.status === 'pending_payment' && !pendingPayment && !succeededPayment
  const canCancel = (buyerOk || isAdmin) && order.status === 'pending_payment'
  const canRefundRequest =
    buyerOk && REFUNDABLE.has(order.status) && Boolean(succeededPayment) && !pendingRefund
  const canShip = iAmSupplier && order.status === 'paid' && !order.shipment
  const canDeliver = iAmSupplier && order.shipment?.status === 'shipped'
  const canOpenDispute =
    (buyerOk || iAmSupplier) && DISPUTABLE.has(order.status) && !order.dispute

  function onDisputeSubmit(event: FormEvent): void {
    event.preventDefault()
    if (!disputeText.trim()) {
      setActionError('Describe the problem before opening a dispute.')
      return
    }
    openDisputeMutation.mutate()
  }

  function onEvidenceSubmit(event: FormEvent): void {
    event.preventDefault()
    if (!evidenceBody.trim() && !evidenceFile) {
      setActionError('Add a note or a file to your evidence.')
      return
    }
    addEvidenceMutation.mutate()
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/marketplace/orders" className="page__backlink">
            ← Orders
          </Link>
          <h1 className="page__title">{order.reference}</h1>
          <p className="page__subtitle">
            {order.supplier_name} · placed {formatDateTime(order.placed_at)}
          </p>
        </div>
        <div className="badge-row">
          <Badge tone={meta.tone}>{meta.label}</Badge>
          {iAmOrderBuyer && <Badge tone="info">Buyer</Badge>}
          {iAmSupplier && <Badge tone="info">Supplier</Badge>}
          {isAdmin && <Badge tone="neutral">Platform admin</Badge>}
        </div>
      </header>

      {actionError && (
        <p className="form-alert" role="alert">
          {actionError}
        </p>
      )}

      <div className="badge-row detail-actions">
        {canPay && (
          <Button
            variant="primary"
            loading={payMutation.isPending}
            onClick={() => payMutation.mutate()}
          >
            Pay {formatMoney(order.total, order.currency)}
          </Button>
        )}
        {canCancel && (
          <Button
            variant="secondary"
            loading={cancelMutation.isPending}
            onClick={() => cancelMutation.mutate()}
          >
            Cancel order
          </Button>
        )}
        {canShip && (
          <Button
            variant="primary"
            loading={shipMutation.isPending}
            onClick={() => shipMutation.mutate()}
          >
            Ship order
          </Button>
        )}
        {canDeliver && (
          <Button
            variant="primary"
            loading={deliverMutation.isPending}
            onClick={() => deliverMutation.mutate()}
          >
            Mark delivered
          </Button>
        )}
      </div>

      <div className="account-grid">
        <Card title="Items">
          <table className="data-table">
            <thead>
              <tr>
                <th>Product</th>
                <th className="num">Qty</th>
                <th className="num">Unit</th>
                <th className="num">Total</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item) => (
                <tr key={item.id}>
                  <td>{item.product_name}</td>
                  <td className="num">{item.quantity}</td>
                  <td className="num">{formatMoney(item.unit_price, order.currency)}</td>
                  <td className="num">{formatMoney(item.line_total, order.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="order-summary">
            <span>Total</span>
            <span>{formatMoney(order.total, order.currency)}</span>
          </div>
          {(order.shipping_name || order.shipping_address) && (
            <dl className="definition-list">
              <dt>Ship to</dt>
              <dd>
                {order.shipping_name}
                {order.shipping_address ? ` — ${order.shipping_address}` : ''}
                {order.shipping_phone ? ` · ${order.shipping_phone}` : ''}
              </dd>
              {order.cancelled_at && (
                <>
                  <dt>Cancelled</dt>
                  <dd>{formatDateTime(order.cancelled_at)}</dd>
                </>
              )}
              {order.paid_at && (
                <>
                  <dt>Paid</dt>
                  <dd>{formatDateTime(order.paid_at)}</dd>
                </>
              )}
            </dl>
          )}
          {canCancel && (
            <label className="field">
              <span className="field__label">Cancellation reason (optional)</span>
              <input
                className="field__control"
                value={cancelReason}
                onChange={(event) => setCancelReason(event.target.value)}
              />
            </label>
          )}
          {canShip && (
            <label className="field">
              <span className="field__label">Tracking number</span>
              <input
                className="field__control"
                value={shipTracking}
                onChange={(event) => setShipTracking(event.target.value)}
              />
            </label>
          )}
        </Card>

        <Card title="Payment">
          <div className="payment-panel">
            {payments.length === 0 && (
              <p className="field__hint">
                No payment attempt yet.
                {order.status === 'pending_payment' && buyerOk
                  ? ' Press “Pay” to start one.'
                  : ''}
              </p>
            )}

            {payments.map((payment, index) => {
              const paymentMeta = statusMeta('payment', payment.status)
              const isLast = index === payments.length - 1
              return (
                <div key={payment.id} className="payment-row">
                  <div className="badge-row">
                    <Badge tone={paymentMeta.tone}>{paymentMeta.label}</Badge>
                    <span className="field__hint">
                      {formatMoney(payment.amount, payment.currency)} ·{' '}
                      {formatDateTime(payment.created_at)}
                    </span>
                  </div>
                  {payment.failure_reason && (
                    <p className="field__error" role="alert">
                      {payment.failure_reason}
                    </p>
                  )}
                  {isLast && payment.events.length > 0 && (
                    <ul className="timeline">
                      {payment.events.map((event) => (
                        <li key={event.id}>
                          <span className="timeline__dot" aria-hidden="true" />
                          <span className="field__hint">
                            {event.event_type} ·{' '}
                            {event.signature_valid ? 'signature verified' : 'invalid signature'}{' '}
                            · {formatDateTime(event.created_at)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {isLast && payment.status === 'pending' && !isAdmin && (
                    <p className="field__hint">
                      Waiting for the payment provider event. In the sandbox, a platform
                      administrator delivers the outcome (this prevents anyone from
                      self-confirming a payment).
                    </p>
                  )}
                  {isLast && payment.status === 'pending' && isAdmin && (
                    <div className="badge-row">
                      <Button
                        variant="primary"
                        size="sm"
                        loading={simulateMutation.isPending && simulateMutation.variables === 'succeeded'}
                        onClick={() => simulateMutation.mutate('succeeded')}
                      >
                        Sandbox: payment succeeds
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        loading={simulateMutation.isPending && simulateMutation.variables === 'failed'}
                        onClick={() => simulateMutation.mutate('failed')}
                      >
                        Sandbox: payment fails
                      </Button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {canRefundRequest && (
            <form
              className="form"
              onSubmit={(event) => {
                event.preventDefault()
                refundRequestMutation.mutate()
              }}
            >
              <label className="field">
                <span className="field__label">Request a refund (reason)</span>
                <input
                  className="field__control"
                  value={refundReason}
                  onChange={(event) => setRefundReason(event.target.value)}
                />
              </label>
              <div className="badge-row">
                <Button
                  type="submit"
                  variant="secondary"
                  size="sm"
                  loading={refundRequestMutation.isPending}
                >
                  Request refund
                </Button>
              </div>
            </form>
          )}

          {pendingRefund && iAmSupplier && (
            <div className="payment-panel">
              <p className="field__hint">
                Refund requested: {formatMoney(pendingRefund.amount, pendingRefund.currency)}
                {pendingRefund.reason ? ` — “${pendingRefund.reason}”` : ''}
              </p>
              <div className="badge-row">
                <Button
                  variant="primary"
                  size="sm"
                  loading={refundDecideMutation.isPending && refundDecideMutation.variables?.approved === true}
                  onClick={() =>
                    refundDecideMutation.mutate({ refundId: pendingRefund.id, approved: true })
                  }
                >
                  Approve refund
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  loading={refundDecideMutation.isPending && refundDecideMutation.variables?.approved === false}
                  onClick={() =>
                    refundDecideMutation.mutate({ refundId: pendingRefund.id, approved: false })
                  }
                >
                  Reject refund
                </Button>
              </div>
            </div>
          )}

          {order.refunds
            .filter((refund) => refund.status !== 'pending')
            .map((refund) => (
              <div key={refund.id} className="badge-row">
                <Badge tone={refund.status === 'approved' ? 'success' : 'danger'}>
                  Refund {refund.status}
                </Badge>
                <span className="field__hint">
                  {formatMoney(refund.amount, refund.currency)}
                  {refund.decision_reason ? ` — ${refund.decision_reason}` : ''}
                </span>
              </div>
            ))}

          {order.shipment && (
            <div className="badge-row">
              <Badge tone={order.shipment.status === 'delivered' ? 'success' : 'info'}>
                {order.shipment.status}
              </Badge>
              <span className="field__hint">
                {order.shipment.tracking_number
                  ? `Tracking ${order.shipment.tracking_number}`
                  : 'No tracking number'}
              </span>
            </div>
          )}
        </Card>
      </div>

      <Card title="Dispute">
        {order.dispute ? (
          <div className="form">
            <div className="badge-row">
              <Badge tone={order.dispute.status === 'resolved' ? 'success' : 'warning'}>
                {order.dispute.status}
              </Badge>
              {order.dispute.resolution && (
                <Badge tone="info">{order.dispute.resolution.replaceAll('_', ' ')}</Badge>
              )}
            </div>
            <p>{order.dispute.description}</p>
            {order.dispute.evidence_entries.length > 0 && (
              <ul className="attachment-list">
                {order.dispute.evidence_entries.map((entry) => (
                  <li key={entry.id} className="attachment-row">
                    <span className="attachment-row__meta">
                      <strong>{entry.file_name ?? 'Note'}</strong>
                      <span className="field__hint">{entry.body}</span>
                    </span>
                    {entry.file_name && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          void downloadFile(
                            `/marketplace/disputes/${order.dispute!.id}/evidence/${entry.id}/download/`,
                            entry.file_name!,
                          ).catch((error: unknown) => fail(error))
                        }
                      >
                        Download
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {(buyerOk || iAmSupplier) && order.dispute.status === 'open' && (
              <form className="form" onSubmit={onEvidenceSubmit}>
                <label className="field">
                  <span className="field__label">Add evidence (note)</span>
                  <textarea
                    className="field__control"
                    rows={3}
                    value={evidenceBody}
                    onChange={(event) => setEvidenceBody(event.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field__label">Attach a file</span>
                  <input
                    className="field__control"
                    type="file"
                    onChange={(event) => setEvidenceFile(event.target.files?.[0] ?? null)}
                  />
                </label>
                <div className="badge-row">
                  <Button
                    type="submit"
                    variant="secondary"
                    size="sm"
                    loading={addEvidenceMutation.isPending}
                  >
                    Add evidence
                  </Button>
                </div>
              </form>
            )}

            {isAdmin && order.dispute.status === 'open' && (
              <div className="badge-row">
                <Button
                  variant="primary"
                  size="sm"
                  loading={resolveDisputeMutation.isPending && resolveDisputeMutation.variables === 'buyer_favored'}
                  onClick={() => resolveDisputeMutation.mutate('buyer_favored')}
                >
                  Resolve for buyer
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  loading={resolveDisputeMutation.isPending && resolveDisputeMutation.variables === 'supplier_favored'}
                  onClick={() => resolveDisputeMutation.mutate('supplier_favored')}
                >
                  Resolve for supplier
                </Button>
              </div>
            )}
          </div>
        ) : canOpenDispute ? (
          <form className="form" onSubmit={onDisputeSubmit}>
            <label className="field">
              <span className="field__label">Something wrong with this order?</span>
              <textarea
                className="field__control"
                rows={3}
                placeholder="Describe the problem"
                value={disputeText}
                onChange={(event) => setDisputeText(event.target.value)}
              />
            </label>
            <div className="badge-row">
              <Button
                type="submit"
                variant="secondary"
                size="sm"
                loading={openDisputeMutation.isPending}
              >
                Open dispute
              </Button>
            </div>
          </form>
        ) : (
          <p className="field__hint">
            No dispute. Disputes can be opened on paid, shipped or delivered orders by
            either party.
          </p>
        )}
      </Card>
    </div>
  )
}
