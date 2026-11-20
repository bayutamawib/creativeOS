# CREATIVE OS — Database Design

**Document:** Database Design  
**Version:** 1.0  
**Status:** Proposed  
**Database:** PostgreSQL  
**Backend:** Python + FastAPI

---

## 1. Purpose

This document defines the database structure for CREATIVE OS, an AI-powered creative agency operations platform.

It serves as the source of truth for:
- Database entities and relationships.
- Data ownership and client isolation.
- Primary and foreign key relationships.
- Data lifecycle and status management.
- Database constraints and indexing.
- Storage of AI-generated outputs and workflow execution records.

The database must support the complete MVP journey:

Client inquiry → Lead management → Client onboarding → Creative brief → AI generation → Human review → Task assignment → Client approval → Reporting.

The schema should remain practical for a single creative agency while allowing future expansion.

## 2. Database Design Principles

### 2.1 Relational data model

PostgreSQL is the primary source of truth for application data.

Use relational tables for structured business entities, including clients, projects, briefs, content, tasks, approvals, and reports.

Use JSONB only for flexible or variable data, such as:
- AI generation parameters.
- AI output metadata.
- External integration payloads.
- Workflow execution metadata.
- Configurable report data.

Do not use JSONB as a substitute for normal relational tables when the data has clear relationships and requires frequent querying.

### 2.2 Client data isolation

Every client-owned business record must be associated with a `client_id`, either directly or through a validated parent relationship.

A client user must only access records belonging to their own client account.

The backend must enforce authorization on every relevant API request.

Never rely exclusively on frontend route restrictions to protect client data.

### 2.3 Agency-wide access

Agency users may access multiple clients depending on their assigned role and permissions.

The MVP uses a single-agency operating model. It does not require SaaS billing, multiple agency tenants, or subscription management.

### 2.4 Human approval

AI-generated content must remain in draft or review status until an authorized agency user approves it.

Client approval is a separate business action and must be recorded independently.

### 2.5 Auditability

Important business actions must be traceable through activity logs.

AI generation and automation executions must have their own records so the agency can investigate failures and review generated outputs.

---

## 3. Entity Overview

The database is divided into eight logical domains.

| Domain | Main entities | Purpose |
|---|---|---|
| Identity & Access | users, agency_memberships, client_memberships | Authentication and authorization |
| CRM | leads, clients | Inquiry and client onboarding |
| Project Management | projects, project_members, milestones, tasks, task_assignees | Delivery and execution |
| Creative Operations | briefs, file_assets, content_items, content_revisions | Creative production |
| Approval & Feedback | content_approvals, content_feedback | Internal and client review |
| AI Operations | ai_generations | AI generation traceability |
| Automation | workflow_runs, notifications | Workflow execution and notifications |
| Reporting & Audit | reports, activity_logs | Performance visibility and accountability |

## 4. Database Entities

### 4.1 Identity and Access Management

#### `users`

Stores all authenticated platform users, including agency staff and client portal users.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Unique user identifier |
| email | VARCHAR(255), UNIQUE | Login email |
| password_hash | TEXT, nullable | Hashed password if using local authentication |
| full_name | VARCHAR(150) | User's full name |
| phone | VARCHAR(30), nullable | Contact number |
| avatar_url | TEXT, nullable | Profile image reference |
| is_active | BOOLEAN | Account status |
| email_verified_at | TIMESTAMPTZ, nullable | Email verification timestamp |
| last_login_at | TIMESTAMPTZ, nullable | Last login timestamp |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

Notes:
- Store password hashes only, never plaintext passwords.
- Email should be normalized before uniqueness validation.
- A user may have an agency membership, a client membership, or both.
- Deactivated users must not be able to authenticate.

#### `agency_memberships`

Defines a user's membership and role within the creative agency.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Membership identifier |
| user_id | UUID, FK → users.id | Agency user |
| role | VARCHAR(30) | Agency role |
| is_active | BOOLEAN | Whether this role currently confers agency access |
| created_at | TIMESTAMPTZ | Creation timestamp |

Allowed roles:
- `admin`
- `agency_manager`
- `team_member`

Constraints:
- Unique combination of `user_id` and `role`.
- A user may have more than one agency role if required.
- Admins may manage all three agency roles. Managers may administer only team_member for another person with no admin or agency_manager membership. Include inactive elevated memberships in the target check. Manager activation/deactivation changes the team membership only. Global users.is_active also governs other memberships and requires Admin authority.
- Once the first active Admin exists, every operation that could remove one (role revoke/deactivate, account disable/delete, bulk operation) must leave an active user with an active admin role. In this single agency, serialize all agency privilege mutations and account status changes on the same transaction-scoped PostgreSQL lock. After acquiring it, re-read actor, target and surviving Admins before writing. Use this path for invitations and their redemption as well. Record actor, target, prior/new role or state and time atomically in activity_logs.

#### `client_memberships`

Connects client portal users to client organizations.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Membership identifier |
| user_id | UUID, FK → users.id | Client portal user |
| client_id | UUID, FK → clients.id | Client organization |
| role | VARCHAR(30) | Client-side role |
| is_active | BOOLEAN | Whether the user may act for this client |
| created_at | TIMESTAMPTZ | Creation timestamp |

Allowed roles:
- `client_admin`
- `client_member`

Constraints:
- Unique combination of `user_id` and `client_id`.
- A client user may belong to more than one client organization.
- Membership must be validated before accessing client-owned records.

#### `project_approval_delegations`

Each grant contains id (UUID PK), client_id, project_id, grantee_membership_id, granted_by_membership_id, granted_at and nullable revoked_at/revoked_by_membership_id. Composite FKs from (project_id, client_id) to projects and from (membership_id, client_id) to client_memberships for both grantee and grantor enforce common ownership. Add the corresponding unique parent keys. Use a partial UNIQUE(project_id, grantee_membership_id) WHERE revoked_at IS NULL. Regrant creates a new row, preserving the basis for earlier decisions.

Only an active client_admin in the owning client can issue or revoke a grant to an active client_member there. An inactive account or membership confers no authority. Close grants when the grantee loses that membership or its eligible role. For automatic invalidation, leave revoked_by_membership_id null and record the initiating actor and reason in the audit log. Re-enabling a client membership requires a fresh grant. Membership changes, revocation and decisions must serialize on the relevant memberships and grant in a consistent order. A committed revocation takes effect on the next decision, even in an existing session.

### 4.2 CRM and Client Management

#### `leads`

Stores prospective clients before they become active clients.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Lead identifier |
| company_name | VARCHAR(200) | Company or brand name |
| contact_name | VARCHAR(150) | Primary contact |
| email | VARCHAR(255) | Contact email |
| phone | VARCHAR(30), nullable | Contact phone |
| industry | VARCHAR(100), nullable | Business industry |
| service_interest | TEXT, nullable | Requested services |
| inquiry_message | TEXT, nullable | Initial inquiry |
| source | VARCHAR(50) | Inquiry source |
| status | VARCHAR(30) | Lead status |
| notes | TEXT, nullable | Internal notes |
| assigned_to | UUID, FK → users.id, nullable | Responsible agency user |
| converted_client_id | UUID, FK → clients.id, nullable | Client created after conversion |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

Allowed statuses:
- `new`
- `contacted`
- `qualified`
- `proposal_sent`
- `converted`
- `rejected`

Possible sources:
- `client_portal`
- `google_forms`
- `manual`
- `referral`
- `other`

Business rules:
- A public inquiry creates a lead, not an authenticated client account.
- Only authorized agency users can convert a lead into a client.
- Conversion creates a client record and links it through `converted_client_id`.
- Preserve the original inquiry data for historical reference.

#### `clients`

Represents a client company or brand working with the agency.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Client identifier |
| company_name | VARCHAR(200) | Registered or operating company name |
| brand_name | VARCHAR(200), nullable | Brand name |
| industry | VARCHAR(100), nullable | Industry |
| website | TEXT, nullable | Website |
| primary_contact_name | VARCHAR(150) | Main contact |
| primary_contact_email | VARCHAR(255) | Main contact email |
| primary_contact_phone | VARCHAR(30), nullable | Main contact phone |
| brand_description | TEXT, nullable | Brand overview |
| brand_guidelines | JSONB, nullable | Structured brand guidelines |
| status | VARCHAR(30) | Client status |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

Allowed statuses:
- `active`
- `inactive`
- `archived`

`brand_guidelines` may contain:
- Brand voice.
- Tone of communication.
- Target audience.
- Preferred terminology.
- Visual direction.
- Content restrictions.
- Brand positioning.

Keep detailed brand documents in file storage and store their references in `file_assets`.

### 4.3 Project Management

#### `projects`

Represents an agency project or campaign for a client.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Project identifier |
| client_id | UUID, FK → clients.id | Project owner |
| name | VARCHAR(200) | Project name |
| description | TEXT, nullable | Project description |
| service_type | VARCHAR(100) | Service category |
| status | VARCHAR(30) | Project status |
| priority | VARCHAR(20) | Project priority |
| start_date | DATE, nullable | Project start date |
| due_date | DATE, nullable | Target completion date |
| budget | NUMERIC(14,2), nullable | Optional project budget |
| created_by | UUID, FK → users.id | Creator |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |
| archived_at | TIMESTAMPTZ, nullable | Archive timestamp |

Allowed statuses:
- `draft`
- `planning`
- `in_progress`
- `in_review`
- `completed`
- `on_hold`
- `cancelled`

Allowed priorities:
- `low`
- `medium`
- `high`
- `urgent`

Rules:
- Every project belongs to exactly one client.
- A project may contain multiple briefs, milestones, tasks, and content items.
- Client users can only access projects belonging to their authorized client memberships.

#### `project_members`

Assigns agency users to projects.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Assignment identifier |
| project_id | UUID, FK → projects.id | Project |
| user_id | UUID, FK → users.id | Agency user |
| project_role | VARCHAR(50), nullable | Project responsibility |
| assigned_at | TIMESTAMPTZ | Assignment timestamp |

Constraints:
- Unique combination of `project_id` and `user_id`.
- Only agency users may be assigned.
- A project may have multiple team members.

#### `milestones`

Tracks important project stages.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Milestone identifier |
| project_id | UUID, FK → projects.id | Parent project |
| name | VARCHAR(200) | Milestone name |
| description | TEXT, nullable | Description |
| due_date | DATE, nullable | Target date |
| status | VARCHAR(30) | Milestone status |
| completed_at | TIMESTAMPTZ, nullable | Completion timestamp |
| created_at | TIMESTAMPTZ | Creation timestamp |

Allowed statuses:
- `pending`
- `in_progress`
- `completed`
- `blocked`

Examples:
- Brief approved.
- Creative direction approved.
- First draft delivered.
- Final content approved.
- Campaign report delivered.

#### `tasks`

Stores internal execution tasks.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Task identifier |
| project_id | UUID, FK → projects.id | Parent project |
| client_id | UUID, FK → clients.id | Denormalized ownership key |
| milestone_id | UUID, FK → milestones.id, nullable | Related milestone |
| title | VARCHAR(200) | Task title |
| description | TEXT, nullable | Task details |
| status | VARCHAR(30) | Task status |
| priority | VARCHAR(20) | Task priority |
| start_date | DATE, nullable | Start date |
| due_date | DATE, nullable | Deadline |
| completed_at | TIMESTAMPTZ, nullable | Completion timestamp |
| created_by | UUID, FK → users.id | Task creator |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

Allowed statuses:
- `todo`
- `in_progress`
- `in_review`
- `completed`
- `blocked`
- `cancelled`

Rules:
- `client_id` must match the parent project's `client_id`.
- Tasks are internal by default.
- Client-facing progress should be exposed through a controlled project progress view, not by exposing all internal task details.
- Internal notes and sensitive operational details must not be returned to client users.

#### `task_assignees`

Allows tasks to be assigned to one or more agency users.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Assignment identifier |
| task_id | UUID, FK → tasks.id | Task |
| user_id | UUID, FK → users.id | Assigned agency user |
| assigned_at | TIMESTAMPTZ | Assignment timestamp |

Constraints:
- Unique combination of `task_id` and `user_id`.
- Only agency users may be assigned.

### 4.4 Creative Operations

#### `briefs`

Stores client creative briefs.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Brief identifier |
| project_id | UUID, FK → projects.id | Related project |
| client_id | UUID, FK → clients.id | Client ownership |
| title | VARCHAR(200) | Brief title |
| objective | TEXT | Campaign or content objective |
| target_audience | TEXT, nullable | Target audience |
| key_message | TEXT, nullable | Main message |
| content_type | VARCHAR(100), nullable | Content format |
| preferred_channels | JSONB, nullable | Intended distribution channels |
| tone_of_voice | TEXT, nullable | Desired tone |
| references | JSONB, nullable | Reference URLs or descriptions |
| restrictions | TEXT, nullable | Content restrictions |
| additional_context | TEXT, nullable | Other information |
| status | VARCHAR(30) | Brief status |
| version | INTEGER | Optimistic lock incremented on each edit or state transition |
| submitted_by | UUID, FK → users.id | Submitting user |
| reviewed_by | UUID, FK → users.id, nullable | Agency reviewer |
| reviewed_at | TIMESTAMPTZ, nullable | Review timestamp |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

Allowed statuses:
- `draft`
- `submitted`
- `under_review`
- `revision_requested`
- `approved`
- `rejected`

Rules:
- A brief must belong to the same client as its parent project.
- Only authorized client users may submit briefs for their client.
- Agency reviewers may request revisions or approve briefs.
- Approved briefs may be used as input to AI generation.

#### `file_assets`

Stores metadata for uploaded or externally stored files.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | File identifier |
| client_id | UUID, FK → clients.id, nullable | Client ownership |
| project_id | UUID, FK → projects.id, nullable | Related project |
| uploaded_by | UUID, FK → users.id | Uploader |
| provider | VARCHAR(30) | Storage provider |
| provider_file_id | TEXT | Provider-side file identifier |
| file_name | VARCHAR(255) | Original file name |
| mime_type | VARCHAR(150) | File MIME type |
| file_size | BIGINT, nullable | Size in bytes |
| category | VARCHAR(50), nullable | File category |
| created_at | TIMESTAMPTZ | Upload timestamp |

Initial provider:
- `google_drive`

Possible categories:
- `brief_attachment`
- `brand_guideline`
- `creative_asset`
- `deliverable`
- `reference`
- `other`

Rules:
- Store Google Drive file IDs, not permanent public sharing URLs as the only reference.
- File access must be checked by the backend.
- Do not assume that knowing a provider file ID grants permission to access the file.
- Validate file type and size during upload.
- Client users must not be able to access files belonging to other clients.

#### `content_items`

Represents a creative deliverable, such as a social media post, caption, campaign concept, or content plan.

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Content identifier |
| project_id | UUID, FK → projects.id | Related project |
| client_id | UUID, FK → clients.id | Client ownership |
| brief_id | UUID, FK → briefs.id, nullable | Source brief |
| title | VARCHAR(200) | Content title |
| content_type | VARCHAR(100) | Content format |
| channel | VARCHAR(100), nullable | Intended channel |
| current_revision_id | UUID, nullable | Current revision |
| status | VARCHAR(30) | Current review stage |
| created_at / updated_at | TIMESTAMPTZ | Creation / last change |

Stages are `draft`, `internal_review`, `client_review`, `revision_requested`, `approved`, and `rejected`. In one transaction insert the item with a null pointer, insert revision 1, then set the pointer. Use a composite FK from (item ID, current revision ID) to (content item ID, revision ID). Serialize revision creation and approval for the item. Approve & Release records an approved internal-stage row and a pending client-stage row for the exact revision in the same transaction. Every committed deliverable has a current revision.

#### `content_revisions`

Immutable rows with UUID PK, content_item_id FK, revision_number, structured content JSONB, created_by FK, created_at and optional source_generation_id FK. UNIQUE(content_item_id, revision_number) and UNIQUE(content_item_id, id). Each accepted edit appends a revision and returns the item to draft. A generation can supply suggested copy. A human saves it as a revision.

#### `content_approvals` and `content_feedback`

Approvals have UUID PK, content_item_id, revision_id (same-item composite FK), stage (internal or client), decision, requested_at, decided_by FK, decided_at and comments. UNIQUE(revision_id, stage). Submission creates a pending row. Pending has null decided_by and decided_at. A human decision (approved, rejected, revision_requested) requires both. Creating a newer revision closes any pending review as superseded without attributing a human decision. Completed historical decisions survive. The client-stage row proves that the exact revision was released to the owning client.

Feedback has UUID PK, the same item/revision FK, author_id FK, visibility (internal or client_visible), message and created_at. Client views require a released revision and client-visible feedback. A revision request writes its required feedback and decision together. For a client decision record the deciding client membership and, for a delegate, the exact delegation ID. Under the same transaction revalidate active account, membership, owning project, authority, current revision and pending client-stage request. A conditional pending-to-decided update admits one winner. Commit decision, audit entry, feedback where required and outbox event together. A losing or duplicate request adds none of these effects.

#### `brief_snapshots`, `creative_proposals` and attachments

Approval inserts an immutable brief_snapshots row with UUID PK, brief_id FK, version (the approved brief version), approved_by FK, approved_at, structured approved fields, attachment IDs and brand context used. UNIQUE(brief_id, version). A later edit of approved material starts a new draft requiring resubmission. Keep existing snapshots and descendants. Serialize edits and approval on the brief. Generation captures snapshot_id and the actual authorized inputs at enqueue time.

Persist a separate creative_proposals row for each validated direction or plan item. Fields are id, generation_id FK, item_index, kind (direction or plan_item), immutable payload, decision (pending, approved, rejected), decided_by FK and decided_at. UNIQUE(generation_id, item_index). Record the selected direction on the plan generation and the plan proposal on any converted content item (unique). Derive project and snapshot through generation. A human approves a plan item to select it for production. Create deterministic tasks from its template in that transaction. Add source_proposal_id and template_step to generated tasks with UNIQUE(source_proposal_id, template_step). Manual tasks have neither field.

Use brief/file and revision/file link tables with unique parent/file pairs. Restrict both ends to the same client and compatible project. File assets carry explicit internal or client_visible visibility. Agency-only files may have null client_id. Files attached to staged deliverables or report exports inherit the release requirement of the revision or published report, including for direct downloads. A snapshot retains its attachment references. Storage deletion must preserve referenced versions. Use provider `local` for the development adapter. Store requested item count and target timeline on the brief when supplied by the guided form. Milestones have a separate client_visible flag, initially false, for explicitly released milestones.

### 4.5 Authentication and intake support

- **agency_invitations** — UUID PK, normalized email, agency role, invited_by user FK, unique token digest, expiry, created_at and nullable accepted_at/revoked_at. Use the same single-use redemption rules as client invitations, within the agency role guard in §4.1. Revalidate inviter authority and the target account on redemption. A manager invitation can confer only team_member.
- **client_invitations** — UUID PK, client_id FK, normalized email, client role, invited_by FK, unique token_digest, expires_at, accepted_at, revoked_at, created_at. Invitation issuance and acceptance are separate from lead conversion. Bind acceptance to the invited email and role. For an existing account require its authenticated identity. Consume once and create or reuse its membership in one transaction, including concurrent redemption. Store only a digest of the high-entropy invitation token.
- **sessions / password_reset_tokens** — User FK, unique opaque token digest, expiry, revocation or consumption timestamp. Renewal rotates the session. Reset is expiring and single-use. Inactive accounts cannot use existing sessions.
- **External submissions** — Unique (source, source_submission_id) receipt with request fingerprint and resulting lead or brief reference, committed with the business record. Return the recorded result on matching replay and reject a changed payload. A brief requires verified submitter membership in the target project’s client organization.

### 4.6 AI and workflow execution

All tables below use UUID identifiers. Business writes and their corresponding outbox events share one PostgreSQL transaction.

| Table | Required contract |
|---|---|
| ai_generations | Project/client ownership, optional brief snapshot, content revision, direction proposal or report FK as appropriate, generation_type, input_snapshot, prompt_version, provider, model, parameters, validated output JSONB, status, timestamps, tokens, latency, safe error classification. Use the five AI execution states in AI §6.1. Exactly one of requested_by (user FK) and service_identity (authenticated service name). Record originating event/run where applicable. Unique (requester scope, operation, idempotency key) with request fingerprint. Include retry count, next attempt and expiring worker claim. |
| outbox_events | Use workflow §18.1 columns and states. id is the stable event_id. Persist claim token and expiry for restart recovery. Index (status, next_attempt_at). |
| processed_events | event_id, consumer_name, processed_at, result_status and result reference. UNIQUE(event_id, consumer_name). Persist receipt and local side effect together. Record independently retryable workflow steps separately. |
| workflow_runs | workflow_name (WF-A through WF-D), workflow_version, trigger_type, event or schedule key, resource reference, n8n execution ID, status (pending, running, completed, failed, cancelled), attempt, started_at, completed_at, safe error and metadata. Unique logical trigger per workflow and attempt. |
| notifications | Recipient user FK, client scope when applicable, related resource, type, channel, deduplication key, delivery status (pending, sending, delivered, failed or uncertain), claim expiry, timestamps and read_at. Reserve each send by an atomic claim. An expired claim after a possible send requires reconciliation. UNIQUE(recipient_id, channel, deduplication_key). Derive keys from event and action, or task, reminder type and agency-local date. Record an uncertain external send for investigation if the provider cannot confirm it. |

For worker claims, use a short transaction to claim an eligible row. Guard completion by the claim token so an expired worker cannot overwrite its successor. Bound retries. Do external I/O outside the transaction. Correlation IDs convey provenance and never authorize a request.

Intake, notification and reminder actions derive recipients from backend records. Check active membership, project assignment and release visibility again before returning data or delivering. Store notification preferences and verified external destinations per user/channel. A browser notification is readable only by its recipient in the selected portal/client scope.

### 4.7 Reports and audit

- **reports** — UUID PK, client_id, project_id, report_type, period_start, period_end, status, metrics snapshot JSONB, editable narrative, optional summary_generation_id, created_at, published_by FK and published_at. Record the requesting human or service as for generations. UNIQUE(project_id, report_type, period_start, period_end) for project reports. A scheduled replay reuses the same report. Validate period order and same-client project. Agency aggregates use separate agency-only query endpoints.
- Report states are `generating`, `draft`, `ready_for_review`, `published`, and `failed`. Preserve deterministic metrics on failure. Retry a failed generation on the same report. A published version is read-only. A linked file export requires the same access as its report.
- **activity_logs** — UUID PK, actor user or authenticated service, action, resource type/ID, optional client/project, occurred_at, request or event ID and minimal change metadata. Record privileged actions with their transaction. Exclude sensitive inputs and tokens.

## 5. Migration order and integrity gates

1. **CP1** — Users, clients (ownership root), memberships, agency invitations, the audit log, sessions and reset tokens. CP1-B also creates the minimal project ownership roots and project approval delegations requested at checkpoint authorization. Test delegated team administration, concurrent last-Admin protection, normalized uniqueness, expiry, revocation, membership FKs and two-client isolation.
2. **CP2** — CRM, project business fields and team assignments, client invitations, intake receipts, outbox, receipts, workflow runs and notifications. Create project before optional lead conversion link. Test duplicate conversion/redemption, transaction rollback and concurrent delivery. Extend intake receipts with brief references when briefs exist.
3. **CP3** — Briefs, files, attachments, immutable snapshots, AI generations and proposals. Add circular references only after both targets exist. Add task-template provenance and the minimal content item/revision pair with its same-item pointer for Creative Studio selection and copywriting. Test snapshot stability, idempotency collisions, worker recovery and same-project lineage.
4. **CP4** — Revision attachments, review stages, approvals and feedback on the CP3 item/revision pair. Test first insertion, delegation and revocation during sign-off, concurrent decisions, stale reviews and feedback visibility.
5. **CP5** — Reports, summary and export links, period uniqueness and publication constraints. Test concurrent scheduling, failure recovery and published-only access.

For repeated ownership keys use composite parent FKs, including (project_id, client_id). Enforce the same parent chain for milestone/task, item/brief, revision/approval, generation/proposal and file links. Use transactions for cross-table invariants. Restrict deletion of referenced history. At each checkpoint apply Alembic to a clean isolated PostgreSQL database and upgrade the previous checkpoint schema with representative data. The first migration and all runtime checks belong to later checkpoints.
