import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { ApiError, apiFetch } from '../../lib/api'
import { formatMoney } from '../../lib/format'
import type { CartItem, Order, Page } from '../../lib/types'

export function CartPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [shipping, setShipping] = useState({ name: '', address: '', phone: '' })
  const [formError, setFormError] = useState<string | null>(null)

  const cartQuery = useQuery({
    queryKey: ['mp-cart'],
    queryFn: () => apiFetch<Page<CartItem>>('/marketplace/cart/'),
  })

  const updateQty = useMutation({
    mutationFn: ({ item, quantity }: { item: CartItem; quantity: number }) =>
      apiFetch<CartItem>(`/marketplace/cart/items/${item.id}/`, {
        method: 'PATCH',
        body: { quantity },
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['mp-cart'] }),
    onError: (error) =>
      setFormError(error instanceof ApiError ? error.message : 'Could not update the cart.'),
  })

  const removeItem = useMutation({
    mutationFn: (itemId: string) =>
      apiFetch<void>(`/marketplace/cart/items/${itemId}/`, { method: 'DELETE' }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['mp-cart'] }),
    onError: (error) =>
      setFormError(error instanceof ApiError ? error.message : 'Could not remove the item.'),
  })

  const checkout = useMutation({
    mutationFn: () =>
      apiFetch<Order[]>('/marketplace/checkout/', {
        method: 'POST',
        body: { shipping },
      }),
    onSuccess: (orders) => {
      void queryClient.invalidateQueries({ queryKey: ['mp-cart'] })
      void queryClient.invalidateQueries({ queryKey: ['mp-orders'] })
      if (orders.length === 1 && orders[0]) {
        navigate(`/marketplace/orders/${orders[0].id}`)
      } else {
        navigate('/marketplace/orders')
      }
    },
    onError: (error) =>
      setFormError(
        error instanceof ApiError ? error.message : 'Checkout failed. Stock may have changed.',
      ),
  })

  function onCheckout(event: FormEvent): void {
    event.preventDefault()
    setFormError(null)
    checkout.mutate()
  }

  if (cartQuery.isPending) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading cart…" />
      </div>
    )
  }
  if (cartQuery.isError) {
    return (
      <ErrorState
        title="Cart unavailable"
        message={
          cartQuery.error instanceof ApiError
            ? cartQuery.error.message
            : 'Could not load your cart.'
        }
        onRetry={() => void cartQuery.refetch()}
        action={
          <Link to="/marketplace" className="btn btn--secondary btn--sm">
            Back to catalog
          </Link>
        }
      />
    )
  }

  const items = cartQuery.data.results
  const total = items.reduce((sum, item) => sum + Number.parseFloat(item.line_total), 0)
  const currency = items[0]?.product_detail.currency ?? 'XOF'

  if (items.length === 0) {
    return (
      <div className="page">
        <header className="page__header">
          <div>
            <h1 className="page__title">Cart</h1>
            <p className="page__subtitle">Items reserved for checkout.</p>
          </div>
        </header>
        <EmptyState
          title="Your cart is empty"
          message="Browse the catalog and add equipment to your cart."
          action={
            <Link to="/marketplace" className="btn btn--primary btn--sm">
              Browse catalog
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/marketplace" className="page__backlink">
            ← Catalog
          </Link>
          <h1 className="page__title">Cart</h1>
          <p className="page__subtitle">
            Stock is reserved when you check out — one order is created per supplier.
          </p>
        </div>
      </header>

      {formError && (
        <p className="form-alert" role="alert">
          {formError}
        </p>
      )}

      <Card title={`${items.length} item${items.length === 1 ? '' : 's'}`}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Product</th>
              <th>Supplier</th>
              <th className="num">Unit</th>
              <th className="num">Qty</th>
              <th className="num">Line total</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link to={`/marketplace/products/${item.product}`} className="product-link">
                    {item.product_detail.name}
                  </Link>
                </td>
                <td>{item.product_detail.supplier_name}</td>
                <td className="num">{formatMoney(item.product_detail.unit_price, item.product_detail.currency)}</td>
                <td className="num">
                  <input
                    className="field__control qty-input"
                    type="number"
                    min={1}
                    max={item.product_detail.free_quantity + item.quantity}
                    value={item.quantity}
                    aria-label={`Quantity for ${item.product_detail.name}`}
                    onChange={(event) => {
                      const quantity = Math.max(1, Number.parseInt(event.target.value, 10) || 1)
                      updateQty.mutate({ item, quantity })
                    }}
                  />
                </td>
                <td className="num">{formatMoney(item.line_total, currency)}</td>
                <td className="num">
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => removeItem.mutate(item.id)}
                  >
                    Remove
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="order-summary">
          <span>Subtotal</span>
          <span>{formatMoney(total, currency)}</span>
        </div>
      </Card>

      <Card title="Shipping & checkout">
        <form className="form" onSubmit={onCheckout}>
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Recipient name</span>
              <input
                className="field__control"
                value={shipping.name}
                onChange={(event) =>
                  setShipping((current) => ({ ...current, name: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span className="field__label">Phone</span>
              <input
                className="field__control"
                value={shipping.phone}
                onChange={(event) =>
                  setShipping((current) => ({ ...current, phone: event.target.value }))
                }
              />
            </label>
          </div>
          <label className="field">
            <span className="field__label">Address</span>
            <textarea
              className="field__control"
              rows={3}
              value={shipping.address}
              onChange={(event) =>
                setShipping((current) => ({ ...current, address: event.target.value }))
              }
            />
          </label>
          <div className="badge-row">
            <Button type="submit" loading={checkout.isPending}>
              Place order{items.length > 0 ? ` — ${formatMoney(total, currency)}` : ''}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
