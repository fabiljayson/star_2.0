export type RoleAssignment = {
  id: number
  role: string
  institution: number | null
  institution_name: string | null
  department: number | null
  department_name: string | null
  is_active: boolean
}

export type User = {
  id: number
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
