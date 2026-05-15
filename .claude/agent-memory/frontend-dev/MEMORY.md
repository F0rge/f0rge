# Frontend Dev Memory

## Project Structure

```
frontend/
  app/
    page.tsx              # Root (dashboard/redirect)
    login/page.tsx        # PIN entry
    checkin/page.tsx      # Today's check-in
    checkin/[date]/page.tsx  # Specific date check-in
    history/page.tsx      # Calendar/monthly view
    history/[date]/page.tsx  # Entry detail view
    settings/page.tsx     # Configuration
  components/
    auth/pin-pad.tsx      # PIN input UI
    checkin/
      checkin-form.tsx    # Main entry form
      scale-input.tsx     # 1-5 scale selector
      binary-input.tsx    # Yes/no toggle
      notes-input.tsx     # Text area for notes
      photo-capture.tsx   # Camera/file upload (capture="environment" for mobile)
    history/
      calendar-view.tsx   # Monthly calendar
      entry-card.tsx      # Entry summary display
    ui/                   # shadcn primitives (card, button, label, input, textarea, radio-group, badge, dialog)
    providers.tsx         # React Query + Sonner toast
  lib/
    api/
      client.ts           # apiGet/Post/Put/Delete/PostForm, credentials='include', 401->login redirect
      types.ts             # Entry, Photo, HealthMetricResponse, WeatherDailySummary, EnrichedDayResponse, AuthUser
      hooks.ts             # React Query hooks (useEntries, useUploadPhoto, etc.)
    utils.ts
```

## Key Patterns

- API client uses credentials='include' for cookie auth
- 401 responses auto-redirect to /login?redirect={current_path}
- React Query for server state (@tanstack/react-query 5.95)
- Sonner for toast notifications
- Photo upload via FormData to POST /entries/{date}/photos

## Dependencies

next 16.2.1, react 19.2.4, typescript 5, tailwindcss 4, @tanstack/react-query 5.95, @base-ui/react (shadcn), lucide-react, sonner, clsx, tailwind-merge

## Styling

- Tailwind CSS v4
- cn() utility for conditional classes (clsx + tailwind-merge)
- Mobile-first design (this is primarily used on phone for daily check-ins)

## Known Gaps

- No loading.tsx or error.tsx files in route directories
- No tests (unit or E2E)
- Photo capture component has no image analysis integration yet
