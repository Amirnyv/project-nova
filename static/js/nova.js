const sidebarButtons =
document.querySelectorAll(".sidebar-button");

const quickCards =
document.querySelectorAll(".quick-card");
const heroNewProjectButton =
document.getElementById("hero-new-project-button");

const pages =
document.querySelectorAll(".page");

function openPage(pageName){

    pages.forEach(page=>{

        page.classList.remove("active-page");

    });

    document
        .getElementById(pageName + "-page")
        .classList.add("active-page");

    sidebarButtons.forEach(button=>{

        button.classList.remove("active");

        if(button.dataset.page===pageName){

            button.classList.add("active");

        }

    });

}

sidebarButtons.forEach(button=>{

    button.onclick=()=>{

        openPage(button.dataset.page);

    };

});

quickCards.forEach(card=>{

    card.onclick=()=>{

        openPage(card.dataset.page);

    };

});

const projectsList =
    document.getElementById("projects-list");

async function loadProjects(){

    try{

        const response =
            await fetch("/api/projects");

        const data =
            await response.json();
            console.log(data);

        projectsList.innerHTML = "";

        if(data.projects.length === 0){

            projectsList.innerHTML = `
                <div class="empty-state">
                    <h3>No projects yet</h3>
                    <p>Create your first project.</p>
                </div>
            `;

            return;

        }

        data.projects.forEach(project=>{

            const card =
            document.createElement("div");

            card.className = "project-item";

            card.innerHTML = `
                <div>

                    <h3>📁 ${project.name}</h3>

                    <p>
                        ${project.description || "No description"}
                    </p>

                </div>

                <button class="resume-button">
                    Open →
                </button>
            `;

            projectsList.appendChild(card);

        });

    }

    catch(error){

        console.error(error);

    }

}

loadProjects();

const projectModal =
    document.getElementById("project-modal");

const newProjectButton =
    document.getElementById("new-project-button");

const cancelProjectButton =
    document.getElementById("cancel-project");
    const createProjectButton =
    document.getElementById("create-project");

const projectNameInput =
    document.getElementById("project-name");

const projectDescriptionInput =
    document.getElementById("project-description");

newProjectButton.onclick = () => {

    projectModal.classList.add("show");

};

cancelProjectButton.onclick = () => {

    projectModal.classList.remove("show");

};
heroNewProjectButton.onclick = () => {

    openPage("projects");

    projectModal.classList.add("show");

};
createProjectButton.onclick = async () => {

    const name =
        projectNameInput.value.trim();

    const description =
        projectDescriptionInput.value.trim();

    if(name === ""){

        alert("Enter a project name.");

        return;

    }

    const response =
        await fetch("/api/projects",{

            method:"POST",

            headers:{
                "Content-Type":"application/json"
            },

            body:JSON.stringify({

                name,
                description

            })

        });

    if(response.ok){

        projectModal.classList.remove("show");

        projectNameInput.value = "";

        projectDescriptionInput.value = "";

        loadProjects();

    }
    else{

        alert("Could not create project.");

    }

};