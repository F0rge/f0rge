import SwiftUI

struct HomeView: View {
    let onLogout: () -> Void

    @State private var status: Components.Schemas.AuthStatus?
    @State private var todaySummary = "Loading…"
    @State private var errorMessage: String?
    private var health = HealthSyncService.shared
    @Bindable private var router = PushRouter.shared

    init(onLogout: @escaping () -> Void) {
        self.onLogout = onLogout
    }

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
                Section("Health") {
                    if !health.available {
                        Text("Health data isn't available on this device.")
                    } else if health.enabled {
                        LabeledContent(
                            "Last sync",
                            value: health.lastSync?.formatted(date: .abbreviated, time: .shortened) ?? "Never"
                        )
                        if !health.lastResult.isEmpty {
                            LabeledContent("Status", value: health.lastResult)
                        }
                        Button("Sync now") {
                            Task { await health.syncNow() }
                        }
                        .disabled(health.isSyncing)
                    } else {
                        Button("Enable Health sync") {
                            Task { await health.enable() }
                        }
                        if let authError = health.authError {
                            Text(authError).foregroundStyle(.red)
                        }
                    }
                }
                Section {
                    Button("Log out", role: .destructive) {
                        Task { await logout() }
                    }
                }
            }
            .navigationTitle("Marrow")
            .task { await load() }
            .sheet(item: $router.pendingTreatment) { route in
                TreatmentDetailView(treatmentID: route.id)
            }
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
        // Best-effort: drop this device's push token while we're still authed,
        // then server logout; local token removal is what matters.
        await Push.unregisterDevice()
        _ = try? await API.client.logoutApiV1AuthLogoutPost()
        Keychain.delete()
        onLogout()
    }
}
