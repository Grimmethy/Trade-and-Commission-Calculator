(function () {
  const body = document.body;

  function resetSelect(selectEl, placeholder) {
    selectEl.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.disabled = true;
    opt.selected = true;
    opt.textContent = placeholder;
    selectEl.appendChild(opt);
  }

  // --- Inventory list page: new-item form ---
  // Same catalog search/browse/manual-entry selection system as the trade
  // room's AddItemForm (trade.js) — same markup classes, same /catalog/*
  // endpoints — adapted to POST /inventory (create a persistent item) instead
  // of sending an "add_item" WebSocket message into a live trade room, and to
  // let a search/browse pick populate the form for review rather than
  // instant-adding, since inventory creation also needs qty/condition set
  // first. SKU is no longer typed by hand — it's auto-derived server-side
  // from game/faction/condition (SGC's strict <game><faction><condition>-NNN
  // scheme, see app/sku_codes.py) and previewed live via /inventory/next-sku.
  class InventoryAddItemForm {
    constructor(form) {
      this.form = form;
      this.ipSelect = form.querySelector(".ip-select");
      this.factionSelect = form.querySelector(".faction-select");
      this.unitSelect = form.querySelector(".unit-select");
      this.manualToggle = form.querySelector(".manual-toggle-checkbox");
      this.manualFields = form.querySelector(".manual-fields");
      this.manualNameInput = form.querySelector(".manual-name");
      this.manualIpInput = form.querySelector(".manual-ip");
      this.manualFactionInput = form.querySelector(".manual-faction");
      this.catalogPicker = form.querySelector(".catalog-picker-details");
      this.qtyInput = form.querySelector(".item-qty-input");
      this.conditionSelect = form.querySelector(".condition-select");
      this.searchInput = form.querySelector(".catalog-search-input");
      this.searchResultsEl = form.querySelector(".catalog-search-results");
      this.selectedUnitEl = form.querySelector(".selected-unit");
      this.skuPreviewEl = form.querySelector(".sku-preview-value");

      this.unitsById = {};
      this.selectedUnit = null;
      this.searchDebounce = null;
      this.searchResults = [];
      this.skuPreviewDebounce = null;

      this._wireCatalogBrowse();
      this._wireSearch();
      this._wireManualToggle();
      this._wireSkuPreview();
      this._wireSubmit();

      fetch("/catalog/ips")
        .then((r) => r.json())
        .then((data) => {
          resetSelect(this.ipSelect, "Game…");
          for (const ip of data.ips) {
            const opt = document.createElement("option");
            opt.value = ip;
            opt.textContent = ip;
            this.ipSelect.appendChild(opt);
          }
        });
    }

    _currentIpFaction() {
      if (this.manualToggle.checked) {
        return { ip: this.manualIpInput.value.trim(), faction: this.manualFactionInput.value.trim() };
      }
      if (this.selectedUnit) {
        return { ip: this.selectedUnit.ip, faction: this.selectedUnit.faction };
      }
      return { ip: "", faction: "" };
    }

    async _refreshSkuPreview() {
      const { ip, faction } = this._currentIpFaction();
      const params = new URLSearchParams({ condition: this.conditionSelect.value });
      if (ip) params.set("ip", ip);
      if (faction) params.set("faction", faction);
      const res = await fetch(`/inventory/next-sku?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      this.skuPreviewEl.textContent = data.sku;
    }

    _wireSkuPreview() {
      const debounced = () => {
        clearTimeout(this.skuPreviewDebounce);
        this.skuPreviewDebounce = setTimeout(() => this._refreshSkuPreview(), 200);
      };
      this.conditionSelect.addEventListener("change", debounced);
      this.manualIpInput.addEventListener("input", debounced);
      this.manualFactionInput.addEventListener("input", debounced);
      // unit selection (search or browse) calls _refreshSkuPreview directly via selectUnit()
    }

    _unitOptionLabel(unit) {
      return `${unit.item_name} — $${unit.box_price.toFixed(2)}${
        unit.models_per_box ? ` (${unit.models_per_box}/kit)` : ""
      }`;
    }

    _wireCatalogBrowse() {
      this.ipSelect.addEventListener("change", async () => {
        resetSelect(this.factionSelect, "Faction…");
        resetSelect(this.unitSelect, "Unit…");
        this.factionSelect.disabled = true;
        this.unitSelect.disabled = true;
        if (!this.ipSelect.value) return;

        const res = await fetch(`/catalog/factions?ip=${encodeURIComponent(this.ipSelect.value)}`);
        const data = await res.json();
        resetSelect(this.factionSelect, "Faction…");
        for (const faction of data.factions) {
          const opt = document.createElement("option");
          opt.value = faction;
          opt.textContent = faction;
          this.factionSelect.appendChild(opt);
        }
        this.factionSelect.disabled = false;
      });

      this.factionSelect.addEventListener("change", async () => {
        resetSelect(this.unitSelect, "Unit…");
        this.unitSelect.disabled = true;
        if (!this.factionSelect.value) return;

        const res = await fetch(
          `/catalog/units?ip=${encodeURIComponent(this.ipSelect.value)}&faction=${encodeURIComponent(this.factionSelect.value)}`
        );
        const data = await res.json();
        resetSelect(this.unitSelect, "Unit…");
        this.unitsById = {};
        for (const unit of data.units) {
          this.unitsById[unit.id] = unit;
          const opt = document.createElement("option");
          opt.value = unit.id;
          opt.textContent = this._unitOptionLabel(unit);
          this.unitSelect.appendChild(opt);
        }
        this.unitSelect.disabled = false;
      });

      this.unitSelect.addEventListener("change", () => {
        const unit = this.unitsById[this.unitSelect.value];
        if (!unit) {
          this.clearSelection();
          return;
        }
        this.searchInput.value = "";
        this.searchResultsEl.hidden = true;
        this.selectUnit(unit);
      });
    }

    _renderSelectedUnit(unit) {
      if (!unit) {
        this.selectedUnitEl.hidden = true;
        return;
      }
      this.selectedUnitEl.hidden = false;
      this.selectedUnitEl.textContent = `Selected: ${unit.item_name} — ${unit.ip} / ${unit.faction} — $${unit.box_price.toFixed(2)}`;
    }

    selectUnit(unit) {
      this.selectedUnit = unit;
      this.unitsById[unit.id] = unit;
      this._renderSelectedUnit(unit);
      if (unit.models_per_box) this.qtyInput.value = unit.models_per_box;
      this._refreshSkuPreview();
    }

    clearSelection() {
      this.selectedUnit = null;
      this.unitSelect.value = "";
      this._renderSelectedUnit(null);
      this._refreshSkuPreview();
    }

    _wireSearch() {
      const renderSearchResults = (results) => {
        this.searchResults = results;
        this.searchResultsEl.innerHTML = "";
        for (const result of results) {
          const li = document.createElement("li");
          li.textContent = this._unitOptionLabel(result) + ` — ${result.ip} / ${result.faction}`;
          li.addEventListener("click", () => {
            this.searchInput.value = "";
            this.searchResultsEl.hidden = true;
            this.searchResultsEl.innerHTML = "";
            this.searchResults = [];
            this.selectUnit(result);
          });
          this.searchResultsEl.appendChild(li);
        }
        this.searchResultsEl.hidden = results.length === 0;
      };

      this.searchInput.addEventListener("input", () => {
        clearTimeout(this.searchDebounce);
        const q = this.searchInput.value.trim();
        if (q.length < 2) {
          this.searchResultsEl.hidden = true;
          this.searchResultsEl.innerHTML = "";
          this.searchResults = [];
          return;
        }
        this.searchDebounce = setTimeout(async () => {
          const res = await fetch(`/catalog/search?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          renderSearchResults(data.results);
        }, 250);
      });

      this.searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          if (this.searchResults.length > 0) {
            this.searchInput.value = "";
            this.searchResultsEl.hidden = true;
            this.selectUnit(this.searchResults[0]);
          }
        }
      });

      document.addEventListener("click", (e) => {
        if (!this.form.contains(e.target)) return;
        if (!this.searchResultsEl.contains(e.target) && e.target !== this.searchInput) {
          this.searchResultsEl.hidden = true;
        }
      });
    }

    _wireManualToggle() {
      this.manualToggle.addEventListener("change", () => {
        const manual = this.manualToggle.checked;
        this.manualFields.hidden = !manual;
        this.catalogPicker.hidden = manual;
        this.form.querySelector(".catalog-search").hidden = manual;
        this.manualNameInput.required = manual;
        if (manual) this.clearSelection();
        this._refreshSkuPreview();
      });
    }

    _wireSubmit() {
      this.form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const payload = {
          qty: parseInt(this.qtyInput.value, 10) || 1,
          condition: this.conditionSelect.value,
        };

        if (this.manualToggle.checked) {
          const name = this.manualNameInput.value.trim();
          if (!name) return;
          payload.name = name;
          payload.source = "manual";
          payload.ip = this.manualIpInput.value.trim() || null;
          payload.faction = this.manualFactionInput.value.trim() || null;
        } else {
          if (!this.selectedUnit) {
            alert('Search or pick a unit, or check "Enter manually"');
            return;
          }
          payload.name = this.selectedUnit.item_name;
          payload.source = "catalog";
          payload.catalog_item_id = this.selectedUnit.id;
          payload.ip = this.selectedUnit.ip;
          payload.faction = this.selectedUnit.faction;
          payload.box_price = this.selectedUnit.box_price;
          payload.models_per_box = this.selectedUnit.models_per_box;
        }

        const res = await fetch("/inventory", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          const item = await res.json();
          window.location.href = `/inventory/${item.id}`;
        } else {
          alert("Failed to create item: " + (await res.text()));
        }
      });
    }
  }

  document.querySelectorAll(".new-item-form").forEach((form) => new InventoryAddItemForm(form));

  // --- Detail page ---
  const itemId = body.dataset.itemId;
  if (!itemId) return;

  const saveFieldsBtn = document.getElementById("save-fields");
  if (saveFieldsBtn) {
    saveFieldsBtn.addEventListener("click", async () => {
      const payload = {
        name: document.getElementById("field-name").value,
        qty: parseInt(document.getElementById("field-qty").value, 10),
        condition: document.getElementById("field-condition").value,
        notes: document.getElementById("field-notes").value,
      };
      const res = await fetch(`/inventory/${itemId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) alert("Save failed: " + (await res.text()));
    });
  }

  const savePricingBtn = document.getElementById("save-pricing");
  if (savePricingBtn) {
    savePricingBtn.addEventListener("click", async () => {
      const value = parseFloat(document.getElementById("field-third-party-price").value);
      if (Number.isNaN(value)) return alert("Enter a 3rd party price first");
      const res = await fetch(`/inventory/${itemId}/pricing`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ third_party_price: value }),
      });
      if (res.ok) window.location.reload();
      else alert("Save failed: " + (await res.text()));
    });
  }

  const markSoldBtn = document.getElementById("mark-sold");
  if (markSoldBtn) {
    markSoldBtn.addEventListener("click", async () => {
      const value = parseFloat(document.getElementById("field-sell-price").value);
      if (Number.isNaN(value)) return alert("Enter a sell price first");
      const res = await fetch(`/inventory/${itemId}/sold`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sell_price: value }),
      });
      if (res.ok) window.location.reload();
      else alert("Failed: " + (await res.text()));
    });
  }

  const photoUploadForm = document.getElementById("photo-upload-form");
  if (photoUploadForm) {
    photoUploadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("photo-upload-input");
      if (!input.files.length) return;
      const formData = new FormData();
      for (const file of input.files) formData.append("files", file);
      const res = await fetch(`/inventory/${itemId}/photos`, { method: "POST", body: formData });
      if (res.ok) window.location.reload();
      else alert("Upload failed: " + (await res.text()));
    });
  }

  document.querySelectorAll(".make-primary-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const photoId = btn.dataset.photoId;
      const res = await fetch(`/inventory/${itemId}/photos/${photoId}/primary`, { method: "POST" });
      if (res.ok) window.location.reload();
      else alert("Failed: " + (await res.text()));
    });
  });

  document.querySelectorAll(".delete-photo-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this photo?")) return;
      const photoId = btn.dataset.photoId;
      const res = await fetch(`/inventory/${itemId}/photos/${photoId}`, { method: "DELETE" });
      if (res.ok) window.location.reload();
      else alert("Failed: " + (await res.text()));
    });
  });

  const printBtn = document.getElementById("print-label");
  if (printBtn) {
    printBtn.addEventListener("click", async () => {
      const res = await fetch(`/inventory/${itemId}/print-label`, { method: "POST" });
      if (res.ok) alert("Sent to printer.");
      else alert("Print failed: " + (await res.text()));
    });
  }

  const dryRunBtn = document.getElementById("dry-run-label");
  if (dryRunBtn) {
    dryRunBtn.addEventListener("click", async () => {
      const res = await fetch(`/inventory/${itemId}/print-label?dry_run=true`, { method: "POST" });
      const preview = document.getElementById("zpl-preview");
      if (res.ok) {
        const data = await res.json();
        preview.textContent = data.zpl;
        preview.hidden = false;
      } else {
        alert("Preview failed: " + (await res.text()));
      }
    });
  }

  const deleteBtn = document.getElementById("delete-item");
  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      if (!confirm("Delete this inventory item? This cannot be undone.")) return;
      const res = await fetch(`/inventory/${itemId}`, { method: "DELETE" });
      if (res.ok) window.location.href = "/inventory";
      else alert("Delete failed: " + (await res.text()));
    });
  }
})();
