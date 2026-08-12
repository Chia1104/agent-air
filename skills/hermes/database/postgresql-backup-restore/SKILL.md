---
name: postgresql-backup-restore
description: Use for PostgreSQL/ParadeDB dump and restore workflows.
version: 1.0.0
author: Hermes Curator
license: MIT
metadata:
  hermes:
    tags: [postgresql, paradedb, backup, restore, docker]
    related_skills: []
---

# PostgreSQL Backup and Restore

## When to Use

Use this skill when exporting, migrating, cloning, or restoring PostgreSQL-compatible databases, especially Docker-hosted PostgreSQL or ParadeDB instances. It also applies when turning a successful manual dump/restore into safe reusable scripts.

## Core workflow

1. **Discover before changing anything**
   - Confirm the exact host, mapped host port, database, user, and client binary version.
   - Test the connection with `psql` and record the database version and size.
   - Before restore, distinguish application-owned tables from extension-owned tables; a ParadeDB database can look non-empty while containing only extension objects.
2. **Choose a dump format deliberately**
   - Plain SQL (`pg_dump --file backup.sql`) is transparent and directly restorable with `psql`.
   - Custom format (`pg_dump -Fc`) is better for selective or parallel restore with `pg_restore`.
   - Use a timestamped output name and write to a `.partial` file first; rename only after success and validation.
3. **Verify the dump**
   - Require a non-empty file and successful `pg_dump` exit status.
   - For plain SQL, confirm the `-- PostgreSQL database dump complete` marker.
   - Record path and byte size. A checksum is optional but useful for transfer.
4. **Guard the restore target**
   - Query the target before restore. Abort if application-owned tables already exist unless the user explicitly approves destructive replacement.
   - Do not treat extension-owned tables as application data.
   - Use `psql -v ON_ERROR_STOP=1 -f backup.sql` for plain SQL so the first SQL error stops the run.
5. **Prepare extensions, then restore**
   - On ParadeDB, ensure required extensions such as `pg_search` and `vector` exist with `CREATE EXTENSION IF NOT EXISTS ...`.
   - Account for pre-created extension schemas in the target; see the ParadeDB reference below.
6. **Verify the restored database**
   - Check expected schemas/tables and representative exact row counts.
   - Require zero invalid indexes (`pg_index.indisvalid = false`).
   - Require zero unvalidated constraints (`pg_constraint.convalidated = false`).
   - Report the exact dump used and target connection without exposing the password.

## Application-table safety query

Use extension dependency metadata rather than counting all non-system tables:

```sql
WITH tables AS (
  SELECT c.oid
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind IN ('r', 'p')
    AND n.nspname NOT IN ('pg_catalog', 'information_schema')
), extension_objects AS (
  SELECT d.objid
  FROM pg_depend d
  WHERE d.deptype = 'e'
    AND d.classid = 'pg_class'::regclass
)
SELECT count(*) FILTER (WHERE e.objid IS NULL) AS application_tables,
       count(*) FILTER (WHERE e.objid IS NOT NULL) AS extension_tables
FROM tables t
LEFT JOIN extension_objects e ON e.objid = t.oid;
```

Any positive `application_tables` count makes an additive plain-SQL restore unsafe by default.

## Script quality requirements

Reusable scripts should:

- Use `set -Eeuo pipefail`.
- Accept `DATABASE_URL`, output directory, and PostgreSQL binary directory as overrides.
- Check executable and input-file prerequisites.
- Avoid silently overwriting dumps.
- Remove partial outputs on failure.
- Refuse a restore into a target containing application tables.
- Verify outcomes with real SQL queries, not only process exit codes.
- Keep credentials out of logs and final responses. Prefer environment variables or `.pgpass` over embedding passwords in shared scripts.

## Pitfalls

- A Docker host port such as `5434` maps to PostgreSQL's container port, commonly `5432`; always query the connected server rather than inferring identity from the host port.
- `pg_dump` and server minor versions can differ, but the dump client should not be older than an incompatible server major version.
- Running restore without `ON_ERROR_STOP=1` can produce a partially restored database while still printing many successful statements.
- `CREATE EXTENSION IF NOT EXISTS` does not prevent an earlier standalone `CREATE SCHEMA` from failing if that schema already exists.
- Do not claim success until indexes, constraints, and representative row counts have been checked.

## References

- `references/paradedb-plain-sql.md` — tested ParadeDB extension/schema handling for portable plain-SQL dumps.
