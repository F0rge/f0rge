import SwiftUI
import UserNotifications

/// A dose-reminder body tap routes here; HomeView presents the detail sheet.
struct TreatmentRoute: Identifiable {
    let id: Int
}

@MainActor
@Observable
final class PushRouter {
    static let shared = PushRouter()
    var pendingTreatment: TreatmentRoute?
}

/// APNs registration + dose logging shared by the notification action and
/// TreatmentDetailView.
enum Push {
    static let tokenDefaultsKey = "apns.deviceToken"

    /// Request notification permission and (re)register with APNs. Called after
    /// login and on every authenticated launch — the system prompt only shows
    /// once, and the backend POST /devices is an idempotent upsert.
    static func register() {
        Task { @MainActor in
            let granted = (try? await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound, .badge])) ?? false
            guard granted else { return }
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    /// Best-effort server-side token removal — call before dropping the auth token.
    static func unregisterDevice() async {
        guard let token = UserDefaults.standard.string(forKey: tokenDefaultsKey) else { return }
        _ = try? await API.client.unregisterDeviceApiV1DevicesTokenDelete(path: .init(token: token))
    }

    /// That date's protocol row for a treatment, or nil when it isn't in the
    /// protocol. Shared by the LOG_DOSE read-before-write and TreatmentDetailView.
    static func protocolItem(id: Int, date: String) async throws -> Components.Schemas.ProtocolItem? {
        try await API.client
            .getProtocolApiV1TreatmentsProtocolGet(query: .init(date: date))
            .ok.body.json.items
            .first { $0.id == id }
    }

    /// Log a dose from the reminder's LOG_DOSE action. The PUT takes an
    /// absolute count and slot k means "after taking, you're at k today", so
    /// read the current count first: a late or duplicate tap never lowers a
    /// count the user already pushed higher manually, and a satisfied slot is
    /// a no-op. If the read fails we still PUT the slot value (best effort).
    static func logDose(treatmentID: Int, date: String, slot: Int) async {
        if let current = try? await protocolItem(id: treatmentID, date: date)?.dosesTaken,
            current >= slot
        {
            return
        }
        do {
            _ = try await API.client.logTreatmentDoseApiV1TreatmentsTreatmentIdLogPut(
                path: .init(treatmentId: treatmentID),
                body: .json(.init(date: date, dosesTaken: slot))
            )
        } catch {
            print("Log-dose PUT failed for treatment \(treatmentID): \(error)")
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // Delegate + categories must be in place before launch finishes so a
        // cold background launch from a notification action is handled.
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        // No .foreground option: LOG_DOSE runs in the background without opening the app.
        let logDose = UNNotificationAction(identifier: "LOG_DOSE", title: "Log dose", options: [])
        center.setNotificationCategories([
            UNNotificationCategory(
                identifier: "DOSE_REMINDER",
                actions: [logDose],
                intentIdentifiers: []
            )
        ])
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        UserDefaults.standard.set(token, forKey: Push.tokenDefaultsKey)
        // Fire-and-forget: registration re-runs on every launch, so a failed
        // POST self-heals next time.
        Task {
            do {
                _ = try await API.client.registerDeviceApiV1DevicesPost(
                    body: .json(.init(token: token, platform: "ios"))
                )
            } catch {
                print("Device registration failed: \(error)")
            }
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        print("APNs registration failed: \(error)")
    }

    // MARK: - UNUserNotificationCenterDelegate

    /// Show dose reminders as a banner even when the app is foregrounded.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let content = response.notification.request.content
        // The backend serializes treatment_id as a JSON string (str(treatment.id)),
        // so it arrives as NSString — read it as String, then parse the Int the
        // generated client expects.
        guard content.categoryIdentifier == "DOSE_REMINDER",
              let treatmentID = (content.userInfo["treatment_id"] as? String).flatMap(Int.init)
        else {
            completionHandler()
            return
        }
        switch response.actionIdentifier {
        case "LOG_DOSE":
            guard let date = content.userInfo["date"] as? String else {
                completionHandler()
                return
            }
            let slot = (content.userInfo["slot"] as? NSNumber)?.intValue
                ?? (content.userInfo["slot"] as? Int)
                ?? 1
            Task { @MainActor in
                var bgTask = UIBackgroundTaskIdentifier.invalid
                bgTask = UIApplication.shared.beginBackgroundTask(withName: "log-dose") {
                    UIApplication.shared.endBackgroundTask(bgTask)
                    bgTask = .invalid
                }
                await Push.logDose(treatmentID: treatmentID, date: date, slot: slot)
                completionHandler()
                if bgTask != .invalid {
                    UIApplication.shared.endBackgroundTask(bgTask)
                }
            }
        case UNNotificationDefaultActionIdentifier:
            // Body tap — open the treatment detail sheet.
            Task { @MainActor in
                PushRouter.shared.pendingTreatment = TreatmentRoute(id: treatmentID)
            }
            completionHandler()
        default:
            completionHandler()
        }
    }
}
