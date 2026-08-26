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
            "p"
        );

    paragraph.textContent =
        content;


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


        const data =
            await response.json();


        thinkingMessage?.remove();


        if (!response.ok) {

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


        const data =
            await response.json();


        thinkingMessage?.remove();


        if (!response.ok) {

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


        if (settingsPlan) {

            settingsPlan.textContent =
                plan.charAt(0).toUpperCase()
                + plan.slice(1);

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

    if (plan === "paid") {

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

        if (upgradeNovaProButton) {

    const isPaid =
        plan === "paid";

    const isActive =
        status === "active";

    const isPastDue =
        status === "past_due";


    if (isPaid && isActive) {

        upgradeNovaProButton.disabled =
            false;

        upgradeNovaProButton.textContent =
            "Manage Subscription";

        upgradeNovaProButton.dataset.mode =
            "manage";

    }

    else if (isPaid && isPastDue) {

        upgradeNovaProButton.disabled =
            false;

        upgradeNovaProButton.textContent =
            "Fix Billing";

        upgradeNovaProButton.dataset.mode =
            "manage";

    }

    else {

        upgradeNovaProButton.disabled =
            false;

        upgradeNovaProButton.textContent =
            "Upgrade to Nova Pro";

        upgradeNovaProButton.dataset.mode =
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


upgradeNovaProButton
    ?.addEventListener(
        "click",
        async () => {

            upgradeNovaProButton.disabled =
                true;

            upgradeNovaProButton.textContent =
    upgradeNovaProButton.dataset.mode === "manage"
        ? "Opening Subscription..."
        : "Opening Checkout...";


            try {

    const endpoint =
        upgradeNovaProButton.dataset.mode === "manage"
            ? "/create-portal-session"
            : "/create-checkout-session";


    const response =
        await fetch(
            endpoint,
            {
                method: "POST"
            }
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

                upgradeNovaProButton.disabled =
                    false;

                upgradeNovaProButton.textContent =
                    "Upgrade to Nova Pro";

            }

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