import SwiftUI

/// Minimal tap-through screen for a dose-reminder body tap: treatment name,
/// today's dose count, and a manual "Log dose" button. Not a treatments manager.
struct TreatmentDetailView: View {
    let treatmentID: Int

    @State private var item: Components.Schemas.ProtocolItem?
    @State private var errorMessage: String?
    @State private var busy = false

    private let today = Date().apiDay

    var body: some View {
        NavigationStack {
            List {
                if let item {
                    Section(item.name) {
                        LabeledContent("Doses today", value: dosesLine(item))
                        Button(busy ? "Logging…" : "Log dose") {
                            Task { await logDose() }
                        }
                        .disabled(busy)
                    }
                } else if let errorMessage {
                    Text(errorMessage).foregroundStyle(.red)
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Treatment")
            .task { await load() }
        }
    }

    private func dosesLine(_ item: Components.Schemas.ProtocolItem) -> String {
        if let perDay = item.dosesPerDay {
            return "\(item.dosesTaken) of \(perDay)"
        }
        return "\(item.dosesTaken)"
    }

    private func load() async {
        do {
            guard let found = try await Push.protocolItem(id: treatmentID, date: today) else {
                errorMessage = "This treatment isn't in today's protocol."
                return
            }
            item = found
        } catch {
            errorMessage = "Could not load treatment: \(error.localizedDescription)"
        }
    }

    private func logDose() async {
        guard let current = item else { return }
        busy = true
        defer { busy = false }
        do {
            let result = try await API.client.logTreatmentDoseApiV1TreatmentsTreatmentIdLogPut(
                path: .init(treatmentId: treatmentID),
                body: .json(.init(date: today, dosesTaken: current.dosesTaken + 1))
            ).ok.body.json
            item?.dosesTaken = result.log.dosesTaken
        } catch {
            errorMessage = "Could not log dose: \(error.localizedDescription)"
        }
    }
}
