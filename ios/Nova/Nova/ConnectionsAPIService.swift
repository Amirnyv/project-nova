import Foundation

// Contract verified in origin/feature/jarvis-phase-1 (90fad39).
// Decode only account metadata; credentials are never requested or retained.
struct NovaConnection: Decodable, Identifiable {
    let id: Int
    let provider: String
    let provider_account_id: String?
    let display_name: String?
    let status: String
    let connection_type: String
    let created_at: String?
    let updated_at: String?
}
struct ConnectionsResponse: Decodable { let connections: [NovaConnection] }
struct ConnectionCapabilitiesResponse: Decodable { let providers: [ConnectionProvider] }
struct ConnectionProvider: Decodable, Identifiable {
    // This nested payload intentionally has no database id or timestamps.
    struct Account: Decodable {
        let provider: String
        let provider_account_id: String?
        let display_name: String?
        let status: String
        let connection_type: String
    }
    struct Service: Decodable, Identifiable {
        let id: String
        let display_name: String
        let capabilities: [String]
    }
    let provider: String
    let display_name: String
    let connection_type: String
    let oauth: Bool
    let connected: Bool
    let services: [Service]
    let accounts: [Account]
    var id: String { provider }
}

struct ConnectionsAPIService {
    static let googleAuthorizationURL = URL(string: "https://workfieldhq.com/api/connections/google/connect")!
    func connections() async throws -> ConnectionsResponse { try await get("api/connections") }
    func capabilities() async throws -> ConnectionCapabilitiesResponse { try await get("api/connections/capabilities") }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: URL(string: "https://workfieldhq.com/\(path)")!)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        try Task.checkCancellation()
        guard let http = response as? HTTPURLResponse else { throw failure("Nova returned an invalid response.") }
        if http.statusCode == 401 || http.url?.path == "/login" { throw failure("Your Nova session expired. Sign in again to view connections.") }
        if http.statusCode == 404 { throw failure("Connections is not available on this Nova server yet.") }
        guard (200..<300).contains(http.statusCode) else { throw failure("Connections could not load (HTTP \(http.statusCode)). Please retry.") }
        guard http.mimeType == "application/json" else { throw failure("Unexpected server response. Check your Nova session and retry.") }
        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw failure("Nova returned an unsupported Connections response. Please retry later.") }
    }
    private func failure(_ message: String) -> NSError {
        NSError(domain: "Nova.Connections", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }
}
