# Marrow iOS — TestFlight Distribution Runbook

Native SwiftUI app (bundle id `com.f0rge.marrow`). Two internal testers: Leo and
Beatriz. No public App Store listing, no CI lane — releases are manual.

- Xcode project: `Marrow.xcodeproj`, scheme `Marrow`.
- Build config: Debug → Dev API (`api-dev.marrow-health.com`), Release → Prod API
  (`api.marrow-health.com`). See `Config/{Shared,Dev,Prod}.xcconfig`.
- Version and Team ID are set in `Config/Shared.xcconfig` (see below).

---

## 1. Prerequisites (Leo — one time, personal)

These need Leo's Apple ID + payment and cannot be automated:

1. **Enroll in the Apple Developer Program** — https://developer.apple.com/programs/
   ($99/yr, Leo's Apple ID). Wait for approval (usually same day).
2. **Set the Team ID in Xcode:**
   - Xcode → Settings → Accounts → add the Apple ID → the team appears.
   - Copy the 10-char Team ID from https://developer.apple.com/account → Membership.
   - Put it in `Config/Shared.xcconfig`:
     ```
     DEVELOPMENT_TEAM = ABCDE12345
     ```
   - Put the **same** value in `ExportOptions.plist` (`teamID` key).

---

## 2. App Store Connect + APNs (one time)

1. **Create the app record** — https://appstoreconnect.apple.com → My Apps → `+`
   → New App. Platform iOS, bundle id `com.f0rge.marrow`, name "Marrow", primary
   language English. (Bundle id must first exist under Certificates, IDs & Profiles
   → Identifiers — Xcode auto-creates it on first archive with a team set.)
2. **Add Beatriz as an internal tester** — App Store Connect → TestFlight →
   Internal Testing → create a group (e.g. "Household") → add Leo + Beatriz by
   Apple ID. Internal builds need no Apple review.
3. **Create an APNs auth key (.p8)** — https://developer.apple.com/account →
   Certificates, IDs & Profiles → Keys → `+` → enable "Apple Push Notifications
   service (APNs)" → download `AuthKey_XXXXXXXXXX.p8` **once** (not re-downloadable).
   Note the **Key ID** (in the filename / key page) and the **Team ID**.

---

## 3. Fly secrets (backend push config)

The backend reads `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_PRIVATE_KEY` (the PEM
*content* of the .p8, not a path), `APNS_TOPIC` (defaults to `com.f0rge.marrow`),
and `APNS_USE_SANDBOX`. Unset → push disabled with a startup warning; in-app
notifications still work.

Run from the repo root (where `AuthKey_XXXX.p8` was downloaded):

```bash
# Prod app (marrow) — serves TestFlight/App Store builds
fly secrets set --app marrow \
  APNS_KEY_ID=XXXXXXXXXX \
  APNS_TEAM_ID=ABCDE12345 \
  APNS_USE_SANDBOX=false \
  APNS_PRIVATE_KEY="$(cat AuthKey_XXXXXXXXXX.p8)"

# Dev app (marrow-dev) — serves Xcode cable builds
fly secrets set --app marrow-dev \
  APNS_KEY_ID=XXXXXXXXXX \
  APNS_TEAM_ID=ABCDE12345 \
  APNS_USE_SANDBOX=true \
  APNS_PRIVATE_KEY="$(cat AuthKey_XXXXXXXXXX.p8)"
```

### Which APNs environment? (critical — wrong one = silent push failure)

Apple picks the APNs environment from **how the build was signed**, not from the
API it talks to. The backend's `APNS_USE_SANDBOX` must match:

| How the build got on the phone      | `aps-environment` | Backend `APNS_USE_SANDBOX` |
| ----------------------------------- | ----------------- | -------------------------- |
| Xcode → cable / Run (dev build)     | `development`     | `true`  (sandbox)          |
| TestFlight or App Store             | `production`      | `false` (production)       |

The entitlement stays `development` in `Config/Marrow.entitlements`; Xcode flips
it to `production` automatically when signing for distribution — don't hand-edit it.

Recommended standing config:
- **marrow** (prod): `APNS_USE_SANDBOX=false` — it only ever serves TestFlight builds.
- **marrow-dev**: `APNS_USE_SANDBOX=true` for day-to-day cable testing.

**Gotcha:** a TestFlight build pointed at the dev API (i.e. a Debug archive) is a
rare combo — TestFlight builds are Release/prod by default. If you ever knowingly
distribute a dev-API build via TestFlight, flip `marrow-dev` to
`APNS_USE_SANDBOX=false` for that window, or its pushes will 400 (BadDeviceToken).

---

## 4. Release a build (every time)

1. **Bump the build number** — one line in `Config/Shared.xcconfig`:
   ```
   CURRENT_PROJECT_VERSION = 2      # increment on EVERY upload; must be unique
   MARKETING_VERSION = 0.1.0        # bump only for a user-facing version change
   ```

2. **Archive + upload (CLI, preferred):**
   ```bash
   cd apps/marrow/ios
   export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer

   xcodebuild -project Marrow.xcodeproj -scheme Marrow \
     -configuration Release -destination 'generic/platform=iOS' \
     -archivePath build/Marrow.xcarchive archive

   xcodebuild -exportArchive \
     -archivePath build/Marrow.xcarchive \
     -exportOptionsPlist ExportOptions.plist \
     -exportPath build/export
   ```
   `ExportOptions.plist` has `destination=upload`, so the second command uploads
   straight to App Store Connect (automatic signing).

3. **Archive + upload (Xcode Organizer, alternative):**
   Xcode → Product → Archive → Organizer opens → Distribute App →
   App Store Connect → Upload → Automatically manage signing → Upload.

4. **Distribute on TestFlight** — App Store Connect → TestFlight. Internal builds
   become available to internal testers automatically after processing (~5-15 min),
   no Apple review. (First-ever build may ask for export-compliance: answer
   "no encryption beyond HTTPS" → uses standard exemption.)

5. **Install** — Leo + Beatriz open the TestFlight app → Marrow → Update/Install.

---

## 5. Regenerate the API client (after a backend spec change)

The Swift client is checked in and generated from the backend OpenAPI contract.
Needs local Xcode (`DEVELOPER_DIR`); not run in Linux CI.

```bash
# Preferred (Nx; marrow-ios is on the project graph):
npx nx run marrow-ios:codegen

# Or directly:
cd apps/marrow/ios
./scripts/generate-client.sh            # reads ../backend/openapi.json
# or: ./scripts/generate-client.sh path/to/openapi.json
```

Commit the regenerated client alongside the change.
