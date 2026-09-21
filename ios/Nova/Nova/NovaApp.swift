//
//  NovaApp.swift
//  Nova
//
//  Created by sabina A on 9/8/26.
//

import SwiftUI

@main
struct NovaApp: App {
    @State private var sessionIdentity = UUID()
    var body: some Scene {
        WindowGroup {
            // Recreate account-scoped UI only after the server confirms logout.
            // This clears conversations and cached user data before another login.
            ContentView(onSignOut: { sessionIdentity = UUID() })
                .id(sessionIdentity)
        }
    }
}
