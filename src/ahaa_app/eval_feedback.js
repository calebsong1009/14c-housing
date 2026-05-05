(function () {
    const bundleFlag = document.querySelector("[data-bundle-flag]");
    const overallFeedback = document.querySelector("[data-overall-feedback]");
    const triggerFlags = Array.from(document.querySelectorAll("[data-flag-button]"));
    const feedbackInputs = Array.from(document.querySelectorAll("[data-feedback-input]"));
    const feedbackList = document.querySelector(".feedback-list");
    const emptyFeedback = document.querySelector(".empty-feedback");
    const saveButton = document.querySelector("[data-save-feedback]");
    const saveStatus = document.querySelector("[data-save-status]");
    const evalResults = document.querySelector("[data-eval-results]");

    function originalResults() {
        if (!evalResults) {
            return { overall_pass: false, triggers: [] };
        }

        try {
            return JSON.parse(evalResults.textContent);
        } catch (error) {
            return { overall_pass: false, triggers: [] };
        }
    }

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
                    key: feedbackKey,
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
        const results = originalResults();
        const saveUrl = saveButton ? saveButton.dataset.saveUrl : "";
        const triggerFeedbackByKey = new Map(
            triggerFlags.map((button) => {
                const feedbackKey = button.dataset.feedbackKey;
                const input = document.querySelector(`[data-feedback-input="${feedbackKey}"]`);

                return [
                    feedbackKey,
                    {
                        flag: button.classList.contains("flagged"),
                        feedback: input ? input.value.trim() : "",
                    },
                ];
            })
        );
        const firedTriggers = (results.triggers || []).map((trigger, index) => ({
            ...trigger,
            ...(triggerFeedbackByKey.get(String(index)) || { flag: false, feedback: "" }),
        }));
        const payload = {
            overall_pass: Boolean(results.overall_pass),
            overall_flag: Boolean(bundleFlag && bundleFlag.classList.contains("flagged")),
            overall_feedback: overallFeedback ? overallFeedback.value.trim() : "",
            fired_triggers: firedTriggers,
            source_files: results.source_files || {},
        };

        if (saveStatus) {
            saveStatus.textContent = "Saving feedback flags...";
        }

        fetch(saveUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Save failed");
                }
                return response.json();
            })
            .then(() => {
                if (saveStatus) {
                    saveStatus.textContent = "✓ Feedback saved.";
                }
            })
            .catch(() => {
                if (saveStatus) {
                    saveStatus.textContent = "Could not save feedback flags.";
                }
            });
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
