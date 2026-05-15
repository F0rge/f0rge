---
name: Photos router refactor — patterns and gotchas
description: How the photos endpoints were made thin and what test updates were required; monkeypatch targets after logic moved to the service
type: project
---

## PhotoService is the single place for all photo logic

`app/services/photos.py` (`PhotoService`) owns: upload (filename generation, resize, save, DB row, vault re-render, background task queueing), `get_file_path` (DB lookup + disk existence check), `delete` (DB commit first, then disk delete, then vault re-render), and `update_meal_time`.

`app/dependencies/photos.py` (`get_photo_service`) takes only `db: Session = Depends(get_db)` — `settings` is imported directly in the service, not injected.

## Monkeypatch target moved when logic moved

Tests that stub `write_daily_file` used to patch `"app.routers.photos.write_daily_file"`. After the logic moved to the service, the target is `"app.services.photos.write_daily_file"`. Same principle applies to any other helper the service imports.

**Why:** Python's monkeypatch patches the *name in the module that uses it*, not the original definition site. If you patch the wrong module, the stub is never called.

**How to apply:** When moving logic from a router into a service, grep tests for `monkeypatch.setattr("app.routers.<module>.*")` and update the path to `"app.services.<module>.*"`.

## Tests that called router functions directly must move to the service

`test_photo_filename.py` and `test_photos_meal_time.py` called `upload_photo(date, background_tasks, file, label, meal_time, db=db)` directly. After the refactor, `upload_photo` no longer accepts `db` — it accepts `service: PhotoService = Depends(...)`. The tests now instantiate `PhotoService(db)` and call `service.upload(...)` directly. This is actually better: tests call the service, not the router, which avoids FastAPI `Form(None)` sentinel bugs (see prior memory entry on that gotcha).

## DB commit before filesystem delete — order matters

In `PhotoService.delete()`, `db.delete(photo)` + `db.commit()` runs *before* `delete_photo(filename, vault_path)`. This is deliberate: if the commit fails (e.g. cascade constraint), no files are removed and the DB row stays — consistent state. Filesystem operations are not transactional so they must follow a successful commit, not precede it.

**Why:** Prior prod incident where files were deleted before commit, then commit failed, leaving orphan DB rows pointing at missing files.

## FileResponse from a thin router

`serve_photo` stays a `def` (sync) endpoint because `FileResponse` is sync-compatible. It's one line:

```python
return FileResponse(service.get_file_path(photo_id), media_type="image/jpeg")
```

`get_file_path` raises `NotFoundError` for both missing DB row and missing file on disk — both map to 404 via the global handler in `main.py`.

## async service method called from async router endpoint

`PhotoService.upload()` is `async` because it calls `await file.read()`. The router endpoint `upload_photo` is therefore also `async def`. FastAPI handles both sync and async handlers natively — no special wiring needed.
