export const ROLE_LABELS: Record<string, string> = {
  independent_surgeon: 'Independent surgeon',
  trainee: 'Trainee / resident',
  supervisor: 'Supervising surgeon',
  examiner: 'Examiner',
  department_manager: 'Department manager',
  institution_admin: 'Institution admin',
  supplier: 'Supplier',
  buyer: 'Buyer',
  platform_admin: 'Platform admin',
}

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role
}

export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : ''
  return (first + last).toUpperCase() || '?'
}
