import { Link } from 'react-router-dom'

const MODULES = [
  {
    icon: '◷',
    title: 'Surgical logbook',
    description:
      'Structured procedure records with participant roles, private attachments, supervisor review, and simulated dictation transcripts.',
  },
  {
    icon: '◆',
    title: 'Training & assessment',
    description:
      'Placements, competency catalogs with versioned rubrics, and examiner decisions — never self-approved.',
  },
  {
    icon: '⤓',
    title: 'Reports & exports',
    description:
      'CSV and PDF exports for progress, reviews, and institution summaries — generated on demand, securely downloadable.',
  },
  {
    icon: '▤',
    title: 'Equipment marketplace',
    description:
      'Verified suppliers, approved catalog, inventory reservations, sandbox payments, shipments, and dispute handling.',
  },
] as const

const STEPS = [
  {
    number: '01',
    title: 'Record',
    description: 'Trainees and surgeons log every procedure with full clinical detail.',
  },
  {
    number: '02',
    title: 'Review',
    description: 'Supervisors approve, return, or request corrections — always audited.',
  },
  {
    number: '03',
    title: 'Assess',
    description: 'Examiners grade competencies against immutable, versioned rubrics.',
  },
  {
    number: '04',
    title: 'Act',
    description: 'Export audited reports and procure equipment through the marketplace.',
  },
] as const

const SECURITY = [
  'JWT sessions with rotation and TOTP two-factor authentication.',
  'Institution-scoped access — clinical data never leaves your organization.',
  'Append-only audit trail on every clinical and financial action.',
  'Private file storage; attachments are never exposed on the public web.',
] as const

export function LandingPage() {
  return (
    <div className="landing">
      <header className="landing-nav glass">
        <div className="landing-nav__inner">
          <Link to="/" className="brand landing-nav__brand">
            <img className="brand__mark" src="/app-icon.png" alt="" width={36} height={36} />
            <span className="brand__text">STAR</span>
          </Link>
          <nav className="landing-nav__links" aria-label="Landing sections">
            <a href="#platform">Platform</a>
            <a href="#workflow">Workflow</a>
            <a href="#security">Security</a>
          </nav>
          <div className="landing-nav__actions">
            <Link to="/login" className="btn btn--ghost btn--sm">
              Sign in
            </Link>
            <Link to="/register" className="btn btn--primary btn--sm">
              Create account
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero__copy">
            <p className="landing-eyebrow">Surgical training platform</p>
            <h1 className="landing-hero__title">
              Track every procedure.
              <br />
              Prove every competency.
            </h1>
            <p className="landing-hero__lead">
              STAR is the secure platform where surgical teams keep their logbook, run
              competency-based training, export audited reports, and source equipment — in
              one place.
            </p>
            <div className="landing-hero__actions">
              <Link to="/register" className="btn btn--primary">
                Create account
              </Link>
              <Link to="/login" className="btn btn--ghost">
                Sign in
              </Link>
            </div>
            <ul className="landing-trust" aria-label="Platform guarantees">
              <li>Role-based access</li>
              <li>Institution-scoped data</li>
              <li>Append-only audit trail</li>
            </ul>
          </div>
          <div className="landing-hero__visual">
            <div className="landing-hero__glow" aria-hidden="true" />
            <figure className="landing-plate">
              <img
                src="/logo.png"
                alt="STAR — Secure Surgical Tracking, Assessment and Resources"
                width={900}
                height={900}
              />
            </figure>
          </div>
        </section>

        <section id="platform" className="landing-section">
          <div className="landing-section__head">
            <p className="landing-eyebrow">The platform</p>
            <h2 className="landing-section__title">Four modules, one record of truth</h2>
            <p className="landing-section__lead">
              From the operating room to the procurement desk, every module writes to the
              same audited backbone.
            </p>
          </div>
          <div className="feature-grid">
            {MODULES.map((module) => (
              <article key={module.title} className="feature-card glass">
                <span className="feature-card__icon" aria-hidden="true">
                  {module.icon}
                </span>
                <h3 className="feature-card__title">{module.title}</h3>
                <p className="feature-card__description">{module.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="workflow" className="landing-section">
          <div className="landing-section__head">
            <p className="landing-eyebrow">Workflow</p>
            <h2 className="landing-section__title">From dictation to decision</h2>
            <p className="landing-section__lead">
              A single, reviewable path turns raw operative notes into verified
              competencies.
            </p>
          </div>
          <ol className="steps">
            {STEPS.map((step) => (
              <li key={step.number} className="step glass">
                <span className="step__number">{step.number}</span>
                <h3 className="step__title">{step.title}</h3>
                <p className="step__description">{step.description}</p>
              </li>
            ))}
          </ol>
        </section>

        <section id="security" className="landing-section">
          <div className="security-band glass">
            <div className="security-band__copy">
              <p className="landing-eyebrow">Security &amp; governance</p>
              <h2 className="landing-section__title">Clinical data deserves more than good intentions</h2>
              <p className="landing-section__lead">
                STAR is built around least privilege, institutional boundaries, and a
                trail nobody can rewrite.
              </p>
            </div>
            <ul className="security-list">
              {SECURITY.map((item) => (
                <li key={item}>
                  <span className="security-list__check" aria-hidden="true">
                    ✓
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="landing-section">
          <div className="cta-band glass">
            <h2 className="cta-band__title">Ready to modernize your surgical program?</h2>
            <p className="cta-band__lead">
              Create an account to explore the platform, or sign in if your institution
              already runs STAR.
            </p>
            <div className="cta-band__actions">
              <Link to="/register" className="btn btn--primary">
                Create account
              </Link>
              <Link to="/login" className="btn btn--ghost">
                Sign in
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-footer__inner">
          <span className="brand">
            <img className="brand__mark" src="/app-icon.png" alt="" width={28} height={28} />
            <span className="brand__text">STAR</span>
          </span>
          <p className="landing-footer__tagline">
            Secure Surgical Tracking, Assessment &amp; Resources
          </p>
          <p className="landing-footer__copy">© 2026 STAR. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
