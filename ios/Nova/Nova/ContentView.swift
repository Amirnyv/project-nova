import SwiftUI

struct ContentView: View {
    @State private var showSignIn = false
    @State private var isLoggedIn = false
    
    var body: some View {
        if isLoggedIn {
            Text("Logged in to Nova")
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.black)
        } else {
            ZStack {
                Color.black
                    .ignoresSafeArea()
                
                VStack(spacing: 24) {
                    Spacer()
                    
                    Text("✦")
                        .font(.system(size: 54))
                        .foregroundStyle(.white)
                    
                    Text("Nova")
                        .font(.system(size: 46, weight: .bold))
                        .foregroundStyle(.white)
                    
                    Text("Your AI workspace.")
                        .font(.title3)
                        .foregroundStyle(.gray)
                    
                    Spacer()
                    
                    VStack(spacing: 14) {
                        Button {
                            showSignIn = true
                        } label: {
                            Text("Sign In")
                                .fontWeight(.semibold)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(.white)
                                .foregroundStyle(.black)
                                .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                        
                        Button {
                            print("Create Account tapped")
                        } label: {
                            Text("Create Account")
                                .fontWeight(.semibold)
                                .frame(maxWidth: .infinity)
                                .padding()
                                .foregroundStyle(.white)
                                .overlay {
                                    RoundedRectangle(cornerRadius: 16)
                                        .stroke(.gray.opacity(0.6), lineWidth: 1)
                                }
                        }
                    }
                    
                    Text("Project Nova")
                        .font(.caption)
                        .foregroundStyle(.gray)
                    
                    Spacer()
                        .frame(height: 20)
                }
                .padding(.horizontal, 24)
            }
            .sheet(isPresented: $showSignIn) {
                SignInView(isLoggedIn: $isLoggedIn)
            }
        }
    }
}
struct SignInView: View {
    @Binding var isLoggedIn: Bool
    @Environment(\.dismiss) private var dismiss

    @State private var email = ""
    @State private var password = ""
    @State private var statusMessage = ""
    @State private var isLoading = false

    var body: some View {
        ZStack {
            Color.black
                .ignoresSafeArea()

            VStack(spacing: 20) {
                HStack {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundStyle(.gray)

                    Spacer()
                }

                Spacer()

                Text("Welcome back")
                    .font(.largeTitle.bold())
                    .foregroundStyle(.white)

                Text("Sign in to Nova")
                    .foregroundStyle(.gray)

                TextField("Email", text: $email)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                    .autocorrectionDisabled()
                    .padding()
                    .background(Color.white.opacity(0.08))
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 14))

                SecureField("Password", text: $password)
                    .padding()
                    .background(Color.white.opacity(0.08))
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 14))

                Button {
                    Task {
                        await signIn()
                    }
                } label: {
                    if isLoading {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                            .padding()
                    } else {
                        Text("Sign In")
                            .fontWeight(.semibold)
                            .frame(maxWidth: .infinity)
                            .padding()
                    }
                }
                .background(.white)
                .foregroundStyle(.black)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .disabled(isLoading)

                if !statusMessage.isEmpty {
                    Text(statusMessage)
                        .font(.footnote)
                        .foregroundStyle(.gray)
                        .multilineTextAlignment(.center)
                }

                Spacer()
            }
            .padding(24)
        }
    }

    @MainActor
    private func signIn() async {
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

            guard let csrfToken = extractCSRFToken(from: loginPageHTML) else {
                statusMessage = "Could not verify Nova session."
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
                "&csrf_token=\(formEncode(csrfToken))"

            request.httpBody = body.data(using: .utf8)

            let (_, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                statusMessage = "Nova did not return a valid response."
                return
            }

            let finalPath = httpResponse.url?.path ?? ""

            if httpResponse.statusCode == 200 && finalPath == "/app" {
                statusMessage = "Signed in successfully."
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
#Preview {
    ContentView()
}
