import SwiftUI

struct SignInView: View {
    @Binding var isLoggedIn: Bool
    @Binding var csrfToken: String
    @Environment(\.dismiss) private var dismiss

    @State private var email = ""
    @State private var password = ""
    @State private var statusMessage = ""
    @State private var isLoading = false
    
    var body: some View {
        NovaLoginScene(email: $email, password: $password,
                       isLoading: isLoading, statusMessage: statusMessage) {
            guard !isLoading else { return }
            Task { await signIn() }
        }
    }

    @MainActor
    private func signIn() async {
        guard !isLoading else { return }
        isLoading = true
        statusMessage = ""

        defer {
            isLoading = false
        }

        do {
            guard let loginURL = URL(string: "https://workfieldhq.com/login") else {
                statusMessage = "Invalid login URL."
                return
            }

            let session = URLSession.shared

            // Step 1: Load login page to establish the Flask session
            // and retrieve the CSRF token.
            let (loginPageData, _) = try await session.data(from: loginURL)

            guard let loginPageHTML = String(
                data: loginPageData,
                encoding: .utf8
            ) else {
                statusMessage = "Could not load Nova login."
                return
            }

            guard let loginCSRFToken = extractCSRFToken(from: loginPageHTML) else {                statusMessage = "Could not verify Nova session."
                return
            }

            // Step 2: Send credentials + CSRF token.
            var request = URLRequest(url: loginURL)
            request.httpMethod = "POST"
            request.setValue(
                "application/x-www-form-urlencoded",
                forHTTPHeaderField: "Content-Type"
            )

            let body =
                "email=\(formEncode(email.lowercased()))" +
                "&password=\(formEncode(password))" +
                "&csrf_token=\(formEncode(loginCSRFToken))"

            request.httpBody = body.data(using: String.Encoding.utf8)
            let (_, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                statusMessage = "Nova did not return a valid response."
                return
            }

            let finalPath = httpResponse.url?.path ?? ""

            if httpResponse.statusCode == 200 && finalPath == "/app" {
                statusMessage = "Signed in successfully."
                csrfToken = loginCSRFToken
                isLoggedIn = true
                dismiss()
            } else {
                statusMessage = "Incorrect email or password."
            }

        } catch {
            statusMessage = "Could not connect to Nova."
            print("Login error:", error)
        }
    }

    private func extractCSRFToken(from html: String) -> String? {
        let pattern = #"name="csrf_token"\s+value="([^"]+)""#

        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return nil
        }

        let range = NSRange(
            html.startIndex..<html.endIndex,
            in: html
        )

        guard
            let match = regex.firstMatch(
                in: html,
                range: range
            ),
            let tokenRange = Range(
                match.range(at: 1),
                in: html
            )
        else {
            return nil
        }

        return String(html[tokenRange])
    }

    private func formEncode(_ value: String) -> String {
        value.addingPercentEncoding(
            withAllowedCharacters: .urlQueryAllowed
        ) ?? value
    }
}
