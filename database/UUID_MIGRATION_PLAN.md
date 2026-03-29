# UUID and Audit Column Migration Plan

This project now has runtime hardening changes in routes and FK metadata.

## Completed Phases

- Phase 1 applied: revision 5496ce7a44d9
	- Added uuid, updated_at, is_deleted, deleted_at to users and subjects
- Phase 2 applied: revision cf6b6076f44b
	- Added uuid and audit/soft-delete fields to quizzes, notes, certificates
	- Added UUID-compatible routes for subjects, assigned quiz start, note edit, certificate download
- Phase 3 applied: revision b0d57f78f74f
	- Added uuid and audit/soft-delete fields to chat rooms/messages, notifications, attendance sessions/records, news, testimonials, contact messages
	- Added soft-delete-aware filtering in chat, notifications, attendance, admin/public CMS routes
	- Switched key UI links to UUID-first for certificate download and note editing
- Phase 4 applied: revision 7fd6a0d35b12
	- Added UUID shadow foreign-key columns (e.g., user_uuid, subject_uuid, quiz_uuid, room_uuid, session_uuid) across core child tables
	- Backfilled shadow UUID FKs from existing integer relations
	- Added indexes on shadow UUID columns for rollout performance

## Phase 5 In Progress

- Added model-level dual-write synchronization hooks:
	- before_insert/before_update listeners now auto-sync int FK <-> UUID shadow FK for core entities
	- keeps future writes consistent without per-route manual shadow assignment
- Added UUID-first read routes with int fallback redirects for high-traffic flows:
	- study plan week grid / week detail / progress (UUID routes)
	- calendar subject view (UUID route)
- Updated primary subjects UI action links to UUID-first endpoints

Current Alembic head: 7fd6a0d35b12

To complete full industry schema standards without downtime, run these DB migrations in order:

1. Add non-breaking columns to all core tables:
- uuid (String(36), unique, nullable at first)
- created_at (if missing)
- updated_at (if missing)
- is_deleted (Boolean, default false)
- deleted_at (DateTime, nullable)

2. Backfill uuid and timestamps for existing rows.

3. Add unique indexes:
- users.uuid
- subjects.uuid
- quizzes.uuid
- notes.uuid
- certificates.cert_number (already present)

4. Update route params from int IDs to UUID for public-facing pages.

5. Switch FKs to UUID columns in child tables (parallel columns first), backfill, then drop integer FKs.

6. Promote UUID columns to primary keys only after all FK references are migrated.

7. Enforce soft delete in query helpers and admin screens with a shared filter.

8. Remove legacy int-id URL paths once UUID paths are fully deployed.

Recommended: use Alembic for phased migrations and rollbacks.

## Next Phase (Suggested)

1. Add uuid/audit/soft-delete columns to remaining core entities (chat rooms/messages, notifications, attendance, public CMS)
2. Expand UUID routes to remaining high-traffic user-facing endpoints and templates
3. Flip selected service/query paths to UUID-first reads while keeping integer fallback temporarily
4. Add DB-level UUID FK constraints after confidence window, then deprecate int-FK writes

## Recommended Next Actions (Phase 5 Completion)

1. Convert remaining template links to UUID-first for week detail/progress/calendar from dashboard cards and analytics pages
2. Add UUID-first API variants for key AJAX endpoints where subject_id is passed via query string
3. Add DB-level CHECK/NOT NULL constraints for high-confidence shadow UUID columns
