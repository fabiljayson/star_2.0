import type { PolicyLanguage, PolicyDetail } from './types'

// ── Language side ──
export function pickLanguage(value: unknown): PolicyLanguage {
  return String(value ?? 'en').toLowerCase().startsWith('fr') ? 'fr' : 'en'
}

export function legalLanguageTags(detail: PolicyDetail): PolicyLanguage[] {
  const known = new Set<PolicyLanguage>([detail.language])
  if (detail.translation_of) known.add(detail.translation_of.language)
  return [...known]
}

// ── Body structure (## headings drive the table of contents) ──
export type PolicySection = {
  id: string
  heading: string
  body: string
}

function slugifyHeading(heading: string): string {
  return heading
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
}

export function policySections(detail: PolicyDetail): PolicySection[] {
  const lines = detail.body.split('\n')
  const sections: PolicySection[] = []
  let heading: string | null = null
  let buffer: string[] = []
  let usedIds = new Set<string>()

  function flush(): void {
    if (heading === null) return
    let id = slugifyHeading(heading)
    let n = 2
    while (usedIds.has(id)) id = `${slugifyHeading(heading)}-${n++}`
    usedIds.add(id)
    sections.push({
      id,
      heading,
      body: buffer.join('\n').trim(),
    })
  }

  for (const line of lines) {
    if (line.startsWith('## ')) {
      flush()
      heading = line.replace(/^## /, '').trim()
      buffer = []
    } else if (heading !== null) {
      buffer.push(line)
    }
  }
  flush()
  return sections
}

export function sectionAnchor(section: PolicySection): string {
  return section.heading.replace(/^\s*/, '')
}

export const POLICY_CATEGORY_LABELS: Record<string, string> = {
  privacy: 'Privacy',
  terms: 'Terms of Service',
  marketplace: 'Marketplace',
  payments: 'Subscription & payments',
  clinical: 'Clinical data',
  data_retention: 'Cookies & data retention',
}

export function policyStatusLabel(status: string): string {
  return status.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase())
}
