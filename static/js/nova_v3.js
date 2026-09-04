// ========================================
// NOVA V3 - PART 1
// CORE NAVIGATION
// ========================================

const sidebarButtons =
    document.querySelectorAll(
        ".sidebar-button"
    );

const quickCards =
    document.querySelectorAll(
        ".quick-card"
    );

const pages =
    document.querySelectorAll(
        ".page"
    );

    const mobileMenuButton =
    document.getElementById(
        "mobile-menu-button"
    );

const mobileSidebarBackdrop =
    document.getElementById(
        "mobile-sidebar-backdrop"
    );

const sidebar =
    document.querySelector(
        ".sidebar"
    );


function openMobileSidebar() {

    if (!sidebar) {
        return;
    }

    sidebar.classList.add(
        "mobile-open"
    );

    mobileSidebarBackdrop
        ?.classList.add(
            "active"
        );

    document.body.classList.add(
        "mobile-menu-open"
    );

    mobileMenuButton
        ?.setAttribute(
            "aria-expanded",
            "true"
        );
}


function closeMobileSidebar() {

    sidebar
        ?.classList.remove(
            "mobile-open"
        );

    mobileSidebarBackdrop
        ?.classList.remove(
            "active"
        );

    document.body.classList.remove(
        "mobile-menu-open"
    );

    mobileMenuButton
        ?.setAttribute(
            "aria-expanded",
            "false"
        );
}


mobileMenuButton
    ?.addEventListener(
        "click",
        openMobileSidebar
    );


mobileSidebarBackdrop
    ?.addEventListener(
        "click",
        closeMobileSidebar
    );

const mobileChatHistoryButton =
    document.getElementById(
        "mobile-chat-history-button"
    );

const mobileChatHistoryBackdrop =
    document.getElementById(
        "mobile-chat-history-backdrop"
    );

const mobileChatHistory =
    document.querySelector(
        ".nova-chat-history"
    );


function openMobileChatHistory() {

    mobileChatHistory
        ?.classList.add(
            "mobile-open"
        );

    mobileChatHistoryBackdrop
        ?.classList.add(
            "active"
        );

    document.body.classList.add(
        "mobile-menu-open"
    );

}


function closeMobileChatHistory() {

    mobileChatHistory
        ?.classList.remove(
            "mobile-open"
        );

    mobileChatHistoryBackdrop
        ?.classList.remove(
            "active"
        );

    document.body.classList.remove(
        "mobile-menu-open"
    );

}


mobileChatHistoryButton
    ?.addEventListener(
        "click",
        openMobileChatHistory
    );


mobileChatHistoryBackdrop
    ?.addEventListener(
        "click",
        closeMobileChatHistory
    );


document
    .getElementById(
        "conversation-list"
    )
    ?.addEventListener(
        "click",
        event => {

            if (
                event.target.closest(
                    ".conversation-item"
                )
            ) {
                closeMobileChatHistory();
            }

        }
    );

function openPage(pageName) {

    pages.forEach(page => {

        page.classList.remove(
            "active-page"
        );

    });


    const targetPage =
        document.getElementById(
            pageName + "-page"
        );


    if (targetPage) {

        targetPage.classList.add(
            "active-page"
        );

    }


    sidebarButtons.forEach(button => {

        button.classList.remove(
            "active"
        );


        if (
            button.dataset.page ===
            pageName
        ) {

            button.classList.add(
                "active"
            );

        }

    });


    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });

}


// ========================================
// SIDEBAR BUTTONS
// ========================================

sidebarButtons.forEach(button => {

    button.addEventListener(
        "click",
        () => {

            const pageName =
                button.dataset.page;


            if (pageName) {

    openPage(
        pageName
    );

    closeMobileSidebar();

}

        }
    );

});


// ========================================
// DASHBOARD QUICK CARDS
// ========================================

quickCards.forEach(card => {

    card.addEventListener(
        "click",
        () => {

            const pageName =
                card.dataset.page;


            if (pageName) {

                openPage(
                    pageName
                );

            }

        }
    );

});


// ========================================
// OTHER DATA-PAGE BUTTONS
// ========================================

document
    .querySelectorAll(
        "[data-page]"
    )
    .forEach(button => {

        if (
            button.classList.contains(
                "sidebar-button"
            )
            ||
            button.classList.contains(
                "quick-card"
            )
        ) {

            return;

        }


        button.addEventListener(
            "click",
            () => {

                const pageName =
                    button.dataset.page;


                if (pageName) {

                    openPage(
                        pageName
                    );

                }

            }
        );

    });

    // ========================================
// NOVA V3 - PART 2
// PROJECT MODAL + PROJECT LOADING
// ========================================

const projectModal =
    document.getElementById(
        "project-modal"
    );

const newProjectButton =
    document.getElementById(
        "new-project-button"
    );

const heroNewProjectButton =
    document.getElementById(
        "hero-new-project-button"
    );

const sidebarNewProjectButton =
    document.getElementById(
        "sidebar-new-project"
    );

const cancelProjectButton =
    document.getElementById(
        "cancel-project"
    );

const closeProjectModalButton =
    document.getElementById(
        "close-project-modal"
    );

const createProjectButton =
    document.getElementById(
        "create-project"
    );

const projectNameInput =
    document.getElementById(
        "project-name"
    );

const projectDescriptionInput =
    document.getElementById(
        "project-description"
    );

const projectsList =
    document.getElementById(
        "projects-list"
    );

const recentProjects =
    document.getElementById(
        "recent-projects"
    );


// ========================================
// OPEN / CLOSE PROJECT MODAL
// ========================================

function openProjectModal() {

    if (!projectModal) {
        return;
    }

    projectModal.classList.add(
        "show"
    );

    setTimeout(
        () => {

            projectNameInput?.focus();

        },
        100
    );

}


function closeProjectModal() {

    if (!projectModal) {
        return;
    }

    projectModal.classList.remove(
        "show"
    );

}


newProjectButton?.addEventListener(
    "click",
    openProjectModal
);


heroNewProjectButton?.addEventListener(
    "click",
    openProjectModal
);


sidebarNewProjectButton
    ?.addEventListener(
        "click",
        () => {

            openPage("projects");
            openProjectModal();

        }
    );


cancelProjectButton
    ?.addEventListener(
        "click",
        closeProjectModal
    );


closeProjectModalButton
    ?.addEventListener(
        "click",
        closeProjectModal
    );


projectModal?.addEventListener(
    "click",
    event => {

        if (
            event.target ===
            projectModal
        ) {

            closeProjectModal();

        }

    }
);


// ========================================
// LOAD PROJECTS
// ========================================

async function loadProjects() {

    if (!projectsList) {
        return;
    }

    try {

        const response =
            await fetch(
                "/api/projects"
            );

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


        if (
            projects.length === 0
        ) {

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


        projects.forEach(
            project => {

                const card =
                    document.createElement(
                        "div"
                    );

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


                openButton
                    ?.addEventListener(
                        "click",
                        () => {

                            openProject(
                                project.id,
                                project.name,
                                project.description
                            );

                        }
                    );


                projectsList
                    .appendChild(
                        card
                    );

            }
        );


        if (recentProjects) {

            recentProjects.innerHTML =
                "";


            projects
                .slice(0, 3)
                .forEach(
                    project => {

                        const recent =
                            document
                                .createElement(
                                    "button"
                                );

                        recent.className =
                            "recent-project-item";


                        recent.innerHTML = `
    <span class="recent-project-icon">
        📁
    </span>

    <div class="recent-project-info">

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

    <span class="recent-project-arrow">
        →
    </span>
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


                        recentProjects
                            .appendChild(
                                recent
                            );

                    }
                );

        }

    }

    catch (error) {

        console.error(
            error
        );

        projectsList.innerHTML = `
            <div class="empty-state">
                Could not load projects.
            </div>
        `;

    }

}


// ========================================
// CREATE PROJECT
// ========================================

createProjectButton
    ?.addEventListener(
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


                const data =
                    await response.json();


                if (!response.ok) {

                    alert(
                        data.error
                        ||
                        "Could not create project."
                    );

                    return;

                }


                projectNameInput.value =
                    "";

                projectDescriptionInput
                    .value =
                    "";


                closeProjectModal();


                await loadProjects();


                openPage(
                    "projects"
                );

            }

            catch (error) {

                console.error(
                    error
                );

                alert(
                    "Could not create project."
                );

            }

        }
    );


// ========================================
// STARTUP PROJECT LOAD
// ========================================

loadProjects();

// ========================================
// NOVA V3 - PART 3
// PROJECT WORKSPACE + TABS
// ========================================

const workspaceBack =
    document.getElementById(
        "workspace-back"
    );

const workspaceTabs =
    document.querySelectorAll(
        ".workspace-tab"
    );

const workspacePanels =
    document.querySelectorAll(
        ".workspace-panel"
    );


function openProject(
    id,
    name,
    description
) {

    openPage(
        "workspace"
    );


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


    loadProjectNotes?.(
        id
    );

    loadProjectTasks?.(
        id
    );

    loadProjectFiles?.(
        id
    );


    if (
    typeof prepareProjectConversation
    === "function"
) {

    prepareProjectConversation(
        id
    );

}
}



// ========================================
// BACK TO PROJECTS
// ========================================

workspaceBack?.addEventListener(
    "click",
    () => {

        openPage(
            "projects"
        );

    }
);


// ========================================
// WORKSPACE TABS
// ========================================

workspaceTabs.forEach(
    tab => {

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
                    tab.dataset
                        .workspaceTab;


                let targetId =
                    "workspace-"
                    + tabName;


                if (
                    tabName ===
                    "chat"
                ) {

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

    }
);

// ========================================
// NOVA V3 - PART 4
// PROJECT NOTES
// ========================================

const projectNotes =
    document.getElementById(
        "project-notes"
    );

const saveNotesButton =
    document.getElementById(
        "save-notes"
    );


async function loadProjectNotes(
    projectId
) {

    if (!projectNotes) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/projects/${projectId}/notes`
            );


        if (!response.ok) {

            throw new Error(
                "Could not load notes."
            );

        }


        const data =
            await response.json();


        projectNotes.value =
            data.content || "";

    }

    catch (error) {

        console.error(
            error
        );

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


            setTimeout(
                () => {

                    saveNotesButton
                        .textContent =
                        "Save Notes";

                },
                1500
            );

        }

        catch (error) {

            console.error(
                error
            );

            alert(
                "Could not save notes."
            );

        }

    }
);


// ========================================
// NOVA V3 - PART 5
// PROJECT TASKS
// ========================================

const taskList =
    document.getElementById(
        "workspace-task-list"
    );

const newTaskButton =
    document.querySelector(
        "#workspace-tasks .primary-button"
    );


async function loadProjectTasks(
    projectId
) {

    if (!taskList) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/projects/${projectId}/tasks`
            );


        if (!response.ok) {

            throw new Error(
                "Could not load tasks."
            );

        }


        const data =
            await response.json();


        taskList.innerHTML =
            "";


        if (
            !data.tasks
            ||
            data.tasks.length === 0
        ) {

            taskList.innerHTML = `
                <div class="empty-state">
                    No tasks yet.
                </div>
            `;

            return;

        }


        data.tasks.forEach(
            task => {

                const row =
                    document.createElement(
                        "div"
                    );

                row.className =
                    "task-item";


                const label =
                    document.createElement(
                        "label"
                    );

                const checkbox =
                    document.createElement(
                        "input"
                    );

                checkbox.type =
                    "checkbox";

                checkbox.checked =
                    Boolean(
                        task.completed
                    );


                const text =
                    document.createElement(
                        "span"
                    );

                text.textContent =
                    task.title;


                label.appendChild(
                    checkbox
                );

                label.appendChild(
                    text
                );


                const deleteButton =
                    document.createElement(
                        "button"
                    );

                deleteButton.className =
                    "task-delete";

                deleteButton.textContent =
                    "Delete";


                checkbox.addEventListener(
                    "change",
                    async () => {

                        const response =
                            await fetch(
                                `/api/projects/${projectId}/tasks/${task.id}`,
                                {
                                    method:
                                        "PATCH",

                                    headers: {
                                        "Content-Type":
                                            "application/json"
                                    },

                                    body:
                                        JSON.stringify({
                                            completed:
                                                checkbox
                                                    .checked
                                        })
                                }
                            );


                        if (!response.ok) {

                            checkbox.checked =
                                !checkbox.checked;

                            alert(
                                "Could not update task."
                            );

                        }

                    }
                );


                deleteButton
                    .addEventListener(
                        "click",
                        async () => {

                            const confirmed =
                                confirm(
                                    `Delete "${task.title}"?`
                                );


                            if (!confirmed) {
                                return;
                            }


                            const response =
                                await fetch(
                                    `/api/projects/${projectId}/tasks/${task.id}`,
                                    {
                                        method:
                                            "DELETE"
                                    }
                                );


                            if (!response.ok) {

                                alert(
                                    "Could not delete task."
                                );

                                return;

                            }


                            await loadProjectTasks(
                                projectId
                            );

                        }
                    );


                row.appendChild(
                    label
                );

                row.appendChild(
                    deleteButton
                );


                taskList.appendChild(
                    row
                );

            }
        );

    }

    catch (error) {

        console.error(
            error
        );

        taskList.innerHTML = `
            <div class="empty-state">
                Could not load tasks.
            </div>
        `;

    }

}


newTaskButton?.addEventListener(
    "click",
    async () => {

        if (!window.currentProject) {
            return;
        }


        const title =
            prompt(
                "Enter task:"
            );


        if (
            !title
            ||
            !title.trim()
        ) {

            return;

        }


        try {

            const response =
                await fetch(
                    `/api/projects/${window.currentProject.id}/tasks`,
                    {
                        method:
                            "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body:
                            JSON.stringify({
                                title:
                                    title.trim()
                            })
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                alert(
                    data.error
                    ||
                    "Could not create task."
                );

                return;

            }


            await loadProjectTasks(
                window.currentProject.id
            );

        }

        catch (error) {

            console.error(
                error
            );

            alert(
                "Could not create task."
            );

        }

    }
);

// ========================================
// NOVA V3 - PART 6
// PROJECT FILES
// ========================================

const workspaceFilesList =
    document.getElementById(
        "workspace-files-list"
    );

const workspaceFilesPanel =
    document.getElementById(
        "workspace-files"
    );

const workspaceUploadButton =
    workspaceFilesPanel
        ?.querySelector(
            ".primary-button"
        );

const workspaceFileInput =
    document.getElementById(
        "workspace-file-input"
    );


// ========================================
// FORMAT FILE SIZE
// ========================================

function formatFileSize(bytes) {

    const size =
        Number(bytes || 0);

    if (size < 1024) {

        return `${size} B`;

    }

    if (size < 1024 * 1024) {

        return (
            `${(
                size / 1024
            ).toFixed(1)} KB`
        );

    }

    return (
        `${(
            size /
            (1024 * 1024)
        ).toFixed(1)} MB`
    );

}


// ========================================
// LOAD PROJECT FILES
// ========================================

async function loadProjectFiles(
    projectId
) {

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


        workspaceFilesList.innerHTML =
            "";


        if (
            !data.files
            ||
            data.files.length === 0
        ) {

            workspaceFilesList.innerHTML = `
                <div class="empty-state">
                    No files yet.
                </div>
            `;

            return;

        }


        data.files.forEach(
            file => {

                const row =
                    document.createElement(
                        "div"
                    );

                row.className =
                    "file-item";


                const info =
                    document.createElement(
                        "div"
                    );


                const name =
                    document.createElement(
                        "strong"
                    );

                name.textContent =
                    `📄 ${file.filename}`;


                const details =
                    document.createElement(
                        "small"
                    );

                details.textContent =
                    [
                        formatFileSize(
                            file.file_size
                        ),

                        file.mime_type || "",

                        file.uploaded_at || ""
                    ]
                        .filter(Boolean)
                        .join(" • ");


                info.appendChild(
                    name
                );

                info.appendChild(
                    details
                );


                const actions =
                    document.createElement(
                        "div"
                    );

                actions.className =
                    "file-actions";


                const downloadButton =
                    document.createElement(
                        "button"
                    );

                downloadButton.className =
                    "secondary-button";

                downloadButton.textContent =
                    "Download";


                const deleteButton =
                    document.createElement(
                        "button"
                    );

                deleteButton.className =
                    "task-delete";

                deleteButton.textContent =
                    "Delete";


                downloadButton
                    .addEventListener(
                        "click",
                        () => {

                            window.location.href =
                                `/api/projects/${projectId}/files/${file.id}/download`;

                        }
                    );


                deleteButton
                    .addEventListener(
                        "click",
                        async () => {

                            const confirmed =
                                confirm(
                                    `Delete "${file.filename}"?`
                                );


                            if (!confirmed) {
                                return;
                            }


                            try {

                                const response =
                                    await fetch(
                                        `/api/projects/${projectId}/files/${file.id}`,
                                        {
                                            method:
                                                "DELETE"
                                        }
                                    );


                                const data =
                                    await response
                                        .json();


                                if (
                                    !response.ok
                                ) {

                                    alert(
                                        data.error
                                        ||
                                        "Could not delete file."
                                    );

                                    return;

                                }


                                await loadProjectFiles(
                                    projectId
                                );

                            }

                            catch (error) {

                                console.error(
                                    error
                                );

                                alert(
                                    "Could not delete file."
                                );

                            }

                        }
                    );


                actions.appendChild(
                    downloadButton
                );

                actions.appendChild(
                    deleteButton
                );


                row.appendChild(
                    info
                );

                row.appendChild(
                    actions
                );


                workspaceFilesList
                    .appendChild(
                        row
                    );

            }
        );

    }

    catch (error) {

        console.error(
            error
        );


        workspaceFilesList.innerHTML = `
            <div class="empty-state">
                Could not load files.
            </div>
        `;

    }

}


// ========================================
// OPEN FILE SELECTOR
// ========================================

workspaceUploadButton
    ?.addEventListener(
        "click",
        () => {

            if (
                !window.currentProject
            ) {

                alert(
                    "Open a project first."
                );

                return;

            }


            if (
                !workspaceFileInput
            ) {

                alert(
                    "File input is missing."
                );

                return;

            }


            workspaceFileInput.click();

        }
    );


// ========================================
// UPLOAD FILE
// ========================================

workspaceFileInput
    ?.addEventListener(
        "change",
        async () => {

            const file =
                workspaceFileInput
                    .files[0];


            if (!file) {
                return;
            }


            if (
                !window.currentProject
            ) {

                alert(
                    "Open a project first."
                );

                workspaceFileInput.value =
                    "";

                return;

            }


            const formData =
                new FormData();


            formData.append(
                "file",
                file
            );


            if (workspaceUploadButton) {

                workspaceUploadButton
                    .disabled =
                    true;

                workspaceUploadButton
                    .textContent =
                    "Uploading...";

            }


            try {

                const response =
                    await fetch(
                        `/api/projects/${window.currentProject.id}/files`,
                        {
                            method:
                                "POST",

                            body:
                                formData
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    alert(
                        data.error
                        ||
                        "Could not upload file."
                    );

                    return;

                }


                await loadProjectFiles(
                    window.currentProject.id
                );

            }

            catch (error) {

                console.error(
                    error
                );


                alert(
                    "Upload failed. Please try again."
                );

            }

            finally {

                workspaceFileInput.value =
                    "";


                if (
                    workspaceUploadButton
                ) {

                    workspaceUploadButton
                        .disabled =
                        false;

                    workspaceUploadButton
                        .textContent =
                        "Upload File";

                }

            }

        }
    );

    // ========================================
// NOVA V3 - PART 7
// MAIN NOVA CHAT
// ========================================

const chatBox =
    document.getElementById(
        "chat-box"
    );

const userInput =
    document.getElementById(
        "user-input"
    );

const sendButton =
    document.getElementById(
        "send-button"
    );

const newChatButton =
    document.getElementById(
        "new-chat-button"
    );

const conversationList =
    document.getElementById(
        "conversation-list"
    );

window.currentConversationId =
    null;


// ========================================
// CREATE CHAT MESSAGE
// ========================================

function createChatMessage(
    role,
    content,
    container,
    autoScroll = true
) {

    if (!container) {
        return null;
    }


    const message =
        document.createElement(
            "div"
        );


    message.className =
        role === "user"
            ? "message user-message"
            : "message ai-message";


    if (role !== "user") {

        const avatar =
            document.createElement(
                "div"
            );

        avatar.className =
            "message-avatar";

        avatar.textContent =
            "✦";

        message.appendChild(
            avatar
        );

    }


    const inner =
        document.createElement(
            "div"
        );

    inner.className =
        "message-content";


    const name =
        document.createElement(
            "div"
        );

    name.className =
        "message-author";

    name.textContent =
        role === "user"
            ? "You"
            : "Nova";


    const paragraph =
    document.createElement(
        "div"
    );

paragraph.className =
    "message-text";


if (role === "user") {

    paragraph.textContent =
        content;

} else {

    const renderedMarkdown =
        marked.parse(
            content
        );

    paragraph.innerHTML =
        DOMPurify.sanitize(
            renderedMarkdown
        );

        paragraph
    .querySelectorAll("pre")
    .forEach((codeBlock) => {

        const copyButton =
            document.createElement(
                "button"
            );

        copyButton.className =
            "code-copy-button";

        copyButton.textContent =
            "Copy";

        copyButton.addEventListener(
            "click",
            async () => {

                const code =
                    codeBlock.querySelector(
                        "code"
                    );

                if (!code) {
                    return;
                }

                await navigator.clipboard.writeText(
                    code.textContent
                );

                copyButton.textContent =
                    "Copied!";

                setTimeout(
                    () => {
                        copyButton.textContent =
                            "Copy";
                    },
                    1500
                );
            }
        );

        codeBlock.appendChild(
            copyButton
        );
    });

}

    inner.appendChild(
        name
    );

    inner.appendChild(
        paragraph
    );


    message.appendChild(
        inner
    );


    container.appendChild(
        message
    );


    if (autoScroll) {

    container.scrollTop =
        container.scrollHeight;

}


    return message;
}


// ========================================
// RESET MAIN CHAT
// ========================================

function resetMainChat() {

    window.currentConversationId =
        null;


    if (!chatBox) {
        return;
    }


    chatBox.innerHTML =
        "";


    createChatMessage(
        "assistant",
        "What can I help you with today?",
        chatBox
    );


    userInput?.focus();

}


// ========================================
// LOAD CONVERSATION LIST
// ========================================

async function loadConversations() {

    if (!conversationList) {
        return;
    }


    try {

        const response =
            await fetch(
                "/api/conversations"
            );


        if (!response.ok) {

            throw new Error(
                "Could not load conversations."
            );

        }


        const data =
            await response.json();


        const conversations =
            (
                data.conversations
                || []
            )
                .filter(
                    conversation =>
                        conversation
                            .project_id
                        === null
                );


        conversationList.innerHTML =
            "";


        if (
            conversations.length
            === 0
        ) {

            const empty =
                document.createElement(
                    "div"
                );


            empty.className =
                "empty-state";


            empty.textContent =
                "No conversations yet.";


            conversationList
                .appendChild(
                    empty
                );


            return;

        }


        conversations.forEach(
            conversation => {

                const item =
                    document
                        .createElement(
                            "button"
                        );


                item.className =
                    "conversation-item";


                if (
                    conversation.id
                    ===
                    window
                        .currentConversationId
                ) {

                    item.classList.add(
                        "active"
                    );

                }


                item.textContent =
                    conversation.title
                    ||
                    "Conversation";


                item.addEventListener(
                    "click",
                    () => {

                        openConversation(
                            conversation.id
                        );

                    }
                );


                conversationList
                    .appendChild(
                        item
                    );

            }
        );

    }

    catch (error) {

        console.error(
            error
        );

    }

}


// ========================================
// OPEN SAVED CONVERSATION
// ========================================

async function openConversation(
    conversationId
) {

    if (!chatBox) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/conversations/${conversationId}`
            );


        if (!response.ok) {

            throw new Error(
                "Could not open conversation."
            );

        }


        const data =
            await response.json();


        window.currentConversationId =
            conversationId;


        chatBox.innerHTML =
            "";


        (
    data.messages
    || []
)
    .forEach(
        message => {

            createChatMessage(
                message.role,
                message.content,
                chatBox,
                false
            );

        }
    );


chatBox.scrollTop = 0;


        await loadConversations();


        userInput?.focus();

    }

    catch (error) {

        console.error(
            error
        );

    }

}


// ========================================
// SEND MAIN CHAT MESSAGE
// ========================================

async function sendMainMessage() {

    if (
        !userInput
        ||
        !chatBox
    ) {

        return;

    }


    const message =
        userInput
            .value
            .trim();


    if (!message) {
        return;
    }


    createChatMessage(
        "user",
        message,
        chatBox
    );


    userInput.value =
        "";


    const thinkingMessage =
        createChatMessage(
            "assistant",
            "Nova is thinking...",
            chatBox
        );


    if (sendButton) {

        sendButton.disabled =
            true;

    }


       try {

        const response =
            await fetch(
                "/chat",
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({
                            message:
                                message,

                            conversation_id:
                                window
                                    .currentConversationId
                        })
                }
            );


        if (!response.ok) {

            const data =
                await response.json();

            thinkingMessage?.remove();

            createChatMessage(
                "assistant",
                data.message
                ||
                "Nova is temporarily unavailable. Please try again.",
                chatBox
            );

            if (data.conversation_id) {

                window.currentConversationId =
                    data.conversation_id;

            }

            await loadConversations();

            return;

        }

        const contentType =
            response.headers.get(
                "content-type"
            )
            || "";


        if (
            contentType.includes(
                "application/json"
            )
        ) {

            const data =
                await response.json();


            thinkingMessage?.remove();


            if (
                data.conversation_id
            ) {

                window.currentConversationId =
                    data.conversation_id;

            }


            createChatMessage(
                "assistant",
                data.reply
                ||
                data.message
                ||
                "Nova could not respond.",
                chatBox
            );


            await loadConversations();

            return;

        }

        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder();

        let buffer = "";
        let fullReply = "";
        let firstChunkReceived =
            false;


        const liveText =
            thinkingMessage
                ?.querySelector(
                    ".message-text"
                );


        while (true) {

            const {
                value,
                done
            } = await reader.read();


            if (done) {
                break;
            }


            buffer += decoder.decode(
                value,
                {
                    stream: true
                }
            );


            const lines =
                buffer.split("\n");


            buffer =
                lines.pop()
                || "";


            for (const line of lines) {

                if (!line.trim()) {
                    continue;
                }


                const data =
                    JSON.parse(
                        line
                    );


                if (
                    data.type
                    === "delta"
                ) {

                    if (
                        !firstChunkReceived
                    ) {

                        firstChunkReceived =
                            true;

                        if (liveText) {

                            liveText.textContent =
                                "";

                        }

                    }


                    fullReply +=
                        data.delta
                        || "";


                    if (liveText) {

                        liveText.textContent =
                            fullReply;

                    }


                    chatBox.scrollTop =
                        chatBox.scrollHeight;

                }


                else if (
    data.type
    === "done"
) {

    if (
        data.conversation_id
    ) {

        window.currentConversationId =
            data.conversation_id;

    }


    if (
        typeof data.reply
        === "string"
        &&
        data.reply.trim()
    ) {

        fullReply =
            data.reply;

    }

}


                else if (
                    data.type
                    === "error"
                ) {

                    throw new Error(
                        data.message
                        ||
                        "Nova streaming failed."
                    );

                }

            }

        }


        thinkingMessage?.remove();


        createChatMessage(
            "assistant",
            fullReply
            ||
            "Nova could not respond.",
            chatBox
        );


        await loadConversations();

    }

    catch (error) {
        thinkingMessage?.remove();


        console.error(
            error
        );


        createChatMessage(
            "assistant",
            "Nova is temporarily unavailable. Please try again.",
            chatBox
        );

    }

    finally {

        if (sendButton) {

            sendButton.disabled =
                false;

        }


        userInput?.focus();

    }

}


// ========================================
// MAIN CHAT BUTTONS
// ========================================

sendButton?.addEventListener(
    "click",
    sendMainMessage
);


userInput?.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Enter"
            &&
            !event.shiftKey
        ) {

            event.preventDefault();


            sendMainMessage();

        }

    }
);


newChatButton?.addEventListener(
    "click",
    resetMainChat
);


// ========================================
// LOAD SAVED CONVERSATIONS
// ========================================

loadConversations();

// ========================================
// NOVA V3 - PART 8
// PROJECT AI CHAT
// ========================================

const workspaceChat =
    document.getElementById(
        "workspace-chat"
    );

const workspaceInput =
    document.getElementById(
        "workspace-input"
    );

const workspaceSend =
    document.getElementById(
        "workspace-send"
    );

window.workspaceConversationId =
    null;


// ========================================
// RESET PROJECT CHAT
// ========================================

function resetWorkspaceChat() {

    window.workspaceConversationId =
        null;


    if (!workspaceChat) {
        return;
    }


    workspaceChat.innerHTML =
        "";


    createChatMessage(
        "assistant",
        "Ask Nova anything about this project.",
        workspaceChat
    );

}


// ========================================
// LOAD SAVED PROJECT CONVERSATION
// ========================================

async function loadProjectConversation(
    projectId
) {

    if (!workspaceChat) {
        return;
    }


    try {

        const response =
            await fetch(
                "/api/conversations"
            );


        if (!response.ok) {

            throw new Error(
                "Could not load project conversation."
            );

        }


        const data =
            await response.json();


        const conversation =
            (
                data.conversations
                || []
            )
                .find(
                    item =>
                        item.project_id
                        === projectId
                );


        if (!conversation) {

            resetWorkspaceChat();

            return;

        }


        const detailResponse =
            await fetch(
                `/api/conversations/${conversation.id}`
            );


        if (!detailResponse.ok) {

            throw new Error(
                "Could not load project messages."
            );

        }


        const detail =
            await detailResponse.json();


        window.workspaceConversationId =
            conversation.id;


        workspaceChat.innerHTML =
            "";


        (
            detail.messages
            || []
        )
            .forEach(
                message => {

                    createChatMessage(
                        message.role,
                        message.content,
                        workspaceChat
                    );

                }
            );


        workspaceChat.scrollTop =
            workspaceChat.scrollHeight;

    }

    catch (error) {

        console.error(
            error
        );


        resetWorkspaceChat();

    }

}


// ========================================
// SEND PROJECT MESSAGE
// ========================================

async function sendWorkspaceMessage() {

    if (
        !window.currentProject
        ||
        !workspaceInput
        ||
        !workspaceChat
    ) {

        return;

    }


    const message =
        workspaceInput
            .value
            .trim();


    if (!message) {
        return;
    }


    createChatMessage(
        "user",
        message,
        workspaceChat
    );


    workspaceInput.value =
        "";


    const thinkingMessage =
        createChatMessage(
            "assistant",
            "Nova is thinking...",
            workspaceChat
        );


    if (workspaceSend) {

        workspaceSend.disabled =
            true;

    }


        try {

        const response =
            await fetch(
                "/chat",
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify({

                            message:
                                message,

                            project_id:
                                window
                                    .currentProject
                                    .id,

                            conversation_id:
                                window
                                    .workspaceConversationId
                        })
                }
            );


        if (!response.ok) {

            const data =
                await response.json();

            thinkingMessage?.remove();

            createChatMessage(
                "assistant",
                data.message
                ||
                "Nova is temporarily unavailable. Please try again.",
                workspaceChat
            );

            if (
                data.conversation_id
            ) {

                window.workspaceConversationId =
                    data.conversation_id;

            }

            return;

        }

        const contentType =
            response.headers.get(
                "content-type"
            )
            || "";


        if (
            contentType.includes(
                "application/json"
            )
        ) {

            const data =
                await response.json();


            thinkingMessage?.remove();


            if (
                data.conversation_id
            ) {

                window.workspaceConversationId =
                    data.conversation_id;

            }


            createChatMessage(
                "assistant",
                data.reply
                ||
                data.message
                ||
                "Nova could not respond.",
                workspaceChat
            );

            return;

        }

        const reader =
            response.body.getReader();

        const decoder =
            new TextDecoder();

        let buffer = "";
        let fullReply = "";
        let firstChunkReceived =
            false;


        const liveText =
            thinkingMessage
                ?.querySelector(
                    ".message-text"
                );


        while (true) {

            const {
                value,
                done
            } = await reader.read();


            if (done) {
                break;
            }


            buffer += decoder.decode(
                value,
                {
                    stream: true
                }
            );


            const lines =
                buffer.split("\n");


            buffer =
                lines.pop()
                || "";


            for (const line of lines) {

                if (!line.trim()) {
                    continue;
                }


                const data =
                    JSON.parse(
                        line
                    );


                if (
                    data.type
                    === "delta"
                ) {

                    if (
                        !firstChunkReceived
                    ) {

                        firstChunkReceived =
                            true;

                        if (liveText) {

                            liveText.textContent =
                                "";

                        }

                    }


                    fullReply +=
                        data.delta
                        || "";


                    if (liveText) {

                        liveText.textContent =
                            fullReply;

                    }


                    workspaceChat.scrollTop =
                        workspaceChat.scrollHeight;

                }


                else if (
    data.type
    === "done"
) {

    if (
        data.conversation_id
    ) {

        window.workspaceConversationId =
            data.conversation_id;

    }


    if (
        typeof data.reply
        === "string"
        &&
        data.reply.trim()
    ) {

        fullReply =
            data.reply;

    }

}


                else if (
                    data.type
                    === "error"
                ) {

                    throw new Error(
                        data.message
                        ||
                        "Nova streaming failed."
                    );

                }

            }

        }


        thinkingMessage?.remove();


        createChatMessage(
            "assistant",
            fullReply
            ||
            "Nova could not respond.",
            workspaceChat
        );

    }

    catch (error) {

        thinkingMessage?.remove();


        console.error(
            error
        );


        createChatMessage(
            "assistant",
            "Nova is temporarily unavailable. Please try again.",
            workspaceChat
        );

    }

    finally {

        if (workspaceSend) {

            workspaceSend.disabled =
                false;

        }


        workspaceInput?.focus();

    }

}


// ========================================
// PROJECT CHAT BUTTONS
// ========================================

workspaceSend?.addEventListener(
    "click",
    sendWorkspaceMessage
);


workspaceInput?.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Enter"
            &&
            !event.shiftKey
        ) {

            event.preventDefault();


            sendWorkspaceMessage();

        }

    }
);

// ========================================
// NOVA V3 - PART 9
// CONVERSATION MANAGEMENT
// ========================================

async function deleteConversation(
    conversationId
) {

    const confirmed =
        confirm(
            "Delete this conversation?"
        );


    if (!confirmed) {
        return;
    }


    try {

        const response =
            await fetch(
                `/api/conversations/${conversationId}`,
                {
                    method:
                        "DELETE"
                }
            );


        if (!response.ok) {

            throw new Error(
                "Could not delete conversation."
            );

        }


        if (
            window.currentConversationId
            === conversationId
        ) {

            resetMainChat();

        }


        await loadConversations();

    }

    catch (error) {

        console.error(
            error
        );


        alert(
            "Could not delete conversation."
        );

    }

}


// ========================================
// UPGRADED CONVERSATION LIST
// ========================================

async function loadConversations() {

    if (!conversationList) {
        return;
    }


    try {

        const response =
            await fetch(
                "/api/conversations"
            );


        if (!response.ok) {

            throw new Error(
                "Could not load conversations."
            );

        }


        const data =
            await response.json();


        const conversations =
            (
                data.conversations
                || []
            )
                .filter(
                    conversation =>
                        conversation
                            .project_id
                        === null
                );


        conversationList.innerHTML =
            "";


        if (
            conversations.length
            === 0
        ) {

            const empty =
                document.createElement(
                    "div"
                );


            empty.className =
                "empty-state";


            empty.textContent =
                "No conversations yet.";


            conversationList
                .appendChild(
                    empty
                );


            return;

        }


        conversations.forEach(
            conversation => {

                const wrapper =
                    document.createElement(
                        "div"
                    );


                wrapper.className =
                    "conversation-row";


                const item =
                    document.createElement(
                        "button"
                    );


                item.className =
                    "conversation-item";


                if (
                    conversation.id
                    ===
                    window
                        .currentConversationId
                ) {

                    item.classList.add(
                        "active"
                    );

                }


                item.textContent =
                    conversation.title
                    ||
                    "Conversation";


                item.addEventListener(
                    "click",
                    () => {

                        openConversation(
                            conversation.id
                        );

                    }
                );


                const deleteButton =
                    document.createElement(
                        "button"
                    );


                deleteButton.className =
                    "conversation-delete";


                deleteButton.textContent =
                    "×";


                deleteButton.title =
                    "Delete conversation";


                deleteButton.addEventListener(
                    "click",
                    event => {

                        event.stopPropagation();


                        deleteConversation(
                            conversation.id
                        );

                    }
                );


                wrapper.appendChild(
                    item
                );


                wrapper.appendChild(
                    deleteButton
                );


                conversationList
                    .appendChild(
                        wrapper
                    );

            }
        );

    }

    catch (error) {

        console.error(
            error
        );

    }

}

// ========================================
// NOVA V3 - PART 10
// STARTUP + CHAT POLISH
// ========================================


// ========================================
// CLEAN NEW CHAT
// ========================================

function startNewConversation() {

    window.currentConversationId =
        null;


    if (chatBox) {

        chatBox.innerHTML =
            "";

        createChatMessage(
            "assistant",
            "What can I help you with today?",
            chatBox
        );

    }


    loadConversations();


    userInput?.focus();

}


newChatButton?.addEventListener(
    "click",
    startNewConversation
);


// ========================================
// RESTORE MOST RECENT MAIN CHAT
// ========================================

async function restoreLatestConversation() {

    if (
        !conversationList
        ||
        !chatBox
    ) {

        return;

    }


    try {

        const response =
            await fetch(
                "/api/conversations"
            );


        if (!response.ok) {
            return;
        }


        const data =
            await response.json();


        const conversations =
            (
                data.conversations
                || []
            )
                .filter(
                    conversation =>
                        conversation
                            .project_id
                        === null
                );


        if (
            conversations.length
            === 0
        ) {

            resetMainChat();

            return;

        }


        const latest =
            conversations[0];


        await openConversation(
            latest.id
        );

    }

    catch (error) {

        console.error(
            error
        );

    }

}


// ========================================
// PROJECT CHAT RESET WHEN SWITCHING PROJECTS
// ========================================

function prepareProjectConversation(
    projectId
) {

    window.workspaceConversationId =
        null;


    if (workspaceChat) {

        workspaceChat.innerHTML =
            "";

    }


    loadProjectConversation(
        projectId
    );

}


// ========================================
// FINAL STARTUP
// ========================================

restoreLatestConversation();

loadConversations();

// ========================================
// NOVA V3 - PART 11E
// SETTINGS - AI USAGE
// ========================================

const settingsPlan =
    document.getElementById(
        "settings-plan"
    );

const settingsSubscriptionStatus =
    document.getElementById(
        "settings-subscription-status"
    );

const settingsAiUsage =
    document.getElementById(
        "settings-ai-usage"
    );

const settingsAiRemaining =
    document.getElementById(
        "settings-ai-remaining"
    );

    const settingsRenewalDate =
    document.getElementById(
        "settings-renewal-date"
    );
    const settingsBillingPeriod =
    document.getElementById(
        "settings-billing-period"
    );

const upgradeNovaProButton =
    document.getElementById(
        "upgrade-nova-pro"
    );

const upgradeNovaMaxButton =
    document.getElementById(
        "upgrade-nova-max"
    );

const settingsPlanPrice =
    document.getElementById(
        "settings-plan-price"
    );

    const billingCardTitle =
    document.getElementById(
        "billing-card-title"
    );

const sidebarPlanName =
    document.getElementById(
        "sidebar-plan-name"
    );

async function loadAiUsage() {

    try {

        const response =
            await fetch(
                "/api/ai/usage"
            );

        if (!response.ok) {
            throw new Error(
                "Could not load AI usage."
            );
        }

        const data =
            await response.json();


        const plan =
            data.subscription?.plan
            || "none";

        const status =
            data.subscription?.status
            || "inactive";

            const currentPeriodEnd =
    data.subscription?.current_period_end
    || null;

            const statusLabelMap = {
    active: "Active",
    past_due: "Past Due",
    inactive: "Inactive",
    canceled: "Canceled",
    unpaid: "Unpaid",
    paused: "Paused",
    trialing: "Trialing"
};


        const planLabelMap = {
    paid: "Nova Pro",
    pro: "Nova Pro",
    max: "Nova Max",
    developer: "Developer",
    none: "No Plan"
};

if (billingCardTitle) {

    billingCardTitle.textContent =
        plan === "none"
            ? "Nova Plans"
            : (
                planLabelMap[plan]
                || "Billing"
            );

}


if (sidebarPlanName) {

    sidebarPlanName.textContent =
        plan === "none"
            ? "Nova"
            : (
                planLabelMap[plan]
                || "Nova"
            );

}

const planPriceMap = {
    paid: "$14.99 / month",
    pro: "$14.99 / month",
    max: "$29.99 / month",
    developer: "Developer access",
    none: "No active subscription"
};


if (settingsPlan) {

    settingsPlan.textContent =
        planLabelMap[plan]
        || plan;

}


if (settingsPlanPrice) {

    settingsPlanPrice.textContent =
        planPriceMap[plan]
        || "";

}


        if (
    settingsSubscriptionStatus
) {

    settingsSubscriptionStatus
        .textContent =
        statusLabelMap[status]
        || status;

}

if (settingsRenewalDate) {

    if (settingsBillingPeriod) {

    if (
    plan === "paid"
    ||
    plan === "pro"
    ||
    plan === "max"
) {

    settingsBillingPeriod.textContent =
        "Monthly";

}

    else if (plan === "developer") {

        settingsBillingPeriod.textContent =
            "Developer Access";

    }

    else {

        settingsBillingPeriod.textContent =
            "No active billing";

    }

}

    if (currentPeriodEnd) {

        const renewalDate =
            new Date(
                currentPeriodEnd.replace(
                    " ",
                    "T"
                )
            );

        settingsRenewalDate.textContent =
            renewalDate.toLocaleDateString(
                undefined,
                {
                    month: "short",
                    day: "numeric",
                    year: "numeric"
                }
            );

    }

    else {

        settingsRenewalDate.textContent =
            "Not available";

    }

}

               const hasPaidPlan =
            plan === "paid"
            ||
            plan === "pro"
            ||
            plan === "max";

        const isActive =
            status === "active";

        const isPastDue =
            status === "past_due";


        if (
            hasPaidPlan
            &&
            (
                isActive
                ||
                isPastDue
            )
        ) {

            const manageLabel =
                isPastDue
                    ? "Fix Billing"
                    : "Manage Subscription";


            if (upgradeNovaProButton) {

                upgradeNovaProButton.disabled =
                    false;

                upgradeNovaProButton.textContent =
                    manageLabel;

                upgradeNovaProButton.dataset.mode =
                    "manage";

            }


            if (upgradeNovaMaxButton) {

    const isMax =
        plan === "max";


    upgradeNovaMaxButton.disabled =
        isMax;


    upgradeNovaMaxButton.textContent =
        isMax
            ? "Nova Max — Current Plan"
            : "Upgrade to Nova Max";


    upgradeNovaMaxButton.dataset.mode =
        "manage";

}

        }

        else {

            if (upgradeNovaProButton) {

                upgradeNovaProButton.disabled =
                    false;

                upgradeNovaProButton.textContent =
                    "Nova Pro — $14.99";

                upgradeNovaProButton.dataset.mode =
                    "upgrade";

            }


            if (upgradeNovaMaxButton) {

                upgradeNovaMaxButton.disabled =
                    false;

                upgradeNovaMaxButton.textContent =
                    "Nova Max — $29.99";

                upgradeNovaMaxButton.dataset.mode =
                    "upgrade";

            }

        }


        if (settingsAiUsage) {

            if (
                data.limit === null
                ||
                data.limit === undefined
            ) {

                settingsAiUsage.textContent =
                    `${data.total_tokens || 0} tokens`;

            }

            else {

                settingsAiUsage.textContent =
                    `${data.used || 0} / ${data.limit} tokens`;

            }

        }


        if (settingsAiRemaining) {

            if (
                data.remaining === null
                ||
                data.remaining === undefined
            ) {

                settingsAiRemaining.textContent =
                    "Unlimited";

            }

            else {

                settingsAiRemaining.textContent =
                    `${data.remaining} tokens`;

            }

        }

    }

    catch (error) {

        console.error(
            error
        );

        if (settingsAiUsage) {

            settingsAiUsage.textContent =
                "Unavailable";

        }

    }

}


loadAiUsage();


async function handleSubscriptionButton(
    button,
    plan
) {

    if (!button) {
        return;
    }


    const originalText =
        button.textContent;

    const isManage =
        button.dataset.mode
        === "manage";


    button.disabled =
        true;

    button.textContent =
        isManage
            ? "Opening Subscription..."
            : "Opening Checkout...";


    try {

        const endpoint =
            isManage
                ? "/create-portal-session"
                : "/create-checkout-session";


        const requestOptions = {
            method: "POST"
        };


        if (!isManage) {

            requestOptions.headers = {
                "Content-Type":
                    "application/json"
            };

            requestOptions.body =
                JSON.stringify({
                    plan: plan
                });

        }


        const response =
            await fetch(
                endpoint,
                requestOptions
            );


        const data =
            await response.json();


        if (!response.ok) {

            alert(
                data.error
                ||
                "Could not start checkout."
            );

            return;

        }


        if (data.url) {

            window.location.href =
                data.url;

        }

    }

    catch (error) {

        console.error(
            error
        );

        alert(
            "Could not start checkout."
        );

    }

    finally {

        button.disabled =
            false;

        button.textContent =
            originalText;

    }

}


upgradeNovaProButton
    ?.addEventListener(
        "click",
        () => {
            handleSubscriptionButton(
                upgradeNovaProButton,
                "pro"
            );
        }
    );


upgradeNovaMaxButton
    ?.addEventListener(
        "click",
        () => {
            handleSubscriptionButton(
                upgradeNovaMaxButton,
                "max"
            );
        }
    );

    // ========================================
// NOVA THEME PICKER
// ========================================

const themePickerButton =
    document.getElementById(
        "theme-picker-button"
    );

const themePickerMenu =
    document.getElementById(
        "theme-picker-menu"
    );

const themePickerLabel =
    document.getElementById(
        "theme-picker-label"
    );

const themeOptions =
    document.querySelectorAll(
        ".theme-option"
    );


function applyTheme(theme) {

    document.documentElement.setAttribute(
        "data-theme",
        theme
    );

    localStorage.setItem(
        "nova-theme",
        theme
    );


    themeOptions.forEach(
        option => {

            const isActive =
                option.dataset.theme
                === theme;

            option.classList.toggle(
                "active",
                isActive
            );

            const check =
                option.querySelector(
                    ".theme-check"
                );

            if (check) {
                check.textContent =
                    isActive ? "✓" : "";
            }

        }
    );


    if (themePickerLabel) {

        if (theme === "light") {
            themePickerLabel.textContent =
                "Light";
        }

        else if (theme === "system") {
            themePickerLabel.textContent =
                "System";
        }

        else {
            themePickerLabel.textContent =
                "Dark";
        }

    }

}


themePickerButton?.addEventListener(
    "click",
    () => {

        const isOpen =
            themePickerButton.getAttribute(
                "aria-expanded"
            ) === "true";

        themePickerButton.setAttribute(
            "aria-expanded",
            String(!isOpen)
        );

        if (themePickerMenu) {
            themePickerMenu.hidden =
                isOpen;
        }

    }
);


themeOptions.forEach(
    option => {

        option.addEventListener(
            "click",
            () => {

                const theme =
                    option.dataset.theme;

                applyTheme(
                    theme
                );

                if (themePickerMenu) {
                    themePickerMenu.hidden =
                        true;
                }

                themePickerButton
                    ?.setAttribute(
                        "aria-expanded",
                        "false"
                    );

            }
        );

    }
);


const savedTheme =
    localStorage.getItem(
        "nova-theme"
    )
    || "dark";

applyTheme(
    savedTheme
);

// ========================================
// NOVA DRIVE - CURRENT SPEED LIMIT
// ========================================

function getCurrentDriveSpeedLimit(
    userCoordinates,
    route
) {

    if (
        !userCoordinates ||
        !route ||
        !route.geometry ||
        !route.geometry.coordinates ||
        !route.legs ||
        !route.legs[0] ||
        !route.legs[0].annotation ||
        !route.legs[0].annotation.maxspeed
    ) {
        return null;
    }

    const routeCoordinates =
        route.geometry.coordinates;

    const maxspeeds =
        route.legs[0].annotation.maxspeed;

    let nearestIndex = 0;
    let nearestDistance = Infinity;

    routeCoordinates.forEach(
        (coordinate, index) => {

            const lngDifference =
                coordinate[0] -
                userCoordinates[0];

            const latDifference =
                coordinate[1] -
                userCoordinates[1];

            const distance =
                (
                    lngDifference *
                    lngDifference
                ) +
                (
                    latDifference *
                    latDifference
                );

            if (distance < nearestDistance) {

                nearestDistance =
                    distance;

                nearestIndex =
                    index;
            }
        }
    );

    const speedData =
        maxspeeds[
            Math.min(
                nearestIndex,
                maxspeeds.length - 1
            )
        ];

    if (
        !speedData ||
        speedData.unknown
    ) {
        return null;
    }

    let speed =
        speedData.speed;

    let unit =
        speedData.unit;

    if (
        unit === "km/h" &&
        speed
    ) {

        speed =
            Math.round(
                speed * 0.621371
            );

        unit = "mph";
    }

    return {
        speed: speed,
        unit: unit
    };
}

// ========================================
// NOVA DRIVE - MAP + GPS
// ========================================

let driveUserCoordinates = null;
let driveMap = null;
let driveActiveRoute = null;
const driveMapElement =
    document.getElementById(
        "drive-map"
    );


if (
    driveMapElement &&
    window.NOVA_MAPBOX_TOKEN
) {

    mapboxgl.accessToken =
        window.NOVA_MAPBOX_TOKEN;


     driveMap =
        new mapboxgl.Map({
            container: "drive-map",
            style: "mapbox://styles/mapbox/navigation-night-v1",
            center: [-73.9855, 40.7580],
            zoom: 12
        });


    driveMap.addControl(
        new mapboxgl.NavigationControl(),
        "top-right"
    );

       driveMap.on(
    "load",
    () => {

loadDriveCameras();

        driveMap.addSource(
            "nova-traffic",
            {
                type: "vector",
                url: "mapbox://mapbox.mapbox-traffic-v1"
            }
        );

        driveMap.addLayer(
            {
                id: "nova-traffic-layer",
                type: "line",
                source: "nova-traffic",
                "source-layer": "traffic",

                paint: {
                    "line-width": [
                        "interpolate",
                        ["linear"],
                        ["zoom"],
                        10, 2,
                        16, 6
                    ],

                    "line-color": [
                        "match",
                        ["get", "congestion"],
                        "low", "#22c55e",
                        "moderate", "#facc15",
                        "heavy", "#f97316",
                        "severe", "#ef4444",
                        "#22c55e"
                    ],

                    "line-opacity": 0.85
                }
            }
        );

    }
);


    const geolocateControl =
        new mapboxgl.GeolocateControl({
    positionOptions: {
        enableHighAccuracy: true
    },

    trackUserLocation: true,

    showUserHeading: true,

    showAccuracyCircle: true,

    fitBoundsOptions: {
        maxZoom: 17
    }
});


    driveMap.addControl(
        geolocateControl,
        "top-right"
    );
    geolocateControl.on(
    "geolocate",
    (event) => {

        driveUserCoordinates = [
            event.coords.longitude,
            event.coords.latitude
        ];

        if (driveActiveRoute) {
    driveMap.easeTo({
        center: driveUserCoordinates,
        zoom: 17,
        pitch: 60,
        bearing: 0,
        duration: 600
    });
}

        console.log(
            "Nova Drive current location:",
            driveUserCoordinates
        );

        if (driveActiveRoute) {

            const currentSpeedLimit =
                getCurrentDriveSpeedLimit(
                    driveUserCoordinates,
                    driveActiveRoute
                );

            console.log(
    "Nova Drive current speed limit:",
    currentSpeedLimit
);

const navSpeedLimitValue =
    document.getElementById(
        "drive-nav-speed-limit"
    );

const oldSpeedLimitSign =
    document.getElementById(
        "drive-speed-limit"
    );

if (oldSpeedLimitSign) {
    oldSpeedLimitSign.hidden = true;
}

if (
    navSpeedLimitValue &&
    currentSpeedLimit &&
    currentSpeedLimit.speed
) {
    navSpeedLimitValue.textContent =
        currentSpeedLimit.speed;
}

const steps =
    driveActiveRoute.legs &&
    driveActiveRoute.legs[0] &&
    driveActiveRoute.legs[0].steps
        ? driveActiveRoute.legs[0].steps
        : [];

if (steps.length > 0) {

    let nearestStep = steps[0];
    let nearestStepDistance = Infinity;

    steps.forEach((step) => {

        if (
            !step.maneuver ||
            !step.maneuver.location
        ) {
            return;
        }

        const stepLng =
            step.maneuver.location[0];

        const stepLat =
            step.maneuver.location[1];

        const lngDifference =
            stepLng - driveUserCoordinates[0];

        const latDifference =
            stepLat - driveUserCoordinates[1];

        const distance =
            (
                lngDifference *
                lngDifference
            ) +
            (
                latDifference *
                latDifference
            );

        if (distance < nearestStepDistance) {
            nearestStepDistance = distance;
            nearestStep = step;
        }
    });


    const turnDistance =
        document.getElementById(
            "drive-nav-turn-distance"
        );

    const turnInstruction =
        document.getElementById(
            "drive-nav-turn-instruction"
        );

    const turnRoad =
        document.getElementById(
            "drive-nav-turn-road"
        );


    const stepMiles =
        nearestStep.distance / 1609.344;

    let distanceText;

    if (stepMiles < 0.1) {
        distanceText =
            Math.round(
                nearestStep.distance * 3.28084
            ) + " ft";
    } else {
        distanceText =
            stepMiles.toFixed(1) + " mi";
    }


    if (turnDistance) {
        turnDistance.textContent =
            distanceText;
    }

    if (turnInstruction) {
        turnInstruction.textContent =
            nearestStep.maneuver &&
            nearestStep.maneuver.instruction
                ? nearestStep.maneuver.instruction
                : "Continue";
    }

    if (turnRoad) {
        turnRoad.textContent =
            nearestStep.name || "";
    }
}

        }

    }

);


    driveMap.on(
        "load",
        () => {

            const placeholder =
                document.querySelector(
                    ".drive-map-placeholder"
                );

            if (placeholder) {
                placeholder.remove();
            }


            setTimeout(
                () => {
                    geolocateControl.trigger();
                },
                500
            );

if (navigator.geolocation) {

    navigator.geolocation.getCurrentPosition(
        (position) => {

            driveUserCoordinates = [
                position.coords.longitude,
                position.coords.latitude
            ];

            console.log(
                "Nova Drive GPS ready:",
                driveUserCoordinates
            );

        },

        (error) => {

            console.error(
                "Nova Drive GPS error:",
                error
            );

        },

        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 5000
        }
    );

}

        }
    );

}

// ========================================
// NOVA DRIVE - DESTINATION SEARCH
// ========================================

async function searchDriveDestination(query) {

    const token =
        window.NOVA_MAPBOX_TOKEN;

    if (!query || !token) {
        return null;
    }

    const url =
        "https://api.mapbox.com/search/geocode/v6/forward" +
        "?q=" + encodeURIComponent(query) +
        "&access_token=" + encodeURIComponent(token) +
        "&limit=1";

    try {

        const response =
            await fetch(url);

        if (!response.ok) {
            throw new Error(
                "Destination search failed"
            );
        }

        const data =
            await response.json();

        if (
            !data.features ||
            data.features.length === 0
        ) {
            return null;
        }

        const feature =
            data.features[0];

        return {
            name:
                feature.properties?.full_address ||
                feature.properties?.name ||
                query,

            coordinates:
                feature.geometry.coordinates
        };

    } catch (error) {

        console.error(
            "Nova Drive destination error:",
            error
        );

        return null;
    }

}

// ========================================
// NOVA DRIVE - GO BUTTON
// ========================================

const driveDestinationInput =
    document.getElementById(
        "drive-destination"
    );

const driveRouteButton =
    document.getElementById(
        "drive-route-button"
    );


if (
    driveDestinationInput &&
    driveRouteButton
) {

    driveRouteButton.addEventListener(
        "click",
        async () => {

            const query =
                driveDestinationInput.value.trim();

            if (!query) {
                return;
            }


            driveRouteButton.disabled = true;
            driveRouteButton.textContent =
                "Searching...";


            const destination =
                await searchDriveDestination(
                    query
                );


            driveRouteButton.disabled = false;
            driveRouteButton.textContent =
                "Go";


            if (!destination) {

                alert(
                    "Nova Drive couldn't find that destination."
                );

                return;
            }


            console.log(
    "Nova Drive destination:",
    destination
);


if (!driveUserCoordinates) {

    alert(
        "Nova Drive is still getting your location. Try again in a moment."
    );

    return;
}


const route =
    await getDriveRoute(
        driveUserCoordinates,
        destination.coordinates
    );


if (!route) {

    alert(
        "Nova Drive couldn't calculate a driving route."
    );

    return;
}


console.log(
    "Nova Drive route:",
    route
);
driveActiveRoute = route;
drawDriveRoute(route);
showDriveIncidents(route);
const navigationUI =
    document.getElementById("drive-navigation-ui");

if (navigationUI) navigationUI.hidden = false;

const driveSearchCard =
    document.querySelector(".drive-search-card");

if (driveSearchCard) {
    driveSearchCard.hidden = true;
}

const oldSpeedLimitSign =
    document.getElementById("drive-speed-limit");

if (oldSpeedLimitSign) {
    oldSpeedLimitSign.hidden = true;
}

const driveNavArrival =
    document.getElementById("drive-nav-arrival");

const driveNavMinutes =
    document.getElementById("drive-nav-minutes");

const driveNavMiles =
    document.getElementById("drive-nav-miles");

const durationMinutes =
    Math.max(
        1,
        Math.round(route.duration / 60)
    );

const distanceMiles =
    (route.distance / 1609.344).toFixed(1);

const arrivalTime =
    new Date(
        Date.now() + route.duration * 1000
    ).toLocaleTimeString(
        [],
        {
            hour: "numeric",
            minute: "2-digit"
        }
    );

if (driveNavArrival) {
    driveNavArrival.textContent =
        arrivalTime;
}

if (driveNavMinutes) {
    driveNavMinutes.textContent =
        durationMinutes;
}

if (driveNavMiles) {
    driveNavMiles.textContent =
        distanceMiles;
}

const firstStep =
    route.legs &&
    route.legs[0] &&
    route.legs[0].steps &&
    route.legs[0].steps[0];

if (firstStep) {

    const turnDistance =
        document.getElementById(
            "drive-nav-turn-distance"
        );

    const turnInstruction =
        document.getElementById(
            "drive-nav-turn-instruction"
        );

    const turnRoad =
        document.getElementById(
            "drive-nav-turn-road"
        );


    const stepMiles =
        firstStep.distance / 1609.344;

    let distanceText;

    if (stepMiles < 0.1) {
        distanceText =
            Math.round(
                firstStep.distance * 3.28084
            ) + " ft";
    } else {
        distanceText =
            stepMiles.toFixed(1) + " mi";
    }


    if (turnDistance) {
        turnDistance.textContent =
            distanceText;
    }


    if (turnInstruction) {
        turnInstruction.textContent =
            firstStep.maneuver &&
            firstStep.maneuver.instruction
                ? firstStep.maneuver.instruction
                : "Continue";
    }


    if (turnRoad) {
        turnRoad.textContent =
            firstStep.name || "";
    }
}

if (
    route.legs &&
    route.legs[0] &&
    route.legs[0].annotation
) {
    console.log(
        "Nova Drive speed limits:",
        route.legs[0].annotation.maxspeed
    );
}
        }
    );

}

// ========================================
// NOVA DRIVE - ROUTE INCIDENTS
// ========================================


let driveIncidentMarkers = [];


let driveCameraMarkers = [];

async function loadDriveCameras() {
    try {
        const response =
            await fetch(
                "/api/drive/cameras"
            );

        if (!response.ok) {
            throw new Error(
                "Camera request failed"
            );
        }

        const data =
            await response.json();

        showDriveCameraMarkers(
            data.cameras || []
        );
    } catch (error) {
        console.error(
            "Nova Drive camera error:",
            error
        );
    }
}

function showDriveCameraMarkers(
    cameras
) {
    if (!driveMap) {
        return;
    }

    driveCameraMarkers.forEach(
        (marker) => marker.remove()
    );

    driveCameraMarkers = [];

    cameras.forEach(
        (camera) => {

            const markerElement =
                document.createElement(
                    "div"
                );

            markerElement.textContent =
                camera.type ===
                "red_light_camera"
                    ? "🚦"
                    : "📸";

            markerElement.style.fontSize =
                "28px";

            markerElement.style.cursor =
                "pointer";

            const popup =
                new mapboxgl.Popup({
                    offset: 20
                })
                .setHTML(
                    "<strong>" +
                    camera.name +
                    "</strong><br>" +
                    camera.street +
                    "<br>" +
                    camera.borough
                );

            const marker =
                new mapboxgl.Marker({
                    element:
                        markerElement
                })
                .setLngLat([
                    camera.longitude,
                    camera.latitude
                ])
                .setPopup(
                    popup
                )
                .addTo(
                    driveMap
                );

            driveCameraMarkers.push(
                marker
            );
        }
    );
}

function showDriveIncidents(route) {

    if (
        !driveMap ||
        !route ||
        !route.legs ||
        !route.geometry ||
        !route.geometry.coordinates
    ) {
        return;
    }

    // Remove old incident markers
    driveIncidentMarkers.forEach(
        (marker) => marker.remove()
    );

    driveIncidentMarkers = [];

    const incidents = [];

    route.legs.forEach(
        (leg) => {

            if (
                leg.incidents &&
                leg.incidents.length > 0
            ) {
                incidents.push(
                    ...leg.incidents
                );
            }

        }
    );

    console.log(
        "Nova Drive incidents:",
        incidents
    );

    incidents.forEach(
        (incident) => {

            const index =
                incident.geometry_index_start;

            const coordinates =
                route.geometry.coordinates[index];

            if (!coordinates) {
                return;
            }

            let icon = "⚠️";

            if (incident.type === "accident") {
                icon = "💥";
            }

            if (incident.type === "construction") {
                icon = "🚧";
            }

            if (incident.type === "road_closure") {
                icon = "⛔";
            }

            if (incident.type === "disabled_vehicle") {
                icon = "🚙";
            }

            const markerElement =
                document.createElement("div");

            markerElement.textContent =
                icon;

            markerElement.style.fontSize =
                "26px";

            markerElement.style.cursor =
                "pointer";

            const title =
                incident.description ||
                incident.type ||
                "Road incident";

            const popup =
                new mapboxgl.Popup({
                    offset: 20
                })
                .setText(title);

            const marker =
                new mapboxgl.Marker({
                    element: markerElement
                })
                .setLngLat(coordinates)
                .setPopup(popup)
                .addTo(driveMap);

            driveIncidentMarkers.push(
                marker
            );

        }
    );
}

// ========================================
// NOVA DRIVE - DRAW ROUTE
// ========================================

function drawDriveRoute(route) {

    if (
        !driveMap ||
        !route ||
        !route.geometry
    ) {
        return;
    }


    const routeData = {
        type: "Feature",
        properties: {},
        geometry: route.geometry
    };


    if (driveMap.getSource("nova-drive-route")) {

        driveMap
            .getSource("nova-drive-route")
            .setData(routeData);

    } else {

        driveMap.addSource(
            "nova-drive-route",
            {
                type: "geojson",
                data: routeData
            }
        );


driveMap.addLayer({
    id: "nova-drive-route-glow",
    type: "line",
    source: "nova-drive-route",

    layout: {
        "line-join": "round",
        "line-cap": "round"
    },

    paint: {
        "line-width": 16,
        "line-color": "#1597ff",
        "line-opacity": 0.22,
        "line-blur": 8
    }
});

        driveMap.addLayer({
            id: "nova-drive-route-line",
            type: "line",
            source: "nova-drive-route",

            layout: {
                "line-join": "round",
                "line-cap": "round"
            },

            paint: {
    "line-width": 8,
    "line-color": "#1597ff",
    "line-opacity": 1
}
        });

    }

const coordinates =
    route.geometry.coordinates;


const bounds =
    coordinates.reduce(
        (bounds, coordinate) => {

            return bounds.extend(
                coordinate
            );

        },

        new mapboxgl.LngLatBounds(
            coordinates[0],
            coordinates[0]
        )
    );


if (driveUserCoordinates) {
    driveMap.easeTo({
        center: driveUserCoordinates,
        zoom: 17,
        pitch: 60,
        bearing: 0,
        duration: 1200
    });
} else {
    driveMap.fitBounds(
        bounds,
        {
            padding: 60,
            duration: 1200
        }
    );
}

}

// ========================================
// NOVA DRIVE - DRIVING ROUTE
// ========================================

async function getDriveRoute(
    startCoordinates,
    endCoordinates
) {

    const token =
        window.NOVA_MAPBOX_TOKEN;

    if (
        !startCoordinates ||
        !endCoordinates ||
        !token
    ) {
        return null;
    }


    const start =
        startCoordinates.join(",");

    const end =
        endCoordinates.join(",");


    const url =
        "https://api.mapbox.com/directions/v5/mapbox/driving-traffic/" +
        start +
        ";" +
        end +
        "?alternatives=false" +
"&geometries=geojson" +
"&overview=full" +
"&steps=true" +
"&annotations=maxspeed" +
"&access_token=" +
        encodeURIComponent(token);


    try {

        const response =
            await fetch(url);


        if (!response.ok) {

            throw new Error(
                "Route request failed"
            );

        }


        const data =
            await response.json();


        if (
            !data.routes ||
            data.routes.length === 0
        ) {

            return null;

        }


        return data.routes[0];


    } catch (error) {

        console.error(
            "Nova Drive route error:",
            error
        );

        return null;

    }

}

// ========================================
// NOVA DRIVE - MODE PICKER
// ========================================

let novaDriveMode = null;

const driveModeSelector =
    document.getElementById(
        "drive-mode-selector"
    );

const driveModeCurrent =
    document.getElementById(
        "drive-mode-current"
    );

const driveModeButtons =
    document.querySelectorAll(
        ".drive-mode-button"
    );

driveModeButtons.forEach(
    (button) => {

        button.addEventListener(
            "click",
            () => {

                novaDriveMode =
                    button.dataset.driveMode;

                driveModeSelector.hidden = true;
                driveModeCurrent.hidden = false;

                if (novaDriveMode === "truck") {

                    driveModeCurrent.textContent =
                        "🚛 Truck ▾";

                } else {

                    driveModeCurrent.textContent =
                        "🚗 Car ▾";
                }

const driveTruckActions =
    document.getElementById(
        "drive-truck-actions"
    );

const driveCarActions =
    document.getElementById(
        "drive-car-actions"
    );

if (driveTruckActions) {

    driveTruckActions.hidden =
        novaDriveMode !== "truck";
}

if (driveCarActions) {

    driveCarActions.hidden =
        novaDriveMode !== "car";
}

                console.log(
                    "Nova Drive mode:",
                    novaDriveMode
                );
            }
        );

    }
);

driveModeCurrent.addEventListener(
    "click",
    () => {

        driveModeSelector.hidden =
            !driveModeSelector.hidden;

    }
);

// ========================================
// NOVA DRIVE - TRUCK DIESEL SEARCH
// ========================================

const driveTruckActionButtons =
    document.querySelectorAll(
        ".drive-truck-action"
    );

async function searchNearbyDrivePlaces(
    category
) {

    if (
        !driveUserCoordinates ||
        !window.NOVA_MAPBOX_TOKEN
    ) {
        alert(
            "Nova Drive is still getting your location."
        );
        return [];
    }

    const proximity =
        driveUserCoordinates.join(",");

    const url =
        "https://api.mapbox.com/search/searchbox/v1/category/" +
        encodeURIComponent(category) +
        "?proximity=" +
        encodeURIComponent(proximity) +
        "&limit=10" +
        "&access_token=" +
        encodeURIComponent(
            window.NOVA_MAPBOX_TOKEN
        );

    try {

        const response =
            await fetch(url);

        if (!response.ok) {

    const errorText =
        await response.text();

    alert(
        "Mapbox error " +
        response.status +
        ": " +
        errorText
    );

    throw new Error(
        "Nearby place search failed"
    );
}

        const data =
            await response.json();

        return data.features || [];

    } catch (error) {

        console.error(
            "Nova Drive nearby search error:",
            error
        );

        return [];
    }
}

// ========================================
// NOVA DRIVE - SEARCH VISIBLE MAP AREA
// ========================================

async function searchVisibleDrivePlaces(
    category
) {

    if (
        !driveMap ||
        !window.NOVA_MAPBOX_TOKEN
    ) {
        return [];
    }

    const bounds =
        driveMap.getBounds();

    const west =
        bounds.getWest();

    const south =
        bounds.getSouth();

    const east =
        bounds.getEast();

    const north =
        bounds.getNorth();

    const bbox =
        west +
        "," +
        south +
        "," +
        east +
        "," +
        north;

    const url =
        "https://api.mapbox.com/search/searchbox/v1/category/" +
        encodeURIComponent(category) +
        "?bbox=" +
        encodeURIComponent(bbox) +
        "&limit=25" +
        "&access_token=" +
        encodeURIComponent(
            window.NOVA_MAPBOX_TOKEN
        );

    try {

        const response =
            await fetch(url);

        if (!response.ok) {

    const errorText =
        await response.text();

    alert(
        "Mapbox error " +
        response.status +
        ": " +
        errorText
    );

    throw new Error(
        "Visible map search failed"
    );
}

        const data =
            await response.json();

        return data.features || [];

    } catch (error) {

        console.error(
            "Nova Drive visible area search error:",
            error
        );

        return [];
    }
}

driveTruckActionButtons.forEach(
    (button) => {

        button.addEventListener(
            "click",
            async () => {

                const action =
                    button.dataset.truckAction;

                if (action !== "diesel") {
                    return;
                }

                const results =
    await searchVisibleDrivePlaces(
        "gas_station"
    );

               console.log(
    "Nova Drive diesel results:",
    results
);

if (results.length === 0) {

    alert(
        "Nova Drive couldn't find nearby fuel locations."
    );

    return;
}

showDrivePlaceMarkers(
    results,
    "⛽"
); 
            }
        );

    }
);

// ========================================
// NOVA DRIVE - PLACE MARKERS
// ========================================

let drivePlaceMarkers = [];

function showDrivePlaceMarkers(
    places,
    icon
) {

    if (!driveMap) {
        return;
    }

    drivePlaceMarkers.forEach(
        (marker) => marker.remove()
    );

    drivePlaceMarkers = [];

    places.forEach(
        (place) => {

            if (
                !place.geometry ||
                !place.geometry.coordinates
            ) {
                return;
            }

            const properties =
                place.properties || {};

            const name =
                properties.name ||
                "Fuel Location";

            const address =
                properties.full_address ||
                properties.address ||
                properties.place_formatted ||
                "";

            const markerElement =
                document.createElement(
                    "div"
                );

            markerElement.textContent =
                icon;

            markerElement.style.width =
                "38px";

            markerElement.style.height =
                "38px";

            markerElement.style.display =
                "flex";

            markerElement.style.alignItems =
                "center";

            markerElement.style.justifyContent =
                "center";

            markerElement.style.borderRadius =
                "50%";

            markerElement.style.background =
                "rgba(15, 17, 28, 0.96)";

            markerElement.style.border =
                "2px solid rgba(139, 103, 255, 0.9)";

            markerElement.style.fontSize =
                "20px";

            markerElement.style.cursor =
                "pointer";

            markerElement.style.boxShadow =
                "0 6px 18px rgba(0,0,0,0.35)";

            const popup =
                new mapboxgl.Popup({
                    offset: 24
                })
                .setHTML(
                    "<strong>" +
                    name +
                    "</strong>" +
                    (
                        address
                            ? "<br>" + address
                            : ""
                    )
                );

            const marker =
                new mapboxgl.Marker({
                    element:
                        markerElement
                })
                .setLngLat(
                    place.geometry.coordinates
                )
                .setPopup(
                    popup
                )
                .addTo(
                    driveMap
                );

            drivePlaceMarkers.push(
                marker
            );
        }
    );

    const bounds =
        new mapboxgl.LngLatBounds();

    bounds.extend(
        driveUserCoordinates
    );

    places.forEach(
        (place) => {

            if (
                place.geometry &&
                place.geometry.coordinates
            ) {
                bounds.extend(
                    place.geometry.coordinates
                );
            }
        }
    );

    driveMap.fitBounds(
        bounds,
        {
            padding: 70,
            duration: 900,
            maxZoom: 14
        }
    );
}

// ========================================
// NOVA DRIVE - CAR FUEL
// ========================================

const driveCarActionButtons =
    document.querySelectorAll(
        ".drive-car-action"
    );

driveCarActionButtons.forEach(
    (button) => {

        button.addEventListener(
            "click",
            async () => {

                const action =
    button.dataset.carAction;

if (
    action !== "fuel" &&
    action !== "shopping" &&
    action !== "charging" &&
    action !== "food"
) {
    return;
}

                let category = "";

if (action === "fuel") {
    category = "gas_station";
}

if (action === "shopping") {
    category = "shopping";
}

if (action === "charging") {
    category = "charging_station";
}

if (action === "food") {
    category = "restaurant";
}

const results =
    await searchVisibleDrivePlaces(
        category
    );

                if (results.length === 0) {

                    alert(
                        "Nova Drive couldn't find nearby fuel locations."
                    );

                    return;
                }

                showDrivePlaceMarkers(
                    results,
                    "⛽"
                );
            }
        );

    }
);
