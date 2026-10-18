import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Badge } from '../../components/Badge'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { apiFetch } from '../../lib/api'
import { formatDateTime, formatMoney } from '../../lib/format'
import type { Order, Page } from '../../lib/types'
import { statusMeta } from '../../lib/status'

export function OrdersPage() {
  const ordersQuery = useQuery({
    queryKey: ['mp-orders'],
    queryFn: () => apiFetch<Page<Order>>('/marketplace/orders/?ordering=-created_at'),
  })

  const orders = ordersQuery.data?.results ?? []

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/marketplace" className="page__backlink">
            ← Catalog
          </Link>
          <h1 className="page__title">Orders</h1>
          <p className="page__subtitle">
            {ordersQuery.isPending
              ? 'Loading orders…'
              : `${ordersQuery.data?.count ?? 0} order${(ordersQuery.data?.count ?? 0) === 1 ? '' : 's'}`}
          </p>
        </div>
        <Link to="/marketplace/cart" className="btn btn--ghost btn--sm">
          Cart
        </Link>
      </header>

      {ordersQuery.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : ordersQuery.isError ? (
        <ErrorState
          message={
            ordersQuery.error instanceof Error
              ? ordersQuery.error.message
              : 'Could not load orders.'
          }
          onRetry={() => void ordersQuery.refetch()}
        />
      ) : orders.length === 0 ? (
        <EmptyState
          title="No orders yet"
          message="Orders appear here after you check out from the cart."
          action={
            <Link to="/marketplace" className="btn btn--primary btn--sm">
              Browse catalog
            </Link>
          }
        />
      ) : (
        <div className="record-list">
          {orders.map((order) => {
            const meta = statusMeta('order', order.status)
            const itemCount = order.items.reduce((sum, item) => sum + item.quantity, 0)
            return (
              <Link
                key={order.id}
                to={`/marketplace/orders/${order.id}`}
                className="record-row glass"
              >
                <span className="record-row__main">
                  <span className="record-row__ref">{order.reference}</span>
                  <span className="record-row__name">{order.supplier_name}</span>
                  <span className="record-row__meta">
                    {formatDateTime(order.placed_at)} · {itemCount} item
                    {itemCount === 1 ? '' : 's'} · {formatMoney(order.total, order.currency)}
                  </span>
                </span>
                <span className="record-row__side">
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                  <span className="record-row__chevron" aria-hidden="true">
                    ›
                  </span>
                </span>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
