import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Modal } from '../../components/Modal'
import { Spinner } from '../../components/Spinner'
import { SubscriptionPaywallModal } from '../../components/SubscriptionPaywallModal'
import { isSubscriptionRequiredError } from '../../lib/subscription'
import { ApiError, apiFetch } from '../../lib/api'
import { formatDateTime, formatMoney } from '../../lib/format'
import { statusMeta } from '../../lib/status'
import type {
  Order,
  Page,
  Product,
  ProductCategory,
  SubscriptionStatusPayload,
  SupplierProfileValue,
} from '../../lib/types'

type Tab = 'profile' | 'products' | 'orders'

const TABS: { value: Tab; label: string }[] = [
  { value: 'profile', label: 'Supplier profile' },
  { value: 'products', label: 'Catalog & inventory' },
  { value: 'orders', label: 'Orders' },
]

const CURRENCIES = ['XOF', 'EUR', 'USD', 'GBP']

export function SupplierWorkspacePage() {
  const { hasRole } = useAuth()
  const [tab, setTab] = useState<Tab>('profile')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const profileQuery = useQuery({
    queryKey: ['mp-supplier-profile'],
    queryFn: () => apiFetch<SupplierProfileValue>('/marketplace/supplier/profile/'),
    enabled: hasRole('supplier'),
    retry: false,
  })

  if (!hasRole('supplier')) {
    return (
      <div className="page">
        <div className="state-block state-block--error" role="alert">
          <h3 className="state-block__title">Supplier access required</h3>
          <p className="state-block__message">
            This workspace manages a verified supplier account and its catalog.
          </p>
          <Link to="/marketplace" className="btn btn--secondary btn--sm">
            Back to marketplace
          </Link>
        </div>
      </div>
    )
  }

  const profile = profileQuery.data ?? null
  const hasProfile = Boolean(profile)
  const profileMissing =
    profileQuery.isError &&
    profileQuery.error instanceof ApiError &&
    profileQuery.error.status === 404

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Supplier workspace</h1>
          <p className="page__subtitle">
            Manage your commercial profile, product listings, inventory and fulfil orders.
          </p>
        </div>
        {profile && (
          <div className="badge-row">
            <Badge
              tone={
                profile.verification_status === 'verified'
                  ? 'success'
                  : profile.verification_status === 'suspended' ||
                      profile.verification_status === 'rejected'
                    ? 'danger'
                    : 'warning'
              }
            >
              {profile.verification_status.replaceAll('_', ' ')}
            </Badge>
            <Link to="/marketplace" className="btn btn--ghost btn--sm">
              Storefront
            </Link>
          </div>
        )}
      </header>

      {(error || success) && (
        <p className={error ? 'form-alert' : 'form-alert form-alert--success'} role="alert">
          {error ?? success}
        </p>
      )}

      <div className="tabs" role="tablist" aria-label="Supplier sections">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={tab === item.value}
            className={`tab ${tab === item.value ? 'tab--active' : ''}`.trim()}
            onClick={() => {
              setTab(item.value)
              setError(null)
              setSuccess(null)
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'profile' &&
        (profileQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" label="Loading supplier profile…" />
          </div>
        ) : (
          <ProfilePanel
            key={profile?.id ?? 'new-profile'}
            profile={profile}
            missing={profileMissing}
            retry={() => void profileQuery.refetch()}
            onError={(mutationError, fallback) => {
              setSuccess(null)
              setError(mutationError instanceof Error ? mutationError.message : fallback)
            }}
            onSaved={(message) => {
              setError(null)
              setSuccess(message)
            }}
          />
        ))}

      {tab === 'products' && (
        <ProductsPanel
          enabled={hasProfile}
          onError={(mutationError, fallback) => {
            setSuccess(null)
            setError(mutationError instanceof Error ? mutationError.message : fallback)
          }}
          onSaved={(message) => {
            setError(null)
            setSuccess(message)
          }}
        />
      )}

      {tab === 'orders' && <OrdersPanel profile={profile} />}
    </div>
  )
}

// ── Profile ──
function ProfilePanel({
  profile,
  missing,
  retry,
  onError,
  onSaved,
}: {
  profile: SupplierProfileValue | null
  missing: boolean
  retry: () => void
  onError: (error: unknown, fallback: string) => void
  onSaved: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [companyName, setCompanyName] = useState(profile?.company_name ?? '')
  const [contactEmail, setContactEmail] = useState(profile?.contact_email ?? '')
  const [contactPhone, setContactPhone] = useState(profile?.contact_phone ?? '')
  const [address, setAddress] = useState(profile?.address ?? '')
  const [commercialNotes, setCommercialNotes] = useState(profile?.commercial_notes ?? '')

  const saveMutation = useMutation({
    mutationFn: () =>
      apiFetch<SupplierProfileValue>('/marketplace/supplier/profile/', {
        method: missing ? 'POST' : 'PATCH',
        body: {
          company_name: companyName.trim(),
          contact_email: contactEmail.trim(),
          contact_phone: contactPhone.trim(),
          address: address.trim(),
          commercial_notes: commercialNotes.trim(),
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mp-supplier-profile'] })
      onSaved(
        missing
          ? 'Supplier profile submitted for verification.'
          : 'Supplier profile updated. Verification status is unchanged.',
      )
    },
    onError: (error) => onError(error, 'Could not save the supplier profile.'),
  })

  return (
    <div className="account-grid">
      <Card title={missing ? 'Register your supplier profile' : 'Commercial profile'}>
        <form
          className="form"
          onSubmit={(event: FormEvent) => {
            event.preventDefault()
            if (!companyName.trim() || !contactEmail.trim()) {
              onError(new Error('Company name and contact email are required.'), 'Missing fields.')
              return
            }
            saveMutation.mutate()
          }}
          noValidate
        >
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Company name *</span>
              <input
                className="field__control"
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">Contact email *</span>
              <input
                className="field__control"
                type="email"
                value={contactEmail}
                onChange={(event) => setContactEmail(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">Contact phone</span>
              <input
                className="field__control"
                value={contactPhone}
                onChange={(event) => setContactPhone(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            <span className="field__label">Address</span>
            <textarea
              className="field__control"
              rows={3}
              value={address}
              onChange={(event) => setAddress(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Commercial notes</span>
            <textarea
              className="field__control"
              rows={3}
              value={commercialNotes}
              onChange={(event) => setCommercialNotes(event.target.value)}
            />
          </label>
          <div className="badge-row">
            <Button type="submit" loading={saveMutation.isPending}>
              {missing ? 'Submit for verification' : 'Save profile'}
            </Button>
          </div>
        </form>
      </Card>

      <Card title="Verification">
        {missing ? (
          <p className="field__hint">
            A supplier profile does not exist yet. Registering it starts the platform verification
            queue. You can list products once a platform administrator approves the profile.
          </p>
        ) : (
          <dl className="definition-list">
            <dt>Status</dt>
            <dd>{profile?.verification_status.replaceAll('_', ' ')}</dd>
            <dt>Verified at</dt>
            <dd>{profile?.verified_at ? formatDateTime(profile.verified_at) : 'Not verified yet'}</dd>
            {profile?.suspension_reason && (
              <>
                <dt>Suspension reason</dt>
                <dd>{profile.suspension_reason}</dd>
              </>
            )}
          </dl>
        )}
        {missing && (
          <div className="badge-row">
            <Button variant="secondary" size="sm" onClick={retry}>
              Reload profile
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}

// ── Products ──
function ProductsPanel({
  enabled,
  onError,
  onSaved,
}: {
  enabled: boolean
  onError: (error: unknown, fallback: string) => void
  onSaved: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [category, setCategory] = useState('')
  const [name, setName] = useState('')
  const [sku, setSku] = useState('')
  const [unitPrice, setUnitPrice] = useState('')
  const [currency, setCurrency] = useState('XOF')
  const [quantity, setQuantity] = useState('1')
  const [description, setDescription] = useState('')
  const [isPublished, setIsPublished] = useState(false)

  const [editing, setEditing] = useState<Product | null>(null)
  const [editPrice, setEditPrice] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editPublished, setEditPublished] = useState(false)
  const [restockQuantity, setRestockQuantity] = useState('10')
  const [paywallOpen, setPaywallOpen] = useState(false)

  const subscriptionQuery = useQuery({
    queryKey: ['mp-subscription-status'],
    queryFn: () => apiFetch<SubscriptionStatusPayload>('/marketplace/subscription/'),
    retry: false,
  })
  const subscriptionActive = subscriptionQuery.data?.can_publish === true

  function handlePublishError(error: unknown, fallback: string): void {
    if (isSubscriptionRequiredError(error)) {
      setPaywallOpen(true)
      return
    }
    onError(error, fallback)
  }

  const categoriesQuery = useQuery({
    queryKey: ['mp-categories'],
    queryFn: () => apiFetch<ProductCategory[]>('/marketplace/categories/'),
  })
  const productsQuery = useQuery({
    queryKey: ['mp-supplier-products'],
    queryFn: () => apiFetch<Page<Product>>('/marketplace/supplier/products/'),
    enabled,
  })

  const categories = categoriesQuery.data ?? []
  const products = productsQuery.data?.results ?? []
  const subscriptionPlans = subscriptionQuery.data?.plans ?? []

  function invalidate(): void {
    void queryClient.invalidateQueries({ queryKey: ['mp-supplier-products'] })
  }

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<Product>('/marketplace/supplier/products/', {
        method: 'POST',
        body: {
          category,
          name: name.trim(),
          sku: sku.trim(),
          unit_price: unitPrice,
          currency,
          available_quantity: Number(quantity),
          description: description.trim(),
          is_published: isPublished,
        },
      }),
    onSuccess: () => {
      setName('')
      setSku('')
      setUnitPrice('')
      setQuantity('1')
      setDescription('')
      setIsPublished(false)
      invalidate()
      onSaved('Product listed. Platform approval may still be required before it is public.')
    },
    onError: (error) => handlePublishError(error, 'Could not create the product.'),
  })

  const updateMutation = useMutation({
    mutationFn: (payload: { id: string; body: Record<string, unknown> }) =>
      apiFetch<Product>(`/marketplace/supplier/products/${payload.id}/`, {
        method: 'PATCH',
        body: payload.body,
      }),
    onSuccess: () => {
      setEditing(null)
      invalidate()
      onSaved('Product updated.')
    },
    onError: (error) => handlePublishError(error, 'Could not update the product.'),
  })

  const restockMutation = useMutation({
    mutationFn: (payload: { id: string; quantity: number }) =>
      apiFetch<Product>(`/marketplace/supplier/products/${payload.id}/restock/`, {
        method: 'POST',
        body: { quantity: payload.quantity },
      }),
    onSuccess: () => {
      invalidate()
      onSaved('Inventory restocked and movement recorded.')
    },
    onError: (error) => onError(error, 'Could not restock the product.'),
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/marketplace/supplier/products/${id}/`, { method: 'DELETE' }),
    onSuccess: () => {
      invalidate()
      onSaved('Product deactivated and unpublished.')
    },
    onError: (error) => onError(error, 'Could not deactivate the product.'),
  })

  if (!enabled) {
    return (
      <Card title="Catalog">
        <p className="field__hint">
          Register the supplier profile first — listings are attached to an approved supplier.
        </p>
      </Card>
    )
  }

  return (
    <div className="account-grid">
      <SubscriptionPaywallModal
        open={paywallOpen}
        onClose={() => setPaywallOpen(false)}
        plans={subscriptionPlans}
      />
      {!subscriptionActive && (
        <Card title="Listing visibility">
          <div className="badge-row">
            <Badge tone="warning">Seller subscription inactive</Badge>
            <Link to="/marketplace/subscription" className="btn btn--secondary btn--sm">
              Manage subscription
            </Link>
          </div>
          <p className="field__hint">
            Publishing is paused. Existing listings are kept but hidden from
            public buyers until the subscription is renewed.
          </p>
        </Card>
      )}
      <Card title="Your listings">
        {productsQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" />
          </div>
        ) : productsQuery.isError ? (
          <ErrorState
            message={
              productsQuery.error instanceof Error
                ? productsQuery.error.message
                : 'Could not load products.'
            }
            onRetry={() => void productsQuery.refetch()}
          />
        ) : products.length === 0 ? (
          <EmptyState title="No products yet" message="List your first product on the right." />
        ) : (
          <ul className="role-list">
            {products.map((product) => (
              <li key={product.id} className="supplier-product">
                <div className="supplier-product__head">
                  <strong>{product.name}</strong>
                  <span className="field__hint">
                    SKU {product.sku} · {product.category_name ?? 'No category'}
                  </span>
                </div>
                <div className="badge-row">
                  <Badge
                    tone={
                      product.is_active && product.is_published
                        ? subscriptionActive
                          ? 'success'
                          : 'warning'
                        : 'neutral'
                    }
                  >
                    {product.is_active
                      ? product.is_published
                        ? subscriptionActive
                          ? 'Published'
                          : 'Hidden by subscription'
                        : 'Unpublished'
                      : 'Inactive'}
                  </Badge>
                  <Badge
                    tone={
                      product.approval_status === 'approved'
                        ? 'success'
                        : product.approval_status === 'rejected'
                          ? 'danger'
                          : 'warning'
                    }
                  >
                    {product.approval_status}
                  </Badge>
                  <Badge tone={product.free_quantity <= 5 ? 'warning' : 'info'}>
                    {product.free_quantity} available
                  </Badge>
                  <Badge tone="neutral">{formatMoney(product.unit_price, product.currency)}</Badge>
                </div>
                <div className="badge-row">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setEditing(product)
                      setEditPrice(product.unit_price)
                      setEditDescription(product.description)
                      setEditPublished(product.is_published)
                      setRestockQuantity('10')
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      updateMutation.mutate({
                        id: product.id,
                        body: { is_published: !product.is_published },
                      })
                    }
                  >
                    {product.is_published ? 'Unpublish' : 'Publish'}
                  </Button>
                  {product.is_active && (
                    <Button
                      variant="danger"
                      size="sm"
                      loading={deactivateMutation.isPending}
                      onClick={() => deactivateMutation.mutate(product.id)}
                    >
                      Deactivate
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="List a product">
        <form
          className="form"
          onSubmit={(event: FormEvent) => {
            event.preventDefault()
            if (!category || !name.trim() || !sku.trim() || !unitPrice.trim()) {
              onError(
                new Error('Category, name, SKU and unit price are required.'),
                'Missing product fields.',
              )
              return
            }
            createMutation.mutate()
          }}
          noValidate
        >
          <label className="field">
            <span className="field__label">Category *</span>
            <select
              className="field__control"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="">
                {categoriesQuery.isPending ? 'Loading…' : 'Choose a category'}
              </option>
              {categories.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Name *</span>
              <input
                className="field__control"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">SKU *</span>
              <input
                className="field__control"
                value={sku}
                onChange={(event) => setSku(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">Unit price *</span>
              <input
                className="field__control"
                inputMode="decimal"
                value={unitPrice}
                onChange={(event) => setUnitPrice(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">Currency</span>
              <select
                className="field__control"
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
              >
                {CURRENCIES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Initial quantity</span>
              <input
                className="field__control"
                type="number"
                min={0}
                value={quantity}
                onChange={(event) => setQuantity(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            <span className="field__label">Description</span>
            <textarea
              className="field__control"
              rows={3}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={isPublished}
              onChange={(event) => setIsPublished(event.target.checked)}
            />
            Publish as soon as it is approved
          </label>
          <div className="badge-row">
            <Button type="submit" loading={createMutation.isPending}>
              List product
            </Button>
          </div>
        </form>
      </Card>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing ? `Edit ${editing.name}` : 'Edit product'}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button
              loading={updateMutation.isPending}
              onClick={() => {
                if (!editing) return
                updateMutation.mutate({
                  id: editing.id,
                  body: {
                    unit_price: editPrice,
                    description: editDescription,
                    is_published: editPublished,
                  },
                })
              }}
            >
              Save product
            </Button>
          </>
        }
      >
        <div className="form">
          <label className="field">
            <span className="field__label">Unit price ({editing?.currency})</span>
            <input
              className="field__control"
              inputMode="decimal"
              value={editPrice}
              onChange={(event) => setEditPrice(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Description</span>
            <textarea
              className="field__control"
              rows={3}
              value={editDescription}
              onChange={(event) => setEditDescription(event.target.value)}
            />
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={editPublished}
              onChange={(event) => setEditPublished(event.target.checked)}
            />
            Published
          </label>
          <div className="restock-row">
            <label className="field">
              <span className="field__label">Restock quantity</span>
              <input
                className="field__control"
                type="number"
                min={1}
                value={restockQuantity}
                onChange={(event) => setRestockQuantity(event.target.value)}
              />
            </label>
            <Button
              variant="secondary"
              loading={restockMutation.isPending}
              onClick={() => {
                if (!editing) return
                const parsed = Number(restockQuantity)
                if (!Number.isInteger(parsed) || parsed <= 0) {
                  onError(new Error('Use a positive whole number.'), 'Invalid restock quantity.')
                  return
                }
                restockMutation.mutate({ id: editing.id, quantity: parsed })
              }}
            >
              Restock
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

// ── Orders ──
function OrdersPanel({ profile }: { profile: SupplierProfileValue | null }) {
  const ordersQuery = useQuery({
    queryKey: ['mp-supplier-orders'],
    queryFn: () => apiFetch<Page<Order>>('/marketplace/orders/?ordering=-placed_at'),
    enabled: Boolean(profile),
  })

  const orders = (ordersQuery.data?.results ?? []).filter(
    (order) => profile && order.supplier === profile.id,
  )

  if (!profile) {
    return (
      <Card title="Orders">
        <p className="field__hint">Register the supplier profile to see purchase orders.</p>
      </Card>
    )
  }

  return (
    <Card title="Purchase orders">
      {ordersQuery.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : ordersQuery.isError ? (
        <ErrorState
          message={
            ordersQuery.error instanceof Error ? ordersQuery.error.message : 'Could not load orders.'
          }
          onRetry={() => void ordersQuery.refetch()}
        />
      ) : orders.length === 0 ? (
        <EmptyState
          title="No orders yet"
          message="Buyers' orders appear here; open one to ship it or decide a refund."
        />
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Reference</th>
                <th>Buyer</th>
                <th className="num">Total</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => {
                const meta = statusMeta('order', order.status)
                return (
                  <tr key={order.id}>
                    <td>
                      {order.reference}
                      <span className="field__hint">{formatDateTime(order.placed_at)}</span>
                    </td>
                    <td>{order.shipping_name || order.buyer_detail?.full_name || '—'}</td>
                    <td className="num">{formatMoney(order.total, order.currency)}</td>
                    <td>
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                    </td>
                    <td className="num">
                      <Link to={`/marketplace/orders/${order.id}`} className="btn btn--secondary btn--sm">
                        Open
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="field__hint">
        Shipping, delivery and refund decisions are recorded on the order detail page so every
        financial step keeps its audit trail.
      </p>
    </Card>
  )
}
