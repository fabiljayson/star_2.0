import type { BadgeTone } from '../components/Badge'

export type StatusMeta = { label: string; tone: BadgeTone }

const PROCEDURE: Record<string, StatusMeta> = {
  draft: { label: 'Draft', tone: 'neutral' },
  submitted: { label: 'Submitted', tone: 'info' },
  under_review: { label: 'Under review', tone: 'info' },
  approved: { label: 'Approved', tone: 'success' },
  returned: { label: 'Returned for correction', tone: 'warning' },
  archived: { label: 'Archived', tone: 'neutral' },
}

const ORDER: Record<string, StatusMeta> = {
  pending_payment: { label: 'Pending payment', tone: 'warning' },
  paid: { label: 'Paid', tone: 'success' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
  shipped: { label: 'Shipped', tone: 'info' },
  delivered: { label: 'Delivered', tone: 'success' },
  refunded: { label: 'Refunded', tone: 'warning' },
}

const PAYMENT: Record<string, StatusMeta> = {
  pending: { label: 'Pending', tone: 'warning' },
  succeeded: { label: 'Succeeded', tone: 'success' },
  failed: { label: 'Failed', tone: 'danger' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
  refunded: { label: 'Refunded', tone: 'info' },
}

const REPORT: Record<string, StatusMeta> = {
  pending: { label: 'Pending', tone: 'neutral' },
  running: { label: 'Running', tone: 'info' },
  succeeded: { label: 'Ready', tone: 'success' },
  failed: { label: 'Failed', tone: 'danger' },
}

const ASSESSMENT: Record<string, StatusMeta> = {
  draft: { label: 'Draft', tone: 'neutral' },
  submitted: { label: 'Submitted', tone: 'info' },
  approved: { label: 'Approved', tone: 'success' },
  needs_correction: { label: 'Needs correction', tone: 'warning' },
  rejected: { label: 'Rejected', tone: 'danger' },
}

const PLACEMENT: Record<string, StatusMeta> = {
  active: { label: 'Active', tone: 'info' },
  completed: { label: 'Completed', tone: 'success' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
}

const MAPS: Record<string, Record<string, StatusMeta>> = {
  procedure: PROCEDURE,
  order: ORDER,
  payment: PAYMENT,
  report: REPORT,
  assessment: ASSESSMENT,
  placement: PLACEMENT,
}

export function statusMeta(kind: keyof typeof MAPS, value: string): StatusMeta {
  return MAPS[kind][value] ?? { label: value.replaceAll('_', ' '), tone: 'neutral' }
}

export const PROCEDURE_STATUSES = Object.keys(PROCEDURE)
export const ORDER_STATUSES = Object.keys(ORDER)
export const PLACEMENT_STATUSES = Object.keys(PLACEMENT)
export const REPORT_TYPES: { value: string; label: string; group: string }[] = [
  { value: 'individual_logbook', label: 'Individual surgical logbook', group: 'Logbook' },
  { value: 'activity_by_date', label: 'Activity by date range', group: 'Logbook' },
  { value: 'activity_by_specialty', label: 'Activity by specialty', group: 'Logbook' },
  { value: 'participation_roles', label: 'Procedures by participation role', group: 'Logbook' },
  { value: 'trainee_progress', label: 'Trainee progress', group: 'Training' },
  { value: 'competency_assessments', label: 'Competency assessments', group: 'Training' },
  { value: 'examiner_reviews', label: 'Examiner reviews', group: 'Training' },
  { value: 'placement_completion', label: 'Placement completion', group: 'Training' },
  { value: 'institution_summary', label: 'Institution summary', group: 'Training' },
  { value: 'supplier_sales', label: 'Supplier sales', group: 'Marketplace' },
  { value: 'buyer_orders', label: 'Buyer orders', group: 'Marketplace' },
  { value: 'marketplace_summary', label: 'Marketplace sales summary', group: 'Marketplace' },
]
