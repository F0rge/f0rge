import SwiftUI

@main
struct MarrowApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var loggedIn = Keychain.load() != nil

    init() {
        // Re-register HealthKit observers on every launch — background
        // delivery relaunches the app and expects them immediately.
        HealthSyncService.shared.startIfEnabled()
        // Re-register with APNs every authenticated launch — the backend
        // upsert is idempotent and this heals failed/stale registrations.
        if Keychain.load() != nil {
            Push.register()
        }
    }

    var body: some Scene {
        WindowGroup {
            if loggedIn {
                HomeView(onLogout: { loggedIn = false })
            } else {
                LoginView(onLogin: {
                    loggedIn = true
                    Push.register()
                })
            }
        }
    }
}
