import Foundation
import HTTPTypes
import OpenAPIRuntime
import OpenAPIURLSession

/// Injects `Authorization: Bearer <token>` from the Keychain into every request.
/// Official swift-openapi auth-client-middleware pattern.
struct AuthMiddleware: ClientMiddleware {
    func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        var request = request
        if let token = Keychain.load() {
            request.headerFields[.authorization] = "Bearer \(token)"
        }
        return try await next(request, body, baseURL)
    }
}

enum API {
    /// Base URL comes from Config/{Dev,Prod}.xcconfig via the Info.plist APIBaseURL key.
    static let client: Client = {
        guard let urlString = Bundle.main.object(forInfoDictionaryKey: "APIBaseURL") as? String,
              let url = URL(string: urlString)
        else {
            fatalError("APIBaseURL missing from Info.plist — check Config/*.xcconfig")
        }
        return Client(
            serverURL: url,
            transport: URLSessionTransport(),
            middlewares: [AuthMiddleware()]
        )
    }()

    /// Best-effort extraction of FastAPI's `{"detail": "..."}` from an undocumented response.
    static func errorDetail(from payload: UndocumentedPayload) async -> String? {
        guard let body = payload.body,
              let data = try? await Data(collecting: body, upTo: 16 * 1024)
        else { return nil }
        return (try? JSONDecoder().decode([String: String].self, from: data))?["detail"]
    }
}
