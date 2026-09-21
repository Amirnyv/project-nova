import SwiftUI

/// Presentation only. Credentials stay in the existing SignInView's transient state.
struct NovaLoginScene: View {
    @Binding var email: String
    @Binding var password: String
    let isLoading: Bool
    let statusMessage: String
    let signIn: () -> Void
    @State private var revealed = false
    @State private var launchComplete = false
    @State private var showPassword = false
    @FocusState private var focused: Field?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    private enum Field: Hashable { case email, password }

    var body: some View {
        ZStack {
            NovaSpaceBackground()
            ScrollView {
                VStack(spacing: 32) {
                    VStack(spacing: 8) {
                        NovaOrbView(size: 64)
                        Text("NOVA")
                            .font(.system(.title, design: .rounded).weight(.light))
                            .tracking(12).padding(.leading, 12)
                            .shadow(color: .cyan.opacity(0.35), radius: 12)
                            .accessibilityLabel("Nova")
                        Text("WORK SMARTER.\nGO FURTHER.")
                            .font(.subheadline.weight(.medium)).tracking(3)
                            .lineSpacing(6).multilineTextAlignment(.center)
                            .foregroundStyle(Color(red: 0.73, green: 0.81, blue: 0.92))
                    }
                    .opacity(revealed ? 1 : 0.15)
                    .onTapGesture { focused = nil }

                    VStack(alignment: .leading, spacing: 13) {
                        glassField(icon: "envelope", field: .email) {
                            TextField("Enter your email", text: $email, prompt: Text("Enter your email").foregroundStyle(.white.opacity(0.65)))
                                .textContentType(.username).keyboardType(.emailAddress)
                                .textInputAutocapitalization(.never).autocorrectionDisabled()
                                .focused($focused, equals: .email).submitLabel(.next)
                                .onSubmit { focused = .password }
                                .accessibilityLabel("Email")
                        }
                        glassField(icon: "lock", field: .password) {
                            Group {
                                if showPassword { TextField("Enter your password", text: $password, prompt: Text("Enter your password").foregroundStyle(.white.opacity(0.65))) }
                                else { SecureField("Enter your password", text: $password, prompt: Text("Enter your password").foregroundStyle(.white.opacity(0.65))) }
                            }
                            .textContentType(.password).textInputAutocapitalization(.never)
                            .autocorrectionDisabled().focused($focused, equals: .password)
                            .submitLabel(.go).onSubmit(submit).accessibilityLabel("Password")
                            Button {
                                showPassword.toggle()
                                focused = .password
                            } label: {
                                Image(systemName: showPassword ? "eye.slash" : "eye")
                                    .frame(width: 44, height: 44)
                            }
                            .foregroundStyle(.white.opacity(0.8))
                            .accessibilityLabel(showPassword ? "Hide password" : "Show password")
                        }
                        Button(action: submit) {
                            HStack(spacing: 12) {
                                if isLoading { ProgressView().tint(.white) }
                                Text(isLoading ? "Signing in…" : "Sign In").fontWeight(.semibold)
                                if !isLoading { Image(systemName: "arrow.right") }
                            }
                            .frame(maxWidth: .infinity, minHeight: 56)
                            .background(LinearGradient(colors: [Color(red: 0.42, green: 0.22, blue: 0.82), Color(red: 0.13, green: 0.3, blue: 0.7), Color(red: 0.03, green: 0.39, blue: 0.52)], startPoint: .leading, endPoint: .trailing), in: RoundedRectangle(cornerRadius: 17))
                            .overlay(RoundedRectangle(cornerRadius: 17).stroke(.white.opacity(0.18)))
                            .shadow(color: .purple.opacity(0.2), radius: 12, y: 4)
                        }.buttonStyle(.plain).disabled(isLoading)
                        if !statusMessage.isEmpty {
                            Text(statusMessage).font(.footnote).foregroundStyle(.white)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(12).background(.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
                                .accessibilityLabel("Sign in status: \(statusMessage)")
                        }
                    }
                    .offset(y: reduceMotion || revealed ? 0 : 14)
                    .opacity(revealed ? 1 : 0.25)
                    Text("Your AI workspace, ready when you are.")
                        .font(.caption).foregroundStyle(.white.opacity(0.65))
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: 380)
                .padding(.horizontal, 24).padding(.top, 32).padding(.bottom, 30)
                .frame(maxWidth: .infinity)
            }
            .scrollDismissesKeyboard(.interactively)
            .opacity(launchComplete ? 1 : 0)
            .allowsHitTesting(launchComplete)
            .accessibilityHidden(!launchComplete)
            if !launchComplete {
                NovaLaunchView {
                    withAnimation(reduceMotion ? .easeOut(duration: 0.15) : .easeInOut(duration: 0.3)) {
                        launchComplete = true
                        revealed = true
                    }
                }.transition(.opacity)
            }
        }
        .foregroundStyle(.white).preferredColorScheme(.dark)
        .onChange(of: reduceMotion) { _, enabled in
            if enabled { finishIntro() }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active { showPassword = false; finishIntro() }
        }
    }

    private func submit() {
        guard !isLoading else { return }
        focused = nil
        signIn()
    }

    private func finishIntro() {
        var transaction = Transaction()
        transaction.disablesAnimations = true
        withTransaction(transaction) { revealed = true }
    }

    private func glassField<Content: View>(icon: String, field: Field, @ViewBuilder content: () -> Content) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon).foregroundStyle(focused == field ? .cyan : .white.opacity(0.65)).accessibilityHidden(true)
            content()
        }
        .padding(.leading, 16).padding(.trailing, 8).padding(.vertical, 6)
        .frame(minHeight: 56)
        .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 17))
        .overlay(RoundedRectangle(cornerRadius: 17).stroke(focused == field ? .cyan.opacity(0.8) : .white.opacity(0.2), lineWidth: 1))
        .shadow(color: focused == field ? .cyan.opacity(0.1) : .clear, radius: 8)
        .animation(reduceMotion ? nil : .easeOut(duration: 0.18), value: focused)
    }
}
