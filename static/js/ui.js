(() => {
  function clickTarget(event) {
    const target = event.target;
    return target instanceof Element ? target : null;
  }

  function openModal(modal) {
    if (!modal || typeof modal.showModal !== "function") {
      return;
    }
    modal.showModal();
  }

  function closeModal(modal) {
    if (!modal || typeof modal.close !== "function") {
      return;
    }
    modal.close();
  }

  document.addEventListener("click", (event) => {
    const target = clickTarget(event);
    if (!target) {
      return;
    }

    const openTrigger = target.closest("[data-open-modal]");
    if (openTrigger) {
      event.preventDefault();
      const modalId = openTrigger.getAttribute("data-open-modal");
      openModal(modalId ? document.getElementById(modalId) : null);
      return;
    }

    const closeTrigger = target.closest("[data-close-modal]");
    if (closeTrigger) {
      event.preventDefault();
      closeModal(closeTrigger.closest("dialog"));
      return;
    }

    const dialog = target.closest("dialog");
    if (dialog && dialog.open) {
      const panel = dialog.querySelector("[data-modal-panel]");
      if (panel && !panel.contains(target)) {
        closeModal(dialog);
      }
    }
  });

  document.addEventListener("input", (event) => {
    const input = clickTarget(event)?.closest("[data-search-target]");
    if (!input) {
      return;
    }
    const tableId = input.getAttribute("data-search-target");
    const table = tableId ? document.getElementById(tableId) : null;
    if (!table) {
      return;
    }
    const query = input.value.trim().toLowerCase();
    table.querySelectorAll("tbody tr").forEach((row) => {
      const text = row.textContent?.toLowerCase() || "";
      row.style.display = text.includes(query) ? "" : "none";
    });
  });

  function syncUserRulesVisibility(userId, checked) {
    document.querySelectorAll(`[data-user-rules="${userId}"]`).forEach((el) => {
      el.classList.toggle("hidden", !checked);
    });
  }

  document.querySelectorAll("[data-user-toggle]").forEach((checkbox) => {
    const userId = checkbox.getAttribute("data-user-toggle");
    if (!userId) {
      return;
    }
    syncUserRulesVisibility(userId, checkbox.checked);
    checkbox.addEventListener("change", () => {
      syncUserRulesVisibility(userId, checkbox.checked);
    });
  });
})();
