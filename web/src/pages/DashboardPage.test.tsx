import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../lib/api'
import { jsonResponse, stubFetch } from '../test/helpers'
import { makeProcedure, makeUser, renderPage } from '../test/render'
import { DashboardPage } from './DashboardPage'

type Fetcher = ReturnType<typeof stubFetch>

function registerDashboard(fetcher: Fetcher): void {
  fetcher.on('/procedures/?mine=1&page_size=5', () =>
    jsonResponse({
      count: 3,
      next: null,
      previous: null,
      results: [makeProcedure({ procedure_name: 'Laparoscopic cholecystectomy' })],
    }),
  )
  fetcher.on('/procedures/?mine=1&status=approved&page_size=1', () =>
    jsonResponse({ count: 7, next: null, previous: null, results: [] }),
  )
  fetcher.on('/procedures/?status=submitted&page_size=1', () =>
    jsonResponse({ count: 2, next: null, previous: null, results: [] }),
  )
  fetcher.on('/training/placements/?status=active&page_size=1', () =>
    jsonResponse({ count: 0, next: null, previous: null, results: [] }),
  )
  fetcher.on('/notifications/unread-count/', () => jsonResponse({ count: 3 }))
  fetcher.on('/notifications/?page_size=3', () =>
    jsonResponse({ count: 0, next: null, previous: null, results: [] }),
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('summarises the logbook with real counts inside the permitted scope', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () =>
      jsonResponse(
        makeUser({
          first_name: 'Ada',
          full_name: 'Ada Surgeon',
          roles: [
            {
              id: 'role-11',
              role: 'independent_surgeon',
              institution: 'inst-1',
              institution_name: 'Demo Hospital',
              department: null,
              department_name: null,
              is_active: true,
            },
          ],
        }),
      ),
    )
    registerDashboard(fetcher)

    renderPage(<DashboardPage />, { route: '/dashboard' })

    expect(await screen.findByText('Welcome back, Ada')).toBeInTheDocument()
    expect(await screen.findByText('Laparoscopic cholecystectomy')).toBeInTheDocument()
    expect(screen.getByText('Awaiting review').closest('a')).toHaveTextContent('2')
    expect(screen.getByText('Approved').closest('a')).toHaveTextContent('7')
    expect(screen.getByText('Unread notifications').closest('a')).toHaveTextContent('3')
    expect(screen.getByRole('link', { name: 'New surgical record' })).toHaveAttribute(
      'href',
      '/logbook/new',
    )
  })
})
