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
import { ApiError, apiFetch } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { roleLabel } from '../../lib/roles'
import type {
  AuditEvent,
  Department,
  Institution,
  Invitation,
  Membership,
  Page,
  UserSummary,
} from '../../lib/types'

const INSTITUTION_ROLES = [
  'trainee',
  'supervisor',
  'examiner',
  'department_manager',
  'institution_admin',
]

const INSTITUTION_TYPES = ['hospital', 'university', 'clinic', 'training_center', 'other']

type Tab = 'profile' | 'departments' | 'members' | 'invitations' | 'audit'

const TABS: { value: Tab; label: string }[] = [
  { value: 'profile', label: 'Institution profile' },
  { value: 'departments', label: 'Departments' },
  { value: 'members', label: 'Members & roles' },
  { value: 'invitations', label: 'Invitations' },
  { value: 'audit', label: 'Audit trail' },
]

export function InstitutionAdminPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const isPlatformAdmin = Boolean(user?.is_platform_admin)
  const administeredIds = (user?.roles ?? [])
    .filter((assignment) => assignment.is_active && assignment.role === 'institution_admin')
    .map((assignment) => assignment.institution)
    .filter((value): value is string => Boolean(value))
  const canAdmin = isPlatformAdmin || administeredIds.length > 0

  const [preferredInstitution, setPreferredInstitution] = useState('')
  const [tab, setTab] = useState<Tab>('profile')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const institutionsQuery = useQuery({
    queryKey: ['institutions'],
    queryFn: () => apiFetch<Page<Institution>>('/institutions/?page_size=100'),
    enabled: canAdmin,
  })

  const institutions = (institutionsQuery.data?.results ?? []).filter(
    (item) => isPlatformAdmin || administeredIds.includes(item.id),
  )

  // Derive the active institution instead of syncing it through an effect.
  const selectedInstitution = preferredInstitution || institutions[0]?.id || ''
  const institution = institutions.find((item) => item.id === selectedInstitution) ?? null

  function invalidate(): void {
    void queryClient.invalidateQueries({ queryKey: ['departments', selectedInstitution] })
    void queryClient.invalidateQueries({ queryKey: ['memberships', selectedInstitution] })
    void queryClient.invalidateQueries({ queryKey: ['invitations', selectedInstitution] })
    void queryClient.invalidateQueries({ queryKey: ['audit', selectedInstitution] })
    void queryClient.invalidateQueries({ queryKey: ['institutions'] })
  }

  function reportError(mutationError: unknown, fallback: string): void {
    setSuccess(null)
    setError(
      mutationError instanceof ApiError
        ? mutationError.message
        : mutationError instanceof Error
          ? mutationError.message
          : fallback,
    )
  }

  if (!canAdmin) {
    return (
      <div className="page">
        <div className="state-block state-block--error" role="alert">
          <h3 className="state-block__title">Institution administrator access required</h3>
          <p className="state-block__message">
            This workspace manages one or more institutions you administer.
          </p>
          <Link to="/dashboard" className="btn btn--secondary btn--sm">
            Back to dashboard
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Institution administration</h1>
          <p className="page__subtitle">
            Departments, memberships, invitations and the audit trail of your institution.
          </p>
        </div>
        {institutions.length > 1 && (
          <label className="field">
            <span className="field__label">Institution</span>
            <select
              className="field__control"
              value={selectedInstitution}
              onChange={(event) => {
                setPreferredInstitution(event.target.value)
                setError(null)
                setSuccess(null)
              }}
            >
              {institutions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>

      {(error || success) && (
        <p className={error ? 'form-alert' : 'form-alert form-alert--success'} role="alert">
          {error ?? success}
        </p>
      )}

      {institutionsQuery.isError ? (
        <ErrorState
          message={
            institutionsQuery.error instanceof Error
              ? institutionsQuery.error.message
              : 'Could not load institutions.'
          }
          onRetry={() => void institutionsQuery.refetch()}
        />
      ) : !institution ? (
        <div className="page-loading" role="status">
          <Spinner size="md" label="Loading institution…" />
        </div>
      ) : (
        <>
          <div className="tabs" role="tablist" aria-label="Institution sections">
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

          {tab === 'profile' && (
            <ProfilePanel
              key={institution.id}
              institution={institution}
              onError={reportError}
              onSuccess={(message) => {
                setError(null)
                setSuccess(message)
                invalidate()
              }}
            />
          )}
          {tab === 'departments' && (
            <DepartmentsPanel institutionId={institution.id} onError={reportError} onChanged={invalidate} />
          )}
          {tab === 'members' && (
            <MembersPanel institutionId={institution.id} onError={reportError} onChanged={invalidate} />
          )}
          {tab === 'invitations' && (
            <InvitationsPanel institutionId={institution.id} onError={reportError} onChanged={invalidate} />
          )}
          {tab === 'audit' && <AuditPanel institutionId={institution.id} />}
        </>
      )}
    </div>
  )
}

// ── Profile ──
function ProfilePanel({
  institution,
  onError,
  onSuccess,
}: {
  institution: Institution
  onError: (error: unknown, fallback: string) => void
  onSuccess: (message: string) => void
}) {
  const [name, setName] = useState(institution.name)
  const [institutionType, setInstitutionType] = useState(institution.institution_type)
  const [city, setCity] = useState(institution.city)
  const [country, setCountry] = useState(institution.country)
  const [address, setAddress] = useState(institution.address ?? '')
  const [website, setWebsite] = useState(institution.website ?? '')
  const [contactEmail, setContactEmail] = useState(institution.contact_email ?? '')

  const saveMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<Institution>(`/institutions/${institution.id}/`, { method: 'PATCH', body: payload }),
    onSuccess: () => onSuccess('Institution profile updated.'),
    onError: (error) => onError(error, 'Could not update the institution.'),
  })

  function onSubmit(event: FormEvent): void {
    event.preventDefault()
    saveMutation.mutate({
      name: name.trim(),
      institution_type: institutionType,
      city: city.trim(),
      country: country.trim(),
      address: address.trim(),
      website: website.trim(),
      contact_email: contactEmail.trim(),
    })
  }

  return (
    <Card title="Profile">
      <form className="form" onSubmit={onSubmit} noValidate>
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
            <span className="field__label">Type</span>
            <select
              className="field__control"
              value={institutionType}
              onChange={(event) => setInstitutionType(event.target.value)}
            >
              {INSTITUTION_TYPES.map((value) => (
                <option key={value} value={value}>
                  {value.replaceAll('_', ' ')}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">City</span>
            <input
              className="field__control"
              value={city}
              onChange={(event) => setCity(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Country</span>
            <input
              className="field__control"
              value={country}
              onChange={(event) => setCountry(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Contact email</span>
            <input
              className="field__control"
              type="email"
              value={contactEmail}
              onChange={(event) => setContactEmail(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Website</span>
            <input
              className="field__control"
              type="url"
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
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
        <div className="badge-row">
          <Button type="submit" loading={saveMutation.isPending} disabled={!name.trim()}>
            Save profile
          </Button>
          <Badge tone={institution.is_active ? 'success' : 'neutral'}>
            {institution.is_active ? 'Active' : 'Inactive'}
          </Badge>
        </div>
      </form>
    </Card>
  )
}

// ── Departments ──
function DepartmentsPanel({
  institutionId,
  onError,
  onChanged,
}: {
  institutionId: string
  onError: (error: unknown, fallback: string) => void
  onChanged: () => void
}) {
  const [name, setName] = useState('')
  const [code, setCode] = useState('')

  const departmentsQuery = useQuery({
    queryKey: ['departments', institutionId],
    queryFn: () =>
      apiFetch<Page<Department>>(`/departments/?institution=${institutionId}&page_size=100`),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<Department>('/departments/', {
        method: 'POST',
        body: { institution: institutionId, name: name.trim(), code: code.trim() },
      }),
    onSuccess: () => {
      setName('')
      setCode('')
      onChanged()
    },
    onError: (error) => onError(error, 'Could not create the department.'),
  })
  const deactivateMutation = useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/departments/${id}/`, { method: 'DELETE' }),
    onSuccess: onChanged,
    onError: (error) => onError(error, 'Could not deactivate the department.'),
  })

  const departments = departmentsQuery.data?.results ?? []

  return (
    <div className="account-grid">
      <Card title="Departments">
        {departmentsQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" />
          </div>
        ) : departmentsQuery.isError ? (
          <ErrorState
            message={
              departmentsQuery.error instanceof Error
                ? departmentsQuery.error.message
                : 'Could not load departments.'
            }
            onRetry={() => void departmentsQuery.refetch()}
          />
        ) : departments.length === 0 ? (
          <EmptyState title="No departments" message="Add the first department on the right." />
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Code</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {departments.map((department) => (
                  <tr key={department.id}>
                    <td>{department.name}</td>
                    <td>{department.code || '—'}</td>
                    <td>
                      <Badge tone={department.is_active ? 'success' : 'neutral'}>
                        {department.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="num">
                      {department.is_active && (
                        <Button
                          variant="danger"
                          size="sm"
                          loading={deactivateMutation.isPending}
                          onClick={() => deactivateMutation.mutate(department.id)}
                        >
                          Deactivate
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Add department">
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault()
            if (!name.trim()) {
              onError(new Error('A department name is required.'), 'A department name is required.')
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
            <span className="field__label">Code</span>
            <input
              className="field__control"
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
          </label>
          <div className="badge-row">
            <Button type="submit" loading={createMutation.isPending}>
              Add department
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

// ── Members & roles ──
function MembersPanel({
  institutionId,
  onError,
  onChanged,
}: {
  institutionId: string
  onError: (error: unknown, fallback: string) => void
  onChanged: () => void
}) {
  const [role, setRole] = useState('trainee')
  const [department, setDepartment] = useState('')
  const [userId, setUserId] = useState('')

  const membersQuery = useQuery({
    queryKey: ['memberships', institutionId],
    queryFn: () =>
      apiFetch<Page<Membership>>(`/memberships/?institution=${institutionId}&page_size=100`),
  })
  const usersQuery = useQuery({
    queryKey: ['institution-users', institutionId],
    queryFn: () => apiFetch<Page<UserSummary>>(`/users/?institution=${institutionId}&page_size=100`),
  })
  const departmentsQuery = useQuery({
    queryKey: ['departments', institutionId],
    queryFn: () =>
      apiFetch<Page<Department>>(`/departments/?institution=${institutionId}&page_size=100`),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<Membership>('/memberships/', {
        method: 'POST',
        body: {
          user: userId,
          role,
          institution: institutionId,
          ...(department ? { department } : {}),
        },
      }),
    onSuccess: () => {
      setUserId('')
      setDepartment('')
      onChanged()
    },
    onError: (error) => onError(error, 'Could not grant the role.'),
  })
  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      apiFetch<Membership>(`/memberships/${id}/`, {
        method: 'PATCH',
        body: { is_active: isActive },
      }),
    onSuccess: onChanged,
    onError: (error) => onError(error, 'Could not update the role assignment.'),
  })

  const members = membersQuery.data?.results ?? []
  const users = usersQuery.data?.results ?? []
  const departments = departmentsQuery.data?.results ?? []

  return (
    <div className="account-grid">
      <Card title="Members and role assignments">
        {membersQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" />
          </div>
        ) : membersQuery.isError ? (
          <ErrorState
            message={
              membersQuery.error instanceof Error
                ? membersQuery.error.message
                : 'Could not load memberships.'
            }
            onRetry={() => void membersQuery.refetch()}
          />
        ) : members.length === 0 ? (
          <EmptyState title="No memberships" message="Invite or grant a role to the first member." />
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Role</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {members.map((membership) => (
                  <tr key={membership.id}>
                    <td>
                      {membership.user_detail.full_name}
                      <span className="field__hint">{membership.user_detail.email}</span>
                    </td>
                    <td>{roleLabel(membership.role)}</td>
                    <td>{membership.department_name ?? '—'}</td>
                    <td>
                      <Badge tone={membership.is_active ? 'success' : 'neutral'}>
                        {membership.is_active ? 'Active' : 'Revoked'}
                      </Badge>
                    </td>
                    <td className="num">
                      <Button
                        variant={membership.is_active ? 'danger' : 'secondary'}
                        size="sm"
                        loading={toggleMutation.isPending}
                        onClick={() =>
                          toggleMutation.mutate({
                            id: membership.id,
                            isActive: !membership.is_active,
                          })
                        }
                      >
                        {membership.is_active ? 'Revoke' : 'Restore'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Grant a role">
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault()
            if (!userId) {
              onError(new Error('Choose a member first.'), 'Choose a member first.')
              return
            }
            createMutation.mutate()
          }}
          noValidate
        >
          <label className="field">
            <span className="field__label">Member *</span>
            <select
              className="field__control"
              value={userId}
              disabled={usersQuery.isPending}
              onChange={(event) => setUserId(event.target.value)}
            >
              <option value="">
                {usersQuery.isPending ? 'Loading…' : 'Choose a member'}
              </option>
              {users.map((candidate) => (
                <option key={candidate.id} value={String(candidate.id)}>
                  {candidate.full_name} — {candidate.email}
                </option>
              ))}
            </select>
          </label>
          {usersQuery.isError && (
            <p className="field__hint">
              The member directory is available to institution administrators only.
            </p>
          )}
          <label className="field">
            <span className="field__label">Role *</span>
            <select
              className="field__control"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              {INSTITUTION_ROLES.map((value) => (
                <option key={value} value={value}>
                  {roleLabel(value)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Department</span>
            <select
              className="field__control"
              value={department}
              disabled={departmentsQuery.isPending}
              onChange={(event) => setDepartment(event.target.value)}
            >
              <option value="">None</option>
              {departments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <div className="badge-row">
            <Button type="submit" loading={createMutation.isPending}>
              Grant role
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

// ── Invitations ──
function InvitationsPanel({
  institutionId,
  onError,
  onChanged,
}: {
  institutionId: string
  onError: (error: unknown, fallback: string) => void
  onChanged: () => void
}) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('trainee')
  const [department, setDepartment] = useState('')

  const invitationsQuery = useQuery({
    queryKey: ['invitations', institutionId],
    queryFn: () =>
      apiFetch<Page<Invitation>>(`/invitations/?institution=${institutionId}&ordering=-created_at`),
  })
  const departmentsQuery = useQuery({
    queryKey: ['departments', institutionId],
    queryFn: () =>
      apiFetch<Page<Department>>(`/departments/?institution=${institutionId}&page_size=100`),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<Invitation>('/invitations/', {
        method: 'POST',
        body: {
          institution: institutionId,
          email: email.trim().toLowerCase(),
          role,
          ...(department ? { department } : {}),
        },
      }),
    onSuccess: () => {
      setEmail('')
      setDepartment('')
      onChanged()
    },
    onError: (error) => onError(error, 'Could not send the invitation.'),
  })
  const revokeMutation = useMutation({
    mutationFn: (id: string) => apiFetch<{ message: string }>(`/invitations/${id}/revoke/`, { method: 'POST' }),
    onSuccess: onChanged,
    onError: (error) => onError(error, 'Could not revoke the invitation.'),
  })

  const invitations = invitationsQuery.data?.results ?? []
  const departments = departmentsQuery.data?.results ?? []
  // Captured once per mount: expiry is informational, the backend enforces it.
  const [now] = useState(Date.now)

  function stateOf(invitation: Invitation): { label: string; tone: 'success' | 'neutral' | 'warning' } {
    if (invitation.accepted_at) return { label: 'Accepted', tone: 'success' }
    if (invitation.revoked_at) return { label: 'Revoked', tone: 'neutral' }
    if (new Date(invitation.expires_at).getTime() < now) {
      return { label: 'Expired', tone: 'warning' }
    }
    return { label: 'Pending', tone: 'warning' }
  }

  return (
    <div className="account-grid">
      <Card title="Invitations">
        {invitationsQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" />
          </div>
        ) : invitationsQuery.isError ? (
          <ErrorState
            message={
              invitationsQuery.error instanceof Error
                ? invitationsQuery.error.message
                : 'Could not load invitations.'
            }
            onRetry={() => void invitationsQuery.refetch()}
          />
        ) : invitations.length === 0 ? (
          <EmptyState title="No invitations" message="Invite a colleague to join the institution." />
        ) : (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Expires</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {invitations.map((invitation) => {
                  const state = stateOf(invitation)
                  return (
                    <tr key={invitation.id}>
                      <td>{invitation.email}</td>
                      <td>{roleLabel(invitation.role)}</td>
                      <td>{formatDate(invitation.expires_at)}</td>
                      <td>
                        <Badge tone={state.tone}>{state.label}</Badge>
                      </td>
                      <td className="num">
                        {!invitation.accepted_at && !invitation.revoked_at && (
                          <Button
                            variant="danger"
                            size="sm"
                            loading={revokeMutation.isPending}
                            onClick={() => revokeMutation.mutate(invitation.id)}
                          >
                            Revoke
                          </Button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Invite a member">
        <form
          className="form"
          onSubmit={(event) => {
            event.preventDefault()
            if (!email.trim()) {
              onError(new Error('An email address is required.'), 'An email address is required.')
              return
            }
            createMutation.mutate()
          }}
          noValidate
        >
          <label className="field">
            <span className="field__label">Email *</span>
            <input
              className="field__control"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Role *</span>
            <select
              className="field__control"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              {INSTITUTION_ROLES.map((value) => (
                <option key={value} value={value}>
                  {roleLabel(value)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Department</span>
            <select
              className="field__control"
              value={department}
              disabled={departmentsQuery.isPending}
              onChange={(event) => setDepartment(event.target.value)}
            >
              <option value="">None</option>
              {departments.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <div className="badge-row">
            <Button type="submit" loading={createMutation.isPending}>
              Send invitation
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

// ── Audit ──
function AuditPanel({ institutionId }: { institutionId: string }) {
  const [action, setAction] = useState('')
  const [appliedAction, setAppliedAction] = useState('')

  const auditQuery = useQuery({
    queryKey: ['audit', institutionId, appliedAction],
    queryFn: () => {
      const params = new URLSearchParams({ institution: institutionId, page_size: '25' })
      if (appliedAction.trim()) params.set('action', appliedAction.trim())
      return apiFetch<Page<AuditEvent>>(`/audit/?${params.toString()}`)
    },
  })

  const events = auditQuery.data?.results ?? []

  return (
    <Card title="Audit trail">
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
            placeholder="e.g. procedure.approved"
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
        <EmptyState title="No audit events" message="Events appear as members act in this institution." />
      ) : (
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Actor</th>
                <th>Object</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{formatDateTime(event.created_at)}</td>
                  <td>{event.action}</td>
                  <td>{event.actor_email ?? '—'}</td>
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
