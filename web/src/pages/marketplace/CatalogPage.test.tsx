import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import type { Product } from '../../lib/types'
import { setAccessToken, storeRefreshToken } from '../../lib/api'
import { jsonResponse, stubFetch } from '../../test/helpers'
import { makeUser, renderPage } from '../../test/render'
import { CatalogPage } from './CatalogPage'

type Fetcher = ReturnType<typeof stubFetch>

const product: Product = {
  id: 'prod-1',
  supplier: 'supp-1',
  supplier_name: 'Demo Surgical Supplies',
  category: 'cat-1',
  category_name: 'Forceps',
  name: 'Adson Forceps',
  description: 'Toothed forceps, 12 cm.',
  sku: 'FRC-001',
  image: 'marketplace/products/artery-forceps.jpg',
  image_url: 'http://api.test/static/marketplace/products/artery-forceps.jpg',
  image_credit: 'Splarka · public domain',
  unit_price: '75000',
  currency: 'XOF',
  available_quantity: 14,
  reserved_quantity: 2,
  free_quantity: 12,
  is_published: true,
  approval_status: 'approved',
  is_active: true,
}

function registerCatalog(fetcher: Fetcher): void {
  // The categories endpoint is deliberately unpaginated on the backend.
  fetcher.on('/marketplace/categories/', () =>
    jsonResponse([{ id: 'cat-1', name: 'Forceps', slug: 'forceps', is_active: true }]),
  )
  fetcher.on('/marketplace/cart/items/', () =>
    jsonResponse({ id: 'cart-item-1', product: 'prod-1', product_name: 'Adson Forceps' }),
  )
  fetcher.on('/marketplace/cart/', () =>
    jsonResponse({ count: 0, next: null, previous: null, results: [] }),
  )
  fetcher.on('/marketplace/products/', () =>
    jsonResponse({ count: 1, next: null, previous: null, results: [product] }),
  )
}

describe('CatalogPage', () => {
  beforeEach(() => {
    setAccessToken(null)
    storeRefreshToken(null)
  })

  it('renders products with price and stock badges', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () =>
      jsonResponse(
        makeUser({
          roles: [
            {
              id: 'role-31',
              role: 'buyer',
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
    registerCatalog(fetcher)

    renderPage(<CatalogPage />, { route: '/marketplace' })

    expect(await screen.findByText('Adson Forceps')).toBeInTheDocument()
    expect(screen.getByText('75,000 XOF')).toBeInTheDocument()
    expect(screen.getByText('12 in stock')).toBeInTheDocument()
    expect(screen.getByText('SKU FRC-001')).toBeInTheDocument()
    const image = document.querySelector<HTMLImageElement>('.product-card__image')
    expect(image?.src).toBe(
      'http://api.test/static/marketplace/products/artery-forceps.jpg',
    )
  })

  it('adds a product to the cart as a buyer (scenario D)', async () => {
    const user = userEvent.setup()
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () =>
      jsonResponse(
        makeUser({
          roles: [
            {
              id: 'role-31',
              role: 'buyer',
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
    registerCatalog(fetcher)

    renderPage(<CatalogPage />, { route: '/marketplace' })
    await screen.findByText('Adson Forceps')

    await user.click(screen.getByRole('button', { name: 'Add to cart' }))

    await waitFor(() =>
      expect(
        fetcher.calls.some(
          (call) =>
            call.url.includes('/marketplace/cart/items/') &&
            call.init?.method === 'POST' &&
            String(call.init.body).includes('prod-1'),
        ),
      ).toBe(true),
    )
  })

  it('disables add-to-cart for non-buyers (marketplace-only accounts stay scoped)', async () => {
    const fetcher = stubFetch()
    storeRefreshToken('refresh-1')
    fetcher.on('/users/me/', () =>
      jsonResponse(
        makeUser({
          roles: [
            {
              id: 'role-32',
              role: 'supplier',
              institution: null,
              institution_name: null,
              department: null,
              department_name: null,
              is_active: true,
            },
          ],
        }),
      ),
    )
    registerCatalog(fetcher)

    renderPage(<CatalogPage />, { route: '/marketplace' })
    await screen.findByText('Adson Forceps')

    expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled()
  })
})
