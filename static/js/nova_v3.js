const sidebarButtons =
    document.querySelectorAll(".sidebar-button");

const quickCards =
    document.querySelectorAll(".quick-card");

const pages =
    document.querySelectorAll(".page");

const projectModal =
    document.getElementById("project-modal");

const newProjectButton =
    document.getElementById("new-project-button");

const heroNewProjectButton =
    document.getElementById("hero-new-project-button");

const sidebarNewProjectButton =
    document.getElementById("sidebar-new-project");

const cancelProjectButton =
    document.getElementById("cancel-project");

const closeProjectModalButton =
    document.getElementById("close-project-modal");

const createProjectButton =
    document.getElementById("create-project");

const projectNameInput =
    document.getElementById("project-name");

const projectDescriptionInput =
    document.getElementById("project-description");

const projectsList =
    document.getElementById("projects-list");

const recentProjects =
    document.getElementById("recent-projects");

const workspaceBack =
    document.getElementById("workspace-back");

const workspaceTabs =
    document.querySelectorAll(".workspace-tab");

const workspacePanels =
    document.querySelectorAll(".workspace-panel");

const notificationButton =
    document.getElementById("notifications-button");

const notificationPanel =
    document.getElementById("notification-panel");

const closeNotifications =
    document.getElementById("close-notifications");


function openPage(pageName) {

    pages.forEach(page => {
        page.classList.remove("active-page");
    });

    const targetPage =
        document.getElementById(pageName + "-page");

    if (targetPage) {
        targetPage.classList.add("active-page");
    }

    sidebarButtons.forEach(button => {

        button.classList.remove("active");

        if (button.dataset.page === pageName) {
            button.classList.add("active");
        }

    });

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


sidebarButtons.forEach(button => {

    button.addEventListener("click", () => {

        openPage(button.dataset.page);

    });

});


quickCards.forEach(card => {

    card.addEventListener("click", () => {

        openPage(card.dataset.page);

    });

});


document
    .querySelectorAll("[data-page]")
    .forEach(button => {

        if (
            button.classList.contains("sidebar-button")
            ||
            button.classList.contains("quick-card")
        ) {
            return;
        }

        button.addEventListener("click", () => {

            openPage(button.dataset.page);

        });

    });


function openProjectModal() {

    if (!projectModal) {
        return;
    }

    projectModal.classList.add("show");

    setTimeout(() => {

        projectNameInput?.focus();

    }, 100);

}


function closeProjectModal() {

    if (!projectModal) {
        return;
    }

    projectModal.classList.remove("show");

}


newProjectButton?.addEventListener(
    "click",
    openProjectModal
);

heroNewProjectButton?.addEventListener(
    "click",
    openProjectModal
);

sidebarNewProjectButton?.addEventListener(
    "click",
    () => {

        openPage("projects");

        openProjectModal();

    }
);

cancelProjectButton?.addEventListener(
    "click",
    closeProjectModal
);

closeProjectModalButton?.addEventListener(
    "click",
    closeProjectModal
);


projectModal?.addEventListener(
    "click",
    event => {

        if (event.target === projectModal) {
            closeProjectModal();
        }

    }
);


async function loadProjects() {

    if (!projectsList) {
        return;
    }

    try {

        const response =
            await fetch("/api/projects");

        if (!response.ok) {
            throw new Error(
                "Could not load projects."
            );
        }

        const data =
            await response.json();

        const projects =
            data.projects || [];

        projectsList.innerHTML = "";

        const projectCount =
            document.getElementById(
                "project-count"
            );

        if (projectCount) {
            projectCount.textContent =
                projects.length;
        }


        if (projects.length === 0) {

            projectsList.innerHTML = `
                <div class="empty-state">
                    No projects yet.
                </div>
            `;

            if (recentProjects) {
                recentProjects.innerHTML = `
                    <div class="empty-state">
                        No recent projects.
                    </div>
                `;
            }

            return;
        }


        projects.forEach(project => {

            const card =
                document.createElement("div");

            card.className =
                "project-item";

            card.innerHTML = `
                <div>
                    <h3>
                        📁 ${project.name}
                    </h3>

                    <p>
                        ${
                            project.description
                            ||
                            "No description"
                        }
                    </p>
                </div>

                <button
                    class="secondary-button open-project"
                >
                    Open →
                </button>
            `;

            const openButton =
                card.querySelector(
                    ".open-project"
                );

            openButton.addEventListener(
                "click",
                () => {

                    openProject(
                        project.id,
                        project.name,
                        project.description
                    );

                }
            );

            projectsList.appendChild(card);

        });


        if (recentProjects) {

            recentProjects.innerHTML = "";

            projects
                .slice(0, 3)
                .forEach(project => {

                    const recent =
                        document.createElement(
                            "button"
                        );

                    recent.className =
                        "recent-project-item";

                    recent.innerHTML = `
                        <span>📁</span>

                        <div>
                            <strong>
                                ${project.name}
                            </strong>

                            <small>
                                ${
                                    project.description
                                    ||
                                    "No description"
                                }
                            </small>
                        </div>
                    `;

                    recent.addEventListener(
                        "click",
                        () => {

                            openProject(
                                project.id,
                                project.name,
                                project.description
                            );

                        }
                    );

                    recentProjects.appendChild(
                        recent
                    );

                });

        }

    }

    catch (error) {

        console.error(error);

        projectsList.innerHTML = `
            <div class="empty-state">
                Could not load projects.
            </div>
        `;

    }

}


createProjectButton?.addEventListener(
    "click",
    async () => {

        const name =
            projectNameInput
                .value
                .trim();

        const description =
            projectDescriptionInput
                .value
                .trim();


        if (!name) {

            alert(
                "Enter a project name."
            );

            return;

        }


        try {

            const response =
                await fetch(
                    "/api/projects",
                    {

                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({
                                name,
                                description
                            })

                    }
                );


            if (!response.ok) {

                const errorData =
                    await response.json();

                alert(
                    errorData.error
                    ||
                    "Could not create project."
                );

                return;

            }


            projectNameInput.value = "";

            projectDescriptionInput.value = "";

            closeProjectModal();

            await loadProjects();

            openPage("projects");

        }

        catch (error) {

            console.error(error);

            alert(
                "Could not create project."
            );

        }

    }
);


function openProject(
    id,
    name,
    description
) {

    openPage("workspace");

    const title =
        document.getElementById(
            "workspace-title"
        );

    const descriptionElement =
        document.getElementById(
            "workspace-description"
        );

    if (title) {

        title.textContent =
            "📁 " + name;

    }

    if (descriptionElement) {

        descriptionElement.textContent =
            description
            ||
            "No description.";

    }

    window.currentProject = {
        id,
        name,
        description
    };

loadProjectNotes(id);
loadProjectTasks(id);
loadProjectFiles(id);

}


workspaceBack?.addEventListener(
    "click",
    () => {

        openPage("projects");

    }
);


workspaceTabs.forEach(tab => {

    tab.addEventListener(
        "click",
        () => {

            workspaceTabs.forEach(
                item => {

                    item.classList.remove(
                        "active"
                    );

                }
            );

            tab.classList.add(
                "active"
            );


            workspacePanels.forEach(
                panel => {

                    panel.classList.remove(
                        "active-workspace-panel"
                    );

                }
            );


            const tabName =
                tab.dataset.workspaceTab;

            let targetId =
                "workspace-" + tabName;


            if (tabName === "chat") {
                targetId =
                    "workspace-chat-panel";
            }


            const target =
                document.getElementById(
                    targetId
                );

            if (target) {

                target.classList.add(
                    "active-workspace-panel"
                );

            }

        }
    );

});


notificationButton?.addEventListener(
    "click",
    () => {

        notificationPanel
            ?.classList
            .toggle("show");

    }
);


closeNotifications?.addEventListener(
    "click",
    () => {

        notificationPanel
            ?.classList
            .remove("show");

    }
);


document.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Escape"
        ) {

            closeProjectModal();

            notificationPanel
                ?.classList
                .remove("show");

        }

    }
);


loadProjects();

const projectNotes =
    document.getElementById("project-notes");

const saveNotesButton =
    document.getElementById("save-notes");


async function loadProjectNotes(projectId) {

    if (!projectNotes) {
        return;
    }

    try {

        const response =
            await fetch(
                `/api/projects/${projectId}/notes`
            );

        if (!response.ok) {
            throw new Error("Could not load notes.");
        }

        const data =
            await response.json();

        projectNotes.value =
            data.content || "";

    }

    catch (error) {

        console.error(error);

    }

}


saveNotesButton?.addEventListener(
    "click",
    async () => {

        if (!window.currentProject) {
            return;
        }

        try {

            const response =
                await fetch(
                    `/api/projects/${window.currentProject.id}/notes`,
                    {

                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({
                                content:
                                    projectNotes.value
                            })

                    }
                );

            if (!response.ok) {
                throw new Error(
                    "Could not save notes."
                );
            }

            saveNotesButton.textContent =
                "Saved ✓";

            setTimeout(() => {

                saveNotesButton.textContent =
                    "Save Notes";

            }, 1500);

        }

        catch (error) {

            console.error(error);

            alert("Could not save notes.");

        }

    }
);

const taskList =
    document.getElementById("workspace-task-list");

const newTaskButton =
    document.querySelector(
        '#workspace-tasks .primary-button'
    );


async function loadProjectTasks(projectId) {

    if (!taskList) {
        return;
    }

    try {

        const response =
            await fetch(
                `/api/projects/${projectId}/tasks`
            );

        const data =
            await response.json();

        taskList.innerHTML = "";

        if (!data.tasks || data.tasks.length === 0) {

            taskList.innerHTML =
                '<div class="empty-state">No tasks yet.</div>';

            return;
        }


        data.tasks.forEach(task => {

            const row =
                document.createElement("div");

            row.className = "task-item";

            row.innerHTML = `
                <label>
                    <input
                        type="checkbox"
                        ${task.completed ? "checked" : ""}
                    >
                    <span>
                        ${task.title}
                    </span>
                </label>

                <button class="task-delete">
                    Delete
                </button>
            `;


            const checkbox =
                row.querySelector(
                    'input[type="checkbox"]'
                );

            checkbox.addEventListener(
                "change",
                async () => {

                    await fetch(
                        `/api/projects/${projectId}/tasks/${task.id}`,
                        {
                            method: "PATCH",
                            headers: {
                                "Content-Type":
                                    "application/json"
                            },
                            body:
                                JSON.stringify({
                                    completed:
                                        checkbox.checked
                                })
                        }
                    );

                }
            );


            const deleteButton =
                row.querySelector(
                    ".task-delete"
                );

            deleteButton.addEventListener(
                "click",
                async () => {

                    await fetch(
                        `/api/projects/${projectId}/tasks/${task.id}`,
                        {
                            method: "DELETE"
                        }
                    );

                    loadProjectTasks(
                        projectId
                    );

                }
            );


            taskList.appendChild(row);

        });

    }

    catch (error) {

        console.error(error);

    }

}


newTaskButton?.addEventListener(
    "click",
    async () => {

        if (!window.currentProject) {
            return;
        }

        const title =
            prompt("Enter task:");

        if (!title || !title.trim()) {
            return;
        }

        await fetch(
            `/api/projects/${window.currentProject.id}/tasks`,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body:
                    JSON.stringify({
                        title: title.trim()
                    })
            }
        );

        loadProjectTasks(
            window.currentProject.id
        );

    }
);

// ========================================
// PROJECT AI CHAT
// ========================================

const workspaceChat =
    document.getElementById("workspace-chat");

const workspaceInput =
    document.getElementById("workspace-input");

const workspaceSend =
    document.getElementById("workspace-send");


async function sendWorkspaceMessage() {

    if (!window.currentProject) {
        return;
    }

    const message =
        workspaceInput.value.trim();

    if (!message) {
        return;
    }


    // Show user's message
    const userMessage =
        document.createElement("div");

    userMessage.className =
        "message user-message";

    userMessage.innerHTML = `
        <div>
            <strong>You</strong>
            <p>${message}</p>
        </div>
    `;

    workspaceChat.appendChild(userMessage);


    workspaceInput.value = "";


    // Show thinking message
    const thinkingMessage =
        document.createElement("div");

    thinkingMessage.className =
        "message ai-message";

    thinkingMessage.innerHTML = `
        <div>
            <strong>Nova</strong>
            <p>Nova is thinking...</p>
        </div>
    `;

    workspaceChat.appendChild(
        thinkingMessage
    );


    try {

        const response =
            await fetch("/chat", {

                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({

                    message: message,

                    project_id:
                        window.currentProject.id,

                    project_name:
                        window.currentProject.name

                })

            });


        const data =
            await response.json();


        thinkingMessage.remove();


        const aiMessage =
            document.createElement("div");

        aiMessage.className =
            "message ai-message";

        aiMessage.innerHTML = `
            <div>
                <strong>Nova</strong>
                <p>${data.reply || data.response || data.message || "Nova could not respond."}</p>
            </div>
        `;

        workspaceChat.appendChild(
            aiMessage
        );

    }

    catch (error) {

        thinkingMessage.remove();

        const errorMessage =
            document.createElement("div");

        errorMessage.className =
            "message ai-message";

        errorMessage.innerHTML = `
            <div>
                <strong>Nova</strong>
                <p>Something went wrong connecting to Nova.</p>
            </div>
        `;

        workspaceChat.appendChild(
            errorMessage
        );

        console.error(error);

    }


    workspaceChat.scrollTop =
        workspaceChat.scrollHeight;

}


workspaceSend?.addEventListener(
    "click",
    sendWorkspaceMessage
);


workspaceInput?.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendWorkspaceMessage();

        }

    }
);

// ========================================
// PROJECT FILES
// ========================================

const workspaceFilesList =
    document.getElementById("workspace-files-list");

const workspaceFilesPanel =
    document.getElementById("workspace-files");

const workspaceUploadButton =
    document.getElementById(
        "workspace-upload-button"
    );

const workspaceFileInput =
    document.getElementById(
        "workspace-file-input"
    );


async function loadProjectFiles(projectId) {

    if (!workspaceFilesList) {
        return;
    }

    try {

        const response =
            await fetch(
                `/api/projects/${projectId}/files`
            );

        if (!response.ok) {
            throw new Error(
                "Could not load project files."
            );
        }

        const data =
            await response.json();

        workspaceFilesList.innerHTML = "";

        if (!data.files || data.files.length === 0) {

            workspaceFilesList.innerHTML = `
                <div class="empty-state">
                    No files yet.
                </div>
            `;

            return;
        }

        data.files.forEach(file => {

            const row =
                document.createElement("div");

            row.className = "file-item";

            row.innerHTML = `
                <div>
                    <strong>
                        📄 ${file.filename}
                    </strong>

                    <small>
                        ${file.uploaded_at || ""}
                    </small>
                </div>
            `;

            workspaceFilesList.appendChild(row);

        });

    }

    catch (error) {

        console.error(error);

        workspaceFilesList.innerHTML = `
            <div class="empty-state">
                Could not load files.
            </div>
        `;

    }

}

workspaceUploadButton?.addEventListener(
    "click",
    () => {

        if (!window.currentProject) {

            alert("Open a project first.");
            return;

        }

        workspaceFileInput.click();

    }
);


workspaceFileInput?.addEventListener(
    "change",
    async () => {

        const file =
            workspaceFileInput.files[0];

        if (!file) {
            return;
        }

        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );

        try {

            const response =
                await fetch(
                    `/api/projects/${window.currentProject.id}/files`,
                    {
                        method: "POST",
                        body: formData
                    }
                );

            const data =
                await response.json();

            if (!response.ok) {

                alert(
                    data.error ||
                    "Could not upload file."
                );

                return;

            }

            await loadProjectFiles(
                window.currentProject.id
            );

            workspaceFileInput.value = "";

        }

        catch (error) {

            console.error(error);

            alert(
                "Upload failed. Please try again."
            );

        }

    }
);