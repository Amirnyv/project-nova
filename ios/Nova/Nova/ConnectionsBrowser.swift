import SwiftUI
import SafariServices

/// System browser with its own cookie jar. No attempt to export Nova cookies,
/// intercept Google's credentials, or treat /app navigation as native success.
struct ConnectionsBrowser: UIViewControllerRepresentable {
    let onClose: () -> Void
    func makeCoordinator() -> Coordinator { Coordinator(onClose: onClose) }
    func makeUIViewController(context: Context) -> SFSafariViewController {
        let controller = SFSafariViewController(url: ConnectionsAPIService.googleAuthorizationURL)
        controller.delegate = context.coordinator
        controller.dismissButtonStyle = .done
        return controller
    }
    func updateUIViewController(_ controller: SFSafariViewController, context: Context) {}
    final class Coordinator: NSObject, SFSafariViewControllerDelegate {
        let onClose: () -> Void
        init(onClose: @escaping () -> Void) { self.onClose = onClose }
        func safariViewControllerDidFinish(_ controller: SFSafariViewController) { onClose() }
    }
}
