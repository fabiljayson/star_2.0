import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useAuth } from '../../auth/context'
import { Badge } from '../../components/Badge'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { EmptyState } from '../../components/EmptyState'
import { ErrorState } from '../../components/ErrorState'
import { Spinner } from '../../components/Spinner'
import { ApiError, apiFetch } from '../../lib/api'
import { downloadFile } from '../../lib/download'
import { formatDateTime } from '../../lib/format'
import type { Institution, Page, ReportJob } from '../../lib/types'
import { REPORT_TYPES, statusMeta } from '../../lib/status'

const MARKETPLACE_GROUPS = new Set(['Marketplace'])

function groupOf(reportType: string): string {
  return REPORT_TYPES.find((item) => item.value === reportType)?.group ?? 'Logbook'
}

export function ReportsPage() {
  const { user, hasRole } = useAuth()
  const queryClient = useQueryClient()

  const canPickInstitution = hasRole('institution_admin') || hasRole('department_manager')
  const marketplaceUser = hasRole('buyer') || hasRole('supplier')

  const [reportType, setReportType] = useState(
    marketplaceUser ? 'buyer_orders' : 'individual_logbook',
  )
  const [format, setFormat] = useState<'csv' | 'pdf'>('csv')
  const [institution, setInstitution] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const isMarketplaceReport = MARKETPLACE_GROUPS.has(groupOf(reportType))
  const needsInstitution = !isMarketplaceReport

  const institutionsQuery = useQuery({
    queryKey: ['institutions'],
    queryFn: () => apiFetch<Page<Institution>>('/institutions/?page_size=100'),
    enabled: needsInstitution && canPickInstitution,
  })

  const jobsQuery = useQuery({
    queryKey: ['reports', user?.id],
    queryFn: () => apiFetch<Page<ReportJob>>('/reports/?ordering=-created_at'),
  })

  const createMutation = useMutation({
    mutationFn: () => {
      const parameters: Record<string, string> = {}
      if (dateFrom) parameters.date_from = dateFrom
      if (dateTo) parameters.date_to = dateTo
      const body: Record<string, unknown> = {
        report_type: reportType,
        format,
        parameters,
      }
      if (!isMarketplaceReport && institution) body.institution = institution
      return apiFetch<ReportJob>('/reports/', { method: 'POST', body })
    },
    onSuccess: () => {
      setFormError(null)
      void queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
    onError: (error) => {
      if (error instanceof ApiError && typeof error.details === 'object' && error.details) {
        const details = error.details as Record<string, unknown>
        const first = Object.values(details)[0]
        setFormError(Array.isArray(first) ? String(first[0]) : String(first))
      } else {
        setFormError(error instanceof Error ? error.message : 'Could not start the report.')
      }
    },
  })

  function onSubmit(event: FormEvent): void {
    event.preventDefault()
    setFormError(null)
    if (needsInstitution && canPickInstitution && !institution) {
      setFormError('Choose the institution this report must cover.')
      return
    }
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setFormError('The start date must not be after the end date.')
      return
    }
    createMutation.mutate()
  }

  const jobs = jobsQuery.data?.results ?? []
  const groups = ['Logbook', 'Training', 'Marketplace']

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">Reports</h1>
          <p className="page__subtitle">
            Generate CSV or PDF exports inside your permitted scope. Downloads expire after
            a while for safety.
          </p>
        </div>
      </header>

      <Card title="Request a report">
        <form className="form" onSubmit={onSubmit} noValidate>
          {formError && (
            <p className="form-alert" role="alert">
              {formError}
            </p>
          )}
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Report</span>
              <select
                className="field__control"
                value={reportType}
                onChange={(event) => setReportType(event.target.value)}
              >
                {groups.map((group) => (
                  <optgroup key={group} label={group}>
                    {REPORT_TYPES.filter((item) => item.group === group).map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>

            <label className="field">
              <span className="field__label">Format</span>
              <select
                className="field__control"
                value={format}
                onChange={(event) => setFormat(event.target.value as 'csv' | 'pdf')}
              >
                <option value="csv">CSV</option>
                <option value="pdf">PDF</option>
              </select>
            </label>

            {needsInstitution && canPickInstitution && (
              <label className="field">
                <span className="field__label">Institution *</span>
                <select
                  className="field__control"
                  value={institution}
                  onChange={(event) => setInstitution(event.target.value)}
                >
                  <option value="">
                    {institutionsQuery.isPending ? 'Loading…' : 'Choose an institution'}
                  </option>
                  {(institutionsQuery.data?.results ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <label className="field">
              <span className="field__label">From</span>
              <input
                className="field__control"
                type="date"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">To</span>
              <input
                className="field__control"
                type="date"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
              />
            </label>
          </div>

          <div className="badge-row">
            <Button type="submit" loading={createMutation.isPending}>
              Generate report
            </Button>
          </div>
        </form>
      </Card>

      <Card title="Your reports">
        {jobsQuery.isPending ? (
          <div className="page-loading" role="status">
            <Spinner size="md" />
          </div>
        ) : jobsQuery.isError ? (
          <ErrorState
            message={
              jobsQuery.error instanceof Error
                ? jobsQuery.error.message
                : 'Could not load reports.'
            }
            onRetry={() => void jobsQuery.refetch()}
          />
        ) : jobs.length === 0 ? (
          <EmptyState
            title="No reports yet"
            message="Request your first export above — it appears here when ready."
          />
        ) : (
          <>
            {downloadError && (
              <p className="form-alert" role="alert">
                {downloadError}
              </p>
            )}
            <ul className="role-list report-list">
              {jobs.map((job) => {
                const meta = statusMeta('report', job.status)
                const label =
                  REPORT_TYPES.find((item) => item.value === job.report_type)?.label ??
                  job.report_type
                return (
                  <li key={job.id} className="report-row">
                    <span className="report-row__main">
                      <span className="badge-row">
                        <strong>{label}</strong>
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                        <Badge tone="neutral">{job.format.toUpperCase()}</Badge>
                      </span>
                      <span className="field__hint">
                        {formatDateTime(job.created_at)}
                        {job.institution_name ? ` · ${job.institution_name}` : ''}
                        {job.row_count !== null ? ` · ${job.row_count} rows` : ''}
                      </span>
                      {job.error && (
                        <span className="field__error" role="alert">
                          {job.error}
                        </span>
                      )}
                    </span>
                    {job.status === 'succeeded' && job.download_url && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setDownloadError(null)
                          void downloadFile(
                            `/reports/${job.id}/download/`,
                            job.artifact_name ?? `report.${job.format}`,
                          ).catch((error: unknown) => {
                            setDownloadError(
                              error instanceof ApiError
                                ? error.message
                                : 'Download failed.',
                            )
                          })
                        }}
                      >
                        Download
                      </Button>
                    )}
                  </li>
                )
              })}
            </ul>
          </>
        )}
      </Card>
    </div>
  )
}
