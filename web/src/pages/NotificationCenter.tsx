import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge } from '../components/Badge'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { EmptyState } from '../components/EmptyState'
import { ErrorState } from '../components/ErrorState'
import { Spinner } from '../components/Spinner'
import { ApiError, apiFetch } from '../lib/api'
import { formatDateTime } from '../lib/format'
import type { Notification, NotificationPreference } from '../lib/types'

export function NotificationCenter() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [prefError, setPrefError] = useState<string | null>(null)

  const notificationsQuery = useQuery({
    queryKey: ['notifications'],
    queryFn: () => apiFetch<Notification[]>('/notifications/'),
  })
  const unreadQuery = useQuery({
    queryKey: ['notifications-unread'],
    queryFn: () => apiFetch<{ count: number }>('/notifications/unread-count/'),
  })
  const preferencesQuery = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: () => apiFetch<NotificationPreference[]>('/notifications/preferences/'),
  })

  const readMutation = useMutation({
    mutationFn: (id: string) =>
      apiFetch<Notification>(`/notifications/${id}/read/`, { method: 'POST' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['notifications'] })
      void queryClient.invalidateQueries({ queryKey: ['notifications-unread'] })
    },
  })
  const readAllMutation = useMutation({
    mutationFn: () => apiFetch('/notifications/read-all/', { method: 'POST' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['notifications'] })
      void queryClient.invalidateQueries({ queryKey: ['notifications-unread'] })
    },
  })
  const preferencesMutation = useMutation({
    mutationFn: (prefs: NotificationPreference[]) =>
      apiFetch<NotificationPreference[]>('/notifications/preferences/', {
        method: 'PATCH',
        body: { preferences: prefs },
      }),
    onSuccess: () => {
      setPrefError(null)
      void queryClient.invalidateQueries({ queryKey: ['notification-preferences'] })
    },
    onError: (error) => {
      setPrefError(error instanceof ApiError ? error.message : 'Could not save preferences.')
    },
  })

  const notifications = notificationsQuery.data ?? []
  const unreadCount = unreadQuery.data?.count ?? 0

  if (notificationsQuery.isPending && notifications.length === 0) {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" label="Loading notifications…" />
      </div>
    )
  }
  if (notificationsQuery.isError) {
    return (
      <ErrorState
        message={
          notificationsQuery.error instanceof Error
            ? notificationsQuery.error.message
            : 'Could not load notifications.'
        }
        onRetry={() => void notificationsQuery.refetch()}
      />
    )
  }

  function onMarkRead(id: string): void {
    readMutation.mutate(id)
  }
  function onMarkAllRead(): void {
    readAllMutation.mutate()
  }
  function onGoTo(link: string | null): void {
    if (link) navigate(link, { replace: true })
  }

  function onPreferenceChange(index: number, checked: boolean): void {
    const next = (preferencesQuery.data?.slice() ?? []) as NotificationPreference[]
    next[index] = { ...next[index], in_app: checked }
    preferencesMutation.mutate(next)
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Notification center</h1>
          <p className="page__subtitle">
            Activity across your logbook, training, and marketplace workspaces.
          </p>
        </div>
        <div className="badge-row">
          <Button
            variant="secondary"
            size="sm"
            disabled={unreadCount === 0 || readAllMutation.isPending}
            loading={readAllMutation.isPending}
            onClick={onMarkAllRead}
          >
            Mark all read
          </Button>
        </div>
      </header>

      {unreadCount > 0 && (
        <div className="badge-row unread-banner">
          <Badge tone="info">{unreadCount} unread</Badge>
        </div>
      )}

      {notifications.length === 0 ? (
        <EmptyState
          title="No notifications yet"
          message="Activity here — record submissions, reviews, orders, and more — appears in your feed."
        />
      ) : (
        <ul className="notification-list">
          {notifications.map((notification) => (
            <li
              key={notification.id}
              className={`notification-row ${!notification.is_read ? 'notification-row--unread' : ''}`}
            >
              <button
                type="button"
                className="notification-row__body"
                onClick={() => {
                  onGoTo(notification.link)
                  if (!notification.is_read) onMarkRead(notification.id)
                }}
              >
                <span className="badge-row">
                  <Badge
                    tone={!notification.is_read ? 'info' : 'neutral'}
                    title={notification.category}
                  >
                    {!notification.is_read && '●'}
                  </Badge>
                  <span className="field__hint">
                    {formatDateTime(notification.created_at)}
                  </span>
                </span>
                <div>
                  <strong className="notification-row__title">{notification.title}</strong>
                  <p className="notification-row__body-text">{notification.body}</p>
                  {notification.actor_detail && (
                    <span className="notification-row__meta">
                      by {notification.actor_detail.full_name}
                    </span>
                  )}
                </div>
                {!notification.is_read && (
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={readMutation.variables === notification.id}
                    onClick={(event) => {
                      event.stopPropagation()
                      onMarkRead(notification.id)
                    }}
                  >
                    Mark read
                  </Button>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <Card title="Delivery preferences">
        <p className="field__hint">
          Choose which kinds of activity appear in your in-app feed. Email
          delivery is not available yet, so no email option is shown.
        </p>
        {preferencesQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" />
          </div>
        ) : preferencesQuery.isError ? (
          <ErrorState message="Could not load preferences." onRetry={() => void preferencesQuery.refetch()} />
        ) : (
          <form className="form" onSubmit={(event) => event.preventDefault()} noValidate>
            {prefError && (
              <p className="form-alert" role="alert">{prefError}</p>
            )}
            <ul className="preference-list">
              {(preferencesQuery.data ?? []).map((pref, index) => (
                <li key={pref.category} className="preference-item">
                  <span className="preference-item__label">
                    {pref.category.replaceAll('_', ' ')}
                  </span>
                  <div className="badge-row">
                    <label className="toggle">
                      <input
                        type="checkbox"
                        checked={pref.in_app}
                        onChange={(event) =>
                          onPreferenceChange(index, event.target.checked)
                        }
                      />
                      <span className="toggle__thumb" aria-hidden="true" />
                      <span className="toggle__label" aria-hidden="true">
                        In app
                      </span>
                    </label>
                  </div>
                </li>
              ))}
            </ul>
            {preferencesMutation.isPending && (
              <p className="field__hint">
                <Spinner size="sm" /> Saving…
              </p>
            )}
          </form>
        )}
      </Card>
    </div>
  )
}
