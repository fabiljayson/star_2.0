import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { makeProcedure, makeUser, renderPage } from '../../test/render'
import { ProcedureDetailPage } from './ProcedureDetailPage'

type Fetcher = ReturnType<typeof stubFetch>

function registerSession(fetcher: Fetcher, user: ReturnType<typeof makeUser>): void {
  storeRefreshToken('refresh-1')
  fetcher.on('/users/me/', () => jsonResponse(user))
}

const surgeon = makeUser({
  id: 'user-1',
  full_name: 'Demo Surgeon',
  roles: [
    {
      id: 'role-11',
      role: 'supervisor',
      institution: 'inst-1',
      institution_name: 'Demo Hospital',
      department: null,
      department_name: null,
      is_active: true,
    },
  ],
})

const examiner = makeUser({
  id: 'user-42',
  full_name: 'Demo Examiner',
  roles: [
    {
      id: 'role-14',
      role: 'examiner',
      institution: 'inst-1',
      institution_name: 'Demo Hospital',
      department: null,
      department_name: null,
      is_active: true,
    },
  ],
})

describe('ProcedureDetailPage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('hides foreign records behind a 404 without leaking details (scenario C)', async () => {
    const fetcher = stubFetch()
    registerSession(fetcher, surgeon)
    fetcher.on('/procedures/proc-1/', () =>
      jsonResponse({ error: { code: 'not_found', message: 'Not found.' } }, 404),
    )

    renderPage(<ProcedureDetailPage />, { route: '/logbook/proc-1', path: '/logbook/:id' })

    expect(await screen.findByText('Record not found')).toBeInTheDocument()
    expect(screen.queryByText('STAR-2026-000123')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Submit for review' })).not.toBeInTheDocument()
  })

  it('lets the author submit a draft for review (scenario A)', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    registerSession(fetcher, surgeon)
    fetcher.on('/procedures/proc-1/submit/', () =>
      jsonResponse(makeProcedure({ status: 'submitted', submitted_at: '2026-10-18T11:00:00Z' })),
    )
    fetcher.on('/procedures/proc-1/attachments/', () => jsonResponse([]))
    fetcher.on('/procedures/proc-1/reviews/', () => jsonResponse([]))
    fetcher.on('/procedures/proc-1/versions/', () => jsonResponse([]))
    let detailCalls = 0
    fetcher.on('/procedures/proc-1/', () => {
      detailCalls += 1
      return jsonResponse(
        detailCalls > 1
          ? makeProcedure({ status: 'submitted' })
          : makeProcedure(),
      )
    })

    renderPage(<ProcedureDetailPage />, { route: '/logbook/proc-1', path: '/logbook/:id' })

    await user.click(await screen.findByRole('button', { name: 'Submit for review' }))

    await waitFor(() =>
      expect(
        fetcher.calls.some((call) => call.url.includes('/procedures/proc-1/submit/')),
      ).toBe(true),
    )
    await waitFor(() => expect(screen.getAllByText('Submitted')).toHaveLength(2))
    expect(screen.queryByRole('button', { name: 'Submit for review' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit record' })).not.toBeInTheDocument()
  })

  it('requires a reason before requesting a correction (scenario B)', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    registerSession(fetcher, examiner)
    fetcher.on('/procedures/proc-1/attachments/', () => jsonResponse([]))
    fetcher.on('/procedures/proc-1/reviews/', () => jsonResponse([]))
    fetcher.on('/procedures/proc-1/versions/', () => jsonResponse([]))
    fetcher.on('/procedures/proc-1/', () =>
      jsonResponse(makeProcedure({ status: 'submitted', author: 'user-1' })),
    )

    renderPage(<ProcedureDetailPage />, { route: '/logbook/proc-1', path: '/logbook/:id' })

    await user.click(await screen.findByRole('button', { name: 'Request correction' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(
      await screen.findByText('A reason is required when a record is not approved.'),
    ).toBeInTheDocument()
    expect(
      fetcher.calls.some((call) => call.url.includes('/reviews/') && call.init?.method === 'POST'),
    ).toBe(false)

    await user.type(screen.getByLabelText('Reason (required)'), 'Add the postoperative note.')
    await user.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() =>
      expect(
        fetcher.calls.some(
          (call) =>
            call.url.includes('/reviews/') &&
            call.init?.method === 'POST' &&
            String(call.init.body).includes('request_correction') &&
            String(call.init.body).includes('postoperative note'),
        ),
      ).toBe(true),
    )
  })

  it('reports transcription failure and keeps the draft usable (scenario H)', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    registerSession(fetcher, surgeon)
    fetcher.on('/procedures/proc-1/transcribe/', () =>
      jsonResponse(
        {
          error: {
            code: 'transcription_unavailable',
            message: 'Transcription provider is unavailable right now.',
          },
        },
        503,
      ),
    )
    fetcher.on('/procedures/proc-1/attachments/', () => jsonResponse([]))
    fetcher.on('/procedures/proc-1/reviews/', () => jsonResponse([]))
    fetcher.on('/procedures/proc-1/versions/', () => jsonResponse([]))
    fetcher.on('/procedures/proc-1/', () => jsonResponse(makeProcedure()))

    renderPage(<ProcedureDetailPage />, { route: '/logbook/proc-1', path: '/logbook/:id' })

    const fileInput = await screen.findByLabelText('Audio file')
    const audio = new File(['fake-bytes'], 'dictation.wav', { type: 'audio/wav' })
    await user.upload(fileInput, audio)
    await user.click(screen.getByRole('button', { name: 'Generate transcript' }))

    expect(
      await screen.findByText(/Transcription provider is unavailable right now\./),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/keep writing the summary manually/i),
    ).toBeInTheDocument()
    // The draft is still displayed and editable.
    expect(screen.getByText('Uneventful procedure.')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Edit record' }),
    ).toBeInTheDocument()
  })
})
