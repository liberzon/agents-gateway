# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open source community documentation (CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md)
- GitHub issue and PR templates
- Pre-commit hooks configuration
- Dependabot configuration for automated dependency updates
- CodeQL security scanning workflow
- Multi-cloud deployment examples (AWS, Azure, GCP, Kubernetes)
- Observability module with pluggable providers (Console, OTLP, Sentry, Logtail)
- Prompts storage and management service with postgres and langsmith backends
- Docker Compose configuration for local development
- Postman collection for API testing
- Testcontainers for integration testing
- Agent CLI and Team CLI tools
- V2 prompts API routes (`/v2/prompts`)

### Changed
- Renamed project from `agent-api` to `agents-gateway`
- **BREAKING**: Renamed `org_id` parameter to `tenant_id` across Knowledge API
- Database migrations consolidated into single `setup.sql`
- Version handling improvements in `pyproject.toml`

### Removed
- ExpenseReimbursementToolkit and expense service
- Modal.py deployment configuration
- Redundant GCP deployment scripts
- Dependency review action from CI workflow

### Fixed
- Knowledge upload functionality
- Contacts search (removed organizations field)
- Various test suite fixes

## [0.2.1] - 2026-01-20

Initial open source release.

### Added
- V2 API with full CRUD operations for agents, teams, and knowledge
- OAuth2 token management with encrypted storage
- Multi-provider toolkit support (Google, Microsoft)
- CalendarToolkit for calendar management
- EmailToolkit for email operations
- ContactsToolkit for contact management
- DriveToolkit for file operations
- Workspace Suite library for vendor-agnostic integrations
- Dynamic Knowledge Base with Qdrant vector storage
- PostgreSQL database for metadata persistence
- SQLite agent storage for conversation history
- Streaming responses via Server-Sent Events
- Token caching with TTL-based expiration
- Comprehensive test suite with pytest

### Security
- Fernet encryption for OAuth tokens
- Input validation with Pydantic models
- SQL injection prevention via SQLAlchemy ORM

[Unreleased]: https://github.com/anthropics/agents-gateway/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/anthropics/agents-gateway/releases/tag/v0.2.1