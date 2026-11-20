# CREATIVE OS
## Product Requirements Document (PRD)

**Version:** 0.1  
**Status:** Initial Draft  
**Product Type:** AI-Powered Creative Agency Operations Platform

## 1. Product Overview

CREATIVE OS is a web-based platform designed to streamline creative agency operations through workflow automation, AI-assisted content production, client management, project management, and operational reporting.

The platform provides two interfaces:

- **Client Portal:** Allows clients to submit briefs, monitor project progress, review creative deliverables, provide feedback, and access reports.
- **Admin Portal:** Allows agency personnel to manage clients, projects, content production, tasks, deadlines, automations, and operational analytics.

Both interfaces share a centralized backend and database.

## 2. Product Objectives

1. Centralize client and project information.
2. Automate administrative and client onboarding processes.
3. Use AI to analyze creative briefs and assist content production.
4. Automate task creation, assignment, and deadline notifications.
5. Provide transparent project progress to clients.
6. Generate operational reports automatically.
7. Integrate external services through APIs and webhooks.

## 3. User Roles

### Client
- Access their own client workspace.
- Submit and update creative briefs.
- Upload brand guidelines and reference files.
- View their projects and milestones.
- Both client roles may view released deliverables and submit non-binding feedback within their authorized client workspace.
- A client_admin can approve or formally request revisions for the owning organization. They may grant or revoke this authority for an active client_member on a specific project.
- A client_member can make a binding decision only with active delegation for that project. The grant conveys neither client role management nor the ability to delegate.
- Access client-specific reports.

### Admin
- Invite, activate and deactivate agency members and grant or revoke any agency role. Preserve at least one active Admin after initial bootstrap.
- Control authentication policies and security-sensitive settings.
- Manage clients and onboarding.
- Create and manage projects.
- Review AI-generated content.
- Manage tasks, deadlines, and assignments.
- Access operational analytics.
- Monitor automation execution.

### Team Member
- View assigned tasks.
- Update task status.
- Submit deliverables.
- Receive notifications.
- Collaborate on projects.

### Agency Manager
- Access agency-wide operational information.
- Monitor project and team performance.
- Review reports.
- Manage project assignments, tasks, workflows and non-security operational settings.
- Invite, activate or deactivate Team Members and grant or revoke the Team Member role. Admin and Agency Manager roles, elevated accounts and the manager’s own privileges are outside this authority.

FastAPI checks current authority on every mutation. Record membership and role changes, project approval grants and revocations, and binding client decisions in the audit log. A client review admits a single decision on the exact submitted revision.

## 4. Core Functional Modules

### Module A — Client Acquisition & Onboarding
- Client inquiry submission.
- Client registration and profile management.
- Onboarding forms.
- Document and brand guideline uploads.
- Lead status tracking.
- Automated notifications.
- External form integration.

### Module B — AI Creative Intelligence
- Creative brief submission.
- AI brief analysis.
- Tone and audience interpretation.
- Ambiguity detection.
- Creative direction generation.
- Campaign and content ideation.
- Copywriting assistance.
- Human review and approval.
- Feedback and revision tracking.

### Module C — Project & Task Management
- Project creation.
- Task generation from approved content plans.
- Task assignment.
- Deadline management.
- Milestone tracking.
- Kanban board.
- Automated reminders.
- Overdue task monitoring.
- Client-facing progress visibility.

### Module D — Reporting & Performance Monitoring
- Client-specific project reports.
- Campaign production progress.
- Task completion metrics.
- Project status reporting.
- Agency-wide operational dashboard.
- Scheduled weekly reports.
- Automation execution logs.

## 5. External Integrations

Initial MVP integrations:

- Google Forms: External inquiry and brief submissions.
- Google Drive: Document and creative reference storage.
- Gmail: Email notifications and communication.
- Telegram Bot API: Internal notifications and reminders.
- LLM API: AI brief analysis and content generation.
- n8n: Workflow orchestration.

The application must also support native input forms within the Client Portal.

## 6. User Interface

### Client Portal
- Client Dashboard
- Project Overview
- Creative Brief
- Content Studio
- Files & Communication
- Reports

### Admin Portal
- Operations Dashboard
- Client Management
- Project Management
- Task Management
- Content Management
- AI Workspace
- Reports & Analytics
- Automation Logs
- User & Role Management

## 7. Technical Direction

- Frontend: Next.js
- UI: Tailwind CSS and shadcn/ui
- Backend: Python and FastAPI
- Database: PostgreSQL
- Workflow automation: n8n
- AI services: Python and LLM APIs
- File storage: Google Drive integration initially
- Notifications: Telegram and Gmail
- Containerization: Docker

The application will use a shared backend with role-based access control and client-level data isolation.

## 8. MVP Scope

The MVP must demonstrate one complete operational journey:

1. A client submits an inquiry.
2. The inquiry creates a lead. Agency qualification and conversion create the client record, followed by an invitation.
3. The client submits a creative brief.
4. AI analyzes the brief.
5. AI generates a creative direction and content plan.
6. An agency user reviews and approves the proposed content.
7. The system creates project tasks.
8. Team members receive notifications.
9. The client views project progress and approves deliverables.
10. The system updates operational dashboards and generates a weekly report.

## 9. Research Extension — Mechanistic Interpretability

A separate experimental research module will investigate whether internal representations of small language models can provide useful insights into creative communication attributes.

Potential attributes:
- Empathy
- Warmth
- Assertiveness
- Formality
- Persuasion intensity
- Brand voice consistency

Research techniques may include Group Sparse Autoencoders, latent representation analysis, orthogonal projection, and ablation experiments.

This research module is not a runtime dependency of the core CREATIVE OS application.

## 10. Non-Functional Requirements

- Responsive web interfaces.
- Secure authentication and authorization.
- Client-level data isolation.
- Input validation.
- Structured API responses.
- Error handling and workflow retry mechanisms.
- Automation execution logging.
- Maintainable modular architecture.
- Automated tests for critical workflows.
- Environment-based configuration and secret management.

## 11. MVP Acceptance Criteria

The MVP is considered complete when:

- Client and agency users can authenticate.
- Client data is isolated between organizations.
- Clients can submit briefs through the portal.
- Admin users can manage client records.
- AI can generate structured brief analysis.
- AI can generate draft creative content.
- Human approval is required before client delivery.
- Approved content can generate project tasks.
- Task status and deadlines are visible in the dashboard.
- Telegram notifications work.
- Client-specific project reports are accessible.
- Weekly operational reporting can execute.
- Critical workflows have automated tests.
- The application can run through Docker Compose.

## 12. Out of Scope for Initial MVP

- Automatic publishing to social media.
- Direct integration with every social media analytics platform.
- Autonomous client communication without human approval.
- Full accounting and invoicing system.
- Advanced employee payroll and HR management.
- Production-grade multi-tenant SaaS billing.
- Mechanistic interpretability as a required runtime feature.