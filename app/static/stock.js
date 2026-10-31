// Private mode only: search our own stock (inventory plugin) from inside a trade room and drop the pick into the
// manual-entry fields with its current listed price. Read-only; nothing is written to inventory from here.
(function () {
  function price(listedOn) { const m = /\$([0-9]+(?:\.[0-9]{1,2})?)/.exec(listedOn || ""); return m ? m[1] : ""; }
  document.querySelectorAll(".add-item-form").forEach((form) => {
    const box = document.createElement("div");
    box.className = "stock-search";
    box.innerHTML = '<input type="search" class="stock-input" placeholder="Our stock: search code or name" autocomplete="off" /><ul class="stock-results" hidden></ul>';
    form.insertBefore(box, form.firstChild);
    const input = box.querySelector("input"), list = box.querySelector("ul");
    let timer = null;
    input.addEventListener("input", () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) { list.hidden = true; return; }
      timer = setTimeout(async () => {
        let data;
        try { const r = await fetch("/api/inventory/items?limit=8&q=" + encodeURIComponent(q)); data = r.ok ? await r.json() : { items: [] }; }
        catch (e) { data = { items: [] }; }
        list.innerHTML = "";
        if (!data.items.length) { list.innerHTML = "<li>No matching stock (is the inventory tab running?)</li>"; list.hidden = false; return; }
        data.items.forEach((it) => {
          const li = document.createElement("li");
          li.textContent = `${it.code} · ${it.name}${it.listed_on ? " · " + it.listed_on : ""}${it.owner === "JWC" ? " · JWC" : ""}`;
          li.addEventListener("click", () => {
            const toggle = form.querySelector(".manual-toggle-checkbox");
            if (!toggle.checked) { toggle.checked = true; toggle.dispatchEvent(new Event("change")); }
            form.querySelector(".manual-name").value = `${it.code} ${it.name}`;
            form.querySelector(".item-price-input").value = price(it.listed_on);
            list.hidden = true; input.value = "";
            form.querySelector(".item-price-input").focus();
          });
          list.appendChild(li);
        });
        list.hidden = false;
      }, 250);
    });
  });
})();
