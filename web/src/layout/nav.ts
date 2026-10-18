export type NavItem = {
  to: string
  label: string
  icon: string
  roles?: string[]
  end?: boolean
}

/**
 * Navigation registry: every item must point to a screen that exists.
 * Items with `roles` only appear when the signed-in user holds one of them.
 * Grows milestone by milestone — never pre-register empty destinations.
 */
export const NAV_ITEMS: NavItem[] = [{ to: '/account', label: 'Account', icon: '◍' }]

export function filterNavItems(
  items: NavItem[],
  hasAnyRole: (roles?: string[]) => boolean,
): NavItem[] {
  return items.filter((item) => hasAnyRole(item.roles))
}
