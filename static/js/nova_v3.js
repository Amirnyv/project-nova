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