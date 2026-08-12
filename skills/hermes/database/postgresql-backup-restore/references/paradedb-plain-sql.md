# ParadeDB plain-SQL dump/restore notes

This reference captures a tested migration pattern for a ParadeDB Docker database using PostgreSQL 18 clients.

## Why an apparently fresh ParadeDB database is not empty

A fresh ParadeDB database may contain dozens of tables owned by extensions such as:

- `pg_search` in schema `paradedb`
- `pg_ivm` in schema `pgivm`
- PostGIS objects in `public`, `tiger`, and `topology`
- `vector` objects in `public`

Counting every non-system table incorrectly classifies this as user data. Use the extension-dependency query in `SKILL.md`; a safe fresh target has zero application-owned tables even if extension-owned tables are present.

## Extension-schema collision

A plain dump from a ParadeDB source can contain both:

```sql
CREATE SCHEMA paradedb;
CREATE EXTENSION IF NOT EXISTS pg_search WITH SCHEMA paradedb;
```

It may similarly emit standalone `CREATE SCHEMA tiger` and `CREATE SCHEMA topology` statements. On a fresh ParadeDB target these schemas can already exist, so restore stops at `schema already exists` despite `CREATE EXTENSION IF NOT EXISTS` being safe.

The tested solution is to exclude pre-provisioned extension schemas at dump time:

```bash
pg_dump "$DATABASE_URL" \
  --no-password \
  --exclude-schema=paradedb \
  --exclude-schema=pgivm \
  --exclude-schema=tiger \
  --exclude-schema=topology \
  --file "$OUTPUT_FILE"
```

This keeps application schemas and data while avoiding duplicate creation of ParadeDB/PostGIS infrastructure schemas. Use this only when those excluded schemas are reserved for extensions; inspect them first if the application intentionally stores its own objects there.

## Restore sequence

For a target with zero application-owned tables:

```sql
CREATE EXTENSION IF NOT EXISTS pg_search;
CREATE EXTENSION IF NOT EXISTS vector;
```

Then restore with:

```bash
psql "$DATABASE_URL" --no-password -v ON_ERROR_STOP=1 -f "$DUMP_FILE"
```

## Validated checks

After restore, verify:

```sql
SELECT count(*) AS invalid_indexes
FROM pg_index
WHERE NOT indisvalid;

SELECT count(*) AS unvalidated_constraints
FROM pg_constraint
WHERE NOT convalidated;
```

Both counts should be zero. Also query exact row counts for a few known application tables.

## How the reusable scripts were tested

The dump script was executed against a live restored ParadeDB database. The restore script was then exercised end-to-end by:

1. Creating a temporary database on the same ParadeDB server.
2. Ensuring `pg_search` and `vector` existed.
3. Restoring the generated plain-SQL dump with `ON_ERROR_STOP=1`.
4. Checking representative row counts, invalid indexes, and unvalidated constraints.
5. Dropping the temporary test database.

This end-to-end test exposed and resolved the extension-schema collision; syntax-only testing would not have found it.
