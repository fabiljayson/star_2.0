import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { makeUser, renderPage } from '../../test/render'
import { ReportsPage } from './ReportsPage'

type Fetcher = ReturnType<typeof stubFetch>

const jobFixture = {
  id: 'job-1',
  institution: null,
  institution_name: null,
  report_type: 'individual_logbook',
  format: 'csv' as const,
  parameters: {},
  status: 'succeeded' as const,
  error: null,
  row_count: 12,
  artifact_name: 'logbook.csv',
  completed_at: '2026-10-18T09:05:00Z',
  expires_at: '2026-10-19T09:05:00Z',
  download_url: '/reports/job-1/download/',
  created_at: '2026-10-18T09:00:00Z',
}

function registerReports(fetcher: Fetcher): void {
  fetcher.on('/reports/', (_url, init) => {
    if (init?.method === 'POST') return jsonResponse(jobFixture, 201)
    return jsonResponse({ count: 1, next: null, previous: null, results: [jobFixture] })
  })
}

describe('ReportsPage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('lists export jobs inside the permitted scope (scenario G)', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () => jsonResponse(makeUser({ is_platform_admin: true })))
    registerReports(fetcher)

    renderPage(<ReportsPage />, { route: '/reports' })

    expect(await screen.findByText('Individual surgical logbook')).toBeInTheDocument()
    expect(screen.getByText('CSV')).toBeInTheDocument()
    await expect(screen.findByText(/12 rows/)).resolves.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Download' }).length).toBeGreaterThan(0)
  })

  it('creates a report job with the selected type and format (scenario G)', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () => jsonResponse(makeUser({ is_platform_admin: true })))
    registerReports(fetcher)

    renderPage(<ReportsPage />, { route: '/reports' })
    await screen.findByText('Individual surgical logbook')

    await user.selectOptions(screen.getByLabelText('Report'), 'examiner_reviews')
    await user.selectOptions(screen.getByLabelText('Format'), 'pdf')
    await user.click(screen.getByRole('button', { name: 'Generate report' }))

    await waitFor(() =>
      expect(
        fetcher.calls.some(
          (call) =>
            call.url.includes('/reports/') &&
            call.init?.method === 'POST' &&
            String(call.init.body).includes('examiner_reviews') &&
            String(call.init.body).includes('pdf'),
        ),
      ).toBe(true),
    )
  })
})
