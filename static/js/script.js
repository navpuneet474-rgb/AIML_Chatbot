// Function to handle feedback submission
function submitFeedback(button, feedbackType) {
    const responseId = button.getAttribute("data-id");
    fetch(`/feedback/${responseId}/${feedbackType}`, {
        method: "POST"
    }).then(response => {
        if (response.ok) {
            alert("Thank you for your feedback!");
        } else {
            alert("Error submitting feedback.");
        }
    });
}

// FEATURE 3: Fill query input when a trending question is clicked
function fillQuery(question) {
    const queryInput = document.getElementById("query");
    queryInput.value = question;
    queryInput.focus();
    // Scroll down to the chatbox so user sees the input filled
    queryInput.scrollIntoView({ behavior: "smooth", block: "center" });
}

// Validate input to prevent empty submissions
function validateInput() {
    const queryInput = document.getElementById("query");
    const appendMessageTo = document.getElementById("query-form");
    const errorElement = document.querySelector('.error-message');
    if (!queryInput.value.trim()) {
        if (!errorElement) {
            const errorMessage = document.createElement("span");
            errorMessage.classList.add('error-message');
            errorMessage.textContent = "Please enter a valid text.";
            errorMessage.style.color = "red";
            errorMessage.style.paddingLeft = "2px";
            errorMessage.style.marginTop = "10px";
            appendMessageTo.parentNode.appendChild(errorMessage);
        }
        return false;
    }
    return true;
}

function submitQuery(event) {
    if (!validateInput()) {
        event.preventDefault();
        return false;
    } else {
        const loadingIndicator = document.getElementById("loading-indicator");
        const queryInput = document.getElementById("query");
        const askButton = document.getElementById("ask-button");

        loadingIndicator.style.display = "block";
        askButton.disabled = true;
        askButton.textContent = "Processing...";

        setTimeout(() => {
            queryInput.value = "";
        }, 100);

        return true;
    }
}

// Scroll to bottom of chat and focus input on page load
document.addEventListener('DOMContentLoaded', function () {
    setTimeout(function () {
        const contentDiv = document.getElementById("chat-content");
        if (contentDiv) {
            contentDiv.scrollTop = contentDiv.scrollHeight;
        }
        const queryInput = document.getElementById("query");
        if (queryInput) {
            queryInput.focus();
        }
    }, 100);
});