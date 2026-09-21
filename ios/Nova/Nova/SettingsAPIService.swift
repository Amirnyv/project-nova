import Foundation

struct NovaPlanResponse: Decodable {
    struct Subscription: Decodable {
        let plan: String
        let status: String
    }
    let subscription: Subscription
}

struct SettingsFailure: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

struct SettingsAPIService {
    func plan() async throws -> NovaPlanResponse {
        var request = URLRequest(url: URL(string: "https://workfieldhq.com/api/ai/usage")!)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 30
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse,
              http.statusCode == 200, http.mimeType == "application/json" else {
            throw SettingsFailure(message: "Plan information is unavailable. Check your connection and Nova session, then retry.")
        }
        return try JSONDecoder().decode(NovaPlanResponse.self, from: data)
    }

    func signOut(csrfToken: String) async throws {
        guard !csrfToken.isEmpty else { throw SettingsFailure(message: "Your session could not be verified. Please try again.") }
        var request = URLRequest(url: URL(string: "https://workfieldhq.com/logout")!)
        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.setValue(csrfToken, forHTTPHeaderField: "X-CSRF-Token")
        let (_, response) = try await URLSession.shared.data(for: request)
        // Flask logout redirects to /login; shared URLSession follows the redirect
        // and receives the updated session cookie before local account state resets.
        guard let http = response as? HTTPURLResponse,
              http.statusCode == 200, http.url?.path == "/login" else {
            throw SettingsFailure(message: "Nova could not confirm sign-out. Please try again.")
        }
    }
}
