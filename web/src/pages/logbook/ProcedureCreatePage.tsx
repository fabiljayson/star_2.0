import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../../components/Button'
import { Card } from '../../components/Card'
import { ErrorState } from '../../components/ErrorState'
import { TextField } from '../../components/TextField'
import { ApiError, apiFetch } from '../../lib/api'
import { todayIsoDate } from '../../lib/format'
import type {
  Department,
  Institution,
  Page,
  PatientReference,
  Specialty,
  SurgicalProcedure,
} from '../../lib/types'

const CATEGORIES = ['elective', 'emergency', 'trauma', 'diagnostic', 'other'] as const

type FieldErrors = Record<string, string>

export function ProcedureCreatePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const institutionsQuery = useQuery({
    queryKey: ['institutions'],
    queryFn: () => apiFetch<Page<Institution>>('/institutions/?page_size=100'),
  })
  const specialtiesQuery = useQuery({
    queryKey: ['specialties'],
    queryFn: () => apiFetch<Page<Specialty>>('/specialties/'),
  })

  const [institution, setInstitution] = useState('')
  const [department, setDepartment] = useState('')
  const [specialty, setSpecialty] = useState('')
  const [patientReference, setPatientReference] = useState('')
  const [procedureDate, setProcedureDate] = useState(todayIsoDate())
  const [category, setCategory] = useState<string>('elective')
  const [procedureName, setProcedureName] = useState('')
  const [indication, setIndication] = useState('')
  const [summary, setSummary] = useState('')
  const [complications, setComplications] = useState('')
  const [postoperative, setPostoperative] = useState('')
  const [trainingObjectives, setTrainingObjectives] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const departmentsQuery = useQuery({
    queryKey: ['departments', institution],
    queryFn: () => apiFetch<Page<Department>>(`/departments/?institution=${institution}`),
    enabled: Boolean(institution),
  })
  const patientRefsQuery = useQuery({
    queryKey: ['patient-refs'],
    queryFn: () => apiFetch<Page<PatientReference>>('/patients/references/'),
  })

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<SurgicalProcedure>('/procedures/', { method: 'POST', body: payload }),
    onSuccess: (procedure) => {
      void queryClient.invalidateQueries({ queryKey: ['procedures'] })
      navigate(`/logbook/${procedure.id}`, { replace: true })
    },
    onError: (error) => {
      if (error instanceof ApiError && typeof error.details === 'object' && error.details) {
        const details = error.details as Record<string, unknown>
        const mapped: FieldErrors = {}
        for (const [key, value] of Object.entries(details)) {
          mapped[key] = Array.isArray(value) ? String(value[0]) : String(value)
        }
        setErrors(mapped)
        const general = mapped.non_field_errors
        setFormError(general ?? (Object.keys(mapped).length === 0 ? error.message : null))
      } else {
        setFormError(error instanceof Error ? error.message : 'Could not create the record.')
      }
    },
  })

  function onSubmit(event: FormEvent): void {
    event.preventDefault()
    setFormError(null)
    const next: FieldErrors = {}
    if (!institution) next.institution = 'Choose an institution.'
    if (!procedureDate) next.procedure_date = 'The procedure date is required.'
    if (!procedureName.trim()) next.procedure_name = 'The procedure name is required.'
    setErrors(next)
    if (Object.keys(next).length > 0) return

    const payload: Record<string, unknown> = {
      institution,
      procedure_date: procedureDate,
      category,
      procedure_name: procedureName.trim(),
      indication,
      summary,
      complications,
      postoperative,
      training_objectives: trainingObjectives,
    }
    if (department) payload.department = department
    if (specialty) payload.specialty = specialty
    if (patientReference) payload.patient_reference = patientReference

    createMutation.mutate(payload)
  }

  if (institutionsQuery.isError) {
    return (
      <ErrorState
        message="Could not load institutions. Go back and retry."
        onRetry={() => void institutionsQuery.refetch()}
      />
    )
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1 className="page__title">New surgical record</h1>
          <p className="page__subtitle">
            The record starts as a draft — you can edit and attach files before submitting.
          </p>
        </div>
        <Link to="/logbook" className="btn btn--ghost btn--sm">
          ← Back to logbook
        </Link>
      </header>

      <form className="form" onSubmit={onSubmit} noValidate>
        {formError && (
          <p className="form-alert" role="alert">
            {formError}
          </p>
        )}

        <Card title="Scope & classification">
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Institution *</span>
              <select
                className="field__control"
                value={institution}
                aria-invalid={errors.institution ? true : undefined}
                onChange={(event) => {
                  setInstitution(event.target.value)
                  setDepartment('')
                  setPatientReference('')
                }}
              >
                <option value="">
                  {institutionsQuery.isPending ? 'Loading…' : 'Choose an institution'}
                </option>
                {(institutionsQuery.data?.results ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              {errors.institution && (
                <span className="field__error" role="alert">
                  {errors.institution}
                </span>
              )}
            </label>

            <label className="field">
              <span className="field__label">Department</span>
              <select
                className="field__control"
                value={department}
                disabled={!institution || departmentsQuery.isPending}
                onChange={(event) => setDepartment(event.target.value)}
              >
                <option value="">None</option>
                {(departmentsQuery.data?.results ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span className="field__label">Specialty</span>
              <select
                className="field__control"
                value={specialty}
                onChange={(event) => setSpecialty(event.target.value)}
              >
                <option value="">None</option>
                {(specialtiesQuery.data?.results ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span className="field__label">Patient reference</span>
              <select
                className="field__control"
                value={patientReference}
                disabled={!institution}
                onChange={(event) => setPatientReference(event.target.value)}
              >
                <option value="">None (pseudonymous code not required)</option>
                {(patientRefsQuery.data?.results ?? [])
                  .filter((item) => item.institution === institution)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.code} — {item.label}
                    </option>
                  ))}
              </select>
            </label>

            <TextField
              label="Procedure date *"
              type="date"
              name="procedure_date"
              value={procedureDate}
              error={errors.procedure_date}
              onChange={(event) => setProcedureDate(event.target.value)}
            />

            <label className="field">
              <span className="field__label">Category *</span>
              <select
                className="field__control"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                {CATEGORIES.map((value) => (
                  <option key={value} value={value}>
                    {value.charAt(0).toUpperCase() + value.slice(1)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <TextField
            label="Procedure name *"
            name="procedure_name"
            value={procedureName}
            error={errors.procedure_name}
            placeholder="e.g. Laparoscopic cholecystectomy"
            onChange={(event) => setProcedureName(event.target.value)}
          />
        </Card>

        <Card title="Clinical notes">
          <label className="field">
            <span className="field__label">Indication</span>
            <textarea
              className="field__control"
              rows={3}
              value={indication}
              onChange={(event) => setIndication(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field__label">Operative summary</span>
            <textarea
              className="field__control"
              rows={4}
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
            />
          </label>
          <div className="form-grid">
            <label className="field">
              <span className="field__label">Complications</span>
              <textarea
                className="field__control"
                rows={3}
                value={complications}
                onChange={(event) => setComplications(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field__label">Postoperative course</span>
              <textarea
                className="field__control"
                rows={3}
                value={postoperative}
                onChange={(event) => setPostoperative(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            <span className="field__label">Training objectives</span>
            <textarea
              className="field__control"
              rows={3}
              value={trainingObjectives}
              onChange={(event) => setTrainingObjectives(event.target.value)}
            />
          </label>
        </Card>

        <div className="badge-row">
          <Button type="submit" loading={createMutation.isPending}>
            Create draft
          </Button>
          <Link to="/logbook" className="btn btn--ghost">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
