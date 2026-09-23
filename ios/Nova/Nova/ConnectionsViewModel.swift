import Foundation
import Combine

@MainActor
final class ConnectionsViewModel: ObservableObject {
    @Published private(set) var accounts: [NovaConnection] = []
    @Published private(set) var providers: [ConnectionProvider] = []
    @Published private(set) var loading = false
    @Published private(set) var loaded = false
    @Published private(set) var error: String?
    @Published var browserStarted = false
    private let api = ConnectionsAPIService()
    private var refreshAgain = false

    func refresh() async {
        if loading { refreshAgain = true; return }
        loading = true
        defer { loading = false }
        repeat {
            refreshAgain = false
            error = nil
            do {
                async let connections = api.connections()
                async let capabilities = api.capabilities()
                let result = try await (connections, capabilities)
                try Task.checkCancellation()
                accounts = result.0.connections
                providers = result.1.providers
                loaded = true
            } catch {
                if !Task.isCancelled {
                    self.error = error.localizedDescription
                    accounts = []
                    providers = []
                    loaded = false
                }
            }
        } while refreshAgain && !Task.isCancelled
    }
}
