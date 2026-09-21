import SwiftUI

struct NovaSpaceBackground: View {
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                Color(red: 0.008, green: 0.015, blue: 0.035)
                RadialGradient(colors: [.purple.opacity(0.18), .clear], center: .init(x: 0.9, y: 0.22), startRadius: 0, endRadius: geometry.size.width)
                RadialGradient(colors: [.blue.opacity(0.18), .clear], center: .init(x: 0.15, y: 0.45), startRadius: 0, endRadius: geometry.size.width * 0.8)
                Canvas { context, size in
                    for index in 0..<55 {
                        let x = CGFloat((index * 73 + 19) % 997) / 997 * size.width
                        let y = CGFloat((index * 137 + 43) % 991) / 991 * size.height * 0.65
                        let diameter: CGFloat = index % 9 == 0 ? 1.7 : 1
                        context.fill(Path(ellipseIn: CGRect(x: x, y: y, width: diameter, height: diameter)), with: .color(.white.opacity(index % 3 == 0 ? 0.45 : 0.2)))
                    }
                    // A shallow horizon extending beyond both screen edges, never a disk.
                    var horizon = Path()
                    horizon.move(to: CGPoint(x: -20, y: size.height * 0.59))
                    horizon.addQuadCurve(to: CGPoint(x: size.width + 20, y: size.height * 0.56), control: CGPoint(x: size.width * 0.52, y: size.height * 0.40))
                    var ground = horizon
                    ground.addLine(to: CGPoint(x: size.width + 20, y: size.height))
                    ground.addLine(to: CGPoint(x: -20, y: size.height))
                    ground.closeSubpath()
                    context.fill(ground, with: .linearGradient(Gradient(colors: [Color(red: 0.025, green: 0.065, blue: 0.10), Color(red: 0.006, green: 0.011, blue: 0.025)]), startPoint: CGPoint(x: 0, y: size.height * 0.48), endPoint: CGPoint(x: 0, y: size.height * 0.8)))
                    context.stroke(horizon, with: .color(.cyan.opacity(0.06)), lineWidth: 12)
                    context.stroke(horizon, with: .color(.cyan.opacity(0.12)), lineWidth: 4)
                    context.stroke(horizon, with: .color(.cyan.opacity(0.32)), lineWidth: 0.8)
                }
                RadialGradient(colors: [.cyan.opacity(0.14), .blue.opacity(0.06), .clear], center: .init(x: 0.87, y: 0.52), startRadius: 0, endRadius: geometry.size.width * 0.35)
            }
        }.ignoresSafeArea().accessibilityHidden(true).allowsHitTesting(false)
    }
}
