# ATLAS LENS Development Rules

## 1. Project Identity And Current Scope

This repository is the LENS module of the ATLAS platform.

ATLAS is a modular, self-hosted newsroom and photography platform. LENS handles the professional photography workflow, including photo ingestion integration, image management, captions, IPTC metadata, editing workflow, galleries, exports, and agency delivery preparation.

All development work in this repository must preserve the current scope of LENS and avoid introducing responsibilities that belong to other ATLAS modules.

## 2. ATLAS Module Architecture

ATLAS is organized into independent modules:

- ORBIT
- FLOW
- LENS
- DISPATCH
- PULSE
- NEXUS
- ARCHIVE
- INSIGHT
- MARKET

Maintain module independence while respecting shared ATLAS interfaces. Do not create tight coupling between modules. Shared contracts, manifests, events, APIs, or storage conventions must remain explicit, documented, and backwards compatible whenever possible.

## 3. LENS Responsibilities And Boundaries

LENS is responsible for professional photography workflows:

- Photo ingestion integration.
- Image and asset management.
- Caption workflows.
- IPTC metadata creation, editing, validation, and export.
- Editing workflow state and review preparation.
- Gallery organization and delivery views.
- Export packaging.
- Agency delivery preparation.

LENS should not own unrelated newsroom planning, publishing orchestration, analytics, marketplace, archive policy, or dispatch operations unless those capabilities are exposed through documented ATLAS interfaces.

## 4. Rules For Inspecting The Existing Implementation Before Changes

Before proposing or implementing changes:

- Inspect the repository and existing documentation before proposing changes.
- Read the relevant code, configuration, tests, and documentation.
- Identify the existing architecture, naming conventions, data flow, and extension points.
- Check whether a requested feature or service already exists.
- Prefer existing patterns over new abstractions.
- When uncertain, stop and ask.

Do not assume missing functionality without verifying the current implementation.

## 5. Rules Against Reinstalling, Duplicating, Or Rebuilding Working Components

Preserve current working functionality.

- Extend existing components instead of replacing them whenever possible.
- Never reinstall or duplicate an existing service without first verifying its documented state.
- Never replace a working module, service, dependency, container, database, or configuration simply to simplify implementation.
- Do not rebuild working components unless explicitly approved and documented.
- Avoid duplicate services, duplicate background workers, duplicate schemas, duplicate queues, and duplicate configuration paths.

If an existing component appears broken, document the evidence before proposing repair or replacement.

## 6. Coding And Dependency Standards

Code must be clean, documented, maintainable, and consistent with the existing project.

- Avoid unnecessary dependencies.
- Prefer open-source solutions.
- Preserve backwards compatibility.
- Keep changes small, focused, reversible, and documented.
- Do not modify unrelated files.
- Use structured parsers and framework-supported APIs instead of brittle string manipulation when practical.
- Keep Docker compatibility.
- Keep Proxmox compatibility.
- Use environment variables instead of hardcoded values.

New dependencies must be justified by clear project value and must not duplicate existing capabilities.

## 7. Security And Secrets Management

Never commit secrets, passwords, tokens, API keys, or private configuration.

- Use environment variables and provide safe example files when necessary.
- Do not hardcode credentials, private endpoints, production paths, or personal access tokens.
- Keep sensitive local configuration out of version control.
- Redact secrets from logs, documentation, examples, screenshots, and command output.
- Prefer least-privilege access for services, integrations, and database users.

Security-sensitive changes must be documented clearly.

## 8. Docker, Proxmox, And Self-Hosted Compatibility

ATLAS must remain self-hosted and operational in Docker and Proxmox-oriented environments.

- Preserve Dockerfile and docker-compose compatibility.
- Do not introduce assumptions that require a managed cloud platform.
- Keep service configuration environment-driven.
- Avoid host-specific absolute paths unless they are configurable.
- Document ports, volumes, environment variables, health checks, and startup requirements.
- Ensure changes can run in constrained self-hosted infrastructure.

## 9. Database And Migration Safety

Database changes must be safe, reversible where possible, and compatible with existing data.

- Inspect existing schemas, migrations, models, and seed data before changes.
- Do not delete, truncate, overwrite, or reset databases without explicit approval.
- Prefer additive migrations for existing production data.
- Document migration purpose, expected impact, and rollback considerations.
- Preserve existing identifiers and relationships unless a migration plan is approved.
- Validate migrations against local or test data before reporting completion.

Never delete files, data, containers, volumes, databases, or configurations without explicit approval.

## 10. Testing And Validation Requirements

Run relevant tests or checks before reporting completion.

- Use the project's existing test commands and validation tools.
- Add or update focused tests when behavior changes.
- Validate Docker or service startup when infrastructure changes require it.
- Report clearly which checks passed or failed.
- If a check cannot be run, explain why and describe the remaining risk.

Do not claim completion without validation appropriate to the change.

## 11. Logging And Error-Handling Requirements

Generate logs for important actions.

- Log ingestion, export, delivery preparation, metadata updates, and other important workflow events.
- Keep logs useful for operators without exposing secrets.
- Handle errors explicitly and preserve actionable error messages.
- Avoid swallowing exceptions silently.
- Prefer recoverable failure modes for long-running ingestion, export, and delivery workflows.
- Document operational failure cases when they affect setup or support.

## 12. Documentation Requirements

Update documentation whenever code changes affect behavior, setup, configuration, operations, APIs, data formats, or workflows.

- Keep documentation clear and technically accurate.
- Document new environment variables.
- Document service startup and validation steps.
- Document user-visible workflow changes.
- Keep examples safe and free of secrets.

Documentation changes must remain scoped to the feature or fix being implemented.

## 13. Technical Log, Installation Inventory, And Architecture Decision Records

Maintain durable project knowledge.

- Record important technical changes in the appropriate technical log when one exists.
- Maintain installation inventory for services, dependencies, integrations, ports, volumes, and runtime assumptions.
- Use architecture decision records for significant design decisions, module boundaries, data contracts, or infrastructure choices.
- Before reinstalling, replacing, or duplicating any service, verify its documented state in the installation inventory or related documentation.
- If documentation is missing, note the gap before making significant operational changes.

## 14. Git Workflow And Commit Rules

Keep commits focused and small.

- Do not create a Git commit unless explicitly requested.
- Do not modify unrelated files.
- Review the working tree before and after changes.
- Preserve user changes and never revert work that was not part of the request.
- Keep changes logically grouped and easy to review.
- Report clearly which files changed, which commands ran, and which checks passed or failed.

Commit messages, when requested, must describe the actual scoped change.

## 15. Destructive-Action Approval Rules

Destructive actions require explicit approval before execution.

Destructive actions include deleting, overwriting, resetting, pruning, reinstalling, or recreating:

- Files.
- Data.
- Containers.
- Volumes.
- Databases.
- Configurations.
- Branches.
- Runtime state.

Never delete files, data, containers, volumes, databases, or configurations without explicit approval. If a destructive action appears necessary, stop, explain the reason, list the exact target, and wait for approval.

## 16. Definition Of Done

Work is done only when:

- The existing implementation and documentation were inspected.
- Current working functionality was preserved.
- Existing components were extended instead of replaced whenever possible.
- The change is small, focused, reversible, and documented.
- No unrelated files were modified.
- Secrets were not committed or exposed.
- Relevant tests or checks were run.
- Failures, skipped checks, and residual risks were reported clearly.
- Changed files and commands run were reported clearly.
- No Git commit was created unless explicitly requested.
- Module independence was maintained while respecting shared ATLAS interfaces.
- Uncertainty was resolved by inspection or by asking before proceeding.
