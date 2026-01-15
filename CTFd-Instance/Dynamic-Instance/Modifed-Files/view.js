CTFd._internal.challenge.data = undefined

CTFd._internal.challenge.renderer = CTFd._internal.markdown;


CTFd._internal.challenge.preRender = function() {}

CTFd._internal.challenge.render = function(markdown) {

    return CTFd._internal.challenge.renderer.parse(markdown)
}


CTFd._internal.challenge.postRender = function() {
    const containername = CTFd._internal.challenge.data.docker_image;
    get_docker_status(containername);
    createWarningModalBody();
}

function createWarningModalBody(){
    // Creates the Warning Modal placeholder, that will be updated when stuff happens.
    if (CTFd.lib.$('#warningModalBody').length === 0) {
        CTFd.lib.$('body').append('<div id="warningModalBody"></div>');
    }
}

function get_docker_status(container) {
    const containerDiv = CTFd.lib.$('#docker_container');
    const NormalStartButtonHTML = `
        <span>
            <a onclick="start_container('${container}');" class='btn btn-dark'>
                <small style='color:white;'><i class="fas fa-play"></i> <b>START INSTANCE</b></small>
            </a>
        </span>`;

    CTFd.fetch("/api/v1/docker_status")
    .then(response => response.json())
    .then(result => {
        if (!result.success || !result.data || result.data.length === 0) {
            containerDiv.html(NormalStartButtonHTML);
            return;
        }

        let matchFound = false;
        result.data.forEach(item => {
            if (item.docker_image == container) {
                matchFound = true;
                const ports = String(item.ports).split(',');
                let data = '';
                
                ports.forEach(port => {
                    const cleanPort = port.split('/')[0];
                    const fullAddress = `${item.host}:${cleanPort}`;
                    // Added the href Link format you requested
                    data += `Link: <a href="http://${fullAddress}" target="_blank" style="color: #00bc8c; text-decoration: underline;">${fullAddress}</a><br />`;
                });

                const instance_short_id = String(item.instance_id).substring(0, 10);
                
                containerDiv.html(`
                    <pre style="color:inherit;">Docker Container Information:<br />${data}</pre>
                    <div class="mb-2">
                        <a onclick="start_container('${item.docker_image}');" class="btn btn-warning btn-sm mr-2">
                            <small style="color:black;"><i class="fas fa-sync-alt"></i> <b>RESTART INSTANCE</b></small>
                        </a>
                    </div>
                    <div id="${instance_short_id}_expiry_timer"></div>
                `);

                const countDownDate = new Date(parseInt(item.revert_time) * 1000).getTime();
                if (window.dockerInterval) clearInterval(window.dockerInterval);

                window.dockerInterval = setInterval(function() {
                    const now = new Date().getTime();
                    const distance = countDownDate - now;

                    if (distance <= 0) {
                        clearInterval(window.dockerInterval);
                        containerDiv.html('<small class="text-info">Instance expired. Resetting UI...</small>');
                        
                        // Increased to 7 seconds to ensure the Python thread (which sleeps 3s) has run
                        setTimeout(() => {
                            get_docker_status(container);
                        }, 7000);
                        return;
                    }

                    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((distance % (1000 * 60)) / 1000).toString().padStart(2, '0');

                    CTFd.lib.$(`#${instance_short_id}_expiry_timer`).html(
                        `<small class="text-muted">Instance expires in: <b>${minutes}:${seconds}</b></small>`
                    );
                }, 1000);
            }
        });

        if (!matchFound) containerDiv.html(NormalStartButtonHTML);
    });
}
function stop_container(container) {
    if (confirm("Are you sure you want to stop the container for: \n" + CTFd._internal.challenge.data.name)) {
        CTFd.fetch("/api/v1/container?name=" + encodeURIComponent(container) + 
                   "&challenge=" + encodeURIComponent(CTFd._internal.challenge.data.name) + 
                   "&stopcontainer=True", {
            method: "GET"
        })
        .then(function (response) {
            return response.json().then(function (json) {
                if (response.ok) {
                    updateWarningModal({
                        title: "Attention!",
                        warningText: "The Docker container for <br><strong>" + CTFd._internal.challenge.data.name + "</strong><br> was stopped successfully.",
                        buttonText: "Close",
                        onClose: function () {
                            get_docker_status(container);  // ← Will be called when modal is closed
                        }
                    });
                } else {
                    throw new Error(json.message || 'Failed to stop container');
                }
            });
        })
        .catch(function (error) {
            updateWarningModal({
                title: "Error",
                warningText: error.message || "An unknown error occurred while stopping the container.",
                buttonText: "Close",
                onClose: function () {
                    get_docker_status(container);  // ← Will be called when modal is closed
                }
            });

        });
    }
}

function start_container(container) {
    CTFd.lib.$('#docker_container').html('<div class="text-center"><i class="fas fa-circle-notch fa-spin fa-1x"></i></div>');
    CTFd.fetch("/api/v1/container?name=" + encodeURIComponent(container) + "&challenge=" + encodeURIComponent(CTFd._internal.challenge.data.name), {
        method: "GET"
    }).then(function (response) {
        return response.json().then(function (json) {
            if (response.ok) {
                get_docker_status(container);
    
                updateWarningModal({
                    title: "Attention!",
                    warningText: "A Docker container is started for you.<br>Note that you can only revert or stop a container once per 5 minutes!",
                    buttonText: "Got it!"
                });

            } else {
                throw new Error(json.message || 'Failed to start container');
            }
        });
    }).catch(function (error) {
        // Handle error and notify the user
        updateWarningModal({
            title: "Error!",
            warningText: error.message || "An unknown error occurred when starting your Docker container.",
            buttonText: "Got it!",
            onClose: function () {
                get_docker_status(container);  // ← Will be called when modal is closed
            }
        });
    });
}

// WE NEED TO CREATE THE MODAL FIRST, and this should be only used to fill it.

function updateWarningModal({
    title , warningText, buttonText, onClose } = {}) {
    const modalHTML = `
        <div id="warningModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; z-index:9999; background-color:rgba(0,0,0,0.5);">
          <div style="position:relative; margin:10% auto; width:400px; background:white; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.3); overflow:hidden;">
            <div class="modal-header bg-warning text-dark" style="padding:1rem; display:flex; justify-content:space-between; align-items:center;">
              <h5 class="modal-title" style="margin:0;">${title}</h5>
              <button type="button" id="warningCloseBtn" style="border:none; background:none; font-size:1.5rem; line-height:1; cursor:pointer;">&times;</button>
            </div>
            <div class="modal-body" style="padding:1rem;">
              ${warningText}
            </div>
            <div class="modal-footer" style="padding:1rem; text-align:right; border-top:1px solid #dee2e6;">
              <button type="button" class="btn btn-secondary" id="warningOkBtn">${buttonText}</button>
            </div>
          </div>
        </div>
    `;
    CTFd.lib.$("#warningModalBody").html(modalHTML);

    // Show the modal
    CTFd.lib.$("#warningModal").show();

    // Close logic with callback
    const closeModal = () => {
        CTFd.lib.$("#warningModal").hide();
        if (typeof onClose === 'function') {
            onClose();  
        }
    };

    CTFd.lib.$("#warningCloseBtn").on("click", closeModal);
    CTFd.lib.$("#warningOkBtn").on("click", closeModal);
}

// In order to capture the flag submission, and remove the "Revert" and "Stop" buttons after solving a challenge
// We need to hook that call, and do this manually.
function checkForCorrectFlag() {
    const challengeWindow = document.querySelector('#challenge-window');
    if (!challengeWindow || getComputedStyle(challengeWindow).display === 'none') {
        // console.log("❌ Challenge window hidden or closed, stopping check.");
        clearInterval(checkInterval);
        checkInterval = null;
        return;
    }

    const notification = document.querySelector('.notification-row .alert');
    if (!notification) return;

    const strong = notification.querySelector('strong');
    if (!strong) return;

    const message = strong.textContent.trim();

    if (message.includes("Correct")) {
        // console.log("✅ Correct flag detected:", message);
        get_docker_status(CTFd._internal.challenge.data.docker_image);
        clearInterval(checkInterval);
        checkInterval = null;
    }
}

if (!checkInterval) {
    var checkInterval = setInterval(checkForCorrectFlag, 1500);
}
