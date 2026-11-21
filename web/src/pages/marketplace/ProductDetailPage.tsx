import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { ApiError, apiFetch } from '../../lib/api'
import { formatMoney } from '../../lib/format'
import type { CartItem, Product } from '../../lib/types'

export function ProductDetailPage() {
  const { id = '' } = useParams()
  const { hasRole } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isBuyer = hasRole('buyer')

  const [quantity, setQuantity] = useState(1)
  const [error, setError] = useState<string | null>(null)

  const productQuery = useQuery({
    queryKey: ['mp-product', id],
    queryFn: () => apiFetch<Product>(`/marketplace/products/${id}/`),
    enabled: Boolean(id),
  })

  const addToCart = useMutation({
    mutationFn: () =>
      apiFetch<CartItem>('/marketplace/cart/items/', {
        method: 'POST',
        body: { product: id, quantity },
      }),
    onSuccess: () => {
      setError(null)
      void queryClient.invalidateQueries({ queryKey: ['mp-cart'] })
      navigate('/marketplace/cart')
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : 'Could not add to the cart.'),
  })

  if (productQuery.isPending) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading product…" />
      </div>
    )
  }
  if (productQuery.isError) {
    const err = productQuery.error
    if (err instanceof ApiError && err.status === 404) {
      return (
        <div className="page">
          <div className="state-block state-block--error" role="alert">
            <h3 className="state-block__title">Product not found</h3>
            <p className="state-block__message">
              This product does not exist or is no longer published.
            </p>
            <Link to="/marketplace" className="btn btn--secondary btn--sm">
              Back to catalog
            </Link>
          </div>
        </div>
      )
    }
    return (
      <ErrorState
        message={err instanceof Error ? err.message : 'Could not load the product.'}
        onRetry={() => void productQuery.refetch()}
      />
    )
  }

  const product = productQuery.data

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <Link to="/marketplace" className="page__backlink">
            ← Catalog
          </Link>
          <h1 className="page__title">{product.name}</h1>
          <p className="page__subtitle">
            {product.supplier_name}
            {product.category_name ? ` · ${product.category_name}` : ''} · SKU {product.sku}
          </p>
        </div>
        <span className="product-card__price">{formatMoney(product.unit_price, product.currency)}</span>
      </header>

      {error && (
        <p className="form-alert" role="alert">
          {error}
        </p>
      )}

      {product.image_url && (
        <figure className="product-detail__media">
          <img
            className="product-detail__image"
            src={product.image_url}
            alt={product.name}
          />
          {product.image_credit && (
            <figcaption className="product-detail__credit">
              Photo: {product.image_credit}
            </figcaption>
          )}
        </figure>
      )}

      <div className="account-grid">
        <Card title="Description">
          <p>{product.description || 'No description provided.'}</p>
          <div className="badge-row">
            {product.free_quantity > 0 ? (
              <Badge tone={product.free_quantity <= 5 ? 'warning' : 'success'}>
                {product.free_quantity} available
              </Badge>
            ) : (
              <Badge tone="danger">Out of stock</Badge>
            )}
            <Badge tone="neutral">{product.reserved_quantity} reserved</Badge>
          </div>
        </Card>

        <Card title="Order">
          <label className="field">
            <span className="field__label">Quantity</span>
            <input
              className="field__control"
              type="number"
              min={1}
              max={Math.max(product.free_quantity, 1)}
              value={quantity}
              onChange={(event) =>
                setQuantity(Math.max(1, Number.parseInt(event.target.value, 10) || 1))
              }
            />
          </label>
          <div className="badge-row">
            <Button
              disabled={!isBuyer || product.free_quantity === 0}
              loading={addToCart.isPending}
              onClick={() => addToCart.mutate()}
            >
              {isBuyer ? 'Add to cart' : 'Buyer role required'}
            </Button>
          </div>
          {!isBuyer && (
            <p className="field__hint">
              Your account cannot check out — ask an administrator for the buyer role.
            </p>
          )}
        </Card>
      </div>
    </div>
  )
}
