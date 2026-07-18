import SwiftUI

@main
struct MarrowApp: App {
    @State private var loggedIn = Keychain.load() != nil

    init() {
        // Re-register HealthKit observers on every launch — background
        // delivery relaunches the app and expects them immediately.
        HealthSyncService.shared.startIfEnabled()
    }

    var body: some Scene {
        WindowGroup {
            if loggedIn {
                HomeView(onLogout: { loggedIn = false })
            } else {
                LoginView(onLogin: { loggedIn = true })
            }
        }
    }
}
