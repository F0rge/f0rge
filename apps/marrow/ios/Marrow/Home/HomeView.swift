import SwiftUI

struct HomeView: View {
    let onLogout: () -> Void

    @State private var status: Components.Schemas.AuthStatus?
    @State private var todaySummary = "Loading…"
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            List {
                Section("Account") {
                    if let status {
                        LabeledContent("Email", value: status.email ?? "—")
                        LabeledContent("Handle", value: status.handle ?? "—")
                    } else if let errorMessage {
                        Text(errorMessage).foregroundStyle(.red)
                    } else {
                        ProgressView()
                    }
                }
                Section("Today") {
                    Text(todaySummary)
                }
                Section {
                    Button("Log out", role: .destructive) {
                        Task { await logout() }
                    }
                }
            }
            .navigationTitle("Marrow")
            .task { await load() }
        }
    }

    private func load() async {
        do {
            let output = try await API.client.meApiV1AuthMeGet()
            let me = try output.ok.body.json
            if me.authenticated {
                status = me
            } else {
                // Token expired or revoked — back to login.
                Keychain.delete()
                onLogout()
                return
            }
        } catch {
            errorMessage = "Could not load account: \(error.localizedDescription)"
        }
        await loadTodayEntry()
    }

    private func loadTodayEntry() async {
        let today = Date().formatted(.iso8601.year().month().day().dateSeparator(.dash))
        do {
            let output = try await API.client.getEntryApiV1EntriesDateGet(path: .init(date: today))
            switch output {
            case .ok(let ok):
                let entry = try ok.body.json
                todaySummary = "Overall \(entry.overall), bloating \(entry.bloating)"
            case .undocumented(404, _):
                todaySummary = "No entry logged today"
            case .unprocessableContent, .undocumented:
                todaySummary = "Could not load today's entry"
            }
        } catch {
            todaySummary = "Could not load today's entry"
        }
    }

    private func logout() async {
        // Best-effort server logout; local token removal is what matters.
        _ = try? await API.client.logoutApiV1AuthLogoutPost()
        Keychain.delete()
        onLogout()
    }
}
