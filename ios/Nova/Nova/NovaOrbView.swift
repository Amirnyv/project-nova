import SwiftUI

struct NovaOrbView: View {
    var size: CGFloat = 116

    var body: some View {
        Circle()
            .fill(RadialGradient(colors: [Color(red: 0.045, green: 0.10, blue: 0.17), Color(red: 0.008, green: 0.012, blue: 0.03)], center: .topLeading, startRadius: 0, endRadius: size * 0.85))
            .overlay {
                Circle().stroke(AngularGradient(colors: [.cyan.opacity(0.9), .blue.opacity(0.12), .purple.opacity(0.85), .purple.opacity(0.12), .cyan.opacity(0.9)], center: .center), lineWidth: 1)
            }
            .shadow(color: .cyan.opacity(0.12), radius: 10, x: -4)
            .shadow(color: .purple.opacity(0.12), radius: 10, x: 4)
            .frame(width: size, height: size)
            .accessibilityHidden(true)
    }
}
