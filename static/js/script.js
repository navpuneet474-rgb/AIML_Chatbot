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

// Validate input to prevent empty submissions
function validateInput() {
    const queryInput = document.getElementById("query");
    const appendMessageTo = document.getElementById("query-form")
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
        return false
    }
    return true;
}

function submitQuery(event) {
    if (!validateInput()) {
        event.preventDefault();
        return false;
    } else {
        // Show loading indicator
        const loadingIndicator = document.getElementById("loading-indicator");
        const queryInput = document.getElementById("query");
        const askButton = document.getElementById("ask-button");
        
        // Display loading message
        loadingIndicator.style.display = "block";
        
        // Disable button and clear input
        askButton.disabled = true;
        askButton.textContent = "Processing...";
        
        // Clear input box immediately
        setTimeout(() => {
            queryInput.value = "";
        }, 100);
        
        // Allow form to submit
        return true;
    }
}

// Keep user at bottom (near input box) when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Small delay to ensure page is fully rendered
    setTimeout(function() {
        // Scroll to the bottom of the content div
        const contentDiv = document.querySelector('.content');
        if (contentDiv) {
            contentDiv.scrollTop = contentDiv.scrollHeight;
        }

        // also focus on input
        const queryInput = document.getElementById("query");
        if (queryInput) {
            queryInput.focus();
        }
    }, 100);
});