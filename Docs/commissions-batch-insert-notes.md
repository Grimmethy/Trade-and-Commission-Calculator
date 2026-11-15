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
