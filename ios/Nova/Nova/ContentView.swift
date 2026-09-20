import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @State private var showSignIn = false
    @State private var isLoggedIn = false
    @State private var showChat = false
    @State private var showProjects = false
    @State private var csrfToken = ""
    
    var body: some View {
        if isLoggedIn {

            ZStack {

                LinearGradient(
                    colors: [
                        Color(red: 0.027, green: 0.035, blue: 0.078),
                        Color(red: 0.024, green: 0.031, blue: 0.071),
                        Color(red: 0.020, green: 0.027, blue: 0.059)
                    ],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .ignoresSafeArea()

                RadialGradient(
                    colors: [
                        Color.purple.opacity(0.25),
                        Color.clear
                    ],
                    center: .topTrailing,
                    startRadius: 10,
                    endRadius: 230
                )
                .ignoresSafeArea()

                ScrollView {

                    VStack(spacing: 16) {

                        // MARK: - HERO

                        VStack(
                            alignment: .leading,
                            spacing: 16
                        ) {

                            HStack(spacing: 8) {

                                Circle()
                                    .fill(
                                        Color(
                                            red: 0.55,
                                            green: 0.36,
                                            blue: 0.96
                                        )
                                    )
                                    .frame(
                                        width: 7,
                                        height: 7
                                    )
                                    .shadow(
                                        color: .purple,
                                        radius: 7
                                    )

                                Text("NOVA WORKSPACE")
                                    .font(
                                        .system(
                                            size: 10,
                                            weight: .heavy
                                        )
                                    )
                                    .tracking(1.2)
                                    .foregroundStyle(
                                        Color(
                                            red: 0.65,
                                            green: 0.55,
                                            blue: 0.98
                                        )
                                    )
                            }

                            VStack(
                                alignment: .leading,
                                spacing: 7
                            ) {

                                Text("Good Evening,")
                                    .font(
                                        .system(
                                            size: 27,
                                            weight: .bold
                                        )
                                    )
                                    .foregroundStyle(.white)

                                Text("Welcome to Nova")
                                    .font(
                                        .system(
                                            size: 27,
                                            weight: .bold
                                        )
                                    )
                                    .foregroundStyle(
                                        LinearGradient(
                                            colors: [
                                                .white,
                                                Color(
                                                    red: 0.72,
                                                    green: 0.65,
                                                    blue: 1.0
                                                )
                                            ],
                                            startPoint: .leading,
                                            endPoint: .trailing
                                        )
                                    )

                                Text(
                                    "Your workspace is ready. What are we building today?"
                                )
                                .font(.system(size: 13))
                                .foregroundStyle(.gray)
                                .lineSpacing(3)
                            }

                            HStack(spacing: 9) {

                                Button {
                                    showChat = true
                                } label: {

                                    HStack(spacing: 7) {

                                        Text("✦")

                                        Text("Ask Nova")
                                            .fontWeight(.semibold)
                                    }
                                    .frame(
                                        maxWidth: .infinity,
                                        minHeight: 44
                                    )
                                    .foregroundStyle(.white)
                                    .background(
                                        Color.white.opacity(0.07)
                                    )
                                    .overlay {

                                        RoundedRectangle(
                                            cornerRadius: 13
                                        )
                                        .stroke(
                                            Color.white.opacity(0.10),
                                            lineWidth: 1
                                        )
                                    }
                                    .clipShape(
                                        RoundedRectangle(
                                            cornerRadius: 13
                                        )
                                    )
                                }

                                Button {
                                    print("New Project tapped")
                                } label: {

                                    HStack(spacing: 7) {

                                        Text("＋")

                                        Text("New Project")
                                            .fontWeight(.semibold)
                                    }
                                    .frame(
                                        maxWidth: .infinity,
                                        minHeight: 44
                                    )
                                    .foregroundStyle(.white)
                                    .background(
                                        LinearGradient(
                                            colors: [
                                                Color(
                                                    red: 0.49,
                                                    green: 0.31,
                                                    blue: 0.94
                                                ),
                                                Color(
                                                    red: 0.38,
                                                    green: 0.23,
                                                    blue: 0.84
                                                )
                                            ],
                                            startPoint: .topLeading,
                                            endPoint: .bottomTrailing
                                        )
                                    )
                                    .clipShape(
                                        RoundedRectangle(
                                            cornerRadius: 13
                                        )
                                    )
                                }
                            }
                        }
                        .padding(16)
                        .background(
                            Color.white.opacity(0.035)
                        )
                        .overlay {

                            RoundedRectangle(
                                cornerRadius: 18
                            )
                            .stroke(
                                Color.white.opacity(0.08),
                                lineWidth: 1
                            )
                        }
                        .clipShape(
                            RoundedRectangle(
                                cornerRadius: 18
                            )
                        )

                        // MARK: - QUICK ACTIONS

                        HStack(spacing: 10) {

                            Button {
                                showProjects = true
                            } label: {

                                VStack(
                                    alignment: .leading,
                                    spacing: 8
                                ) {

                                    Text("◇")
                                        .font(.system(size: 18))
                                        .foregroundStyle(
                                            Color.purple.opacity(0.9)
                                        )
                                        .frame(
                                            width: 34,
                                            height: 34
                                        )
                                        .background(
                                            Color.purple.opacity(0.12)
                                        )
                                        .clipShape(
                                            RoundedRectangle(
                                                cornerRadius: 9
                                            )
                                        )

                                    Text("Projects")
                                        .font(
                                            .system(
                                                size: 13,
                                                weight: .bold
                                            )
                                        )
                                        .foregroundStyle(.white)

                                    Text("Manage your workspaces")
                                        .font(.system(size: 11))
                                        .foregroundStyle(.gray)
                                        .multilineTextAlignment(.leading)
                                }
                                .frame(
                                    maxWidth: .infinity,
                                    minHeight: 104,
                                    alignment: .leading
                                )
                                .padding(14)
                                .background(
                                    Color.white.opacity(0.035)
                                )
                                .overlay {

                                    RoundedRectangle(
                                        cornerRadius: 16
                                    )
                                    .stroke(
                                        Color.white.opacity(0.08),
                                        lineWidth: 1
                                    )
                                }
                                .clipShape(
                                    RoundedRectangle(
                                        cornerRadius: 16
                                    )
                                )
                            }

                            Button {
                                showChat = true
                            } label: {

                                VStack(
                                    alignment: .leading,
                                    spacing: 8
                                ) {

                                    Text("✦")
                                        .font(.system(size: 18))
                                        .foregroundStyle(
                                            Color.purple.opacity(0.9)
                                        )
                                        .frame(
                                            width: 34,
                                            height: 34
                                        )
                                        .background(
                                            Color.purple.opacity(0.12)
                                        )
                                        .clipShape(
                                            RoundedRectangle(
                                                cornerRadius: 9
                                            )
                                        )

                                    Text("Nova Chat")
                                        .font(
                                            .system(
                                                size: 13,
                                                weight: .bold
                                            )
                                        )
                                        .foregroundStyle(.white)

                                    Text("Work with your AI assistant")
                                        .font(.system(size: 11))
                                        .foregroundStyle(.gray)
                                        .multilineTextAlignment(.leading)
                                }
                                .frame(
                                    maxWidth: .infinity,
                                    minHeight: 104,
                                    alignment: .leading
                                )
                                .padding(14)
                                .background(
                                    Color.white.opacity(0.035)
                                )
                                .overlay {

                                    RoundedRectangle(
                                        cornerRadius: 16
                                    )
                                    .stroke(
                                        Color.white.opacity(0.08),
                                        lineWidth: 1
                                    )
                                }
                                .clipShape(
                                    RoundedRectangle(
                                        cornerRadius: 16
                                    )
                                )
                            }
                        }

                        HStack(spacing: 10) {

                            Button {
                                print("Markets tapped")
                            } label: {

                                VStack(
                                    alignment: .leading,
                                    spacing: 8
                                ) {

                                    Text("↗")
                                        .font(.system(size: 18))
                                        .foregroundStyle(
                                            Color.purple.opacity(0.9)
                                        )
                                        .frame(
                                            width: 34,
                                            height: 34
                                        )
                                        .background(
                                            Color.purple.opacity(0.12)
                                        )
                                        .clipShape(
                                            RoundedRectangle(
                                                cornerRadius: 9
                                            )
                                        )

                                    Text("Markets")
                                        .font(
                                            .system(
                                                size: 13,
                                                weight: .bold
                                            )
                                        )
                                        .foregroundStyle(.white)

                                    Text("Research markets and stocks")
                                        .font(.system(size: 11))
                                        .foregroundStyle(.gray)
                                        .multilineTextAlignment(.leading)
                                }
                                .frame(
                                    maxWidth: .infinity,
                                    minHeight: 104,
                                    alignment: .leading
                                )
                                .padding(14)
                                .background(
                                    Color.white.opacity(0.035)
                                )
                                .overlay {

                                    RoundedRectangle(
                                        cornerRadius: 16
                                    )
                                    .stroke(
                                        Color.white.opacity(0.08),
                                        lineWidth: 1
                                    )
                                }
                                .clipShape(
                                    RoundedRectangle(
                                        cornerRadius: 16
                                    )
                                )
                            }

                            Button {
                                print("AI Agents tapped")
                            } label: {

                                VStack(
                                    alignment: .leading,
                                    spacing: 8
                                ) {

                                    Text("◎")
                                        .font(.system(size: 18))
                                        .foregroundStyle(
                                            Color.purple.opacity(0.9)
                                        )
                                        .frame(
                                            width: 34,
                                            height: 34
                                        )
                                        .background(
                                            Color.purple.opacity(0.12)
                                        )
                                        .clipShape(
                                            RoundedRectangle(
                                                cornerRadius: 9
                                            )
                                        )

                                    Text("AI Agents")
                                        .font(
                                            .system(
                                                size: 13,
                                                weight: .bold
                                            )
                                        )
                                        .foregroundStyle(.white)

                                    Text("Use specialized assistants")
                                        .font(.system(size: 11))
                                        .foregroundStyle(.gray)
                                        .multilineTextAlignment(.leading)
                                }
                                .frame(
                                    maxWidth: .infinity,
                                    minHeight: 104,
                                    alignment: .leading
                                )
                                .padding(14)
                                .background(
                                    Color.white.opacity(0.035)
                                )
                                .overlay {

                                    RoundedRectangle(
                                        cornerRadius: 16
                                    )
                                    .stroke(
                                        Color.white.opacity(0.08),
                                        lineWidth: 1
                                    )
                                }
                                .clipShape(
                                    RoundedRectangle(
                                        cornerRadius: 16
                                    )
                                )
                            }
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 10)
                    .padding(.bottom, 30)
                }
            }
            .sheet(isPresented: $showChat) {
                NovaChatView(csrfToken: csrfToken)
            }
            
            .sheet(isPresented: $showProjects) {
                NovaProjectsView(csrfToken: csrfToken)
            }
            
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
                SignInView(
                    isLoggedIn: $isLoggedIn,
                    csrfToken: $csrfToken
                )
            }
        }
    }
}

struct NovaProject: Identifiable, Decodable {
    let id: Int
    let name: String
    let description: String
    let created_at: String
    let updated_at: String
}

struct NovaProjectsResponse: Decodable {
    let projects: [NovaProject]
}

struct NovaProjectsView: View {
    
    let csrfToken: String
    
    init(csrfToken: String) {
            self.csrfToken = csrfToken
        }
    
    @Environment(\.dismiss) private var dismiss

    @State private var projects: [NovaProject] = []
    @State private var isLoading = true
    @State private var errorMessage = ""
    @State private var selectedProject: NovaProject?

    var body: some View {

        ZStack {

            LinearGradient(
                colors: [
                    Color(red: 0.027, green: 0.035, blue: 0.078),
                    Color(red: 0.020, green: 0.027, blue: 0.059)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 0) {

                HStack {

                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 17, weight: .semibold))
                            .foregroundStyle(.white)
                    }

                    Spacer()

                    Text("Projects")
                        .font(.headline)
                        .foregroundStyle(.white)

                    Spacer()

                    Button {
                        print("New Project tapped")
                    } label: {
                        Image(systemName: "plus")
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundStyle(.white)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 16)

                Divider()
                    .background(Color.white.opacity(0.08))

                if isLoading {

                    Spacer()

                    ProgressView()
                        .tint(.white)

                    Text("Loading projects...")
                        .font(.caption)
                        .foregroundStyle(.gray)
                        .padding(.top, 10)

                    Spacer()

                } else if !errorMessage.isEmpty {

                    Spacer()

                    Text(errorMessage)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                        .padding()

                    Spacer()

                } else if projects.isEmpty {

                    VStack(spacing: 14) {

                        Text("◇")
                            .font(.system(size: 38))
                            .foregroundStyle(
                                Color(
                                    red: 0.65,
                                    green: 0.40,
                                    blue: 1.0
                                )
                            )

                        Text("Your Projects")
                            .font(.system(size: 26, weight: .bold))
                            .foregroundStyle(.white)

                        Text("You don't have any projects yet.")
                            .font(.system(size: 14))
                            .foregroundStyle(.gray)
                    }
                    .padding(.top, 70)

                    Spacer()

                } else {

                    ScrollView {

                        LazyVStack(spacing: 12) {

                            ForEach(projects) { project in

                                Button {
                                    selectedProject = project
                                } label: {

                                    HStack(spacing: 14) {

                                        Text("◇")
                                            .font(.system(size: 18))
                                            .foregroundStyle(
                                                Color.purple.opacity(0.9)
                                            )
                                            .frame(
                                                width: 40,
                                                height: 40
                                            )
                                            .background(
                                                Color.purple.opacity(0.12)
                                            )
                                            .clipShape(
                                                RoundedRectangle(
                                                    cornerRadius: 10
                                                )
                                            )

                                        VStack(
                                            alignment: .leading,
                                            spacing: 5
                                        ) {

                                            Text(project.name)
                                                .font(
                                                    .system(
                                                        size: 15,
                                                        weight: .semibold
                                                    )
                                                )
                                                .foregroundStyle(.white)

                                            if !project.description.isEmpty {

                                                Text(project.description)
                                                    .font(.system(size: 12))
                                                    .foregroundStyle(.gray)
                                                    .lineLimit(2)
                                            }
                                        }

                                        Spacer()

                                        Image(
                                            systemName: "chevron.right"
                                        )
                                        .font(.system(size: 13))
                                        .foregroundStyle(.gray)
                                    }
                                    .padding(14)
                                    .background(
                                        Color.white.opacity(0.035)
                                    )
                                    .overlay {

                                        RoundedRectangle(
                                            cornerRadius: 14
                                        )
                                        .stroke(
                                            Color.white.opacity(0.08),
                                            lineWidth: 1
                                        )
                                    }
                                    .clipShape(
                                        RoundedRectangle(
                                            cornerRadius: 14
                                        )
                                    )
                                }
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 16)
                        .padding(.bottom, 30)
                    }
                }
            }
        }
        .task {
            await loadProjects()
        }
        
        .sheet(item: $selectedProject) { project in
            NovaProjectWorkspaceView(
                project: project,
                csrfToken: csrfToken
            )
        }
        
    }

    @MainActor
    private func loadProjects() async {

        guard let url = URL(
            string: "https://workfieldhq.com/api/projects"
        ) else {
            return
        }

        do {

            let (data, response) =
                try await URLSession.shared.data(
                    from: url
                )

            guard let httpResponse =
                response as? HTTPURLResponse
            else {
                errorMessage = "Unable to load projects."
                isLoading = false
                return
            }

            print(
                "Projects status:",
                httpResponse.statusCode
            )

            guard httpResponse.statusCode == 200 else {
                errorMessage =
                    "Unable to load projects."
                isLoading = false
                return
            }

            let decoded =
                try JSONDecoder().decode(
                    NovaProjectsResponse.self,
                    from: data
                )

            projects = decoded.projects
            isLoading = false

        } catch {

            print(
                "Projects error:",
                error
            )

            errorMessage =
                "Unable to load projects."

            isLoading = false
        }
    }
}

struct NovaProjectTask: Identifiable, Decodable {
    let id: Int
    let title: String
    var completed: Bool
    let created_at: String?
    let updated_at: String?
}

struct NovaProjectTasksResponse: Decodable {
    let tasks: [NovaProjectTask]
}

struct NovaProjectFile: Identifiable, Decodable {
    let id: Int
    let filename: String
    let stored_name: String?
    let file_size: Int
    let mime_type: String?
    let uploaded_at: String?
}

struct NovaProjectFilesResponse: Decodable {
    let files: [NovaProjectFile]
}

struct NovaProjectNotesResponse: Decodable {
    let content: String
}

enum ProjectWorkspaceTab: String, CaseIterable {
    case notes = "Notes"
    case tasks = "Tasks"
    case files = "Files"
}

struct NovaProjectWorkspaceView: View {

    let project: NovaProject
    let csrfToken: String

    @Environment(\.dismiss) private var dismiss

    @State private var selectedTab: ProjectWorkspaceTab = .notes

    @State private var notes = ""
    @State private var notesLoaded = false
    @State private var isSavingNotes = false
    @State private var notesStatus = ""

    @State private var tasks: [NovaProjectTask] = []
    @State private var newTaskTitle = ""
    @State private var tasksLoaded = false
    @State private var isCreatingTask = false

    @State private var projectFiles: [NovaProjectFile] = []
    @State private var filesLoaded = false
    @State private var showFileImporter = false
    @State private var isUploadingFile = false

    @State private var isLoading = true
    @State private var errorMessage = ""

    var body: some View {

        ZStack {

            LinearGradient(
                colors: [
                    Color(
                        red: 0.027,
                        green: 0.035,
                        blue: 0.078
                    ),
                    Color(
                        red: 0.020,
                        green: 0.027,
                        blue: 0.059
                    )
                ],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 0) {

                projectHeader

                Divider()
                    .background(
                        Color.white.opacity(0.08)
                    )

                projectTabs

                if isLoading {

                    Spacer()

                    ProgressView()
                        .tint(.white)

                    Text("Loading workspace...")
                        .font(.caption)
                        .foregroundStyle(.gray)
                        .padding(.top, 10)

                    Spacer()

                } else if !errorMessage.isEmpty {

                    Spacer()

                    VStack(spacing: 12) {

                        Image(
                            systemName:
                                "exclamationmark.triangle"
                        )
                        .font(.system(size: 28))
                        .foregroundStyle(.orange)

                        Text(errorMessage)
                            .foregroundStyle(.white)
                            .multilineTextAlignment(.center)

                        Button("Try Again") {
                            Task {
                                await loadWorkspace()
                            }
                        }
                        .foregroundStyle(.purple)
                    }
                    .padding()

                    Spacer()

                } else {

                    switch selectedTab {

                    case .notes:
                        notesView

                    case .tasks:
                        tasksView

                    case .files:
                        filesView
                    }
                }
            }
        }
        .task {
            await loadWorkspace()
        }
        .fileImporter(
            isPresented: $showFileImporter,
            allowedContentTypes: [.item],
            allowsMultipleSelection: false
        ) { result in

            switch result {

            case .success(let urls):

                guard let fileURL = urls.first else {
                    return
                }

                Task {
                    await uploadFile(fileURL)
                }

            case .failure(let error):

                print(
                    "File picker error:",
                    error
                )
            }
        }
    }

    private var projectHeader: some View {

        HStack(spacing: 14) {

            Button {
                dismiss()
            } label: {

                Image(
                    systemName: "chevron.left"
                )
                .font(
                    .system(
                        size: 17,
                        weight: .semibold
                    )
                )
                .foregroundStyle(.white)
                .frame(
                    width: 36,
                    height: 36
                )
                .background(
                    Color.white.opacity(0.06)
                )
                .clipShape(Circle())
            }

            VStack(
                alignment: .leading,
                spacing: 3
            ) {

                Text(project.name)
                    .font(
                        .system(
                            size: 18,
                            weight: .bold
                        )
                    )
                    .foregroundStyle(.white)
                    .lineLimit(1)

                if !project.description.isEmpty {

                    Text(project.description)
                        .font(.system(size: 11))
                        .foregroundStyle(.gray)
                        .lineLimit(1)
                }
            }

            Spacer()

            Text("◇")
                .font(.system(size: 23))
                .foregroundStyle(
                    Color(
                        red: 0.66,
                        green: 0.45,
                        blue: 1
                    )
                )
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }

    private var projectTabs: some View {

        HStack(spacing: 8) {

            ForEach(
                ProjectWorkspaceTab.allCases,
                id: \.self
            ) { tab in

                Button {

                    selectedTab = tab

                } label: {

                    HStack(spacing: 6) {

                        Image(
                            systemName:
                                iconForTab(tab)
                        )

                        Text(tab.rawValue)
                    }
                    .font(
                        .system(
                            size: 13,
                            weight: .semibold
                        )
                    )
                    .foregroundStyle(
                        selectedTab == tab
                            ? .white
                            : .gray
                    )
                    .frame(
                        maxWidth: .infinity
                    )
                    .padding(.vertical, 11)
                    .background(
                        selectedTab == tab
                            ? Color.purple.opacity(0.22)
                            : Color.white.opacity(0.035)
                    )
                    .overlay {

                        RoundedRectangle(
                            cornerRadius: 11
                        )
                        .stroke(
                            selectedTab == tab
                                ? Color.purple.opacity(0.55)
                                : Color.white.opacity(0.06),
                            lineWidth: 1
                        )
                    }
                    .clipShape(
                        RoundedRectangle(
                            cornerRadius: 11
                        )
                    )
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private var notesView: some View {

        VStack(spacing: 14) {

            HStack {

                VStack(
                    alignment: .leading,
                    spacing: 3
                ) {

                    Text("Project Notes")
                        .font(
                            .system(
                                size: 20,
                                weight: .bold
                            )
                        )
                        .foregroundStyle(.white)

                    Text(
                        "Keep ideas and information for this project."
                    )
                    .font(.system(size: 12))
                    .foregroundStyle(.gray)
                }

                Spacer()
            }

            TextEditor(text: $notes)
                .scrollContentBackground(.hidden)
                .foregroundStyle(.white)
                .font(.system(size: 15))
                .padding(10)
                .background(
                    Color.white.opacity(0.04)
                )
                .overlay {

                    RoundedRectangle(
                        cornerRadius: 14
                    )
                    .stroke(
                        Color.white.opacity(0.08),
                        lineWidth: 1
                    )
                }
                .clipShape(
                    RoundedRectangle(
                        cornerRadius: 14
                    )
                )

            HStack {

                Text(notesStatus)
                    .font(.caption)
                    .foregroundStyle(.gray)

                Spacer()

                Button {

                    Task {
                        await saveNotes()
                    }

                } label: {

                    HStack(spacing: 7) {

                        if isSavingNotes {

                            ProgressView()
                                .tint(.black)
                                .scaleEffect(0.8)

                        } else {

                            Image(
                                systemName: "square.and.arrow.down"
                            )
                        }

                        Text(
                            isSavingNotes
                                ? "Saving"
                                : "Save Notes"
                        )
                    }
                    .font(
                        .system(
                            size: 13,
                            weight: .bold
                        )
                    )
                    .foregroundStyle(.black)
                    .padding(.horizontal, 16)
                    .frame(height: 42)
                    .background(.white)
                    .clipShape(
                        RoundedRectangle(
                            cornerRadius: 12
                        )
                    )
                }
                .disabled(isSavingNotes)
            }
        }
        .padding(16)
    }

    private var tasksView: some View {

        VStack(spacing: 14) {

            HStack {

                VStack(
                    alignment: .leading,
                    spacing: 3
                ) {

                    Text("Tasks")
                        .font(
                            .system(
                                size: 20,
                                weight: .bold
                            )
                        )
                        .foregroundStyle(.white)

                    Text(
                        "\(tasks.filter { !$0.completed }.count) remaining"
                    )
                    .font(.system(size: 12))
                    .foregroundStyle(.gray)
                }

                Spacer()
            }

            HStack(spacing: 10) {

                TextField(
                    "Add a task...",
                    text: $newTaskTitle
                )
                .padding(.horizontal, 14)
                .frame(height: 44)
                .background(
                    Color.white.opacity(0.05)
                )
                .foregroundStyle(.white)
                .clipShape(
                    RoundedRectangle(
                        cornerRadius: 12
                    )
                )

                Button {

                    Task {
                        await createTask()
                    }

                } label: {

                    Image(
                        systemName: "plus"
                    )
                    .font(
                        .system(
                            size: 16,
                            weight: .bold
                        )
                    )
                    .foregroundStyle(.black)
                    .frame(
                        width: 44,
                        height: 44
                    )
                    .background(.white)
                    .clipShape(
                        RoundedRectangle(
                            cornerRadius: 12
                        )
                    )
                }
                .disabled(
                    isCreatingTask ||
                    newTaskTitle
                        .trimmingCharacters(
                            in: .whitespacesAndNewlines
                        )
                        .isEmpty
                )
            }

            if tasks.isEmpty {

                Spacer()

                VStack(spacing: 12) {

                    Image(
                        systemName:
                            "checkmark.circle"
                    )
                    .font(.system(size: 34))
                    .foregroundStyle(
                        Color.purple.opacity(0.8)
                    )

                    Text("No tasks yet")
                        .font(.headline)
                        .foregroundStyle(.white)

                    Text(
                        "Add a task above to get started."
                    )
                    .font(.caption)
                    .foregroundStyle(.gray)
                }

                Spacer()

            } else {

                ScrollView {

                    LazyVStack(spacing: 9) {

                        ForEach(tasks) { task in

                            HStack(spacing: 12) {

                                Button {

                                    Task {
                                        await toggleTask(
                                            task
                                        )
                                    }

                                } label: {

                                    Image(
                                        systemName:
                                            task.completed
                                            ? "checkmark.circle.fill"
                                            : "circle"
                                    )
                                    .font(.system(size: 21))
                                    .foregroundStyle(
                                        task.completed
                                            ? Color.purple
                                            : Color.gray
                                    )
                                }

                                Text(task.title)
                                    .font(.system(size: 14))
                                    .foregroundStyle(
                                        task.completed
                                            ? Color.gray
                                            : Color.white
                                    )
                                    .strikethrough(
                                        task.completed
                                    )
                                    .frame(
                                        maxWidth: .infinity,
                                        alignment: .leading
                                    )

                                Button {

                                    Task {
                                        await deleteTask(
                                            task
                                        )
                                    }

                                } label: {

                                    Image(
                                        systemName: "trash"
                                    )
                                    .font(.system(size: 14))
                                    .foregroundStyle(
                                        Color.red.opacity(0.8)
                                    )
                                    .frame(
                                        width: 32,
                                        height: 32
                                    )
                                }
                            }
                            .padding(13)
                            .background(
                                Color.white.opacity(0.035)
                            )
                            .overlay {

                                RoundedRectangle(
                                    cornerRadius: 13
                                )
                                .stroke(
                                    Color.white.opacity(0.07),
                                    lineWidth: 1
                                )
                            }
                            .clipShape(
                                RoundedRectangle(
                                    cornerRadius: 13
                                )
                            )
                        }
                    }
                    .padding(.bottom, 20)
                }
            }
        }
        .padding(16)
    }

    private var filesView: some View {

        VStack(spacing: 14) {

            HStack {

                VStack(
                    alignment: .leading,
                    spacing: 3
                ) {

                    Text("Files")
                        .font(
                            .system(
                                size: 20,
                                weight: .bold
                            )
                        )
                        .foregroundStyle(.white)

                    Text(
                        "\(projectFiles.count) project files"
                    )
                    .font(.system(size: 12))
                    .foregroundStyle(.gray)
                }

                Spacer()

                Button {

                    showFileImporter = true

                } label: {

                    HStack(spacing: 6) {

                        if isUploadingFile {

                            ProgressView()
                                .tint(.black)
                                .scaleEffect(0.8)

                        } else {

                            Image(
                                systemName:
                                    "square.and.arrow.up"
                            )
                        }

                        Text(
                            isUploadingFile
                                ? "Uploading"
                                : "Upload"
                        )
                    }
                    .font(
                        .system(
                            size: 12,
                            weight: .bold
                        )
                    )
                    .foregroundStyle(.black)
                    .padding(.horizontal, 13)
                    .frame(height: 38)
                    .background(.white)
                    .clipShape(
                        RoundedRectangle(
                            cornerRadius: 11
                        )
                    )
                }
                .disabled(isUploadingFile)
            }

            if projectFiles.isEmpty {

                Spacer()

                VStack(spacing: 12) {

                    Image(
                        systemName: "folder"
                    )
                    .font(.system(size: 36))
                    .foregroundStyle(
                        Color.purple.opacity(0.8)
                    )

                    Text("No files yet")
                        .font(.headline)
                        .foregroundStyle(.white)

                    Text(
                        "Upload a file to this project."
                    )
                    .font(.caption)
                    .foregroundStyle(.gray)
                }

                Spacer()

            } else {

                ScrollView {

                    LazyVStack(spacing: 9) {

                        ForEach(
                            projectFiles
                        ) { file in

                            HStack(spacing: 12) {

                                Image(
                                    systemName:
                                        fileIcon(
                                            file.filename
                                        )
                                )
                                .font(.system(size: 19))
                                .foregroundStyle(
                                    Color.purple
                                )
                                .frame(
                                    width: 40,
                                    height: 40
                                )
                                .background(
                                    Color.purple.opacity(0.12)
                                )
                                .clipShape(
                                    RoundedRectangle(
                                        cornerRadius: 10
                                    )
                                )

                                VStack(
                                    alignment: .leading,
                                    spacing: 4
                                ) {

                                    Text(file.filename)
                                        .font(
                                            .system(
                                                size: 13,
                                                weight: .semibold
                                            )
                                        )
                                        .foregroundStyle(.white)
                                        .lineLimit(1)

                                    Text(
                                        formatFileSize(
                                            file.file_size
                                        )
                                    )
                                    .font(.system(size: 11))
                                    .foregroundStyle(.gray)
                                }

                                Spacer()

                                Button {

                                    Task {
                                        await deleteFile(
                                            file
                                        )
                                    }

                                } label: {

                                    Image(
                                        systemName: "trash"
                                    )
                                    .font(.system(size: 14))
                                    .foregroundStyle(
                                        Color.red.opacity(0.8)
                                    )
                                    .frame(
                                        width: 34,
                                        height: 34
                                    )
                                }
                            }
                            .padding(12)
                            .background(
                                Color.white.opacity(0.035)
                            )
                            .overlay {

                                RoundedRectangle(
                                    cornerRadius: 13
                                )
                                .stroke(
                                    Color.white.opacity(0.07),
                                    lineWidth: 1
                                )
                            }
                            .clipShape(
                                RoundedRectangle(
                                    cornerRadius: 13
                                )
                            )
                        }
                    }
                    .padding(.bottom, 20)
                }
            }
        }
        .padding(16)
    }

    private func iconForTab(
        _ tab: ProjectWorkspaceTab
    ) -> String {

        switch tab {

        case .notes:
            return "note.text"

        case .tasks:
            return "checkmark.circle"

        case .files:
            return "folder"
        }
    }

    @MainActor
    private func loadWorkspace() async {

        isLoading = true
        errorMessage = ""

        do {

            try await loadNotes()
            try await loadTasks()
            try await loadFiles()

            notesLoaded = true
            tasksLoaded = true
            filesLoaded = true

            isLoading = false

        } catch {

            print(
                "Workspace load error:",
                error
            )

            errorMessage =
                "Unable to load this project."

            isLoading = false
        }
    }

    @MainActor
    private func loadNotes() async throws {

        guard let url = URL(
            string:
                "https://workfieldhq.com/api/projects/\(project.id)/notes"
        ) else {
            return
        }

        let (data, response) =
            try await URLSession.shared.data(
                from: url
            )

        guard
            let httpResponse =
                response as? HTTPURLResponse,
            httpResponse.statusCode == 200
        else {
            throw URLError(.badServerResponse)
        }

        let decoded =
            try JSONDecoder().decode(
                NovaProjectNotesResponse.self,
                from: data
            )

        notes = decoded.content
    }

    @MainActor
    private func saveNotes() async {

        guard let url = URL(
            string:
                "https://workfieldhq.com/api/projects/\(project.id)/notes"
        ) else {
            return
        }

        isSavingNotes = true
        notesStatus = ""

        var request =
            URLRequest(url: url)

        request.httpMethod = "POST"

        request.setValue(
            "application/json",
            forHTTPHeaderField:
                "Content-Type"
        )

        request.setValue(
            csrfToken,
            forHTTPHeaderField:
                "X-CSRF-Token"
        )

        request.httpBody =
            try? JSONSerialization.data(
                withJSONObject: [
                    "content": notes
                ]
            )

        do {

            let (_, response) =
                try await URLSession.shared.data(
                    for: request
                )

            guard
                let httpResponse =
                    response as? HTTPURLResponse,
                httpResponse.statusCode == 200
            else {
                notesStatus =
                    "Save failed."
                isSavingNotes = false
                return
            }

            notesStatus =
                "Saved"

        } catch {

            print(
                "Save notes error:",
                error
            )

            notesStatus =
                "Save failed."
        }

        isSavingNotes = false
    }

    @MainActor
    private func loadTasks() async throws {

        guard let url = URL(
            string:
                "https://workfieldhq.com/api/projects/\(project.id)/tasks"
        ) else {
            return
        }

        let (data, response) =
            try await URLSession.shared.data(
                from: url
            )

        guard
            let httpResponse =
                response as? HTTPURLResponse,
            httpResponse.statusCode == 200
        else {
            throw URLError(.badServerResponse)
        }

        let decoded =
            try JSONDecoder().decode(
                NovaProjectTasksResponse.self,
                from: data
            )

        tasks = decoded.tasks
    }

    @MainActor
    private func createTask() async {

        let title =
            newTaskTitle.trimmingCharacters(
                in: .whitespacesAndNewlines
            )

        guard !title.isEmpty else {
            return
        }

        guard let url = URL(
            string:
                "https://workfieldhq.com/api/projects/\(project.id)/tasks"
        ) else {
            return
        }

        isCreatingTask = true

        var request =
            URLRequest(url: url)

        request.httpMethod = "POST"

        request.setValue(
            "application/json",
            forHTTPHeaderField:
                "Content-Type"
        )

        request.setValue(
            csrfToken,
            forHTTPHeaderField:
                "X-CSRF-Token"
        )

        request.httpBody =
            try? JSONSerialization.data(
                withJSONObject: [
                    "title": title
                ]
            )

        do {

            let (_, response) =
                try await URLSession.shared.data(
                    for: request
                )

            guard
                let httpResponse =
                    response as? HTTPURLResponse,
                httpResponse.statusCode == 201
            else {
                isCreatingTask = false
                return
            }

            newTaskTitle = ""

            try await loadTasks()

        } catch {

            print(
                "Create task error:",
                error
            )
        }

        isCreatingTask = false
    }

    @MainActor
    private func toggleTask(
        _ task: NovaProjectTask
    ) async {

        guard let url = URL(
            string:
                "https://workfieldhq.com/api/projects/\(project.id)/tasks/\(task.id)"
        ) else {
            return
        }

        var request =
            URLRequest(url: url)

        request.httpMethod = "PATCH"

        request.setValue(
            "application/json",
            forHTTPHeaderField:
                "Content-Type"
        )

        request.setValue(
            csrfToken,
            forHTTPHeaderField:
                "X-CSRF-Token"
        )

        request.httpBody =
            try? JSONSerialization.data(
                withJSONObject: [
                    "completed":
                        !task.completed
                ]
            )

        do {

            let (_, response) =
                try await URLSession.shared.data(
                    for: request
                )

            guard
                let httpResponse =
                    response as? HTTPURLResponse,
                httpResponse.statusCode == 200
            else {
                return
            }

            try await loadTasks()

        } catch {

            print(
                "Toggle task error:",
                error
            )
        }
    }

    @MainActor
    private func deleteTask(
        _ task: NovaProjectTask
    ) async {

        guard let url = URL(
            string:
                "https://workfieldhq.com/api/projects/\(project.id)/tasks/\(task.id)"
        ) else {
            return
        }

        var request =
            URLRequest(url: url)

        request.httpMethod = "DELETE"

        request.setValue(
            csrfToken,
            forHTTPHeaderField:
                "X-CSRF-Token"
        )

        do {

            let (_, response) =
                try await URLSession.shared.data(
                    for: request
                )

            guard
                let httpResponse =
                    response as? HTTPURLResponse,
                httpResponse.statusCode == 200
            else {
                return
            }

            tasks.removeAll {
                $0.id == task.id
            }

        } catch {

            print(
                "Delete task error:",
                error
            )
        }
    }

    @MainActor
    private func loadFiles() async throws {

        guard let url = URL(
            string:
                "https://workfieldhq.com/api/projects/\(project.id)/files"
        ) else {
            return
        }

        let (data, response) =
            try await URLSession.shared.data(
                from: url
            )

        guard
            let httpResponse =
                response as? HTTPURLResponse,
            httpResponse.statusCode == 200
        else {
            throw URLError(.badServerResponse)
        }

        let decoded =
            try JSONDecoder().decode(
                NovaProjectFilesResponse.self,
                from: data
            )

        projectFiles = decoded.files
    }

    @MainActor
    private func uploadFile(
        _ fileURL: URL
    ) async {

        let hasAccess =
            fileURL
                .startAccessingSecurityScopedResource()

        defer {

            if hasAccess {
                fileURL
                    .stopAccessingSecurityScopedResource()
            }
        }

        do {

            let fileData =
                try Data(
                    contentsOf: fileURL
                )

            guard
                fileData.count <=
                    10 * 1024 * 1024
            else {

                print(
                    "File is larger than 10 MB."
                )

                return
            }

            guard let url = URL(
                string:
                    "https://workfieldhq.com/api/projects/\(project.id)/files"
            ) else {
                return
            }

            isUploadingFile = true

            let boundary =
                "Boundary-\(UUID().uuidString)"

            var body = Data()

            body.append(
                "--\(boundary)\r\n"
                    .data(
                        using: .utf8
                    )!
            )

            body.append(
                "Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\r\n"
                    .data(
                        using: .utf8
                    )!
            )

            body.append(
                "Content-Type: application/octet-stream\r\n\r\n"
                    .data(
                        using: .utf8
                    )!
            )

            body.append(fileData)

            body.append(
                "\r\n--\(boundary)--\r\n"
                    .data(
                        using: .utf8
                    )!
            )

            var request =
                URLRequest(url: url)

            request.httpMethod = "POST"

            request.setValue(
                "multipart/form-data; boundary=\(boundary)",
                forHTTPHeaderField:
                    "Content-Type"
            )

            request.setValue(
                csrfToken,
                forHTTPHeaderField:
                    "X-CSRF-Token"
            )

            request.httpBody = body

            let (_, response) =
                try await URLSession.shared.data(
                    for: request
                )

            guard
                let httpResponse =
                    response as? HTTPURLResponse,
                httpResponse.statusCode == 201
            else {

                isUploadingFile = false
                return
            }

            try await loadFiles()

        } catch {

            print(
                "Upload file error:",
                error
            )
        }

        isUploadingFile = false
    }

    @MainActor
    private func deleteFile(
        _ file: NovaProjectFile
    ) async {

        guard let url = URL(
            string:
                "https://workfieldhq.com/api/projects/\(project.id)/files/\(file.id)"
        ) else {
            return
        }

        var request =
            URLRequest(url: url)

        request.httpMethod = "DELETE"

        request.setValue(
            csrfToken,
            forHTTPHeaderField:
                "X-CSRF-Token"
        )

        do {

            let (_, response) =
                try await URLSession.shared.data(
                    for: request
                )

            guard
                let httpResponse =
                    response as? HTTPURLResponse,
                httpResponse.statusCode == 200
            else {
                return
            }

            projectFiles.removeAll {
                $0.id == file.id
            }

        } catch {

            print(
                "Delete file error:",
                error
            )
        }
    }

    private func formatFileSize(
        _ bytes: Int
    ) -> String {

        let formatter =
            ByteCountFormatter()

        formatter.countStyle = .file

        return formatter.string(
            fromByteCount:
                Int64(bytes)
        )
    }

    private func fileIcon(
        _ filename: String
    ) -> String {

        let lower =
            filename.lowercased()

        if lower.hasSuffix(".pdf") {
            return "doc.richtext"
        }

        if lower.hasSuffix(".png") ||
            lower.hasSuffix(".jpg") ||
            lower.hasSuffix(".jpeg") ||
            lower.hasSuffix(".gif") ||
            lower.hasSuffix(".webp") {

            return "photo"
        }

        if lower.hasSuffix(".py") ||
            lower.hasSuffix(".js") ||
            lower.hasSuffix(".html") ||
            lower.hasSuffix(".css") ||
            lower.hasSuffix(".json") {

            return "chevron.left.forwardslash.chevron.right"
        }

        return "doc"
    }
}

struct SignInView: View {
    @Binding var isLoggedIn: Bool
    @Binding var csrfToken: String
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

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: String
    var text: String
}

struct NovaChatView: View {

    let csrfToken: String

    @Environment(\.dismiss) private var dismiss

    @State private var message = ""
    @State private var novaReply = ""
    @State private var sentMessage = ""
    @State private var messages: [ChatMessage] = []

    var body: some View {
        ZStack {
            Color.black
                .ignoresSafeArea()

            VStack(spacing: 0) {

                HStack {
                    Button("Close") {
                        dismiss()
                    }
                    .foregroundStyle(.gray)

                    Spacer()

                    Text("Nova")
                        .font(.headline)
                        .foregroundStyle(.white)

                    Spacer()

                    Color.clear
                        .frame(width: 44, height: 1)
                }
                .padding()

                Divider()
                    .background(Color.gray.opacity(0.3))

                ScrollView {
                    VStack(spacing: 14) {
                        ForEach(messages) { chatMessage in
                            Group {
                                if chatMessage.role == "user" {
                                    HStack {
                                        Spacer()

                                        Text(chatMessage.text)
                                            .foregroundStyle(.white)
                                            .padding(.horizontal, 14)
                                            .padding(.vertical, 10)
                                            .background(Color.white.opacity(0.14))
                                            .clipShape(
                                                RoundedRectangle(
                                                    cornerRadius: 16
                                                )
                                            )
                                    }
                                } else {
                                    HStack(
                                        alignment: .top,
                                        spacing: 10
                                    ) {
                                        Text("✦")
                                            .foregroundStyle(.white)

                                        Text(chatMessage.text)
                                            .foregroundStyle(.white)
                                            .frame(
                                                maxWidth: .infinity,
                                                alignment: .leading
                                            )
                                    }
                                }
                            }
                            .id(chatMessage.id)
                        }
                    }
                    .padding()
                }

                HStack(spacing: 12) {
                    TextField(
                        "Message Nova...",
                        text: $message
                    )
                    .padding()
                    .background(
                        Color.white.opacity(0.08)
                    )
                    .foregroundStyle(.white)
                    .clipShape(
                        RoundedRectangle(
                            cornerRadius: 14
                        )
                    )

                    Button {
                        Task {
                            await sendMessage()
                        }
                    } label: {
                        Image(systemName: "arrow.up")
                            .font(
                                .system(
                                    size: 16,
                                    weight: .bold
                                )
                            )
                            .frame(
                                width: 44,
                                height: 44
                            )
                            .background(.white)
                            .foregroundStyle(.black)
                            .clipShape(Circle())
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 10)
                .background(Color.black)
            }
        }
    }

    @MainActor
    private func sendMessage() async {
        let trimmedMessage = message.trimmingCharacters(
            in: .whitespacesAndNewlines
        )

        guard !trimmedMessage.isEmpty else {
            return
        }

        sentMessage = trimmedMessage
        novaReply = ""
        message = ""

        messages.append(
            ChatMessage(
                role: "user",
                text: trimmedMessage
            )
        )

        guard let url = URL(
            string: "https://workfieldhq.com/chat"
        ) else {
            return
        }

        var request = URLRequest(url: url)

        request.httpMethod = "POST"

        request.setValue(
            "application/json",
            forHTTPHeaderField: "Content-Type"
        )

        request.setValue(
            csrfToken,
            forHTTPHeaderField: "X-CSRF-Token"
        )

        let body: [String: Any] = [
            "message": trimmedMessage,
            "agent_mode": "default"
        ]

        request.httpBody = try? JSONSerialization.data(
            withJSONObject: body
        )

        do {
            let (bytes, response) =
                try await URLSession.shared.bytes(
                    for: request
                )

            guard let httpResponse =
                response as? HTTPURLResponse
            else {
                return
            }

            print(
                "Nova status:",
                httpResponse.statusCode
            )

            messages.append(
                ChatMessage(
                    role: "assistant",
                    text: ""
                )
            )

            let novaMessageIndex =
                messages.count - 1

            for try await line in bytes.lines {

                print("Nova stream:", line)

                guard
                    let data = line.data(
                        using: String.Encoding.utf8
                    ),
                    let json = try?
                        JSONSerialization.jsonObject(
                            with: data
                        ) as? [String: Any],
                    let type =
                        json["type"] as? String
                else {
                    continue
                }

                if type == "delta",
                   let delta =
                    json["delta"] as? String {

                    novaReply += delta

                    messages[
                        novaMessageIndex
                    ].text += delta
                }
            }

        } catch {
            print(
                "Nova chat error:",
                error
            )
        }
    }
}
#Preview {
        ContentView()
    }
    

