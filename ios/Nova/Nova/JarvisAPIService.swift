import Foundation

struct JarvisStatus: Decodable {
    struct Features: Decodable {
        let tools_available: Bool
        let planner_available: Bool
        let confirmations_available: Bool
        let project_resolution_available: Bool
    }
    struct Capabilities: Decodable {
        let read_tools: [String]
        let write_tools: [String]
        let destructive_tools: [String]
    }
    let jarvis: Features
    let capabilities: Capabilities
}

struct JarvisEvent: Decodable {
    var type: String?
    var delta: String?
    var reply: String?
    var message: String?
    var error: String?
    var conversation_id: Int?
}

struct JarvisFailure: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

/// Uses the same cookie storage and authenticated session as the existing app.
struct JarvisAPIService {
    private let session = URLSession.shared
    private let baseURL = URL(string: "https://workfieldhq.com")!

    func get<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, response) = try await session.data(for: request)
        try validate(response, data: data)
        return try JSONDecoder().decode(T.self, from: data)
    }

    func chat(message: String, conversationID: Int?, csrfToken: String, agentMode: String = "default",
              receive: (JarvisEvent) -> Void) async throws {
        guard !csrfToken.isEmpty else {
            throw JarvisFailure(message: "Your session could not be verified. Please sign in again.")
        }
        var request = URLRequest(url: baseURL.appendingPathComponent("chat"))
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(csrfToken, forHTTPHeaderField: "X-CSRF-Token")
        var body: [String: Any] = ["message": message, "agent_mode": agentMode]
        if let conversationID { body["conversation_id"] = conversationID }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (bytes, response) = try await session.bytes(for: request)
        let http = response as? HTTPURLResponse
        let isJSON = http?.mimeType == "application/json"
        if isJSON || !(200..<300).contains(http?.statusCode ?? 0) {
            var data = Data()
            for try await byte in bytes {
                try Task.checkCancellation()
                data.append(byte)
                if data.count > 1_048_576 { throw JarvisFailure(message: "Unexpected server response.") }
            }
            try validate(response, data: data)
            var event = try decodeEvent(data)
            event.type = event.error == nil ? "done" : "error"
            if event.type == "done" { try validateCompletion(event) }
            receive(event)
            if event.type == "error" { throw JarvisFailure(message: event.message ?? event.error ?? "Request failed.") }
            return
        }
        try validate(response)
        guard http?.mimeType == "application/x-ndjson" else {
            throw JarvisFailure(message: "Unexpected response. Please sign in again.")
        }
        var completed = false
        for try await line in bytes.lines {
            try Task.checkCancellation()
            if line.trimmingCharacters(in: .whitespaces).isEmpty { continue }
            let event = try decodeEvent(Data(line.utf8))
            switch event.type {
            case "delta":
                guard event.delta != nil else { throw invalidStream() }
            case "done": try validateCompletion(event)
            case "error": break
            default: throw invalidStream()
            }
            receive(event)
            if event.type == "error" {
                throw JarvisFailure(message: event.message ?? "Nova could not complete the request.")
            }
            if event.type == "done" { completed = true; break }
        }
        guard completed else {
            throw JarvisFailure(message: "The connection ended before completion. Check your tasks before repeating a write command.")
        }
    }

    private func invalidStream() -> JarvisFailure {
        JarvisFailure(message: "Nova returned an invalid response. Check your tasks before repeating a write command.")
    }

    private func decodeEvent(_ data: Data) throws -> JarvisEvent {
        do {
            let event = try JSONDecoder().decode(JarvisEvent.self, from: data)
            if let id = event.conversation_id, id <= 0 { throw invalidStream() }
            return event
        } catch { throw invalidStream() }
    }

    private func validateCompletion(_ event: JarvisEvent) throws {
        guard event.conversation_id != nil,
              let reply = event.reply, !reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw invalidStream()
        }
    }

    private func validate(_ response: URLResponse, data: Data? = nil) throws {
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        if http.url?.path == "/login" || http.statusCode == 401 {
            throw JarvisFailure(message: "Your session expired. Please sign in again.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let event = data.flatMap { try? JSONDecoder().decode(JarvisEvent.self, from: $0) }
            if event?.error == "csrf_failed" {
                throw JarvisFailure(message: "Your session could not be verified. Please sign in again.")
            }
            throw JarvisFailure(message: event?.message ?? event?.error ?? "Nova returned HTTP \(http.statusCode). Please try again.")
        }
    }
}
