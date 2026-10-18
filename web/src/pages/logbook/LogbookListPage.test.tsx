import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { makeProcedure, renderPage } from '../../test/render'
import { LogbookListPage } from './LogbookListPage'

function page(results: unknown[], count = results.length) {
  return jsonResponse({ count, next: null, previous: null, results })
}

describe('LogbookListPage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('renders procedure rows with reference, name and status badge', async () => {
    const fetcher = stubFetch()
    fetcher.on('/procedures/', () =>
      page([makeProcedure(), makeProcedure({ id: 'proc-2', reference: 'STAR-2026-000124', status: 'approved' })]),
    )

    renderPage(<LogbookListPage />, { route: '/logbook' })

    expect(await screen.findByText('STAR-2026-000123')).toBeInTheDocument()
    expect(screen.getAllByText('Laparoscopic cholecystectomy')).toHaveLength(2)
    expect(screen.getByTitle('Draft')).toBeInTheDocument()
    expect(screen.getByTitle('Approved')).toBeInTheDocument()
    expect(screen.getByText('2 records')).toBeInTheDocument()
  })

  it('shows an empty state when no record exists yet', async () => {
    const fetcher = stubFetch()
    fetcher.on('/procedures/', () => page([]))

    renderPage(<LogbookListPage />, { route: '/logbook' })

    expect(await screen.findByText('No procedures yet')).toBeInTheDocument()
    const links = screen.getAllByRole('link', { name: 'New record' })
    expect(links).toHaveLength(2)
    expect(links[0]).toHaveAttribute('href', '/logbook/new')
  })

  it('filters by status through the query string', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    fetcher.on('/procedures/', (url) => {
      if (url.includes('status=approved')) return page([])
      return page([makeProcedure()])
    })

    renderPage(<LogbookListPage />, { route: '/logbook' })
    await screen.findByText('STAR-2026-000123')

    await user.selectOptions(screen.getByLabelText('Status'), 'approved')
    await user.click(screen.getByRole('button', { name: 'Apply' }))

    expect(await screen.findByText('No procedures yet')).toBeInTheDocument()
    expect(
      fetcher.calls.some((call) => call.url.includes('status=approved')),
    ).toBe(true)
  })
})
