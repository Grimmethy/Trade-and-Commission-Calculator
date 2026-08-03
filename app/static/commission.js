(function () {
  function debounce(fn, ms) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }

  function money(n) {
    return "$" + Number(n).toFixed(2);
  }

  function wireForm(form) {
    const searchInput = form.querySelector(".catalog-search-input");
    const resultsEl = form.querySelector(".catalog-search-results");
    const catalogIdInput = form.querySelector(".catalog-item-id-input");
    const nameInput = form.querySelector(".item-name-input");
    const priceInput = form.querySelector(".item-price-input");

    async function search(query) {
      if (!query || query.length < 2) {
        resultsEl.hidden = true;
        resultsEl.innerHTML = "";
        return;
      }
      const res = await fetch(`/catalog/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      resultsEl.innerHTML = "";
      for (const item of data.results) {
        const li = document.createElement("li");
        li.textContent = `${item.item_name} (${item.faction})`;
        li.addEventListener("click", () => {
          catalogIdInput.value = item.id;
          nameInput.value = item.item_name;
          const unitPrice = item.models_per_box
            ? Math.round((item.box_price / item.models_per_box) * 100) / 100
            : item.box_price;
          priceInput.value = unitPrice;
          resultsEl.hidden = true;
          resultsEl.innerHTML = "";
        });
        resultsEl.appendChild(li);
      }
      resultsEl.hidden = data.results.length === 0;
    }

    searchInput.addEventListener("input", debounce(() => search(searchInput.value), 250));

    // Typing a name manually after picking a catalog result (or without ever picking
    // one) means this is no longer that catalog item -- clear the hidden id so the
    // server treats it as a manual entry instead of silently keeping a stale match.
    nameInput.addEventListener("input", () => {
      catalogIdInput.value = "";
    });

    document.addEventListener("click", (event) => {
      if (!form.contains(event.target)) {
        resultsEl.hidden = true;
      }
    });
  }

  document.querySelectorAll(".commission-add-item-form").forEach(wireForm);

  function wireRename() {
    const codeEl = document.getElementById("commission-code");
    if (!codeEl) return;
    let currentCode = document.body.dataset.commissionCode;

    codeEl.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        codeEl.blur();
      }
    });

    codeEl.addEventListener("blur", async () => {
      const newName = codeEl.textContent.trim();
      if (!newName || newName === currentCode) {
        codeEl.textContent = currentCode;
        return;
      }
      try {
        // keepalive: without it, the browser aborts this request mid-flight if the
        // blur was caused by clicking a link (e.g. "All commissions") and the page
        // starts navigating away before the response comes back.
        const res = await fetch(`/commissions/${currentCode}/rename`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: "new_name=" + encodeURIComponent(newName),
          keepalive: true,
        });
        if (!res.ok) {
          codeEl.textContent = currentCode;
          codeEl.classList.add("rename-failed");
          setTimeout(() => codeEl.classList.remove("rename-failed"), 1500);
          return;
        }
        const newCode = res.url.split("/").pop();
        // Full reload, not just history.replaceState: every other form on this page
        // (settings, status, add-item, verify, delete) has the old code baked into its
        // action URL from server-side rendering -- only a fresh render fixes all of them
        // at once, unlike the trade room page where every action goes through one
        // websocket keyed by room id, not room code.
        window.location.href = `/commissions/${newCode}`;
      } catch {
        codeEl.textContent = currentCode;
        codeEl.classList.add("rename-failed");
        setTimeout(() => codeEl.classList.remove("rename-failed"), 1500);
      }
    });
  }

  wireRename();
})();
