import SwiftUI

@main
struct MarrowApp: App {
    @State private var loggedIn = Keychain.load() != nil

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
