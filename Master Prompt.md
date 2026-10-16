# MASTER IMPLEMENTATION PROMPT — STAR
## Secure Surgical Tracking, Assessment & Resources Platform

### 1. YOUR ROLE

Act as a senior full-stack software architect, Django backend engineer, Flutter developer, UI/UX designer, database architect, cybersecurity engineer, QA engineer, and DevOps engineer.

Your mission is to **fully design, implement, test, document, and prepare STAR for deployment** as a production-oriented surgical logbook, training management, reporting, and surgical equipment marketplace platform.

Do not deliver only a prototype, static dashboard, incomplete scaffold, design mockup, or collection of disconnected screens.

Build a coherent application with functional navigation, persistent database storage, validated business logic, secure APIs, meaningful error handling, automated tests, and complete setup documentation.

**Official project name: STAR**

STAR is a professional digital platform for documenting surgical procedures, tracking clinical training experience, managing assessments, generating reports, and purchasing surgical equipment from verified suppliers.

Use STAR consistently throughout the application, documentation, metadata, branding, configuration, and user-facing interface.

Do not use SurgiLog as the product name.

---

### 2. INITIAL REPOSITORY INSPECTION

Before modifying anything, inspect the existing repository and understand its current state.

1. Identify the programming languages, frameworks, directory structure, existing modules, dependencies, database configuration, environment variables, tests, and documentation.
2. Determine whether the repository already contains a Django backend, Flutter application, web frontend, or existing implementation.
3. Read the README, project requirements, design specifications, configuration files, and relevant source files.
4. Identify existing functionality that can be preserved or improved.
5. Detect incomplete features, security issues, duplicated code, broken integrations, and architectural inconsistencies.
6. Check available development tools and installed framework versions.
7. Identify missing requirements and document assumptions.

Do not overwrite or delete existing working functionality without a clear justification.

If the repository is empty, create a complete project structure.

If the repository already contains code, adapt the implementation to its existing conventions wherever reasonable.

### 3. EXECUTION STRATEGY

Work in the following sequence:

**Phase A — Discovery and planning**
- Inspect the repository.
- Create an implementation plan.
- Define the architecture, data model, security boundaries, and development milestones.
- Identify dependencies and unresolved decisions.
- Present a concise plan before substantial modifications when working interactively.

**Phase B — Architecture and foundations**
- Establish the project structure.
- Configure the database and environment management.
- Implement authentication, authorization, common API conventions, error handling, and audit infrastructure.
- Create database migrations and development fixtures.

**Phase C — Core application**
- Implement the surgical logbook.
- Implement voice and text entry.
- Implement users, institutions, training placements, examiners, assessments, reports, and attachments.

**Phase D — Marketplace**
- Implement suppliers, product catalogs, inventory, carts, orders, payments, refunds, shipments, and disputes.

**Phase E — User interfaces**
- Implement every required screen and connect it to real backend functionality.
- Ensure web and mobile interfaces handle loading, empty, success, validation, and error states.

**Phase F — Verification and delivery**
- Run migrations, automated tests, static checks, and available build commands.
- Fix discovered failures rather than merely documenting them.
- Verify critical workflows end to end.
- Complete documentation and deployment configuration.

Do not stop after generating a plan or scaffolding. Continue implementation through the available milestones. If credentials or external services are unavailable, complete the integration boundary and a safe development implementation, document the limitation, and continue with the remaining work.

---

### 4. PRODUCT VISION

STAR must support three connected business domains:

1. **Surgical documentation:** record procedures, participants, observations, notes, and permitted attachments.
2. **Clinical education and reporting:** manage trainees, placements, competencies, evaluations, examiner reviews, and reports.
3. **Surgical equipment marketplace:** enable verified suppliers to list equipment and authorized buyers to place and track orders.

These domains must share a consistent authentication and authorization system while maintaining strict separation between medical information and commercial data.

STAR is a documentation and education platform. It must not independently diagnose patients, prescribe treatment, or replace an institution's official medical record system.

---

### 5. REQUIRED TECHNOLOGY STACK

Use the following architecture unless repository constraints justify a documented alternative.

#### Backend
- Python
- Django
- Django REST Framework
- PostgreSQL
- Django ORM and migrations
- Token-based or session-based authentication appropriate to each client
- OpenAPI documentation, preferably generated with a maintained DRF-compatible package
- Redis and Celery when asynchronous processing is necessary
- A private object-storage service for images and attachments

#### Mobile application
- Flutter
- Dart
- A maintainable architecture separating presentation, application state, domain logic, and data access
- A consistent routing strategy
- Typed API models and centralized API error handling
- Secure token storage and protected local drafts

#### Web application
Inspect the repository before choosing the web strategy.

Prefer an architecture that provides:
- Responsive dashboards and data tables.
- Accessible forms and keyboard navigation.
- Efficient administration and reporting workflows.
- A consistent design language with the mobile application.

Choose Flutter Web if an existing Flutter codebase and its requirements justify sharing the interface. Otherwise, consider a dedicated responsive web frontend while retaining Flutter for mobile.

Do not create unnecessary duplicate applications or introduce additional frameworks without a clear reason.

#### Engineering standards
- Use supported, compatible dependency versions.
- Pin or constrain dependencies appropriately.
- Separate development, testing, staging, and production configuration.
- Never commit credentials, private keys, payment secrets, or real patient data.
- Use environment variables and provide a complete `.env.example`.
- Add automated quality checks and CI configuration where practical.

---

### 6. USER ROLES AND AUTHORIZATION

Implement a flexible role-based and institution-scoped permission system.

Required roles:

1. Independent surgeon.
2. Trainee or medical resident.
3. Supervising surgeon.
4. Examiner.
5. Department or service manager.
6. Institution administrator.
7. Verified equipment supplier.
8. Authorized equipment buyer.
9. Platform administrator.

Users may have multiple roles and affiliations.

Implement the following requirements:

- Every protected operation must be authorized on the backend.
- Permissions must consider the user, role, institution, resource ownership, and resource status.
- Users must not gain access to another institution's private records merely by changing a URL or API identifier.
- Suppliers must never access surgical records.
- Platform administrators must not receive unrestricted medical-content access by default.
- Sensitive administrative access must be justified, restricted, and auditable.
- Disabled accounts must lose access according to the session-revocation policy.
- Use secure password hashing and appropriate account recovery.
- Support stronger authentication for privileged accounts.
- Avoid using a professional or academic registration number as the sole authentication credential.

Create automated authorization tests for both permitted and denied operations.

---

### 7. SURGICAL LOGBOOK MODULE

Implement a complete intervention management workflow.

Each surgical record should support, where applicable:

- Unique record reference.
- Procedure date and relevant timestamps.
- Institution and department.
- Surgical specialty.
- Procedure category or name.
- Pseudonymized patient reference.
- Authorized participating professionals.
- Participant roles: primary operator, assistant, or observer.
- Preoperative indication and diagnosis where appropriate.
- Procedure summary and relevant operative details.
- Complications and postoperative information when available and authorized.
- Training objectives or competency links.
- Attachments and images.
- Author and creation metadata.
- Review and validation history.
- Versioned notes and modification history.

Allow users to create drafts, edit authorized records, search, filter, and submit records for review.

Provide filters for date range, institution, specialty, participant role, record status, and other authorized fields.

Never expose inaccessible records through search results, autocomplete, pagination, exports, or API error messages.

#### Record lifecycle

Implement explicit state transitions:

- Draft.
- Submitted.
- Under review, if required.
- Approved.
- Returned for correction.
- Archived, subject to retention rules.

Define valid transitions and enforce them on the backend.

A rejected record must include a reason.

A trainee must not approve their own record when independent approval is required.

Modifications after approval must create a traceable version or correction event and trigger re-review when appropriate.

Do not silently overwrite approved clinical or educational records.

Avoid permanent deletion of records that must be retained for audit or institutional obligations.

---

### 8. PATIENT PRIVACY AND PSEUDONYMIZATION

The surgical logbook must use pseudonymized patient references instead of full patient names in ordinary workflows.

Implement:

- A patient-reference entity with a unique pseudonymous code within the appropriate institutional scope.
- Separation between the pseudonymous reference and any re-identification mapping.
- Strict access controls for any mapping that links the reference to an official hospital record.
- Protection against accidental exposure of patient identifiers in notes, filenames, attachments, logs, exports, and voice transcripts.
- A configurable data-retention policy.
- Auditing of sensitive access.
- Secure deletion or archival procedures when legally and institutionally permitted.

Do not derive patient codes directly from names, phone numbers, birth dates, or other identifying information.

Do not invent patient information.

All seed and demo data must be synthetic and clearly identified as fictional.

The application must not become a parallel official medical record system without explicit institutional authorization and a separate compliance review.

---

### 9. VOICE DICTATION AND TEXT ENTRY

Users must be able to document procedures by typing or dictating.

Implement a transcription provider abstraction so the platform can support a compatible local engine or an approved external provider.

Required workflow:

1. User starts dictation.
2. The application records or captures speech according to the selected implementation.
3. Audio is processed by the configured transcription service.
4. The transcript appears in an editable field.
5. The application clearly reports transcription failures or uncertainty when available.
6. The user corrects and reviews the transcript.
7. The user saves a draft or submits the record explicitly.

Requirements:

- Support the languages actually selected for the project.
- Handle permission denial, microphone errors, timeouts, network loss, and provider failure.
- Do not assume that transcription is medically accurate.
- Never automatically approve or submit a record because transcription has completed.
- Do not retain raw audio indefinitely.
- Provide a configurable audio-retention policy and clear user feedback.
- Evaluate privacy and contractual conditions before sending clinical speech to an external provider.
- Allow manual text entry if voice functionality is unavailable.

Provide a working development implementation or clearly isolated mock transcription adapter when real provider credentials are unavailable. Never present simulated transcription as a real external-service result.

---

### 10. IMAGES AND ATTACHMENTS

Implement secure attachment handling.

Required features:
- Upload permitted image and document formats.
- Enforce file-size limits and configurable file-type allowlists.
- Validate file content instead of trusting filenames or declared MIME types.
- Scan files where suitable scanning infrastructure is available.
- Store files in private storage.
- Use short-lived authorized download links where appropriate.
- Prevent public access to clinical attachments.
- Record uploader, timestamp, resource association, and applicable authorization metadata.
- Apply a configurable retention policy.
- Protect against path traversal, unsafe file processing, and malicious uploads.
- Remove unnecessary metadata from images where appropriate and safe.
- Avoid logging sensitive file contents or public URLs.

Do not claim that a file has been medically approved merely because it has been successfully uploaded.

---

### 11. TRAINING, PLACEMENTS, AND COMPETENCY ASSESSMENTS

Implement the complete educational workflow.

#### Training placements
- Assign trainees to institutions, departments, supervisors, and training periods.
- Track active, completed, and cancelled placements.
- Support placement objectives and expected competencies.
- Prevent invalid or contradictory assignments according to configured rules.

#### Competencies
- Maintain a configurable competency catalog.
- Define evaluation criteria and rubric versions.
- Associate competencies with procedures, placements, and assessments where appropriate.
- Keep quantitative procedure counts separate from qualitative competency ratings.

#### Examiner workflow
- Assign authorized examiners to records or trainees.
- Allow examiners to review authorized records.
- Record scores, feedback, review decisions, and timestamps.
- Support approval, rejection, and requests for correction.
- Prevent unauthorized self-approval.
- Preserve historical assessments when rubrics change.

#### Progress tracking
Display:
- Procedures performed.
- Procedures assisted.
- Procedures observed.
- Records awaiting review.
- Approved and rejected records.
- Competency progress.
- Placement completion status.

Do not automatically declare a trainee competent solely because a numerical procedure threshold has been reached.

---

### 12. REPORTS AND EXPORTS

Implement real reporting based on database records.

Required reports:
- Individual surgical logbook.
- Activity by date range.
- Activity by specialty and institution.
- Procedures grouped by participation role.
- Trainee progress report.
- Competency assessment report.
- Examiner review report.
- Placement completion report.
- Institution-level aggregated report.
- Marketplace sales and order reports for authorized commercial users.

Support suitable PDF and CSV/XLSX exports.

Requirements:
- Enforce permissions when generating and downloading reports.
- Avoid exposing patient identifiers in ordinary reports.
- Use aggregation or pseudonymization when detailed records are unnecessary.
- Record the requester and generation status.
- Handle large exports asynchronously where necessary.
- Protect temporary export files and expire download links.
- Prevent formula injection in CSV/XLSX exports.
- Provide clear error states for failed report generation.

Do not generate misleading statistics from missing or unapproved data.

---

### 13. SURGICAL EQUIPMENT MARKETPLACE

Implement a functional marketplace, not merely a product catalog.

#### Supplier management
- Supplier registration and profile.
- Business verification status.
- Authorized product categories.
- Supplier contact and commercial information.
- Product listing approval.
- Supplier suspension and complaint handling.

Do not allow suppliers to sell restricted or unapproved products without the required checks.

#### Product catalog
Each product should support:
- Name and description.
- Category.
- Supplier.
- Product reference or SKU.
- Price and currency.
- Available quantity.
- Product images.
- Relevant specifications.
- Applicable regulatory or conformity documentation where required.
- Availability and publication status.

Do not invent regulatory approvals or certifications.

#### Inventory
- Track available and reserved quantities where applicable.
- Prevent overselling through appropriate database transactions and concurrency controls.
- Record inventory changes.
- Define stock-release rules for expired or cancelled reservations.
- Do not permit negative inventory unless a deliberately approved business rule supports backorders.

#### Shopping cart
- Add, update, and remove items.
- Validate quantities and product availability.
- Calculate subtotals, taxes, shipping, discounts, and totals according to configured rules.
- Display the currency explicitly.
- Revalidate prices and inventory during checkout.

#### Orders
- Create unique order references.
- Persist order-item snapshots of product descriptions, quantities, unit prices, currencies, and applicable charges.
- Track order status.
- Support cancellation where permitted.
- Support multiple suppliers and shipments if the marketplace model requires them.
- Maintain a complete order history.
- Provide buyer and supplier views with appropriate permissions.

#### Payment integration
Implement a provider abstraction for payments.

The system must support the lifecycle of payment initiation, pending status, verified success, failure, cancellation, refund, and reconciliation.

Security requirements:
- Never store full card numbers or card security codes.
- Verify payment webhooks and provider signatures.
- Use idempotency keys or equivalent mechanisms to prevent duplicate processing.
- Match provider references, amounts, and currencies against the expected transaction.
- Do not mark an order paid based solely on a browser redirect.
- Do not trust client-submitted payment status.
- Persist payment events for reconciliation.
- Protect against duplicate refunds and invalid state transitions.
- Define how inventory is reserved and released when payments fail or expire.

If real payment credentials are unavailable, implement a clearly isolated sandbox or mock provider for automated tests and development only. Production must refuse to treat mock payment results as real money movement.

Select the actual provider only after confirming its current availability in the target country, supported currencies, fees, merchant requirements, and seller payout capabilities.

#### Shipping, refunds, and disputes
- Record shipping address information only where necessary.
- Support shipment references and tracking statuses.
- Implement order cancellation rules.
- Implement refund requests and refund status tracking.
- Support disputes between buyers and suppliers.
- Preserve evidence and status changes.
- Define administrator intervention permissions.
- Provide a clear audit trail for financial operations.

Do not implement a fake payment integration that merely displays a successful checkout screen.

---

### 14. NOTIFICATIONS

Implement notifications for:
- Record submission.
- Review assignment.
- Approval or rejection.
- Requested corrections.
- Upcoming placement milestones where configured.
- Competency review updates.
- Order confirmation.
- Payment status changes.
- Shipment updates.
- Refund and dispute updates.

Support an in-app notification center.

Email and push notifications may be added through provider abstractions.

Do not include patient names, detailed clinical notes, payment secrets, or other sensitive information in notification previews.

Notifications must not be treated as the authoritative record of a payment or clinical approval.

---

### 15. REQUIRED APPLICATION SCREENS

Implement all screens required for a complete user journey.

#### Shared screens
- Login.
- Registration or invitation acceptance.
- Password recovery.
- Account verification where required.
- Profile.
- Security settings.
- Notification center.
- Access-denied page.
- Not-found page.
- Error and maintenance states.

#### Surgical workspace
- Dashboard.
- Surgical logbook list.
- Create intervention.
- Edit draft.
- Intervention details.
- Voice dictation interface.
- Attachment management.
- Submission confirmation.
- Review history.
- Search and filtering.
- Individual reports.

#### Training workspace
- Trainee directory.
- Trainee profile.
- Training placement list and details.
- Supervisor assignments.
- Competency catalog.
- Assessment form.
- Examiner review queue.
- Assessment history.
- Progress dashboard.
- Placement completion report.

#### Institution administration
- Institution profile.
- Department and specialty management.
- User and membership management.
- Role and permission management.
- Examiner assignments.
- Configurable review rules.
- Institution-level reports.
- Audit event viewer for authorized administrators.

#### Marketplace
- Marketplace home.
- Product catalog.
- Product details.
- Category and search results.
- Supplier profile.
- Supplier verification status.
- Cart.
- Checkout.
- Payment status.
- Order confirmation.
- Buyer order history.
- Supplier dashboard.
- Product management.
- Inventory management.
- Supplier order management.
- Shipment management.
- Refund requests.
- Dispute management.

#### Platform administration
- System dashboard.
- User and institution administration.
- Supplier verification queue.
- Product moderation.
- Incident and complaint management.
- Audit and operational monitoring.
- System configuration.

Do not create navigation items that lead to empty pages or buttons with no meaningful action.

Every screen must have suitable loading, empty, success, validation, and failure states.

---

### 16. UI/UX DESIGN REQUIREMENTS

Build STAR as a professional healthcare technology product.

Visual direction:
- Clean, modern, restrained, and trustworthy.
- Strong information hierarchy.
- High readability for clinical documentation.
- Consistent spacing, typography, and component behavior.
- Responsive layouts for desktop, tablet, and mobile.
- Accessible forms and understandable error messages.
- Clear distinction between medical, educational, administrative, and commercial workspaces.
- Consistent status indicators for drafts, pending reviews, approvals, failed payments, and shipments.

Avoid:
- Excessive gradients.
- Decorative animations that distract from clinical tasks.
- Overcrowded dashboards.
- Unreadable data tables.
- Fake statistics presented as real data.
- Unnecessary animations during documentation.
- Buttons without implemented actions.
- Excessive modal dialogs for routine operations.

Use reusable components, consistent design tokens, and accessible color contrast.

Ensure keyboard navigation, visible focus states, descriptive labels, and screen-reader-compatible controls.

If an existing design specification is provided, read and follow it. Do not invent a conflicting visual identity.

---

### 17. DATA MODEL AND DATABASE DESIGN

Design a normalized relational model using PostgreSQL.

Include, at minimum, the following domain entities:

Identity and organization:
- User.
- ProfessionalProfile.
- Institution.
- InstitutionMembership.
- Department.
- Specialty.

Surgical documentation:
- PatientReference.
- SurgicalProcedure.
- ProcedureParticipant.
- ProcedureNoteVersion.
- Attachment.
- ClinicalConsentRecord or applicable authorization evidence.
- ReviewDecision.
- AuditEvent.

Education:
- TrainingPlacement.
- Competency.
- CompetencyRubricVersion.
- Assessment.
- ExaminerAssignment.

Reporting:
- ReportJob.
- ExportArtifact, if required.

Marketplace:
- SupplierProfile.
- ProductCategory.
- Product.
- Inventory.
- InventoryMovement.
- Cart.
- CartItem.
- Order.
- OrderItem.
- Payment.
- PaymentEvent.
- Refund.
- Shipment.
- Dispute.

Supporting entities:
- Notification.
- NotificationPreference.
- IdempotencyRecord where appropriate.

Define:
- Primary keys and foreign keys.
- Unique constraints.
- Indexes for common filters.
- Appropriate decimal monetary fields.
- Explicit currency codes.
- Timestamps and timezone conventions.
- Status enums and permitted transitions.
- Soft deletion only where justified.
- Retention and archival policies.
- Database transaction boundaries.
- Institution-scoped uniqueness where required.

Do not duplicate authoritative information unnecessarily.

Use immutable historical snapshots for confirmed order prices and other business facts that must not change retroactively.

Do not put large attachment binaries directly into ordinary relational tables without a compelling documented reason.

Create and maintain:
1. An entity-relationship diagram.
2. A documented data dictionary.
3. Django models and migrations.
4. A clear explanation of relationships and constraints.

---

### 18. API DESIGN

Create a versioned REST API with consistent naming and behavior.

Suggested endpoint groups:

- `/api/v1/auth/`
- `/api/v1/users/`
- `/api/v1/institutions/`
- `/api/v1/departments/`
- `/api/v1/specialties/`
- `/api/v1/patients/references/`
- `/api/v1/procedures/`
- `/api/v1/procedures/{id}/participants/`
- `/api/v1/procedures/{id}/attachments/`
- `/api/v1/procedures/{id}/submit/`
- `/api/v1/procedures/{id}/reviews/`
- `/api/v1/training/placements/`
- `/api/v1/competencies/`
- `/api/v1/assessments/`
- `/api/v1/reports/`
- `/api/v1/suppliers/`
- `/api/v1/products/`
- `/api/v1/cart/`
- `/api/v1/orders/`
- `/api/v1/payments/`
- `/api/v1/refunds/`
- `/api/v1/shipments/`
- `/api/v1/disputes/`
- `/api/v1/notifications/`
- `/api/v1/audit/`

These paths are suggestions. Adapt them to a consistent and maintainable API design.

Implement:
- Request validation.
- Response serialization.
- Pagination.
- Filtering and search.
- Appropriate status codes.
- Consistent error responses.
- Permission checks.
- API documentation.
- Rate limiting for sensitive endpoints.
- Safe upload handling.
- Authentication and token revocation policies.
- Transaction-safe status transitions.
- Idempotent payment event handling.

Do not expose unrestricted Django model serialization.

Document required fields, optional fields, validation constraints, authorization rules, and representative error responses.

---

### 19. SECURITY ENGINEERING

Treat security as a core product requirement.

Implement and test:
- Secure password hashing.
- Backend-enforced permissions.
- Institution-level data isolation.
- Protection against insecure direct object references.
- Input validation and output encoding.
- CSRF protection where applicable.
- Secure session and token handling.
- Login and sensitive-operation rate limits.
- Safe file uploads.
- Secret management.
- HTTPS deployment configuration.
- CORS restrictions where relevant.
- Database access controls.
- Protected audit logs.
- Dependency vulnerability checks where available.
- Secure error messages.
- Backup protection and restoration tests.
- Secure handling of payment webhooks.
- Protection against duplicate financial operations.
- Safe handling of exported files.
- Explicit privacy and retention controls.

Never hardcode secrets.

Do not log passwords, authentication tokens, payment credentials, raw clinical transcripts, or unnecessary patient identifiers.

Use synthetic fixtures in development and automated tests.

Do not claim that STAR is legally compliant or certified merely because technical controls exist. Require a separate review of applicable legal, institutional, and contractual obligations before production deployment.

---

### 20. TESTING REQUIREMENTS

Write real automated tests rather than relying only on manual inspection.

#### Backend tests
- Authentication and account permissions.
- Institution-level isolation.
- Surgical record creation and modification.
- Record lifecycle transitions.
- Version history and audit events.
- Pseudonymous patient references.
- Attachment authorization.
- Training placements and examiner assignments.
- Competency assessments.
- Report permissions and exports.
- Supplier verification.
- Product availability and inventory concurrency.
- Cart calculations.
- Order creation.
- Payment webhook verification.
- Duplicate payment event handling.
- Refund state transitions.
- Shipment and dispute workflows.
- Notification permissions.

#### Frontend tests
- Authentication flows.
- Form validation.
- Navigation.
- Loading and error states.
- Surgical record creation.
- Voice-provider failure handling.
- Examiner review flow.
- Report generation requests.
- Product browsing and cart behavior.
- Checkout failure and success states.
- Responsive layouts and accessibility basics.

#### Integration and end-to-end tests
At minimum, test these complete scenarios:

**Scenario A — Surgical logbook**
A surgeon signs in, creates a record, edits the draft, attaches an authorized file, submits it, and reviews its status.

**Scenario B — Trainee assessment**
A trainee submits an intervention. An authorized examiner reviews it, requests corrections, receives the revised record, and approves it. The audit history remains consistent.

**Scenario C — Unauthorized access**
A user attempts to access another institution's private record by changing a URL or API identifier. The request is denied and no sensitive content is disclosed.

**Scenario D — Marketplace order**
A buyer selects an available product, checks out, receives a pending payment status, and receives a confirmed status only after a verified payment event.

**Scenario E — Duplicate payment notification**
The same valid provider event is delivered twice. The system does not duplicate the financial effect or fulfill the order twice.

**Scenario F — Failed payment**
A payment fails or expires. The order and inventory follow the defined cancellation and stock-release policy.

**Scenario G — Reporting**
A user generates an authorized report and cannot export records outside their permitted scope.

**Scenario H — Voice transcription failure**
The transcription service becomes unavailable. The application reports the failure and allows the user to continue manually without losing the draft.

Use isolated test databases and mocked external services. Never run financial tests against real payment accounts by default.

---

### 21. DEVELOPMENT DATA AND DEMONSTRATION MODE

Provide a safe and useful demonstration environment.

Create:
- Synthetic institutions.
- Fictional professional accounts.
- Fictional trainees and examiners.
- Fictional surgical records.
- Synthetic competency assessments.
- Fictional suppliers and products.
- Test orders and simulated payment events.

All records must be clearly identified as demonstration data.

Never include actual patient information, real hospital credentials, real payment credentials, or copied confidential records in fixtures.

Document how to create an initial administrator account securely.

Do not commit a universal production password.

---

### 22. DOCUMENTATION DELIVERABLES

Provide a complete documentation package.

Required files should include, where appropriate:

- `README.md` — project overview, features, architecture, prerequisites, installation, startup, testing, and troubleshooting.
- `.env.example` — every required environment variable with safe placeholder values.
- `docs/architecture.md` — architecture and technology decisions.
- `docs/requirements.md` — functional and non-functional requirements.
- `docs/business-rules.md` — lifecycle, validation, and marketplace rules.
- `docs/data-dictionary.md` — entities, attributes, relationships, and constraints.
- `docs/api.md` or generated OpenAPI documentation.
- `docs/security.md` — threat considerations, access control, secret management, and security testing.
- `docs/privacy-and-retention.md` — pseudonymization, retention, attachments, voice, and exports.
- `docs/deployment.md` — staging and production deployment.
- `docs/backup-and-recovery.md` — backup, restoration, and recovery procedures.
- `docs/testing.md` — test commands and coverage.
- `docs/decisions.md` — assumptions, unresolved decisions, and architecture decisions.
- `docs/marketplace.md` — provider integration, order lifecycle, and payment reconciliation.
- UML use-case and entity-relationship diagrams.

Provide development and deployment instructions appropriate to the actual repository.

Include migrations and a reproducible development setup.

If Docker is appropriate, provide a development Docker Compose configuration with safe defaults, health checks where practical, and documented service dependencies.

Never place production secrets in Docker files or example configuration.

---

### 23. DEPLOYMENT AND OPERATIONS

Prepare the project for deployment without pretending that deployment has already occurred.

Provide:
- Environment-specific settings.
- Database migration instructions.
- Static and uploaded file handling.
- HTTPS and trusted-host configuration.
- Production-safe debug settings.
- Secure secret configuration.
- Health and readiness checks.
- Structured application logging.
- Error monitoring integration points.
- Backup scheduling guidance.
- Database and file restoration instructions.
- Dependency update procedures.
- Deployment and rollback instructions.
- Worker and scheduler configuration where required.

Separate medical application logs from operational metrics and avoid including unnecessary sensitive information.

The deployment plan must explicitly identify the intended data-hosting location and the legal, institutional, and contractual review required for that choice.

---

### 24. PERFORMANCE AND RELIABILITY

Optimize the system for real workloads rather than synthetic demonstrations.

Implement:
- Database indexes for common filters.
- Pagination on potentially large lists.
- Appropriate query optimization.
- Transaction-safe inventory and payment operations.
- Background jobs for expensive reports.
- Timeouts and retries for external services.
- Bounded retry behavior for payment integrations.
- Clear synchronization states on mobile.
- Conflict handling for offline drafts.
- Monitoring for failed background jobs.
- Resource limits for file uploads and exports.

Do not introduce caching that risks exposing one user's private records to another user.

Define and test performance targets after the expected number of users, institutions, and concurrent requests has been established.

---

### 25. PRIORITIZED IMPLEMENTATION MILESTONES

Build the application in the following order.

**Milestone 1 — Project foundations**
- Repository structure.
- Database configuration.
- Authentication.
- User profiles and roles.
- Institutions and memberships.
- Core security and audit infrastructure.
- Development environment and CI.

**Milestone 2 — Surgical documentation**
- Surgical records.
- Participant assignments.
- Text entry.
- Record versioning and lifecycle.
- Attachments.
- Search and filtering.

**Milestone 3 — Voice and education**
- Transcription adapter.
- Trainee placements.
- Supervisors and examiners.
- Competency catalog.
- Assessment workflow.
- Notifications.

**Milestone 4 — Reporting**
- Dashboards.
- Individual reports.
- Institutional aggregates.
- PDF and CSV/XLSX exports.
- Export security.

**Milestone 5 — Marketplace**
- Supplier verification.
- Products and inventory.
- Cart and checkout.
- Orders and payment abstraction.
- Refunds and shipments.
- Disputes and reconciliation.

**Milestone 6 — Complete interfaces**
- Implement all web and mobile screens.
- Connect every form and action to the backend.
- Add responsive layouts and accessible states.
- Verify navigation and authorization behavior.

**Milestone 7 — Quality and delivery**
- Automated tests.
- Security checks.
- Database migration verification.
- Performance testing.
- Deployment documentation.
- Final acceptance report.

Do not sacrifice critical security or data integrity to make a milestone appear complete.

If time or execution limits prevent full completion, finish the most important end-to-end workflows first and document precisely what remains unfinished.

---

### 26. DEFINITION OF DONE

STAR is not considered complete merely because the application starts.

A feature is complete only when:
- Its database model and migration exist where required.
- Its backend logic is implemented.
- Its permissions are enforced on the server.
- Its UI is connected to real application state and APIs.
- Its loading, empty, success, and error states work.
- Its business rules are enforced.
- Its tests pass.
- Its documentation is updated.
- Its implementation does not expose secrets or real patient data.
- Its functionality has been verified in the appropriate environment.

The overall project is ready for a controlled pilot when:
- The principal surgical documentation workflow works end to end.
- Trainee and examiner workflows work.
- Reports respect permissions.
- Marketplace orders and payment state transitions are verified in a sandbox.
- Critical security tests pass.
- Backup restoration has been demonstrated.
- All required environment variables are documented.
- Known limitations and unresolved legal or institutional decisions are clearly recorded.

Do not describe a feature as completed when only its UI or endpoint placeholder exists.

Do not claim production readiness without evidence.

---

### 27. FINAL EXECUTION INSTRUCTIONS

Start by inspecting the repository and identifying the actual state of the project.

Then:
1. Summarize the existing architecture.
2. Identify gaps relative to this specification.
3. Produce a prioritized implementation plan.
4. Define the core data model and security boundaries.
5. Implement the application incrementally.
6. Run migrations, tests, static checks, and available build commands.
7. Fix discovered issues.
8. Update the documentation.
9. Provide a final implementation report.

The final report must distinguish:
- Features fully implemented and tested.
- Features implemented but not fully verified.
- Features requiring external credentials or third-party approval.
- Remaining defects.
- Remaining legal, institutional, or operational decisions.
- Exact commands for running, testing, and deploying the project.

Be transparent about failures and limitations.

Use sensible defaults for reversible decisions, but never invent legal approval, successful payments, medical validation, external provider availability, or production deployment.

**Your ultimate objective is to deliver STAR as a coherent, secure, maintainable, tested, and deployable surgical logbook and marketplace platform—not merely a demonstration of what the platform might look like.**