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
const CLINICAL_ROLES = [
  'independent_surgeon',
  'trainee',
  'supervisor',
  'examiner',
  'department_manager',
  'institution_admin',
  'platform_admin',
]

export const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: '◈', end: true },
  { to: '/logbook', label: 'Logbook', icon: '◷', roles: CLINICAL_ROLES },
  { to: '/training', label: 'Training', icon: '◆', roles: CLINICAL_ROLES },
  { to: '/notifications', label: 'Notifications', icon: '☰' },
  { to: '/marketplace', label: 'Marketplace', icon: '▤' },
  { to: '/reports', label: 'Reports', icon: '⤓' },
  { to: '/supplier', label: 'Supplier', icon: '▦', roles: ['supplier'] },
  {
    to: '/institution',
    label: 'Institution',
    icon: '⌂',
    roles: ['institution_admin', 'platform_admin'],
  },
  { to: '/admin', label: 'Platform admin', icon: '⚑', roles: ['platform_admin'] },
  { to: '/account', label: 'Account', icon: '◍' },
]

export function filterNavItems(
  items: NavItem[],
  hasAnyRole: (roles?: string[]) => boolean,
): NavItem[] {
  return items.filter((item) => hasAnyRole(item.roles))
}
