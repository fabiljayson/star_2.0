import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { apiFetch } from '../../lib/api'
import { formatDateTime, formatMoney } from '../../lib/format'
import type {
  AuditEvent,
  Dispute,
  Page,
  Product,
  ProductCategory,
  SupplierProfileValue,
} from '../../lib/types'

type Tab = 'suppliers' | 'products' | 'categories' | 'disputes' | 'audit'

const TABS: { value: Tab; label: string }[] = [
  { value: 'suppliers', label: 'Supplier verification' },
  { value: 'products', label: 'Product moderation' },
  { value: 'categories', label: 'Categories' },
  { value: 'disputes', label: 'Disputes' },
  { value: 'audit', label: 'Audit & monitoring' },
]

export function PlatformAdminPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('suppliers')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  if (!user?.is_platform_admin) {
    return (
      <div className="page">
        <div className="state-block state-block--error" role="alert">
          <h3 className="state-block__title">Platform administrator access required</h3>
          <p className="state-block__message">
            This workspace verifies suppliers, moderates products and resolves marketplace
            disputes.
          </p>
          <Link to="/dashboard" className="btn btn--secondary btn--sm">
            Back to dashboard
          </Link>
        </div>
      </div>
    )
  }

  function reportError(mutationError: unknown, fallback: string): void {
    setSuccess(null)
    setError(mutationError instanceof Error ? mutationError.message : fallback)
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Platform administration</h1>
          <p className="page__subtitle">
            Verification and moderation queues, category catalog, disputes and the audit trail.
          </p>
        </div>
      </header>

      {(error || success) && (
        <p className={error ? 'form-alert' : 'form-alert form-alert--success'} role="alert">
          {error ?? success}
        </p>
      )}

      <div className="tabs" role="tablist" aria-label="Platform administration sections">
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

      {tab === 'suppliers' && (
        <SuppliersPanel
          onError={reportError}
          onSaved={(message) => {
            setError(null)
            setSuccess(message)
          }}
        />
      )}
      {tab === 'products' && (
        <ProductsPanel
          onError={reportError}
          onSaved={(message) => {
            setError(null)
            setSuccess(message)
          }}
        />
      )}
      {tab === 'categories' && (
        <CategoriesPanel
          onError={reportError}
          onSaved={(message) => {
            setError(null)
            setSuccess(message)
          }}
        />
      )}
      {tab === 'disputes' && (
        <DisputesPanel
          onError={reportError}
          onSaved={(message) => {
            setError(null)
            setSuccess(message)
          }}
        />
      )}
      {tab === 'audit' && <AuditPanel />}
    </div>
  )
}

// ── Supplier verification ──
function SuppliersPanel({
  onError,
  onSaved,
}: {
  onError: (error: unknown, fallback: string) => void
  onSaved: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [suspendReason, setSuspendReason] = useState('')

  const suppliersQuery = useQuery({
    queryKey: ['admin-suppliers'],
    queryFn: () => apiFetch<SupplierProfileValue[]>('/marketplace/admin/suppliers/'),
  })

  const decideMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'verify' | 'reject' | 'suspend' }) =>
      apiFetch<SupplierProfileValue>(`/marketplace/admin/suppliers/${id}/${action}/`, {
        method: 'POST',
        body: action === 'suspend' ? { reason: suspendReason } : {},
      }),
    onSuccess: (_data, variables) => {
      setSuspendReason('')
      void queryClient.invalidateQueries({ queryKey: ['admin-suppliers'] })
      onSaved(
        variables.action === 'verify'
          ? 'Supplier verified.'
          : variables.action === 'reject'
            ? 'Supplier application rejected.'
            : 'Supplier suspended.',
      )
    },
    onError: (error) => onError(error, 'Could not update the supplier.'),
  })

  const suppliers = suppliersQuery.data ?? []

  return (
    <Card title="Supplier verification queue">
      {suppliersQuery.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : suppliersQuery.isError ? (
        <ErrorState
          message={
            suppliersQuery.error instanceof Error
              ? suppliersQuery.error.message
              : 'Could not load suppliers.'
          }
          onRetry={() => void suppliersQuery.refetch()}
        />
      ) : suppliers.length === 0 ? (
        <EmptyState
          title="No supplier profiles"
          message="Supplier registrations appear here for verification."
        />
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Contact</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {suppliers.map((supplier) => (
                <tr key={supplier.id}>
                  <td>{supplier.company_name}</td>
                  <td>
                    {supplier.contact_email}
                    <span className="field__hint">{supplier.contact_phone || '—'}</span>
                  </td>
                  <td>
                    <Badge
                      tone={
                        supplier.verification_status === 'verified'
                          ? 'success'
                          : supplier.verification_status === 'rejected' ||
                              supplier.verification_status === 'suspended'
                            ? 'danger'
                            : 'warning'
                      }
                    >
                      {supplier.verification_status.replaceAll('_', ' ')}
                    </Badge>
                  </td>
                  <td className="num">
                    <div className="badge-row">
                      {supplier.verification_status !== 'verified' && (
                        <Button
                          size="sm"
                          loading={decideMutation.isPending}
                          onClick={() =>
                            decideMutation.mutate({ id: supplier.id, action: 'verify' })
                          }
                        >
                          Verify
                        </Button>
                      )}
                      {supplier.verification_status === 'pending' && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            decideMutation.mutate({ id: supplier.id, action: 'reject' })
                          }
                        >
                          Reject
                        </Button>
                      )}
                      {supplier.verification_status === 'verified' && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() =>
                            decideMutation.mutate({ id: supplier.id, action: 'suspend' })
                          }
                        >
                          Suspend
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <label className="field">
        <span className="field__label">Suspension reason (used when suspending)</span>
        <input
          className="field__control"
          value={suspendReason}
          onChange={(event) => setSuspendReason(event.target.value)}
        />
      </label>
    </Card>
  )
}

// ── Product moderation ──
function ProductsPanel({
  onError,
  onSaved,
}: {
  onError: (error: unknown, fallback: string) => void
  onSaved: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')

  const productsQuery = useQuery({
    queryKey: ['admin-products'],
    queryFn: () => apiFetch<Page<Product>>('/marketplace/admin/products/'),
  })

  const decideMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'approve' | 'reject' }) =>
      apiFetch<Product>(`/marketplace/admin/products/${id}/${action}/`, { method: 'POST' }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['admin-products'] })
      onSaved(variables.action === 'approve' ? 'Product approved.' : 'Product rejected.')
    },
    onError: (error) => onError(error, 'Could not moderate the product.'),
  })

  const products = (productsQuery.data?.results ?? []).filter(
    (product) => !statusFilter || product.approval_status === statusFilter,
  )

  return (
    <Card title="Product moderation queue">
      <form className="list-filters" role="search" onSubmit={(event) => event.preventDefault()}>
        <label className="field">
          <span className="field__label">Approval status</span>
          <select
            className="field__control"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
      </form>

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
        <EmptyState title="No products to moderate" message="Listings appear here for approval." />
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Supplier</th>
                <th className="num">Price</th>
                <th>Approval</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id}>
                  <td>
                    {product.name}
                    <span className="field__hint">SKU {product.sku}</span>
                  </td>
                  <td>{product.supplier_name}</td>
                  <td className="num">{formatMoney(product.unit_price, product.currency)}</td>
                  <td>
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
                  </td>
                  <td className="num">
                    <div className="badge-row">
                      <Link
                        to={`/marketplace/products/${product.id}`}
                        className="btn btn--ghost btn--sm"
                      >
                        View
                      </Link>
                      {product.approval_status !== 'approved' && (
                        <Button
                          size="sm"
                          onClick={() => decideMutation.mutate({ id: product.id, action: 'approve' })}
                        >
                          Approve
                        </Button>
                      )}
                      {product.approval_status !== 'rejected' && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => decideMutation.mutate({ id: product.id, action: 'reject' })}
                        >
                          Reject
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

// ── Categories ──
function CategoriesPanel({
  onError,
  onSaved,
}: {
  onError: (error: unknown, fallback: string) => void
  onSaved: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')

  const categoriesQuery = useQuery({
    queryKey: ['admin-categories'],
    queryFn: () => apiFetch<Page<ProductCategory>>('/marketplace/admin/categories/'),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<ProductCategory>('/marketplace/admin/categories/', {
        method: 'POST',
        body: { name: name.trim(), slug: slug.trim().toLowerCase() },
      }),
    onSuccess: () => {
      setName('')
      setSlug('')
      void queryClient.invalidateQueries({ queryKey: ['admin-categories'] })
      void queryClient.invalidateQueries({ queryKey: ['mp-categories'] })
      onSaved('Category created.')
    },
    onError: (error) => onError(error, 'Could not create the category.'),
  })

  const categories = categoriesQuery.data?.results ?? []

  return (
    <div className="account-grid">
      <Card title="Marketplace categories">
        {categoriesQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" />
          </div>
        ) : categoriesQuery.isError ? (
          <ErrorState
            message={
              categoriesQuery.error instanceof Error
                ? categoriesQuery.error.message
                : 'Could not load categories.'
            }
            onRetry={() => void categoriesQuery.refetch()}
          />
        ) : categories.length === 0 ? (
          <EmptyState title="No categories" message="Create the first product category." />
        ) : (
          <ul className="role-list">
            {categories.map((category) => (
              <li key={category.id}>
                <span className="badge-row">
                  <strong>{category.name}</strong>
                  <Badge tone={category.is_active ? 'success' : 'neutral'}>
                    {category.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                  <span className="field__hint">{category.slug}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="New category">
        <form
          className="form"
          onSubmit={(event: FormEvent) => {
            event.preventDefault()
            if (!name.trim() || !slug.trim()) {
              onError(new Error('Name and slug are required.'), 'Missing category fields.')
              return
            }
            createMutation.mutate()
          }}
          noValidate
        >
          <label className="field">
            <span className="field__label">Name *</span>
            <input
              className="field__control"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Slug *</span>
            <input
              className="field__control"
              value={slug}
              placeholder="surgical-instruments"
              onChange={(event) => setSlug(event.target.value)}
            />
          </label>
          <div className="badge-row">
            <Button type="submit" loading={createMutation.isPending}>
              Create category
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

// ── Disputes ──
function DisputesPanel({
  onError,
  onSaved,
}: {
  onError: (error: unknown, fallback: string) => void
  onSaved: (message: string) => void
}) {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('open')

  const disputesQuery = useQuery({
    queryKey: ['admin-disputes', statusFilter],
    queryFn: () =>
      apiFetch<Page<Dispute>>(
        `/marketplace/disputes/${statusFilter ? `?status=${statusFilter}` : ''}`,
      ),
  })

  const resolveMutation = useMutation({
    mutationFn: ({
      id,
      resolution,
    }: {
      id: string
      resolution: 'buyer_favored' | 'supplier_favored'
    }) =>
      apiFetch<Dispute>(`/marketplace/disputes/${id}/resolve/`, {
        method: 'POST',
        body: { resolution },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin-disputes'] })
      onSaved('Dispute resolved and the outcome recorded.')
    },
    onError: (error) => onError(error, 'Could not resolve the dispute.'),
  })

  const disputes = disputesQuery.data?.results ?? []

  return (
    <Card title="Disputes">
      <form className="list-filters" role="search" onSubmit={(event) => event.preventDefault()}>
        <label className="field">
          <span className="field__label">Status</span>
          <select
            className="field__control"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
            <option value="">All</option>
          </select>
        </label>
      </form>

      {disputesQuery.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : disputesQuery.isError ? (
        <ErrorState
          message={
            disputesQuery.error instanceof Error
              ? disputesQuery.error.message
              : 'Could not load disputes.'
          }
          onRetry={() => void disputesQuery.refetch()}
        />
      ) : disputes.length === 0 ? (
        <EmptyState title="No disputes" message="Buyer and supplier disputes appear here." />
      ) : (
        <ul className="role-list">
          {disputes.map((dispute) => (
            <li key={dispute.id}>
              <span className="badge-row">
                <strong>Order {dispute.order.slice(0, 8)}</strong>
                <Badge tone={dispute.status === 'resolved' ? 'success' : 'warning'}>
                  {dispute.status}
                </Badge>
                <span className="field__hint">{formatDateTime(dispute.created_at)}</span>
              </span>
              <p>{dispute.description}</p>
              {dispute.evidence_entries.length > 0 && (
                <span className="field__hint">
                  {dispute.evidence_entries.length} evidence entr
                  {dispute.evidence_entries.length === 1 ? 'y' : 'ies'}
                </span>
              )}
              {dispute.status === 'open' && (
                <div className="badge-row">
                  <Button
                    size="sm"
                    loading={resolveMutation.isPending}
                    onClick={() =>
                      resolveMutation.mutate({ id: dispute.id, resolution: 'buyer_favored' })
                    }
                  >
                    Buyer favored
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      resolveMutation.mutate({ id: dispute.id, resolution: 'supplier_favored' })
                    }
                  >
                    Supplier favored
                  </Button>
                  <Link
                    to={`/marketplace/orders/${dispute.order}`}
                    className="btn btn--ghost btn--sm"
                  >
                    Open order
                  </Link>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

// ── Audit ──
function AuditPanel() {
  const [action, setAction] = useState('')
  const [appliedAction, setAppliedAction] = useState('')

  const auditQuery = useQuery({
    queryKey: ['admin-audit', appliedAction],
    queryFn: () => {
      const params = new URLSearchParams({ page_size: '25' })
      if (appliedAction.trim()) params.set('action', appliedAction.trim())
      return apiFetch<Page<AuditEvent>>(`/audit/?${params.toString()}`)
    },
  })

  const events = auditQuery.data?.results ?? []

  return (
    <Card title="Audit and operational monitoring">
      <form
        className="list-filters"
        role="search"
        onSubmit={(event) => {
          event.preventDefault()
          setAppliedAction(action)
        }}
      >
        <label className="field list-filters__search">
          <span className="field__label">Action</span>
          <input
            className="field__control"
            type="search"
            placeholder="e.g. payment.succeeded"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          />
        </label>
        <Button type="submit" variant="secondary" size="sm">
          Filter
        </Button>
        {appliedAction && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setAction('')
              setAppliedAction('')
            }}
          >
            Reset
          </Button>
        )}
      </form>

      {auditQuery.isPending ? (
        <div className="page-loading" role="status">
          <Spinner size="md" />
        </div>
      ) : auditQuery.isError ? (
        <ErrorState
          message={
            auditQuery.error instanceof Error ? auditQuery.error.message : 'Could not load audit events.'
          }
          onRetry={() => void auditQuery.refetch()}
        />
      ) : events.length === 0 ? (
        <EmptyState title="No audit events" message="Try a different action filter." />
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Institution</th>
                <th>Object</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{formatDateTime(event.created_at)}</td>
                  <td>{event.action}</td>
                  <td>{event.actor_email ?? '—'}</td>
                  <td>{event.institution_name ?? '—'}</td>
                  <td>
                    {event.object_type}
                    {event.object_pk ? ` · ${event.object_pk}` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
