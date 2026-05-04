(function () {
    const bundleFlag = document.querySelector("[data-bundle-flag]");
    const overallFeedback = document.querySelector("[data-overall-feedback]");
    const triggerFlags = Array.from(document.querySelectorAll("[data-flag-button]"));
    const feedbackInputs = Array.from(document.querySelectorAll("[data-feedback-input]"));
    const feedbackList = document.querySelector(".feedback-list");
    const emptyFeedback = document.querySelector(".empty-feedback");
    const saveButton = document.querySelector("[data-save-feedback]");
    const saveStatus = document.querySelector("[data-save-status]");

    function escapeHtml(value) {
        return value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function currentFeedbackItems() {
        const items = [];

        if (bundleFlag && bundleFlag.classList.contains("flagged")) {
            items.push({
                title: "Document bundle passed",
                feedback: overallFeedback ? overallFeedback.value.trim() : "",
            });
        }

        triggerFlags
            .filter((button) => button.classList.contains("flagged"))
            .forEach((button) => {
                const feedbackKey = button.dataset.feedbackKey;
                const input = document.querySelector(`[data-feedback-input="${feedbackKey}"]`);

                items.push({
                    title: button.dataset.feedbackTitle,
                    feedback: input ? input.value.trim() : "",
                });
            });

        return items;
    }

    function updateFeedbackFlags() {
        const items = currentFeedbackItems();

        emptyFeedback.style.display = items.length ? "none" : "block";
        feedbackList.innerHTML = items
            .map((item) => `
                <div class="feedback-item">
                    <div class="feedback-item-title">${escapeHtml(item.title)}</div>
                    <div class="feedback-item-text">${escapeHtml(item.feedback)}</div>
                </div>
            `)
            .join("");

        if (saveButton) {
            saveButton.disabled = !items.length;
        }

        if (saveStatus) {
            saveStatus.textContent = "";
        }
    }

    function saveFeedbackFlags() {
        const items = currentFeedbackItems();
        const payload = {
            savedAt: new Date().toISOString(),
            items,
        };

        localStorage.setItem("eligibilityCheckerFeedbackFlags", JSON.stringify(payload));

        if (saveStatus) {
            saveStatus.textContent = items.length
                ? "Saved feedback flags in this browser."
                : "No feedback flags to save.";
        }
    }

    if (bundleFlag) {
        bundleFlag.addEventListener("click", () => {
            bundleFlag.classList.toggle("flagged");
            updateFeedbackFlags();
        });
    }

    if (overallFeedback) {
        overallFeedback.addEventListener("input", updateFeedbackFlags);
    }

    triggerFlags.forEach((button) => {
        button.addEventListener("click", () => {
            button.classList.toggle("flagged");
            updateFeedbackFlags();
        });
    });

    feedbackInputs.forEach((input) => {
        input.addEventListener("input", updateFeedbackFlags);
    });

    if (saveButton) {
        saveButton.disabled = true;
        saveButton.addEventListener("click", saveFeedbackFlags);
    }
})();
