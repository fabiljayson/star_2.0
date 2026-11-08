# STAR — Complete Policies & Legal Center Implementation Prompt

## 1. Role and mission

Act as a senior full-stack software engineer, software architect, application security engineer, privacy-conscious product designer, and technical documentation specialist.

Your mission is to design and implement a complete **Policies & Legal Center** within the existing STAR platform.

STAR is a surgical documentation, education, and medical equipment marketplace platform with this existing technology stack:

- **Backend:** Django and Django REST Framework.
- **Database:** PostgreSQL.
- **Web frontend:** React and Vite.
- **Mobile application:** Flutter and Dart.
- **Authentication:** Reuse the existing authentication and authorization system.
- **Application name:** STAR.
- **Brand colors:** Navy `#1E2B58` and bronze `#C68B29`.
- **Languages:** English and French.
- **Environment:** Development and student demonstration using synthetic data only.

Implement six complete policy categories:

1. Privacy Policy.
2. Terms of Service.
3. Marketplace & Seller Policy.
4. Subscription, Payment & Refund Policy.
5. Clinical Data & Professional Responsibility Policy.
6. Cookie & Data Retention Policy.

Create complete initial policy drafts in both languages, clearly marked as drafts requiring review and approval by qualified legal professionals before production publication.

The result must be a functional, integrated feature—not merely static pages, placeholder components, or a UI prototype.

Do not replace the existing STAR application, introduce an unnecessary new architecture, or break existing functionality.

---

## 2. Mandatory execution workflow

### Phase 0 — Repository audit and planning

Before changing any files, inspect the actual repository.

Identify:

- Django apps, settings modules, URL configurations, models, serializers, views, permissions, and migrations.
- The configured Django user model and authentication system.
- Existing user registration, login, logout, and account settings flows.
- Existing React/Vite routes, layouts, components, styling, localization, API client, and state management.
- Existing Flutter navigation, screens, theme, localization, API services, and state management.
- PostgreSQL configuration and existing database migration conventions.
- Existing notification, audit logging, consent, analytics, cookie, or policy implementations.
- Existing marketplace subscription and payment flows.
- Existing clinical documentation and access-control boundaries.
- Existing tests, fixtures, development commands, deployment configuration, and documentation.
- Existing accessibility and responsive-design conventions.

Search for duplicate functionality before implementing anything.

Produce an audit report containing:

1. Current architecture and relevant file paths.
2. Existing features that can be reused.
3. Missing capabilities.
4. Potential migration and compatibility risks.
5. Proposed data model and API changes.
6. Proposed React/Vite and Flutter changes.
7. Proposed policy-drafting and translation strategy.
8. Security, privacy, and legal-review considerations.
9. Implementation phases.
10. Acceptance criteria and test strategy.

**STOP after presenting the audit and implementation plan. Wait for explicit user confirmation before modifying files.**

Do not make code changes during this first phase. Once confirmation is received, proceed with implementation without repeatedly requesting approval for every ordinary development step.

### Phase 1 — Implementation

After confirmation:

- Implement the backend, database migrations, policy content, web interface, mobile interface, consent workflows, tests, and documentation.
- Preserve existing functionality and follow the actual repository conventions.
- Reuse existing authentication, API services, design systems, and localization infrastructure.
- Do not create duplicate user models or unrelated services.
- Do not delete historical user, clinical, marketplace, subscription, or payment data.
- Keep a record of implementation decisions and any deviations from the approved plan.

### Phase 2 — Verification

Run the relevant backend, frontend, mobile, migration, security, accessibility, and regression tests.

Inspect the final changes and report precisely what is complete, what has been tested, what still requires configuration, and what requires legal approval.

---

## 3. Standard 22-point software project checklist

Apply all 22 requirements to this feature.

### Planning and architecture

**1. Repository and architecture audit**

Inspect the real project before modifying files. Identify dependencies, reusable components, integration points, constraints, and risks.

**2. Requirements, implementation plan, and acceptance criteria**

Document functional requirements, nonfunctional requirements, API contracts, data model decisions, implementation phases, and measurable completion criteria. Obtain confirmation after the initial audit.

**3. Preserve existing functionality and architecture**

Extend the existing STAR implementation. Preserve authentication, user accounts, marketplace subscriptions, clinical workflows, navigation, and unrelated features. Avoid unnecessary rewrites and breaking API changes.

### Features and user experience

**4. Complete functionality and edge cases**

Implement all six policy categories, bilingual content, policy versioning, consent collection, historical consent records, policy updates, acknowledgment workflows, and relevant account settings.

**5. Responsive design and accessibility**

Support desktop, tablet, and mobile layouts. Implement semantic HTML, keyboard navigation, visible focus indicators, accessible forms, readable typography, sufficient contrast, screen-reader labels, accessible dialogs, and appropriate loading, empty, error, and offline states.

**6. Maintainable architecture and type safety**

Use maintainable Django models, serializers, services, permissions, React components, typed interfaces where available, and appropriately structured Flutter models and services. Avoid duplicated business logic.

### Engineering and data

**7. Database integrity and migrations**

Create reversible or carefully documented Django migrations. Add appropriate indexes, constraints, foreign keys, uniqueness rules, and transaction boundaries. Preserve historical records and document backup and recovery considerations.

**8. API contracts and integration**

Implement documented, validated, authenticated API endpoints where required. Reuse existing API conventions, return consistent error responses, and maintain compatibility with both web and mobile clients.

**9. Authentication and authorization**

Enforce permissions on the backend. Users may read public policies, but only authorized users may create, approve, publish, archive, or supersede policy versions. Protect personal consent history and administrative actions.

### Security, privacy, and legal safeguards

**10. Privacy Policy**

Provide a comprehensive draft describing the actual data STAR collects, purposes, access, sharing, retention, security, user rights, and privacy request procedures.

**11. Confidentiality and clinical information protection**

Provide clear confidentiality safeguards for surgical logbooks, pseudonymized patient information, attachments, assessments, and institutional information. Avoid unnecessary collection or disclosure of clinical data.

**12. Terms of Service, consent, and data rights**

Require explicit acceptance of the applicable Terms of Service during registration. Record the exact accepted version, timestamp, and user reference. Support policy history, withdrawal or account requests where appropriate, and renewed acceptance when required.

**13. Secure configuration and secrets management**

Use environment variables for sensitive configuration. Never expose secrets in frontend bundles, mobile applications, logs, fixtures, or committed environment files. Validate production security settings.

### Quality assurance

**14. Automated tests**

Implement backend unit tests, API tests, permission tests, policy-version tests, consent tests, frontend tests, and Flutter tests following existing project conventions.

**15. Regression testing**

Verify that registration, login, logout, account management, clinical workflows, marketplace purchases, seller subscriptions, and other existing features continue to work.

### Production readiness

**16. CI/CD and deployment readiness**

Update build and deployment configuration only when necessary. Ensure migrations, static assets, environment variables, and production settings are documented. Do not deploy or publish draft policies as approved legal documents.

**17. Monitoring and audit logging**

Record important policy administration, publication, acceptance, reacceptance, and consent-withdrawal events. Protect logs against tampering and prevent unnecessary exposure of personal information.

**18. Performance and scalability**

Use pagination where needed, avoid N+1 queries, cache only safe public content, invalidate caches on publication changes, and keep user-specific consent information private.

**19. Documentation**

Document the data model, API endpoints, policy lifecycle, bilingual content management, consent requirements, configuration, migrations, test commands, deployment, and legal-review workflow.

**20. Dependency and cost management**

Reuse existing dependencies whenever possible. Avoid unnecessary paid services, duplicate packages, or infrastructure. Keep the student demonstration compatible with the existing deployment architecture.

### Application safeguards and completion

**21. Appropriate safeguards for AI or automated content**

If AI is used to draft, translate, summarize, classify, or update policies, treat its output as unapproved draft content. Require authorized human review before publication. Do not automatically publish generated legal text or claim that AI output is legally validated.

**22. Honest final verification and delivery**

Run the relevant tests, inspect changes, report exact results, document incomplete features and limitations, and identify remaining configuration and legal-review requirements. Never claim a feature was tested, deployed, legally reviewed, or completed if it was not.

---

## 4. Policy Center information architecture

Create a dedicated, discoverable **Policies & Legal Center** accessible from:

- The website footer.
- The web application's account settings.
- The Flutter application's settings.
- Registration and authentication screens.
- Relevant marketplace subscription and checkout screens.
- Relevant clinical documentation workflows.
- Any existing help or support section, where appropriate.

Use the existing router and navigation patterns.

### Required pages

Implement the following:

1. Policies & Legal Center overview.
2. Individual policy detail page.
3. Policy version history.
4. Current policy status and effective date.
5. Policy acceptance and acknowledgment interface.
6. User's consent history.
7. Privacy request information and available request workflow.
8. Authorized administrative policy management interface.
9. Draft-review and publication workflow.
10. English/French language switcher.

Each policy detail page should support:

- Clear title and category.
- Language indicator.
- Draft, pending review, approved, or published status.
- Version identifier.
- Publication date.
- Effective date.
- Last reviewed date.
- Next review date, where configured.
- A structured table of contents.
- Navigable headings.
- Readable policy sections.
- Links to related policies.
- Print-friendly layout.
- An accessible way to return to the Policy Center.
- A clear notice when the document is an unapproved draft.

Never present a draft as an approved or binding policy.

---

## 5. Policy content requirements

Generate six complete initial policy drafts in English and French.

Use a consistent structure, terminology, version metadata, and translation workflow. Store the English and French versions as explicitly related translations of the same logical policy whenever they have equivalent meaning.

Use neutral, professional language suitable for a medical-technology platform and a Cameroon-oriented marketplace, while avoiding unsupported assumptions about the operator's legal identity, establishment, jurisdiction, or compliance status.

Do not invent a company registration number, physical address, legal representative, privacy officer, payment provider, legal certification, or contractual guarantee.

Use clearly identified placeholders for information that must be supplied by the platform operator.

### 5.1 Privacy Policy

The draft must address:

- Who operates STAR, using a placeholder for the legal entity and contact details.
- The distinction between account data, clinical logbook data, marketplace data, subscription records, payment references, support communications, technical logs, and optional analytics.
- Data categories collected and whether each is required or optional.
- Purposes and applicable legal bases, to be confirmed by qualified counsel.
- Account creation and authentication.
- Surgical logbooks and pseudonymized patient information.
- Marketplace listings, orders, and seller subscriptions.
- Payment processing and external providers.
- Hosting, storage, service providers, and potential data transfers.
- Access controls and authorized institutional or supervisory access.
- Security measures and their limitations.
- Retention criteria and deletion practices.
- User access, correction, objection, deletion, or other applicable rights.
- Account closure and its effect on retained records.
- Data incident handling.
- Contact details for privacy requests.
- Policy updates and effective dates.

Do not claim that pseudonymization makes clinical data anonymous. Explain that pseudonymized information may remain personal data.

Do not claim a specific legal basis or cross-border transfer mechanism without review.

### 5.2 Terms of Service

Address:

- Eligibility and account responsibilities.
- Account security and accurate information.
- Acceptable use and prohibited conduct.
- Intellectual property and content ownership.
- User-submitted stories, text, images, and marketplace content.
- Clinical and educational limitations.
- Platform availability and service interruptions.
- Suspension and termination.
- Subscription-related access limitations.
- Marketplace transaction responsibilities.
- Third-party services.
- Complaints and dispute procedures.
- Liability limitations, subject to applicable law and legal review.
- Amendments and material policy changes.
- Contact details and effective dates.

Do not invent legally enforceable waivers or claim that STAR eliminates professional liability.

### 5.3 Marketplace & Seller Policy

Address:

- The unified user account model.
- The ability of all eligible users to browse and purchase equipment.
- The requirement for an active seller subscription before publishing listings.
- Seller identity and verification requirements, where implemented.
- Accurate descriptions, prices, stock, condition, and images.
- Prohibited or restricted listings.
- Medical equipment safety and lawful sale requirements.
- Authenticity, recalls, expiry dates, and condition disclosures where relevant.
- Listing moderation and removal.
- Subscription expiration and automatic public hiding of existing listings.
- Preservation of hidden listings in the owner's private account.
- Reactivation of eligible listings after verified renewal.
- Order processing, shipping, delivery, returns, and disputes.
- Responsibilities of buyers and sellers.
- Reporting suspicious or prohibited listings.
- Marketplace limitations and contact procedures.

Do not invent a seller verification process that the software does not implement.

Clearly distinguish the platform's role from the role of equipment sellers, buyers, payment processors, carriers, and other third parties.

### 5.4 Subscription, Payment & Refund Policy

Use the existing STAR business rule:

- Monthly seller subscription price: **10,000 FCFA**.
- Currency code: `XAF`.
- Duration: one calendar month.
- Active subscription required to publish equipment listings.
- All eligible users can buy without being required to subscribe as sellers.
- Expiration hides existing listings from public discovery but does not delete them.
- Renewal restores eligible listings after payment verification.

Address:

- Subscription eligibility.
- Pricing and applicable charges.
- Checkout initiation.
- Payment provider responsibilities.
- Payment pending, success, failure, cancellation, and verification delays.
- Subscription activation.
- Start and expiration dates.
- Calendar-month calculation.
- Renewal behavior.
- Automatic renewal only if genuinely implemented and appropriately authorized.
- Cancellation.
- Refund requests and applicable conditions.
- Duplicate payments and reconciliation.
- Disputed transactions.
- Failed renewals.
- Subscription expiration.
- Access to existing orders after expiration.
- Payment support and complaint channels.

Do not invent a blanket no-refund policy or promise refunds without an approved business and legal decision.

Use placeholders for provider-specific payment methods, settlement timing, fees, and refund processing times until these are confirmed.

The document must match the actual application implementation.

### 5.5 Clinical Data & Professional Responsibility Policy

Address:

- Permitted use of surgical logbooks and training records.
- Confidentiality and access restrictions.
- Data minimization and pseudonymization.
- Avoiding unnecessary direct patient identifiers.
- Institutional rules and professional confidentiality.
- Authorized supervisors, examiners, and institutional personnel.
- Educational and assessment purposes.
- Secure handling of clinical attachments.
- Restrictions on unauthorized disclosure or publication.
- User responsibility for the accuracy of submitted records.
- Review and correction workflows where implemented.
- The distinction between educational documentation and official medical records.
- The limitations of automated or AI-assisted content.
- Professional judgment and responsibility.
- Reporting suspected privacy or security incidents.
- Retention and deletion considerations.

Explicitly state in the draft that STAR is not a substitute for official medical records, clinical judgment, professional supervision, or institutional procedures.

Do not claim that a platform's pseudonymization alone guarantees compliance or removes confidentiality obligations.

Do not encourage users to upload identifiable patient records to a student demonstration environment.

### 5.6 Cookie & Data Retention Policy

Address:

- Essential cookies and session storage, if used.
- Authentication tokens and session expiration.
- Optional analytics and tracking technologies, if implemented.
- Third-party embeds or integrations, if present.
- User choices and consent behavior where applicable.
- Browser and mobile storage distinctions.
- Data retention categories and criteria.
- Account and clinical record retention considerations.
- Marketplace orders, payments, and financial record retention.
- Security logs and audit events.
- Backup retention and eventual deletion.
- Legal holds or mandatory retention requirements, subject to legal review.
- Account deletion requests.
- Exceptions to deletion.
- Retention review and disposal procedures.

Audit the actual application before describing cookies, analytics, tracking, or local storage. Do not claim that STAR uses or does not use a technology without verifying the implementation.

Where retention periods have not been determined, use explicit policy placeholders and create an administrative configuration or documented decision point rather than inventing durations.

---

## 6. Bilingual content and localization

Implement both English and French.

Requirements:

- English and French drafts for all six policies.
- Consistent section identifiers across translated documents.
- Consistent legal and technical terminology.
- Language selection that works in both React/Vite and Flutter.
- Language preference integration with existing STAR localization.
- Clearly linked translations and version relationships.
- Translation review status.
- Identification of the authoritative version or language, to be confirmed by legal review.
- Correct handling of accents, punctuation, dates, and typography.
- Accessible language-switching controls.

Do not automatically treat two translations as legally identical without review.

If one translation changes materially, require review and a documented publication decision.

Store language codes consistently, for example `en` and `fr`.

If existing localization files are used, integrate into those files rather than creating a separate incompatible localization system.

---

## 7. Policy versioning and lifecycle

Implement a real policy versioning system.

Each logical policy must support multiple immutable versions.

Include appropriate fields such as:

- Policy category.
- Language.
- Version identifier.
- Title.
- Structured policy content.
- Draft status.
- Review status.
- Publication status.
- Effective date.
- Publication timestamp.
- Creation and update timestamps.
- Author or creator reference.
- Reviewer reference.
- Approver reference.
- Approval timestamp.
- Review notes or reason for revision.
- Link to the corresponding translated version.
- Superseded-version reference, if appropriate.
- Content checksum or other integrity mechanism where justified.

Adapt the schema to the existing codebase. Avoid adding unnecessary fields that duplicate existing audit infrastructure.

### Required lifecycle

Support transitions such as:

`Draft → Pending Review → Approved → Published → Superseded`

A draft must not be publicly presented as an approved current policy.

Only explicitly authorized users may approve or publish policies.

Published versions must be immutable. Corrections should create a new version rather than silently altering historical text.

Record the actor, timestamp, and relevant version for approval and publication events.

Allow the administrator to configure effective dates and review dates.

Prevent publication of a translation that has not completed the required review workflow.

Use appropriate database transactions and constraints to avoid two simultaneously active versions of the same policy and language when the business rule requires a single current version.

---

## 8. Explicit consent and acknowledgment

### Registration requirements

Require explicit acceptance of the applicable Terms of Service during registration.

Provide separate, clearly worded links to the Terms of Service and Privacy Policy.

The Terms checkbox must:

- Be unchecked by default.
- Require an affirmative user action.
- Not be bundled with unrelated marketing consent.
- Identify the applicable Terms version.
- Be keyboard accessible.
- Be available in English and French.
- Display validation feedback if the user attempts to register without accepting.

Record at minimum:

- User reference.
- Policy reference.
- Exact policy version.
- Language shown to the user.
- Acceptance timestamp.
- Consent or acceptance action.
- Relevant request or audit correlation reference, where appropriate.

Store acceptance on the server. Never trust a frontend-only boolean as the authoritative consent record.

Use an appropriate database model with uniqueness constraints or event semantics consistent with the audit requirements.

### Privacy Policy acknowledgment

Provide an explicit acknowledgment mechanism where required by the approved product and legal design.

Do not automatically represent reading or acknowledging the Privacy Policy as consent to every processing activity.

Where consent is required for a specific optional purpose, record that purpose separately and support its withdrawal where applicable.

### Policy updates

When a new version is published:

- Determine whether the change is material.
- Identify users who must accept the new Terms version.
- Show a clear notice and the relevant new version.
- Record acceptance of the new version.
- Preserve all previous acceptance records.
- Avoid collecting duplicate acceptance records for repeated identical submissions.
- Do not retroactively change the content of historical acceptance records.

Where renewed acceptance is required, block only the relevant gated actions until acceptance, subject to the approved legal and operational policy. Preserve access to essential account functions and appropriate ways to review the policy or contact support.

Do not automatically log users out or delete accounts simply because a policy version changed.

### Consent history

Allow users to review their own acceptance history, including policy name, version, language, and timestamp.

Do not allow users to modify historical acceptance events.

Support an appropriately authorized administrative view for audit purposes, with minimal disclosure of personal information.

---

## 9. Privacy requests and account rights

Implement a documented and appropriately secured workflow for privacy-related requests.

Depending on the existing application architecture, support requests such as:

- Access to personal data.
- Correction of account information.
- Account closure.
- Data deletion requests.
- Consent withdrawal where applicable.
- Questions about retention.
- Complaints or privacy concerns.

Do not automatically delete records that must be retained for legitimate operational or legal reasons. Instead, record the request, assess applicable retention rules, and document the outcome.

Ensure request status is visible to the requesting user where a request-management interface is implemented.

Use authorization checks so users can access only their own requests.

Do not claim that every record can be deleted immediately or that every request has a fixed legal deadline without qualified review.

---

## 10. Backend implementation

Implement the feature using Django REST Framework and PostgreSQL.

### Models

Design and implement appropriate models for:

1. Logical policy.
2. Policy version.
3. Policy approval or publication event, if existing audit models do not already cover it.
4. Policy acceptance and acknowledgment records.
5. Consent-purpose records, if optional processing consent is applicable.
6. Privacy requests.
7. Relevant audit events, reusing existing infrastructure wherever possible.

Use the configured Django user model through `settings.AUTH_USER_MODEL`.

Add appropriate constraints, indexes, related names, validation, and deletion policies.

Keep historical policy versions and consent events intact.

Do not store sensitive clinical details inside consent records or general-purpose logs.

### Serializers and validation

Implement serializers that:

- Expose only appropriate fields.
- Validate policy status transitions.
- Prevent clients from setting approval or publication status without authorization.
- Reject invalid language codes and version relationships.
- Validate acceptance against the correct published version.
- Prevent users from submitting acceptance for another user.
- Validate privacy requests and allowed state transitions.

### Services

Use a service layer where appropriate for:

- Policy publication.
- Policy version supersession.
- Translation relationships.
- Consent recording.
- Current-policy lookup.
- Reacceptance requirements.
- Privacy request lifecycle.
- Audit-event creation.

Use transactions for operations that must update multiple records consistently.

### Permissions

Implement role-based permissions using the existing STAR authorization system.

Users may:

- Read public published policies.
- Read their own consent history.
- Submit their own privacy requests.
- Update or cancel their own requests only according to the approved workflow.

Authorized policy administrators may:

- Create drafts.
- Edit drafts.
- Submit versions for review.
- Approve versions.
- Publish approved versions.
- Supersede versions.
- View policy administration audit records.

Reviewers and approvers must not receive permissions simply because they are authenticated users.

If the current application does not have policy administration roles, implement the smallest compatible permission extension and document how administrators are assigned.

Prevent unauthorized publication through direct API requests.

### API endpoints

Follow existing route conventions. Implement equivalent functionality to the following where appropriate:

Public endpoints:

- `GET /api/v1/policies/`
- `GET /api/v1/policies/current/`
- `GET /api/v1/policies/{slug}/`
- `GET /api/v1/policies/{slug}/versions/`
- `GET /api/v1/policies/{slug}/versions/{version}/`

Authenticated endpoints:

- `GET /api/v1/me/policy-acceptances/`
- `POST /api/v1/me/policy-acceptances/`
- `GET /api/v1/me/privacy-requests/`
- `POST /api/v1/me/privacy-requests/`
- `GET /api/v1/me/privacy-requests/{id}/`
- Additional request-management endpoints where justified.

Administrative endpoints:

- Create and edit drafts.
- Submit a version for review.
- Approve or reject a version.
- Publish a reviewed version.
- Supersede an existing version.
- View publication history.
- Manage translation relationships.
- Review privacy requests.
- View authorized audit history.

These are suggested paths, not a requirement to duplicate existing routes. Reuse current API conventions and avoid redundant endpoints.

### API response behavior

Provide consistent response schemas and errors.

For example, a current-policy response may include:

- Policy identifier.
- Slug.
- Category.
- Language.
- Version.
- Status.
- Effective date.
- Publication date.
- Content.
- Translation relationship.
- Whether the authenticated user must accept a new Terms version.

A user-specific response may additionally indicate whether the current Terms version has been accepted.

Never expose unpublished drafts through public endpoints.

Do not expose other users' acceptance records or privacy requests.

Document the API using the existing OpenAPI or API documentation approach, if present.

---

## 11. React/Vite implementation

Build a complete, polished Policies & Legal Center using the existing STAR design system.

Use:

- Navy `#1E2B58`.
- Bronze `#C68B29`.
- Existing typography, spacing, buttons, cards, form controls, and layout components.
- Existing routing, API client, localization, and state-management conventions.

Do not introduce gradients, decorative elements, or an unrelated design language if these conflict with the existing STAR UI.

### Required screens and components

Implement:

1. Policies & Legal Center landing page.
2. Policy category cards.
3. Policy detail page.
4. Policy table of contents.
5. English/French language switcher.
6. Policy version history.
7. Draft and review status indicators.
8. Registration Terms acceptance checkbox.
9. Privacy acknowledgment or optional-consent controls where applicable.
10. Consent history page.
11. Privacy request form and status page.
12. Policy update notification.
13. Reacceptance screen or modal.
14. Administrative policy editor.
15. Policy preview.
16. Review and approval workflow screens.
17. Publication confirmation dialog.
18. Appropriate empty, loading, success, offline, and error states.

### Policy detail UX

Display the policy title, category, language, version, effective date, status, and structured content.

Include a table of contents with accessible anchor links.

Keep long-form content readable and responsive.

Distinguish drafts from published policies using both text and visual indicators, not color alone.

Provide a print-friendly presentation without leaking private account data.

### Registration integration

Integrate the required Terms checkbox into the existing registration flow.

Do not create a duplicate registration form.

The checkbox must be unchecked by default.

Prevent submission until the required Terms version is explicitly accepted.

Submit the exact policy version or another validated version reference to the backend. The backend must resolve and validate the current required version.

Display errors accessibly and preserve the user's other valid form inputs after an error.

### Reacceptance UX

When a material Terms update requires renewed acceptance:

- Explain that the Terms have changed.
- Link to the exact new version.
- Clearly identify the version and effective date.
- Provide affirmative acceptance.
- Record the acceptance through the backend.
- Handle failed submissions and network interruptions.
- Do not mark acceptance complete optimistically before the server confirms it.

### Admin UX

Authorized administrators must be able to create drafts, preview English and French versions, manage translations, submit for review, approve, publish, and view historical versions.

Require confirmation for publication and supersession actions.

Do not permit a normal user to access administrative components merely by navigating to their URLs.

---

## 12. Flutter implementation

Integrate the Policies & Legal Center into the existing Flutter application.

Inspect the current navigation, theme, authentication, API services, state management, localization, and form conventions before implementing screens.

Implement equivalent mobile experiences:

- Policy Center.
- Policy category list.
- Policy detail.
- Language switcher.
- Version history.
- Registration Terms acceptance.
- Consent history.
- Privacy request submission and status.
- Policy update notification.
- Required reacceptance workflow.

Use the same backend policy versions and consent records as the web application.

Do not implement a separate mobile-only consent database.

Ensure that acceptance is confirmed by the server before the application considers it recorded.

Use the existing state-management system, such as Riverpod or Bloc, if already established. Do not replace the current architecture.

Support:

- Loading states.
- Network failures.
- Retry actions.
- Offline policy reading where safely supported.
- Clear identification of stale offline policy content.
- Accessible touch targets.
- Screen readers.
- Appropriate navigation and back behavior.
- English and French localization.

Never permit offline acceptance to be treated as authoritative until successfully submitted and confirmed by the backend.

If the application has an administrative mobile workflow, reuse it only where appropriate. Do not expose privileged policy administration to ordinary mobile users.

---

## 13. Security, privacy, and audit trail

Implement defense in depth.

### Security requirements

- Authenticate all private API requests.
- Enforce object-level authorization.
- Validate policy state transitions server-side.
- Keep published policy versions immutable.
- Validate acceptance against a currently required version.
- Prevent users from forging another user's acceptance.
- Prevent clients from setting approval, publication, or audit timestamps.
- Protect administrative routes and APIs.
- Rate-limit sensitive request endpoints where appropriate.
- Validate and sanitize user-supplied text.
- Avoid rendering policy HTML unsafely.
- Protect against cross-site scripting.
- Use appropriate CSRF protection if session authentication is used.
- Keep secrets out of frontend builds, mobile binaries, logs, and Git.
- Avoid logging request bodies that contain unnecessary personal information.
- Ensure privacy request records are accessible only to authorized users and administrators.
- Do not include patient identifiers in policy analytics or audit logs.

### Audit requirements

Record relevant events, including:

- Policy draft creation.
- Draft edits where auditability is required.
- Submission for review.
- Approval and rejection.
- Publication.
- Supersession.
- User acceptance of Terms.
- Relevant consent-purpose changes.
- Consent withdrawal where applicable.
- Privacy request creation and status transitions.
- Authorized administrative access to sensitive request details, where appropriate.

Each audit event should capture the minimum necessary information, such as actor reference, action, timestamp, affected resource, and a correlation identifier.

Do not log secrets or unnecessary clinical details.

Protect audit records against ordinary user modification. Reuse an existing audit framework if available.

Document audit retention and access controls.

---

## 14. Draft publication safeguards

All six policies and their translations must begin in an unapproved draft state.

The initial implementation must not publish them automatically.

Implement explicit review controls and distinguish:

- Draft.
- Pending review.
- Approved.
- Published.
- Superseded.
- Rejected, if supported.

A reviewer must be able to identify which language version they are reviewing.

Publication must require the necessary permissions and a documented approval event.

Where a policy is not approved, display a clear internal or demo notice that it is not approved for production use.

Do not imply that a draft becomes legally valid merely because an administrator clicked Publish. Publication is an application workflow, not a legal certification.

For student demonstrations, use synthetic administrator accounts and clearly label sample policy content.

---

## 15. Testing strategy

Write automated tests following the existing repository's conventions.

### Backend model and service tests

Test:

- Policy creation.
- Version relationships.
- Language validation.
- Draft immutability rules after publication.
- Publication and supersession.
- Effective dates.
- Translation relationships.
- Consent creation.
- Consent uniqueness or idempotency.
- Historical acceptance preservation.
- Reacceptance after a required Terms update.
- Privacy request state transitions.
- Audit event creation.

### API and authorization tests

Test:

- Public users can read published policies.
- Public users cannot read drafts.
- Authenticated users can read their own consent history.
- Users cannot access another user's acceptance records.
- Users cannot access another user's privacy requests.
- Unauthorized users cannot publish policies.
- Authorized reviewers and approvers can perform their permitted actions.
- The backend rejects forged acceptance timestamps and user references.
- The backend rejects acceptance of an invalid or superseded version where it is no longer acceptable.
- Required acceptance is enforced at registration.
- API errors follow documented response conventions.

### Frontend tests

Test:

- Policy Center navigation.
- English/French switching.
- Policy detail rendering.
- Draft and published status display.
- Required Terms checkbox validation.
- Registration submission behavior.
- Policy update notifications.
- Reacceptance workflow.
- Consent history visibility.
- Privacy request submission.
- Loading, error, and empty states.
- Keyboard accessibility and basic accessibility assertions.

### Flutter tests

Test:

- Policy screen rendering.
- Language selection.
- Terms checkbox behavior.
- Required acceptance validation.
- API acceptance submission.
- Failure and retry handling.
- Policy update notifications.
- Consent history.
- Privacy request submission.
- Offline and stale-policy states.
- Navigation and state restoration where applicable.

### Regression tests

Confirm that:

- Registration still works after the required acceptance is supplied.
- Login and logout remain functional.
- Existing account settings continue to work.
- Marketplace subscription and payment behavior remains intact.
- Existing clinical documentation workflows are unaffected.
- Existing user permissions remain correct.
- Existing API contracts are preserved where required.

Run migrations against the development/test database and test the migration path with representative synthetic data.

Do not use real patient information or production personal data in test fixtures.

---

## 16. Accessibility and usability

Aim for WCAG 2.1 AA accessibility practices without claiming formal certification.

Ensure:

- Proper heading hierarchy.
- Keyboard navigation.
- Visible focus states.
- Screen-reader labels.
- Accessible dialogs and focus management.
- Sufficient text contrast.
- Responsive long-form reading.
- Non-color indicators for statuses.
- Clear language selection.
- Plain-language policy summaries.
- Consistent button labels.
- Accessible validation messages.
- Readable error notifications.
- Appropriate touch targets in Flutter.

Do not replace the full policy with a short summary. A summary may supplement the complete document but must not misrepresent it.

---

## 17. Documentation and configuration

Update the existing documentation rather than creating redundant documentation files.

Include:

- Policies & Legal Center overview.
- Architecture and data model.
- API endpoints and response contracts.
- Policy lifecycle.
- Bilingual content management.
- Registration acceptance flow.
- Consent and acknowledgment semantics.
- Reacceptance rules.
- Privacy request workflow.
- Administrative permissions.
- Audit logging.
- Database migrations.
- Environment configuration.
- Development and test commands.
- Deployment requirements.
- Backup and recovery considerations.
- Legal review and publication procedure.

Create or update `.env.example` only where appropriate.

Never overwrite real `.env` files or commit secrets.

Use synthetic data exclusively for development fixtures and demonstration accounts.

Do not introduce paid services unless essential and explicitly documented.

---

## 18. Legal review and compliance boundaries

All policy content is an initial drafting aid, not legal advice.

The implementation must not claim that STAR complies with any law, regulation, certification, or institutional requirement simply because the policies exist.

Before production publication, qualified legal professionals must review:

- The legal identity and jurisdiction of the platform operator.
- Applicable privacy and data-protection obligations.
- Clinical confidentiality and professional obligations.
- Institutional and educational requirements.
- International or cross-border data transfers.
- Payment processing and consumer protection.
- Marketplace rules for medical equipment.
- Subscription, cancellation, refund, and dispute terms.
- Cookie and analytics practices.
- Retention and deletion periods.
- Data-subject request procedures.
- English and French legal consistency.
- Required notices, disclosures, and user consent wording.

Use explicit placeholders for unconfirmed facts.

Do not fabricate legal bases, retention durations, mandatory disclosure periods, addresses, or regulatory approval.

The final documentation must identify every placeholder requiring operator input and every section requiring legal approval.

---

## 19. Definition of done

The feature is complete only when all applicable criteria are satisfied:

1. The repository audit and implementation plan were presented and approved before code changes.
2. All six policy categories exist as complete initial English and French drafts.
3. Draft policies are not automatically published.
4. Policy versions are stored and managed through a controlled lifecycle.
5. Published versions are immutable.
6. English and French versions are linked and their review status is tracked.
7. Registration requires explicit Terms acceptance.
8. Consent records contain the exact version, user reference, language, and server timestamp.
9. Historical acceptance records remain available.
10. Material Terms updates can trigger renewed acceptance.
11. Users can review their own consent history.
12. Privacy requests follow an authorized workflow.
13. Administrative operations are protected by backend permissions.
14. Audit events are generated for relevant actions.
15. React/Vite includes the complete Policies & Legal Center.
16. Flutter includes equivalent policy and consent experiences.
17. Both clients use the same backend source of truth.
18. The implementation is responsive and accessible.
19. Migrations preserve existing data and existing functionality.
20. Automated tests cover the critical business and security rules.
21. Documentation and environment examples are updated.
22. Remaining legal approvals, configuration, untested features, and limitations are clearly reported.

Do not mark the project complete merely because the screens render. Verify the database, API, consent behavior, authorization, and tests.

---

## 20. Final delivery report

After implementation and verification, provide a concise but comprehensive report with:

### A. Repository findings
- Actual backend, web, and mobile paths.
- Relevant existing architecture.
- Important compatibility decisions.

### B. Implemented changes
- Files created.
- Files modified.
- Database models and migrations.
- API endpoints.
- Policy lifecycle and permissions.
- React/Vite components and pages.
- Flutter screens and services.
- English and French policy content.
- Consent and audit behavior.

### C. Verification
- Commands executed.
- Tests passed.
- Tests failed or skipped.
- Migration results.
- Regression findings.
- Security and accessibility checks.

### D. Setup and deployment
- Required environment variables.
- Migration commands.
- Test commands.
- Development commands.
- Administrative setup instructions.

### E. Outstanding work
- Legal placeholders.
- Policies requiring approval.
- External configuration requirements.
- Payment or privacy integrations that remain incomplete.
- Any features that were not implemented or could not be tested.

Be transparent. Never invent test results or claim deployment, legal review, or compliance that has not occurred.

## Final instruction

**Start by auditing the existing STAR repository. Present the audit findings and implementation plan, then wait for my explicit confirmation before changing any files. After approval, implement the complete bilingual Policies & Legal Center end to end, following all 22 checklist requirements, preserving existing functionality, and using synthetic data only.**