import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '../auth/AuthContext'
import type { Order, SurgicalProcedure, User } from '../lib/types'

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

export function renderPage(
  ui: ReactElement,
  options: { route?: string; path?: string; extraRoutes?: ReactElement } = {},
) {
  const route = options.route ?? '/'
  const path = options.path ?? route.split('?')[0]
  const client = createTestQueryClient()
  const result = render(
    <MemoryRouter initialEntries={[route]}>
      <QueryClientProvider client={client}>
        <AuthProvider>
          <Routes>
            <Route path={path} element={ui} />
            {options.extraRoutes}
          </Routes>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
  return { ...result, client }
}

// ── Fixtures ──
export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-1',
    email: 'someone@example.test',
    first_name: 'Some',
    last_name: 'One',
    full_name: 'Some One',
    is_verified: true,
    is_platform_admin: false,
    mfa_enabled: false,
    roles: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeProcedure(
  overrides: Partial<SurgicalProcedure> = {},
): SurgicalProcedure {
  return {
    id: 'proc-1',
    reference: 'STAR-2026-000123',
    status: 'draft',
    institution: 'inst-1',
    institution_name: 'Demo Hospital',
    department: null,
    department_name: null,
    specialty: null,
    specialty_name: null,
    patient_reference: null,
    patient_reference_code: null,
    procedure_date: '2026-10-01',
    category: 'elective',
    procedure_name: 'Laparoscopic cholecystectomy',
    indication: 'Symptomatic cholelithiasis',
    summary: 'Uneventful procedure.',
    complications: '',
    postoperative: '',
    training_objectives: '',
    author: 'user-1',
    author_detail: makeUser({ id: 'user-1', full_name: 'Demo Surgeon' }),
    participants: [],
    version: 1,
    submitted_at: null,
    approved_at: null,
    archived_at: null,
    created_at: '2026-10-01T09:00:00Z',
    updated_at: '2026-10-01T09:00:00Z',
    ...overrides,
  }
}

export function makeOrder(overrides: Partial<Order> = {}): Order {
  return {
    id: 'order-1',
    reference: 'ORD-2026-000001',
    buyer: 'user-1',
    supplier: 'supp-1',
    supplier_name: 'Demo Surgical Supplies',
    status: 'pending_payment',
    currency: 'XOF',
    subtotal: '150000',
    total: '150000',
    shipping_name: 'Demo Hospital',
    shipping_address: '1 Avenue de la Paix',
    shipping_phone: '+221 77 000 00 00',
    placed_at: '2026-10-18T10:00:00Z',
    paid_at: null,
    cancelled_at: null,
    cancel_reason: '',
    items: [
      {
        id: 'item-1',
        product: 'prod-1',
        product_name: 'Adson Forceps',
        product_sku: 'FRC-001',
        product_description: 'Toothed forceps',
        quantity: 2,
        unit_price: '75000',
        line_total: '150000',
      },
    ],
    payments: [],
    refunds: [],
    shipment: null,
    dispute: null,
    ...overrides,
  }
}
