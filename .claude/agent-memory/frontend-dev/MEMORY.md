# Frontend Dev Memory

## Project Stack

- Next.js 16 (App Router) + React 19 + TypeScript strict
- Tailwind CSS v4
- shadcn/ui (via `@base-ui/react`)
- @tanstack/react-query for server state
- Sonner for toasts
- lucide-react for icons
- Mobile-first — this is primarily used on phone

## Layout

- `app/` — App Router pages (`/login`, `/checkin`, `/checkin/[date]`, `/history`, `/history/[date]`, `/settings`)
- `components/auth/` — pin-pad
- `components/checkin/` — checkin-form, photo-capture, scale-input, binary-input, bristol-input, notes-input, supplement-picker, photo-analysis, ingredient-editor
- `components/history/` — calendar-view, entry-card
- `components/ui/` — shadcn primitives
- `lib/api/` — client.ts (apiGet/Post/Put/Patch/Delete/PostForm, `credentials: 'include'`, 401 → /login redirect), types.ts, hooks.ts

## Key Patterns

- API client uses `credentials: 'include'` for cookie auth
- 401 auto-redirects to `/login?redirect={current_path}`
- Photo upload via FormData to `POST /entries/{date}/photos`
- Photo analysis polls `GET /photos/{id}/analysis` with `refetchInterval: 2000` while status is `pending`/`analyzing`

## Lessons learned (patterns that bit us in production)

### fetch wrapper must handle 204 No Content before content-type sniff
FastAPI sets `Content-Type: application/json` on 204 responses with no body. The default response handler in `lib/api/client.ts` calls `res.json()` whenever the content type is JSON — but `res.json()` on an empty body throws `SyntaxError: Unexpected end of JSON input`. The throw propagates to the mutation, `onSuccess` never fires, and any consumer with a `catch { toast.error(...) }` shows a red error toast even though the backend succeeded.

Always add `if (res.status === 204) return null` before the content-type sniff in any custom `handleResponse` / fetch wrapper. Affects every DELETE endpoint in the API.

*Why:* Issues #11 and #12 were the same bug. We filed them separately, investigated independently, and only realised they were one bug on the third debug pass. A one-liner in this file would have caught it at code-review of PR #2.
