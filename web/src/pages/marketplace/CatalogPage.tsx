import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { apiFetch } from '../../lib/api'
import { formatMoney } from '../../lib/format'
import type { CartItem, Page, Product, ProductCategory } from '../../lib/types'

export function CatalogPage() {
  const { hasRole } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isBuyer = hasRole('buyer')

  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [cartError, setCartError] = useState<string | null>(null)

  const categoriesQuery = useQuery({
    queryKey: ['mp-categories'],
    queryFn: () => apiFetch<ProductCategory[]>('/marketplace/categories/'),
  })
  const productsQuery = useQuery({
    queryKey: ['mp-products', category, appliedSearch],
    queryFn: () => {
      const params = new URLSearchParams()
      if (category) params.set('category', category)
      if (appliedSearch) params.set('q', appliedSearch)
      const qs = params.toString()
      return apiFetch<Page<Product>>(`/marketplace/products/${qs ? `?${qs}` : ''}`)
    },
  })
  const cartQuery = useQuery({
    queryKey: ['mp-cart'],
    queryFn: () => apiFetch<Page<CartItem>>('/marketplace/cart/'),
    enabled: isBuyer,
  })

  const addToCart = useMutation({
    mutationFn: (productId: string) =>
      apiFetch<CartItem>('/marketplace/cart/items/', {
        method: 'POST',
        body: { product: productId, quantity: 1 },
      }),
    onSuccess: () => {
      setCartError(null)
      void queryClient.invalidateQueries({ queryKey: ['mp-cart'] })
    },
    onError: (error) =>
      setCartError(error instanceof Error ? error.message : 'Could not add to the cart.'),
  })

  const cartCount = cartQuery.data?.results.length ?? 0
  const products = productsQuery.data?.results ?? []
  const categories = (categoriesQuery.data ?? []).filter((item) => item.is_active)

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Equipment marketplace</h1>
          <p className="page__subtitle">
            {productsQuery.isPending
              ? 'Loading catalog…'
              : `${productsQuery.data?.count ?? 0} product${(productsQuery.data?.count ?? 0) === 1 ? '' : 's'} available`}
          </p>
        </div>
        <div className="badge-row">
          <Link to="/marketplace/orders" className="btn btn--ghost btn--sm">
            My orders
          </Link>
          <Link to="/marketplace/cart" className="btn btn--secondary btn--sm">
            Cart{isBuyer && cartCount > 0 ? ` (${cartCount})` : ''}
          </Link>
        </div>
      </header>

      <form
        className="list-filters"
        role="search"
        onSubmit={(event) => {
          event.preventDefault()
          setAppliedSearch(search)
        }}
      >
        <label className="field list-filters__search">
          <span className="field__label">Search</span>
          <input
            className="field__control"
            type="search"
            placeholder="Product name or SKU"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="field">
          <span className="field__label">Category</span>
          <select
            className="field__control"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">All categories</option>
            {categories.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" variant="secondary" size="sm">
          Search
        </Button>
      </form>

      {cartError && (
        <p className="form-alert" role="alert">
          {cartError}
        </p>
      )}
      {!isBuyer && (
        <p className="field__hint">
          Browsing is open to every account — checkout requires a buyer role.
        </p>
      )}

      {productsQuery.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : productsQuery.isError ? (
        <ErrorState
          message={
            productsQuery.error instanceof Error
              ? productsQuery.error.message
              : 'Could not load the catalog.'
          }
          onRetry={() => void productsQuery.refetch()}
        />
      ) : products.length === 0 ? (
        <EmptyState title="No products match" message="Adjust your search or category filter." />
      ) : (
        <div className="product-grid">
          {products.map((product) => (
            <article key={product.id} className="product-card glass">
              <Link
                to={`/marketplace/products/${product.id}`}
                className="product-card__name product-link"
              >
                {product.name}
              </Link>
              <span className="product-card__supplier">
                {product.supplier_name}
                {product.category_name ? ` · ${product.category_name}` : ''}
              </span>
              <span className="product-card__price">
                {formatMoney(product.unit_price, product.currency)}
              </span>
              <div className="badge-row">
                {product.free_quantity > 0 ? (
                  <Badge tone={product.free_quantity <= 5 ? 'warning' : 'success'}>
                    {product.free_quantity} in stock
                  </Badge>
                ) : (
                  <Badge tone="danger">Out of stock</Badge>
                )}
                <Badge tone="neutral">SKU {product.sku}</Badge>
              </div>
              <div className="product-card__footer">
                <Link
                  to={`/marketplace/products/${product.id}`}
                  className="btn btn--ghost btn--sm"
                >
                  Details
                </Link>
                <Button
                  size="sm"
                  disabled={!isBuyer || product.free_quantity === 0}
                  loading={addToCart.isPending && addToCart.variables === product.id}
                  onClick={() => addToCart.mutate(product.id)}
                >
                  Add to cart
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}

      {isBuyer && cartCount > 0 && (
        <div className="badge-row">
          <Button variant="primary" onClick={() => navigate('/marketplace/cart')}>
            Go to cart ({cartCount})
          </Button>
        </div>
      )}
    </div>
  )
}
