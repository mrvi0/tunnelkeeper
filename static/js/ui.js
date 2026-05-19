(() => {
  document.addEventListener("click", (event) => {
    const openTrigger = event.target.closest("[data-open-modal]");
    if (openTrigger) {
      event.preventDefault();
      const modalId = openTrigger.getAttribute("data-open-modal");
      const modal = modalId ? document.getElementById(modalId) : null;
      if (modal && typeof modal.showModal === "function") {
        modal.showModal();
      }
      return;
    }

    const closeTrigger = event.target.closest("[data-close-modal]");
    if (closeTrigger) {
      event.preventDefault();
      const modal = closeTrigger.closest("dialog");
      if (modal && typeof modal.close === "function") {
        modal.close();
      }
    }
  });

  document.addEventListener("input", (event) => {
    const input = event.target.closest("[data-search-target]");
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

  document.addEventListener("htmx:afterSwap", () => {
    document.querySelectorAll("dialog[open]").forEach((modal) => {
      if (typeof modal.close === "function") {
        modal.close();
      }
    });
  });
})();
