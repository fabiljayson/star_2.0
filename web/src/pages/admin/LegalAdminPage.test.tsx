import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import type { AdminPolicyVersion } from '../../lib/types'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { renderPage } from '../../test/render'
import { LegalAdminPage } from './LegalAdminPage'

const draft: AdminPolicyVersion = {
  id: 'pv-draft',
  policy_slug: 'terms-of-service',
  language: 'en',
  version: '4.0',
  status: 'draft',
  title: 'Terms of Service v4',
  body: '## 1. Acceptance\n\nDraft wording under review.',
  effective_date: '2026-12-01',
  published_at: null,
  approved_by_email: null,
  review_note: '',
}

const pending: AdminPolicyVersion = {
  ...draft,
  id: 'pv-pending',
  version: '4.1',
  status: 'pending_review',
  title: 'Terms of Service v4.1',
}

const published: AdminPolicyVersion = {
  ...draft,
  id: 'pv-published',
  version: '3.0',
  status: 'published',
  title: 'Terms of Service v3',
  body: '## 1. Acceptance\n\nBinding text in force.',
  published_at: '2026-10-20T09:00:00Z',
  approved_by_email: 'admin@example.test',
}

function stubAdmin(fetcher: ReturnType<typeof stubFetch>): void {
  fetcher.on('/legal/policy-versions/pv-draft/', (_url, init) => {
    if (init?.method === 'PATCH') {
      return jsonResponse({
        ...draft,
        title: JSON.parse(String(init.body)).title as string,
      })
    }
    return jsonResponse(draft)
  })
  fetcher.on('/legal/policy-versions/pv-pending/approve/', () =>
    jsonResponse({ ...pending, status: 'approved' }),
  )
  fetcher.on('/legal/policy-versions/', () =>
    jsonResponse({
      count: 3,
      next: null,
      previous: null,
      results: [draft, pending, published],
    }),
  )
  fetcher.on('/legal/policies/?lang=en', () =>
    jsonResponse({
      results: [
        {
          id: 'pol-1',
          slug: 'terms-of-service',
          title: 'Terms of Service',
          category: 'terms',
          summary: 'Rules for using STAR.',
          published_versions: [],
        },
      ],
    }),
  )
}

function renderAdmin() {
  return renderPage(<LegalAdminPage />, { route: '/admin/legal', path: '/admin/legal' })
}

beforeEach(() => {
  setAccessToken(null)
  storeRefreshToken(null)
})

describe('LegalAdminPage', () => {
  it('lists versions with the action allowed by each status', async () => {
    const fetcher = stubFetch()
    stubAdmin(fetcher)

    renderAdmin()

    await waitFor(
      () => expect(screen.getAllByRole('row')).toHaveLength(4),
      { timeout: 3000 },
    )
    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(4)

    const draftRow = within(rows[1])
    expect(draftRow.getByText('Draft')).toBeInTheDocument()
    expect(draftRow.getByRole('button', { name: 'Review & edit' })).toBeInTheDocument()
    expect(draftRow.getByRole('button', { name: 'Submit review' })).toBeInTheDocument()
    expect(draftRow.getByRole('button', { name: 'Archive' })).toBeInTheDocument()
    expect(draftRow.queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument()

    const pendingRow = within(rows[2])
    expect(pendingRow.getByText('Pending review')).toBeInTheDocument()
    expect(pendingRow.getByRole('button', { name: 'Approve' })).toBeInTheDocument()

    const publishedRow = within(rows[3])
    expect(publishedRow.getByText('Published')).toBeInTheDocument()
    expect(publishedRow.getByRole('button', { name: 'Preview' })).toBeInTheDocument()
    expect(publishedRow.queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument()
  })

  it('edits a draft title and saves it without changing the lifecycle', async () => {
    const browser = userEvent.setup()
    const fetcher = stubFetch()
    stubAdmin(fetcher)
    renderAdmin()

    await waitFor(
      () => expect(screen.getAllByRole('row')).toHaveLength(4),
      { timeout: 3000 },
    )
    const rows = screen.getAllByRole('row')
    await browser.click(
      within(rows[1]).getByRole('button', { name: 'Review & edit' }),
    )

    expect(
      await screen.findByRole('heading', { name: 'terms-of-service · EN v4.0' }),
    ).toBeInTheDocument()
    const dialog = within(screen.getByRole('dialog'))
    const title = dialog.getByLabelText('Title')
    expect(title).toHaveValue('Terms of Service v4')

    await browser.clear(title)
    await browser.type(title, 'Terms of Service v4 (revised)')
    await browser.click(screen.getByRole('button', { name: 'Save draft' }))

    await waitFor(() =>
      expect(
        screen.queryByRole('heading', { name: 'terms-of-service · EN v4.0' }),
      ).not.toBeInTheDocument(),
    )
    const patch = fetcher.calls.find((call) => call.init?.method === 'PATCH')
    expect(JSON.parse(String(patch?.init?.body))).toMatchObject({
      title: 'Terms of Service v4 (revised)',
      effective_date: '2026-12-01',
    })
  })

  it('previews a published text without offering edit controls', async () => {
    const browser = userEvent.setup()
    const fetcher = stubFetch()
    stubAdmin(fetcher)
    renderAdmin()

    await waitFor(
      () => expect(screen.getAllByRole('row')).toHaveLength(4),
      { timeout: 3000 },
    )
    const rows = screen.getAllByRole('row')
    await browser.click(within(rows[3]).getByRole('button', { name: 'Preview' }))

    expect(
      await screen.findByText(/Binding text in force/),
    ).toBeInTheDocument()
    const dialog = within(screen.getByRole('dialog'))
    expect(dialog.queryByRole('button', { name: 'Save draft' })).not.toBeInTheDocument()
    expect(dialog.queryByLabelText('Title')).not.toBeInTheDocument()
  })

  it('approves a version that is waiting for review', async () => {
    const browser = userEvent.setup()
    const fetcher = stubFetch()
    stubAdmin(fetcher)
    renderAdmin()

    await waitFor(
      () => expect(screen.getAllByRole('row')).toHaveLength(4),
      { timeout: 3000 },
    )
    const rows = screen.getAllByRole('row')
    await browser.click(within(rows[2]).getByRole('button', { name: 'Approve' }))

    await waitFor(() => expect(screen.getByText('Done.')).toBeInTheDocument())
    expect(
      fetcher.calls.some((call) =>
        call.url.includes('/legal/policy-versions/pv-pending/approve/'),
      ),
    ).toBe(true)
  })
})
