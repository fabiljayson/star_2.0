export type RoleAssignment = {
  id: string
  role: string
  institution: string | null
  institution_name: string | null
  department: string | null
  department_name: string | null
  is_active: boolean
}

export type User = {
  id: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  is_verified: boolean
  is_platform_admin: boolean
  mfa_enabled: boolean
  roles: RoleAssignment[]
  created_at: string
  updated_at: string
}

export type UserSummary = Pick<
  User,
  'id' | 'email' | 'first_name' | 'last_name' | 'full_name' | 'is_verified' | 'is_platform_admin' | 'roles' | 'created_at'
>

export type LoginResponse = {
  mfa_required: boolean
  access?: string
  refresh?: string
  user?: User
  mfa_token?: string
  expires_in?: number
}

export type RegisterResponse = {
  message: string
  user: User
  verification_token?: string
}

export type MessageResponse = { message: string }

// ── Pagination ──
export type Page<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// ── Organizations ──
export type Institution = {
  id: string
  name: string
  slug?: string
  institution_type: string
  city: string
  country: string
  address?: string
  website?: string
  contact_email?: string
  is_active: boolean
}

export type Department = {
  id: string
  institution: string
  institution_name?: string
  name: string
  code?: string
  is_active: boolean
}

export type Specialty = {
  id: string
  name: string
  code?: string
  description?: string
  is_active: boolean
}

export type Membership = {
  id: string
  user: string
  user_detail: UserSummary
  role: string
  institution: string | null
  institution_name: string | null
  department: string | null
  department_name: string | null
  is_active: boolean
  granted_by: string | null
  created_at: string
  updated_at: string
}

export type Invitation = {
  id: string
  institution: string
  institution_name: string
  email: string
  role: string
  department: string | null
  invited_by: string | null
  invited_by_email: string | null
  token: string
  expires_at: string
  accepted_at: string | null
  revoked_at: string | null
  created_at: string
}

export type AuditEvent = {
  id: string
  action: string
  actor: string | null
  actor_email: string | null
  object_type: string
  object_pk: string
  institution: string | null
  institution_name: string | null
  ip_address: string | null
  user_agent: string
  request_id: string
  metadata: Record<string, unknown>
  created_at: string
}

export type PatientReference = {
  id: string
  institution: string
  code: string
  label: string
  is_active: boolean
}

// ── Logbook ──
export type ProcedureStatusValue =
  | 'draft'
  | 'submitted'
  | 'under_review'
  | 'approved'
  | 'returned'
  | 'archived'

export type ParticipantRoleValue = 'primary_operator' | 'assistant' | 'observer'

export type ProcedureParticipant = {
  id: string
  user: string
  user_detail: UserSummary
  role: ParticipantRoleValue
  created_at: string
}

export type SurgicalProcedure = {
  id: string
  reference: string
  status: ProcedureStatusValue
  institution: string
  institution_name: string
  department: string | null
  department_name: string | null
  specialty: string | null
  specialty_name: string | null
  patient_reference: string | null
  patient_reference_code: string | null
  procedure_date: string
  category: string
  procedure_name: string
  indication: string
  summary: string
  complications: string
  postoperative: string
  training_objectives: string
  author: string
  author_detail: UserSummary
  participants: ProcedureParticipant[]
  version: number
  submitted_at: string | null
  approved_at: string | null
  archived_at: string | null
  created_at: string
  updated_at: string
}

export type ProcedureAttachment = {
  id: string
  original_name: string
  declared_content_type: string
  detected_kind: string
  size_bytes: number
  uploaded_by: string
  uploaded_by_detail: UserSummary
  download_url: string
  created_at: string
}

export type ProcedureReview = {
  id: string
  decision: string
  reason: string
  from_status: string
  to_status: string
  review_version: number | null
  reviewer: string | null
  reviewer_detail: UserSummary | null
  created_at: string
}

export type ProcedureVersion = {
  id: string
  version: number
  change_kind: string
  snapshot: Record<string, unknown>
  changed_by: string | null
  changed_by_detail: UserSummary | null
  change_summary: string
  created_at: string
}

export type TranscriptionResult = {
  text: string
  language: string
  provider: string
  simulated: boolean
  confidence: number
  uncertain: boolean
}

export type ProcedureCreatePayload = {
  institution: string
  department?: string | null
  specialty?: string | null
  patient_reference?: string | null
  procedure_date: string
  category: string
  procedure_name: string
  indication?: string
  summary?: string
  complications?: string
  postoperative?: string
  training_objectives?: string
}

// ── Reports ──
export type ReportStatusValue = 'pending' | 'running' | 'succeeded' | 'failed'

export type ReportJob = {
  id: string
  institution: string | null
  institution_name: string | null
  report_type: string
  format: 'csv' | 'pdf'
  parameters: Record<string, string>
  status: ReportStatusValue
  error: string | null
  row_count: number | null
  artifact_name: string | null
  completed_at: string | null
  expires_at: string | null
  download_url: string | null
  created_at: string
}

// ── Marketplace ──
export type ProductCategory = {
  id: string
  name: string
  slug: string
  is_active: boolean
}

export type Product = {
  id: string
  supplier: string
  supplier_name: string
  category: string | null
  category_name: string | null
  name: string
  description: string
  sku: string
  unit_price: string
  currency: string
  available_quantity: number
  reserved_quantity: number
  free_quantity: number
  is_published: boolean
  approval_status: string
  specifications?: Record<string, unknown>
  regulatory_notes?: string
  is_active: boolean
  created_at?: string
}

export type CartItem = {
  id: string
  product: string
  product_detail: Product
  quantity: number
  line_total: string
}

export type OrderItem = {
  id: string
  product: string | null
  product_name: string
  product_sku: string
  product_description: string
  quantity: number
  unit_price: string
  line_total: string
}

export type OrderStatusValue =
  | 'pending_payment'
  | 'paid'
  | 'cancelled'
  | 'shipped'
  | 'delivered'
  | 'refunded'

export type PaymentStatusValue =
  | 'pending'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'refunded'

export type PaymentEvent = {
  id: string
  event_type: string
  signature_valid: boolean
  created_at: string
}

export type Payment = {
  id: string
  order: string
  provider: string
  status: PaymentStatusValue
  amount: string
  currency: string
  idempotency_key: string
  provider_reference: string | null
  failure_reason: string
  paid_at: string | null
  events: PaymentEvent[]
  created_at: string
}

export type Refund = {
  id: string
  order: string
  status: 'pending' | 'approved' | 'rejected'
  amount: string
  currency: string
  reason: string
  decision_reason: string
  created_at: string
}

export type Shipment = {
  id: string
  status: 'shipped' | 'delivered'
  tracking_number: string
  shipped_at: string | null
  delivered_at: string | null
}

export type DisputeEvidence = {
  id: string
  body: string
  file_name: string | null
  created_at: string
}

export type Dispute = {
  id: string
  order: string
  status: 'open' | 'resolved'
  description: string
  resolution: string | null
  resolution_note: string
  evidence_entries: DisputeEvidence[]
  created_at: string
}

export type Order = {
  id: string
  reference: string
  buyer: string
  buyer_detail?: UserSummary
  supplier: string
  supplier_name: string
  status: OrderStatusValue
  currency: string
  subtotal: string
  total: string
  shipping_name: string
  shipping_address: string
  shipping_phone: string
  placed_at: string
  paid_at: string | null
  cancelled_at: string | null
  cancel_reason: string
  items: OrderItem[]
  payments: Payment[]
  refunds: Refund[]
  shipment: Shipment | null
  dispute: Dispute | null
}

export type SupplierProfileValue = {
  id: string
  user: string
  user_detail?: UserSummary
  company_name: string
  contact_email: string
  contact_phone?: string
  address?: string
  commercial_notes?: string
  verification_status: string
  verified_at?: string | null
  suspension_reason?: string
  created_at?: string
}

// ── Training ──
export type PlacementStatusValue = 'active' | 'completed' | 'cancelled'

export type TrainingPlacement = {
  id: string
  title: string
  institution: string
  institution_name: string
  department: string | null
  department_name: string | null
  trainee: string
  trainee_detail: UserSummary
  supervisor: string | null
  supervisor_detail: UserSummary | null
  start_date: string
  end_date: string | null
  status: PlacementStatusValue
  objectives: string
  closure_reason: string
  expected_competencies: Competency[]
  expected_competency_ids?: string[]
  created_by: string | null
  completed_at: string | null
  cancelled_at: string | null
  created_at: string
  updated_at: string
}

export type Competency = {
  id: string
  institution: string
  institution_name: string
  code: string
  title: string
  description: string
  specialty: string | null
  specialty_name: string | null
  order: number
  is_active: boolean
  current_rubric: CompetencyRubricVersion | null
  created_at: string
  updated_at: string
}

export type RubricLevel = { key: string; label: string; rank?: number }
export type RubricCriterion = { key: string; label: string }
export type RubricContent = { scale?: RubricLevel[]; criteria?: RubricCriterion[] }

export type CompetencyRubricVersion = {
  id: string
  competency: string
  version: number
  levels: RubricContent
  notes: string
  is_current: boolean
  created_by: string | null
  created_at: string
}

export type AssessmentStatusValue =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'needs_correction'
  | 'rejected'

export type Assessment = {
  id: string
  placement: string
  trainee_detail: UserSummary
  competency: string
  competency_code: string
  rubric_version: string
  rubric_version_number: number
  procedure: string | null
  assessor: string
  assessor_detail: UserSummary
  status: AssessmentStatusValue
  scores: Record<string, string>
  overall_level: string
  feedback: string
  decision_reason: string
  decided_by: string | null
  decided_by_detail: UserSummary | null
  submitted_at: string | null
  decided_at: string | null
  created_at: string
  updated_at: string
}

export type ExaminerAssignment = {
  id: string
  placement: string
  examiner: string
  examiner_detail: UserSummary
  assigned_by: string | null
  created_at: string
}

// ── Notifications ──
export type NotificationCategoryValue =
  | 'record_submitted'
  | 'review_assigned'
  | 'record_approved'
  | 'record_rejected'
  | 'correction_requested'
  | 'placement_milestone'
  | 'competency_updated'
  | 'order_confirmed'
  | 'payment_changed'
  | 'shipment_updated'
  | 'refund_updated'
  | 'dispute_updated'

export type Notification = {
  id: string
  category: NotificationCategoryValue
  title: string
  body: string
  link: string | null
  actor: string | null
  actor_detail: UserSummary | null
  object_type: string | null
  object_pk: string | null
  institution: string | null
  is_read: boolean
  read_at: string | null
  created_at: string
}

export type NotificationPreference = {
  category: NotificationCategoryValue
  in_app: boolean
  email: boolean
}

// ── Placement progress ──
export type PlacementProgress = {
  placement_id: string
  procedures_performed: number
  procedures_assisted: number
  procedures_observed: number
  records_awaiting_review: number
  approved_records: number
  rejected_records: number
  competency_progress: { competency_code: string; level: string | null }[]
  placement_completion: number
}
