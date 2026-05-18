(() => {
  const modalButtons = document.querySelectorAll("[data-open-modal]");
  modalButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.getAttribute("data-open-modal");
      const modal = document.getElementById(id);
      if (modal && typeof modal.showModal === "function") {
        modal.showModal();
      }
    });
  });

  const searchInputs = document.querySelectorAll("[data-search-target]");
  searchInputs.forEach((input) => {
    input.addEventListener("input", () => {
      const tableId = input.getAttribute("data-search-target");
      const table = document.getElementById(tableId);
      if (!table) return;
      const query = input.value.trim().toLowerCase();
      table.querySelectorAll("tbody tr").forEach((row) => {
        const text = row.textContent?.toLowerCase() || "";
        row.style.display = text.includes(query) ? "" : "none";
      });
    });
  });
})();
