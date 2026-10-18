import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { makeUser, renderPage } from '../../test/render'
import type { Competency, TrainingPlacement } from '../../lib/types'
import { AssessmentCreatePage } from './AssessmentCreatePage'

type Fetcher = ReturnType<typeof stubFetch>

const placement: TrainingPlacement = {
  id: 'place-1',
  title: 'Upper GI rotation',
  institution: 'inst-1',
  institution_name: 'Demo Hospital',
  department: null,
  department_name: null,
  trainee: 'user-42',
  trainee_detail: makeUser({ id: 'user-42', full_name: 'Trainee One' }),
  supervisor: 'user-7',
  supervisor_detail: makeUser({ id: 'user-7', full_name: 'Supervisor Two' }),
  start_date: '2026-09-01',
  end_date: null,
  status: 'active',
  objectives: '',
  closure_reason: '',
  expected_competencies: [],
  created_by: 'user-7',
  completed_at: null,
  cancelled_at: null,
  created_at: '2026-09-01T08:00:00Z',
  updated_at: '2026-09-01T08:00:00Z',
}

const competency: Competency = {
  id: 'comp-1',
  institution: 'inst-1',
  institution_name: 'Demo Hospital',
  code: 'SURG-01',
  title: 'Laparoscopic cholecystectomy',
  description: '',
  specialty: null,
  specialty_name: null,
  order: 0,
  is_active: true,
  current_rubric: {
    id: 'rub-1',
    competency: 'comp-1',
    version: 2,
    levels: {
      scale: [
        { key: 'novice', label: 'Novice', rank: 1 },
        { key: 'competent', label: 'Competent', rank: 3 },
      ],
      criteria: [{ key: 'technique', label: 'Operative technique' }],
    },
    notes: '',
    is_current: true,
    created_by: 'user-7',
    created_at: '2026-09-01T08:00:00Z',
  },
  created_at: '2026-09-01T08:00:00Z',
  updated_at: '2026-09-01T08:00:00Z',
}

function registerOptions(fetcher: Fetcher): void {
  fetcher.on('/training/placements/?page_size=100', () =>
    jsonResponse({ count: 1, next: null, previous: null, results: [placement] }),
  )
  fetcher.on('/competencies/?page_size=100', () =>
    jsonResponse({ count: 1, next: null, previous: null, results: [competency] }),
  )
  fetcher.on('/assessments/', (_url, init) => {
    if (init?.method === 'POST') {
      return jsonResponse({ id: 'assess-1', status: 'draft' }, 201)
    }
    return jsonResponse({ count: 0, next: null, previous: null, results: [] })
  })
}

describe('AssessmentCreatePage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('scores the pinned rubric and saves a draft (no self-assessment)', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () =>
      jsonResponse(
        makeUser({
          id: 'user-7',
          roles: [
            {
              id: 'role-21',
              role: 'supervisor',
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
    registerOptions(fetcher)

    renderPage(<AssessmentCreatePage />, {
      route: '/training/assessments/new',
      extraRoutes: <Route path="/training/assessments/:id" element={<div>Assessment saved</div>} />,
    })

    await screen.findByRole('option', { name: /Upper GI rotation/ })
    await user.selectOptions(screen.getByLabelText(/Placement/), 'place-1')
    await screen.findByRole('option', { name: /SURG-01/ })
    await user.selectOptions(screen.getByLabelText(/Competency/), 'comp-1')

    expect(await screen.findByText(/rubric v2/i)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Operative technique'), 'competent')
    await user.selectOptions(screen.getByLabelText(/Overall level/), 'competent')
    await user.click(screen.getByRole('button', { name: 'Save draft assessment' }))

    await waitFor(() =>
      expect(
        fetcher.calls.some(
          (call) =>
            call.url.includes('/assessments/') &&
            call.init?.method === 'POST' &&
            String(call.init.body).includes('comp-1') &&
            String(call.init.body).includes('technique'),
        ),
      ).toBe(true),
    )
    expect(await screen.findByText('Assessment saved')).toBeInTheDocument()
  })
})
