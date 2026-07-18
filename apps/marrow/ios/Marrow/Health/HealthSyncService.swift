import Foundation
import HealthKit

/// Reads HRV (SDNN), resting heart rate, and sleep analysis from HealthKit,
/// aggregates them into per-day rows, and POSTs them to
/// `/health-metrics/samples`. Read-only; the server upsert is idempotent, so
/// anchors are only advanced after a successful POST and retries are safe.
///
/// Day semantics mirror the legacy Health Auto Export path
/// (`apps/marrow/backend/app/services/health_import.py`):
/// - a sleep session belongs to the day it ENDS,
/// - sleep_hours = asleep-stage total (awake excluded),
/// - sleep_efficiency = asleep / (inBed if recorded, else session window) * 100,
/// - hrv_std is the sample stddev (0.0 for a single sample).
@MainActor
@Observable
final class HealthSyncService {
    static let shared = HealthSyncService()

    private let store = HKHealthStore()
    private let defaults = UserDefaults.standard
    private let calendar = Calendar.current

    private static let hrvType = HKQuantityType(.heartRateVariabilitySDNN)
    private static let restingHRType = HKQuantityType(.restingHeartRate)
    private static let sleepType = HKCategoryType(.sleepAnalysis)
    private static let allTypes: [HKSampleType] = [hrvType, restingHRType, sleepType]

    // ponytail: fixed 90-day backfill on first sync; widen if deeper history is wanted.
    private static let backfillDays = 90

    private enum Keys {
        static let enabled = "healthSync.enabled"
        static let lastSync = "healthSync.lastSync"
        static let lastResult = "healthSync.lastResult"
        static func anchor(_ type: HKSampleType) -> String { "healthSync.anchor.\(type.identifier)" }
    }

    private(set) var enabled: Bool
    private(set) var lastSync: Date?
    private(set) var lastResult: String
    private(set) var isSyncing = false
    private(set) var authError: String?

    private var observersRegistered = false
    private var syncTask: Task<Void, Never>?

    private init() {
        enabled = defaults.bool(forKey: Keys.enabled)
        lastSync = defaults.object(forKey: Keys.lastSync) as? Date
        lastResult = defaults.string(forKey: Keys.lastResult) ?? ""
    }

    var available: Bool { HKHealthStore.isHealthDataAvailable() }

    /// Call on every app launch: background delivery relaunches the app and
    /// expects observer queries to be re-registered immediately.
    func startIfEnabled() {
        guard enabled, available else { return }
        registerObservers()
    }

    /// First-time opt-in: request read authorization, then observe + sync.
    func enable() async {
        guard available else { return }
        do {
            try await store.requestAuthorization(toShare: [], read: Set(Self.allTypes))
        } catch {
            // Read-level denial is invisible to apps by design; this throws
            // only on hard failures (restrictions, missing entitlement).
            authError = "Health access denied — enable in Settings."
            return
        }
        authError = nil
        enabled = true
        defaults.set(true, forKey: Keys.enabled)
        registerObservers()
        await syncNow()
    }

    /// Runs a sync, coalescing concurrent triggers (the three observers often
    /// fire together after a Watch sync).
    func syncNow() async {
        if let syncTask {
            await syncTask.value
            return
        }
        let task = Task { await performSync() }
        syncTask = task
        await task.value
        syncTask = nil
    }

    // MARK: - Background delivery

    private func registerObservers() {
        guard !observersRegistered else { return }
        observersRegistered = true
        for type in Self.allTypes {
            let query = HKObserverQuery(sampleType: type, predicate: nil) { [weak self] _, completionHandler, error in
                // HealthKit stops waking us after 3 missed completions —
                // completionHandler must run on every path.
                guard error == nil, let self else {
                    completionHandler()
                    return
                }
                Task { @MainActor in
                    await self.syncNow()
                    completionHandler()
                }
            }
            store.execute(query)
            store.enableBackgroundDelivery(for: type, frequency: .immediate) { _, error in
                if let error {
                    // Unsigned/simulator builds without the entitlement land
                    // here; foreground sync still works.
                    print("Background delivery unavailable for \(type.identifier): \(error)")
                }
            }
        }
    }

    // MARK: - Sync

    private func performSync() async {
        isSyncing = true
        defer { isSyncing = false }
        do {
            let result = try await runSync()
            lastSync = Date()
            lastResult = result
            defaults.set(lastSync, forKey: Keys.lastSync)
            defaults.set(result, forKey: Keys.lastResult)
        } catch {
            // Anchors were not persisted — the next sync retries the same data.
            lastResult = "Sync failed: \(error.localizedDescription)"
            defaults.set(lastResult, forKey: Keys.lastResult)
        }
    }

    private func runSync() async throws -> String {
        let backfillStart = calendar.date(
            byAdding: .day, value: -Self.backfillDays, to: calendar.startOfDay(for: Date())
        )!
        let scope = HKQuery.predicateForSamples(withStart: backfillStart, end: nil)

        // 1. What changed since the last successful sync?
        let (newHRV, hrvAnchor) = try await anchoredFetch(
            .quantitySample(type: Self.hrvType, predicate: scope), anchorKey: Keys.anchor(Self.hrvType)
        )
        let (newRHR, rhrAnchor) = try await anchoredFetch(
            .quantitySample(type: Self.restingHRType, predicate: scope), anchorKey: Keys.anchor(Self.restingHRType)
        )
        let (newSleep, sleepAnchor) = try await anchoredFetch(
            .categorySample(type: Self.sleepType, predicate: scope), anchorKey: Keys.anchor(Self.sleepType)
        )

        func persistAnchors() {
            saveAnchor(hrvAnchor, key: Keys.anchor(Self.hrvType))
            saveAnchor(rhrAnchor, key: Keys.anchor(Self.restingHRType))
            saveAnchor(sleepAnchor, key: Keys.anchor(Self.sleepType))
        }

        // ponytail: deletions are ignored (HKDeletedObject carries no dates);
        // stale server values self-heal the next time that day gets new data.
        var touched = Set<Date>()
        for sample in newHRV + newRHR {
            touched.insert(calendar.startOfDay(for: sample.startDate))
        }
        for sample in newSleep {
            touched.insert(calendar.startOfDay(for: sample.startDate))
            touched.insert(calendar.startOfDay(for: sample.endDate))
        }
        guard let earliest = touched.min() else {
            persistAnchors()
            return "Up to date"
        }

        // 2. Anchored results alone can't produce day-level means — refetch
        //    every touched day in full and re-aggregate. ±1 day margin covers
        //    sleep sessions spanning midnight.
        let fetchStart = max(backfillStart, calendar.date(byAdding: .day, value: -1, to: earliest)!)
        let fetchScope = HKQuery.predicateForSamples(withStart: fetchStart, end: nil)
        let hrvSamples = try await fullFetch(.quantitySample(type: Self.hrvType, predicate: fetchScope))
        let rhrSamples = try await fullFetch(.quantitySample(type: Self.restingHRType, predicate: fetchScope))
        let sleepSamples = try await fullFetch(.categorySample(type: Self.sleepType, predicate: fetchScope))

        var emitDays = touched
        for day in touched {
            emitDays.insert(calendar.date(byAdding: .day, value: -1, to: day)!)
            emitDays.insert(calendar.date(byAdding: .day, value: 1, to: day)!)
        }
        let rows = buildDailyRows(hrv: hrvSamples, restingHR: rhrSamples, sleep: sleepSamples, days: emitDays)
        guard !rows.isEmpty else {
            persistAnchors()
            return "Up to date"
        }

        // 3. One batched POST; anchors advance only on success.
        let output = try await API.client.ingestHealthSamplesApiV1HealthMetricsSamplesPost(
            body: .json(.init(samples: rows))
        )
        switch output {
        case .ok(let ok):
            let response = try ok.body.json
            persistAnchors()
            return "Synced \(response.datesUpserted) day\(response.datesUpserted == 1 ? "" : "s")"
        case .unprocessableContent:
            throw SyncError.server("server rejected the payload (422)")
        case .undocumented(let status, _):
            throw SyncError.server("server error (\(status))")
        }
    }

    // MARK: - HealthKit queries

    private func anchoredFetch<S: HKSample>(
        _ predicate: HKSamplePredicate<S>,
        anchorKey: String
    ) async throws -> ([S], HKQueryAnchor?) {
        let anchor: HKQueryAnchor? = defaults.data(forKey: anchorKey).flatMap {
            try? NSKeyedUnarchiver.unarchivedObject(ofClass: HKQueryAnchor.self, from: $0)
        }
        let result = try await HKAnchoredObjectQueryDescriptor(
            predicates: [predicate], anchor: anchor, limit: nil
        ).result(for: store)
        return (result.addedSamples, result.newAnchor)
    }

    private func fullFetch<S: HKSample>(_ predicate: HKSamplePredicate<S>) async throws -> [S] {
        try await HKSampleQueryDescriptor(predicates: [predicate], sortDescriptors: [], limit: nil)
            .result(for: store)
    }

    private func saveAnchor(_ anchor: HKQueryAnchor?, key: String) {
        guard let anchor,
              let data = try? NSKeyedArchiver.archivedData(withRootObject: anchor, requiringSecureCoding: true)
        else { return }
        defaults.set(data, forKey: key)
    }

    // MARK: - Aggregation

    private func buildDailyRows(
        hrv: [HKQuantitySample],
        restingHR: [HKQuantitySample],
        sleep: [HKCategorySample],
        days emitDays: Set<Date>
    ) -> [Components.Schemas.HealthMetricCreate] {
        let ms = HKUnit.secondUnit(with: .milli)
        var hrvByDay: [Date: [Double]] = [:]
        for sample in hrv {
            hrvByDay[calendar.startOfDay(for: sample.startDate), default: []]
                .append(sample.quantity.doubleValue(for: ms))
        }
        let bpm = HKUnit.count().unitDivided(by: .minute())
        var rhrByDay: [Date: [Double]] = [:]
        for sample in restingHR {
            rhrByDay[calendar.startOfDay(for: sample.startDate), default: []]
                .append(sample.quantity.doubleValue(for: bpm))
        }
        let sleepByDay = aggregateSleep(sleep)

        let allDays = Set(hrvByDay.keys)
            .union(rhrByDay.keys)
            .union(sleepByDay.keys)
            .intersection(emitDays)

        var rows: [Components.Schemas.HealthMetricCreate] = []
        for day in allDays.sorted() {
            var row = Components.Schemas.HealthMetricCreate(date: Self.dayFormatter.string(from: day))
            if let values = hrvByDay[day] {
                row.hrvMean = round2(mean(values))
                row.hrvStd = round2(stddev(values))
            }
            if let values = rhrByDay[day] {
                row.restingHr = round2(mean(values))
            }
            if let sleepDay = sleepByDay[day] {
                let staged = sleepDay.deepMin + sleepDay.remMin + sleepDay.coreMin
                let asleep = staged + sleepDay.unspecifiedMin
                row.sleepHours = round2(asleep / 60)
                if sleepDay.deepMin > 0 { row.sleepDeepMin = round1(sleepDay.deepMin) }
                if sleepDay.remMin > 0 { row.sleepRemMin = round1(sleepDay.remMin) }
                if sleepDay.coreMin > 0 { row.sleepCoreMin = round1(sleepDay.coreMin) }
                if sleepDay.awakeMin > 0 { row.sleepAwakeMin = round1(sleepDay.awakeMin) }
                if staged > 0 {
                    row.sleepDeepPct = round1(sleepDay.deepMin / staged * 100)
                    row.sleepRemPct = round1(sleepDay.remMin / staged * 100)
                }
                if !sleepDay.efficiencies.isEmpty {
                    row.sleepEfficiency = round1(mean(sleepDay.efficiencies))
                }
                if let start = sleepDay.start { row.sleepStart = Self.timeFormatter.string(from: start) }
                if let end = sleepDay.end { row.sleepEnd = Self.timeFormatter.string(from: end) }
            }
            rows.append(row)
        }
        return rows
    }

    private struct SleepDay {
        var deepMin = 0.0, remMin = 0.0, coreMin = 0.0, awakeMin = 0.0, unspecifiedMin = 0.0
        var efficiencies: [Double] = []
        // Bed/wake times of the latest-ending session that day (legacy keeps the latest).
        var start: Date?
        var end: Date?
    }

    /// Groups sleep samples into sessions (a gap > 1h starts a new one) and
    /// attributes each session to the day it ENDS.
    private func aggregateSleep(_ samples: [HKCategorySample]) -> [Date: SleepDay] {
        struct Session {
            var start: Date
            var end: Date
            var deep = 0.0, rem = 0.0, core = 0.0, awake = 0.0, unspecified = 0.0, inBed = 0.0
        }
        var sessions: [Session] = []
        for sample in samples.sorted(by: { $0.startDate < $1.startDate }) {
            if sessions.isEmpty || sample.startDate.timeIntervalSince(sessions[sessions.count - 1].end) > 3600 {
                sessions.append(Session(start: sample.startDate, end: sample.endDate))
            }
            let i = sessions.count - 1
            sessions[i].end = max(sessions[i].end, sample.endDate)
            let minutes = sample.endDate.timeIntervalSince(sample.startDate) / 60
            switch HKCategoryValueSleepAnalysis(rawValue: sample.value) {
            case .asleepDeep: sessions[i].deep += minutes
            case .asleepREM: sessions[i].rem += minutes
            case .asleepCore: sessions[i].core += minutes
            case .asleepUnspecified: sessions[i].unspecified += minutes
            case .awake: sessions[i].awake += minutes
            case .inBed: sessions[i].inBed += minutes
            default: break
            }
        }

        var byDay: [Date: SleepDay] = [:]
        for session in sessions {
            // A Watch writes staged samples; a phone alongside can add
            // duplicate unspecified ones — count unspecified only when the
            // session has no staged data.
            let staged = session.deep + session.rem + session.core
            let asleep = staged > 0 ? staged : session.unspecified
            guard asleep > 0 else { continue }
            let day = calendar.startOfDay(for: session.end)
            var sleepDay = byDay[day, default: SleepDay()]
            sleepDay.deepMin += session.deep
            sleepDay.remMin += session.rem
            sleepDay.coreMin += session.core
            sleepDay.unspecifiedMin += staged > 0 ? 0 : session.unspecified
            sleepDay.awakeMin += session.awake
            let windowMin = session.end.timeIntervalSince(session.start) / 60
            let denominator = session.inBed > 0 ? session.inBed : windowMin
            if denominator > 0 {
                sleepDay.efficiencies.append(min(asleep / denominator * 100, 100))
            }
            if sleepDay.end.map({ session.end > $0 }) ?? true {
                sleepDay.start = session.start
                sleepDay.end = session.end
            }
            byDay[day] = sleepDay
        }
        return byDay
    }

    // MARK: - Helpers

    private enum SyncError: LocalizedError {
        case server(String)
        var errorDescription: String? {
            switch self {
            case .server(let message): message
            }
        }
    }

    private static let dayFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    private static let timeFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "HH:mm"
        return formatter
    }()

    private func mean(_ values: [Double]) -> Double {
        values.reduce(0, +) / Double(values.count)
    }

    private func stddev(_ values: [Double]) -> Double {
        guard values.count > 1 else { return 0 }
        let m = mean(values)
        return (values.map { ($0 - m) * ($0 - m) }.reduce(0, +) / Double(values.count - 1)).squareRoot()
    }

    private func round2(_ value: Double) -> Double { (value * 100).rounded() / 100 }
    private func round1(_ value: Double) -> Double { (value * 10).rounded() / 10 }
}
