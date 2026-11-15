# HUB0004 · 1/3 · Record batch-caller grep for create_commission

## Command 1 (required)

Run from the repo root:

```
grep -rn "create_commission(" --include=*.py .
```

Verbatim output:

```
./app/commissions.py:8:async def create_commission(painter_name: str) -> Commission:
./app/routers/commissions.py:22:async def create_commission(painter_name: str = Form(...)):
./app/routers/commissions.py:23:    commission = await commissions_service.create_commission(painter_name)
```

## Command 2 (broader check)

```
grep -rn --exclude-dir=.git "create_commission" .
```

Verbatim output:

```
./app/commissions.py:8:async def create_commission(painter_name: str) -> Commission:
./app/routers/commissions.py:22:async def create_commission(painter_name: str = Form(...)):
./app/routers/commissions.py:23:    commission = await commissions_service.create_commission(painter_name)
```

## Per-hit classification

| path:line | kind | note |
|---|---|---|
| app/commissions.py:8 | def | service definition `create_commission(painter_name)` |
| app/routers/commissions.py:22 | def | router handler `create_commission` |
| app/routers/commissions.py:23 | call | the single-row call to the service |

## Conclusion

The only call site is `app/routers/commissions.py:23`, which is a single-row call. No batch caller exists among `.py` hits. The other `.py` hits are definitions.

## Non-code hits

The planning notes for this task cited `Docs/CHANGE_REVIEW_CANDIDATES.md:68-69` as a copy of the same two lines. In this checkout, `Docs/` does not exist (`ls -la Docs` returned "No such file or directory"), and the shell grep above found no hit in a Markdown file. However, the repo search tool (`grep_codebase`) returned `Docs/CHANGE_REVIEW_CANDIDATES.md:68` and `Docs/CHANGE_REVIEW_CANDIDATES.md:69`, each containing one of the same two lines. These two results conflict, and this pass did not resolve the conflict. Either way, that Markdown copy is documentation, not Python, and it is not a caller.

---

## 2026-11-15 · HUB0004 2/3 · Transaction wrapper and schema check

### Grep (step 2)

The `app` directory is not a searchable dir for grep_codebase, so each pattern was run over `.` (whole repo).

- `BEGIN` (dir `.`): no hits.
- `commit` (dir `.`): hits in `app/`:
  - `app/catalog.py:91`, `app/catalog.py:109`
  - `app/catalog_import.py:160` (`conn.commit()`)
  - `app/commissions.py:16`, `app/commissions.py:105`, `app/commissions.py:112`, `app/commissions.py:149`
  - `app/db.py:158`, `app/db.py:183`, `app/db.py:238`, `app/db.py:277`, `app/db.py:308`
  - `app/rooms.py:26`, `app/rooms.py:222`, `app/rooms.py:256`, `app/rooms.py:263`
  - `app/routers/ws.py:26`, `app/routers/gaps.py:37` (found by the case-insensitive `-inE` run over `app/` and `Docs/`)
  - Other hits (`.pytest_cache/README.md`, `Docs/CHANGE_REVIEW_CANDIDATES.md`, `README.md`) are not in `app/`.
- Case-insensitive re-run (`grep -inE 'BEGIN|commit|transaction|create table commissions' app/ Docs/ -r`) matched the same `app/` lines listed above, plus notes-file lines. No `BEGIN` or `transaction` hits in `app/`. The only `Docs/` hits are in this notes file itself, because its own text contains those words.
- `transaction` (dir `.`): no hits.
- `CREATE TABLE IF NOT EXISTS commissions` (dir `.`): `app/db.py:51`.

### Transaction wrapper around `create_commission` INSERT

Finding: no transaction wrapper is present. The INSERT at `app/commissions.py:14` is a single `db.execute` call, followed by `await db.commit()` at `app/commissions.py:16`. There is no `BEGIN` and no `transaction` anywhere in the repo. The function retries up to 10 times on exceptions containing `UNIQUE`. Each attempt runs one INSERT and then commits, so no explicit transaction groups the attempts.

### Commissions schema (`app/db.py` near line 51)

Finding: only `code` is `UNIQUE`. The table is `commissions` with `code TEXT UNIQUE NOT NULL`, and the other columns are `id`, `painter_name`, `status`, `commission_rate`, `cash_amount`, `created_at`, and `updated_at`. There is no `(painter_name, code)` composite UNIQUE constraint.
