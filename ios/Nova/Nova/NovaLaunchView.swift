import SwiftUI

/// One finite, cancellable sequence per unauthenticated view lifetime.
struct NovaLaunchView: View {
    let completion: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @State private var phase = 0
    @State private var finished = false

    var body: some View {
        ZStack {
            Color(red: 0.005, green: 0.008, blue: 0.02).ignoresSafeArea()
            NovaSpaceBackground().opacity(phase >= 1 ? 1 : 0)
            VStack(spacing: 22) {
                NovaOrbView()
                    .opacity(phase >= 2 ? 1 : 0)
                    .scaleEffect(reduceMotion || phase >= 2 ? 1 : 0.92)
                Text("NOVA").font(.system(.largeTitle, design: .rounded).weight(.light))
                    .tracking(12).padding(.leading, 12).foregroundStyle(.white)
                    .accessibilityLabel("Nova")
                    .opacity(phase >= 3 ? 1 : 0)
                Text("WORK SMARTER.\nGO FURTHER.")
                    .font(.subheadline.weight(.medium)).tracking(3).lineSpacing(6)
                    .multilineTextAlignment(.center).foregroundStyle(.white.opacity(0.8))
                    .opacity(phase >= 4 ? 1 : 0)
            }
            .padding(24)
            .offset(y: !reduceMotion && phase == 5 ? -16 : 0)
            .opacity(phase == 5 ? 0 : 1)
        }
        .task {
            if reduceMotion { finish(); return }
            do {
                try await Task.sleep(for: .milliseconds(300)); advance(1)
                try await Task.sleep(for: .milliseconds(200)); advance(2)
                try await Task.sleep(for: .milliseconds(300)); advance(3)
                try await Task.sleep(for: .milliseconds(300)); advance(4)
                try await Task.sleep(for: .milliseconds(500)); advance(5)
                try await Task.sleep(for: .milliseconds(300)); finish()
            } catch { /* Disappearing cancels the sequence; no authentication work occurs here. */ }
        }
        .onChange(of: reduceMotion) { _, enabled in if enabled { finish() } }
        .onChange(of: scenePhase) { _, phase in if phase == .background { finish() } }
    }

    private func advance(_ next: Int) {
        guard !finished else { return }
        withAnimation(.easeInOut(duration: 0.35)) { phase = next }
    }

    private func finish() {
        guard !finished else { return }
        finished = true
        completion()
    }
}
