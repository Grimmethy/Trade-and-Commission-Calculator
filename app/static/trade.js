(function () {
  const roomCode = document.body.dataset.roomCode;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${proto}://${window.location.host}/ws/${roomCode}`);

  const statusEl = document.getElementById("status");
  const totalAEl = document.getElementById("total-a");
  const totalBEl = document.getElementById("total-b");
  const balanceEl = document.getElementById("balance");
  const itemsAEl = document.getElementById("items-a");
  const itemsBEl = document.getElementById("items-b");
  const labelAEl = document.getElementById("label-a");
  const labelBEl = document.getElementById("label-b");
  const cashAEl = document.getElementById("cash-a");
  const cashBEl = document.getElementById("cash-b");
  const venueSelect = document.getElementById("venue-select");
  const inPersonDifferentialInput = document.getElementById("in-person-differential");
  const onlineDifferentialInput = document.getElementById("online-differential");
  const inPersonDifferentialLabel = document.getElementById("in-person-differential-label");
  const onlineDifferentialLabel = document.getElementById("online-differential-label");
  const roomCodeEl = document.getElementById("room-code");
  const commissionSideSelect = document.getElementById("commission-side-select");
  const commissionSideAOption = document.getElementById("commission-side-a-option");
  const commissionSideBOption = document.getElementById("commission-side-b-option");
  const commissionFields = document.getElementById("commission-fields");
  const commissionTypeSelect = document.getElementById("commission-type-select");
  const commissionRateInput = document.getElementById("commission-rate");
  const commissionBaseInput = document.getElementById("commission-base");
  const commissionFlatInput = document.getElementById("commission-flat");
  const commissionRateLabel = document.getElementById("commission-rate-label");
  const commissionBaseLabel = document.getElementById("commission-base-label");
  const commissionFlatLabel = document.getElementById("commission-flat-label");
  const commissionAmountDisplay = document.getElementById("commission-amount-display");

  const CONDITION_LABELS = {
    needs_repair: "Needs Repair",
    assembled: "Assembled",
    partial_paint: "Partial Paint",
    showcase: "Showcase",
  };

  let latestState = null;

  socket.addEventListener("open", () => {
    statusEl.textContent = "Connected";
  });
  socket.addEventListener("close", () => {
    statusEl.textContent = "Disconnected — reload the page to reconnect";
  });
  socket.addEventListener("error", () => {
    statusEl.textContent = "Connection error";
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "full_state") {
      latestState = message.payload;
      render(latestState);
    } else if (message.type === "error") {
      statusEl.textContent = "Error: " + message.payload.message;
    }
  });

  function send(type, payload) {
    socket.send(JSON.stringify({ type, payload }));
  }

  function money(n) {
    return "$" + Number(n).toFixed(2);
  }

  function render(state) {
    if (state.room.code !== roomCodeEl.textContent) {
      // Side B's name drives the room's actual code/URL — keep the address bar and
      // title in sync so a page refresh still resolves (the old URL now 404s).
      roomCodeEl.textContent = state.room.code;
      document.title = `Trade Calculator — Room ${state.room.code}`;
      history.replaceState(null, "", `/trade/${state.room.code}`);
    }

    const venued = state.room.trade_venue !== "direct";
    totalAEl.textContent = venued
      ? `${state.room.label_a}: ${money(state.totals.side_a)} (${money(state.totals.effective_side_a)} after differential)`
      : `${state.room.label_a}: ${money(state.totals.side_a)}`;
    totalBEl.textContent = venued
      ? `${state.room.label_b}: ${money(state.totals.side_b)} (${money(state.totals.effective_side_b)} after differential)`
      : `${state.room.label_b}: ${money(state.totals.side_b)}`;

    if (state.totals.suggested_topup_side === null) {
      balanceEl.textContent = "Balanced";
    } else {
      const sideLabel =
        state.totals.suggested_topup_side === "A" ? state.room.label_a : state.room.label_b;
      balanceEl.textContent = `${sideLabel} should add ${money(state.totals.suggested_topup_amount)} cash to balance`;
    }

    if (document.activeElement !== labelAEl) labelAEl.textContent = state.room.label_a;
    if (document.activeElement !== labelBEl) labelBEl.textContent = state.room.label_b;
    if (document.activeElement !== cashAEl) cashAEl.value = state.room.cash_a;
    if (document.activeElement !== cashBEl) cashBEl.value = state.room.cash_b;
    if (document.activeElement !== venueSelect) venueSelect.value = state.room.trade_venue;
    if (document.activeElement !== inPersonDifferentialInput) {
      inPersonDifferentialInput.value = Math.round(state.room.in_person_differential * 100);
    }
    if (document.activeElement !== onlineDifferentialInput) {
      onlineDifferentialInput.value = Math.round(state.room.online_differential * 100);
    }
    inPersonDifferentialLabel.classList.toggle("active-venue", state.room.trade_venue === "in_person");
    onlineDifferentialLabel.classList.toggle("active-venue", state.room.trade_venue === "online");

    commissionSideAOption.textContent = state.room.label_a;
    commissionSideBOption.textContent = state.room.label_b;
    if (document.activeElement !== commissionSideSelect) {
      commissionSideSelect.value = state.room.commission_side || "";
    }
    const commissionActive = !!state.room.commission_side;
    commissionFields.hidden = !commissionActive;
    if (document.activeElement !== commissionTypeSelect) {
      commissionTypeSelect.value = state.room.commission_type;
    }
    const isPercentage = state.room.commission_type === "percentage";
    commissionRateLabel.hidden = !isPercentage;
    commissionBaseLabel.hidden = !isPercentage;
    commissionFlatLabel.hidden = isPercentage;
    if (document.activeElement !== commissionRateInput) {
      commissionRateInput.value = Math.round(state.room.commission_rate * 100);
    }
    if (document.activeElement !== commissionBaseInput) {
      commissionBaseInput.value = state.room.commission_base;
    }
    if (document.activeElement !== commissionFlatInput) {
      commissionFlatInput.value = state.room.commission_flat_amount;
    }
    if (commissionActive) {
      const owedLabel = state.room.commission_side === "A" ? state.room.label_a : state.room.label_b;
      commissionAmountDisplay.textContent = `${money(state.totals.commission_amount)} owed to ${owedLabel}`;
    }

    renderItems(itemsAEl, state.items.filter((i) => i.side === "A"));
    renderItems(itemsBEl, state.items.filter((i) => i.side === "B"));
  }

  function renderItems(listEl, items) {
    listEl.innerHTML = "";
    for (const item of items) {
      const li = document.createElement("li");
      li.className = "item-row";

      const nameSpan = document.createElement("span");
      nameSpan.className = "item-name";
      nameSpan.textContent = item.name;

      const qtyInput = document.createElement("input");
      qtyInput.type = "number";
      qtyInput.min = "1";
      qtyInput.value = item.qty;
      qtyInput.className = "item-qty";
      qtyInput.addEventListener("change", () => {
        send("edit_item", { item_id: item.id, qty: Number(qtyInput.value) });
      });

      const kitSpan = document.createElement("span");
      kitSpan.className = "item-kit-size";
      if (item.models_per_box) {
        kitSpan.textContent = `of ${item.models_per_box}`;
        if (item.qty < item.models_per_box) kitSpan.classList.add("partial-kit");
      }

      const conditionSelect = document.createElement("select");
      conditionSelect.className = "item-condition";
      for (const [value, label] of Object.entries(CONDITION_LABELS)) {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = label;
        opt.selected = value === item.condition;
        conditionSelect.appendChild(opt);
      }
      conditionSelect.addEventListener("change", () => {
        send("edit_item", { item_id: item.id, condition: conditionSelect.value });
      });

      const priceInput = document.createElement("input");
      priceInput.type = "number";
      priceInput.step = "0.01";
      priceInput.min = "0";
      priceInput.value = item.unit_price;
      priceInput.className = "item-price";
      priceInput.addEventListener("change", () => {
        send("edit_item", { item_id: item.id, unit_price: Number(priceInput.value) });
      });

      const lineTotal = document.createElement("span");
      lineTotal.className = "item-line-total";
      lineTotal.textContent = money(item.line_total);

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "remove-btn";
      removeBtn.textContent = "×";
      removeBtn.addEventListener("click", () => {
        send("remove_item", { item_id: item.id });
      });

      li.append(nameSpan, qtyInput, kitSpan, conditionSelect, priceInput, lineTotal, removeBtn);
      listEl.appendChild(li);
    }
  }

  async function fetchJson(url) {
    const res = await fetch(url);
    return res.json();
  }

  function resetSelect(selectEl, placeholder) {
    selectEl.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "";
    opt.disabled = true;
    opt.selected = true;
    opt.textContent = placeholder;
    selectEl.appendChild(opt);
  }

  // One AddItemForm per side (Side A and Side B are two real, identical
  // instances — not a hypothetical seam). Owns catalog search/browse, the
  // selected-unit and kit-size editing state, and the manual-entry fallback;
  // exposes nothing beyond "construct it and it manages its own <form>".
  class AddItemForm {
    constructor(form) {
      this.form = form;
      this.side = form.closest(".side").dataset.side;
      this.ipSelect = form.querySelector(".ip-select");
      this.factionSelect = form.querySelector(".faction-select");
      this.unitSelect = form.querySelector(".unit-select");
      this.manualToggle = form.querySelector(".manual-toggle-checkbox");
      this.manualFields = form.querySelector(".manual-fields");
      this.manualNameInput = form.querySelector(".manual-name");
      this.catalogPicker = form.querySelector(".catalog-picker-details");
      this.qtyInput = form.querySelector(".item-qty-input");
      this.priceInput = form.querySelector(".item-price-input");
      this.conditionSelect = form.querySelector(".condition-select");
      this.kitInfo = form.querySelector(".kit-info");
      this.kitInfoHint = form.querySelector(".kit-info-hint");
      this.kitModelsInput = form.querySelector(".kit-models-input");
      this.kitModelsSave = form.querySelector(".kit-models-save");
      this.searchInput = form.querySelector(".catalog-search-input");
      this.searchResultsEl = form.querySelector(".catalog-search-results");
      this.selectedUnitEl = form.querySelector(".selected-unit");

      this.unitsById = {};
      this.selectedUnit = null;
      this.searchDebounce = null;
      this.searchResults = [];

      this._wireCatalogBrowse();
      this._wireSearch();
      this._wireKitModelsSave();
      this._wireManualToggle();
      this._wireSubmit();

      fetchJson("/catalog/ips").then((data) => {
        resetSelect(this.ipSelect, "Game…");
        for (const ip of data.ips) {
          const opt = document.createElement("option");
          opt.value = ip;
          opt.textContent = ip;
          this.ipSelect.appendChild(opt);
        }
      });
    }

    _wireCatalogBrowse() {
      this.ipSelect.addEventListener("change", async () => {
        resetSelect(this.factionSelect, "Faction…");
        resetSelect(this.unitSelect, "Unit…");
        this.factionSelect.disabled = true;
        this.unitSelect.disabled = true;
        this.kitInfo.hidden = true;
        if (!this.ipSelect.value) return;

        const data = await fetchJson(`/catalog/factions?ip=${encodeURIComponent(this.ipSelect.value)}`);
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
        this.kitInfo.hidden = true;
        if (!this.factionSelect.value) return;

        const data = await fetchJson(
          `/catalog/units?ip=${encodeURIComponent(this.ipSelect.value)}&faction=${encodeURIComponent(this.factionSelect.value)}`
        );
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

    _unitOptionLabel(unit) {
      return `${unit.item_name} — $${unit.box_price.toFixed(2)}${
        unit.models_per_box ? ` (${unit.models_per_box}/kit)` : ""
      }`;
    }

    _refreshUnitOption(unit) {
      const opt = this.unitSelect.querySelector(`option[value="${unit.id}"]`);
      if (opt) opt.textContent = this._unitOptionLabel(unit);
    }

    _updateKitInfo(unit) {
      if (!unit) {
        this.kitInfo.hidden = true;
        return;
      }
      this.kitInfo.hidden = false;
      this.kitModelsInput.value = unit.models_per_box || "";
      this.kitInfoHint.textContent = unit.models_per_box
        ? "Trading fewer than this is a partial kit — wrong? Fix it above."
        : "Unknown — enter it so partial-kit pricing works";
    }

    _applyDerivedPrice(unit) {
      const derivedPrice = unit.models_per_box ? unit.box_price / unit.models_per_box : unit.box_price;
      this.priceInput.value = derivedPrice.toFixed(2);
    }

    _applyDefaultQty(unit) {
      // Most trades are for a whole kit, not a single model out of it —
      // default to the full count so the common case needs no editing; still
      // just a starting point, freely overridable for partial-kit trades.
      this.qtyInput.value = unit.models_per_box || 1;
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
      this._applyDerivedPrice(unit);
      this._applyDefaultQty(unit);
      this._updateKitInfo(unit);
      this._renderSelectedUnit(unit);
    }

    clearSelection() {
      this.selectedUnit = null;
      this.unitSelect.value = "";
      this._renderSelectedUnit(null);
      this._updateKitInfo(null);
    }

    _wireSearch() {
      // Selecting a search result adds it to the trade immediately (qty
      // defaults to the full kit, condition to Assembled) — search is the
      // fast path; adjust qty/condition/price afterward on the item's own
      // row, same as any other item. The dropdown "browse by game/faction"
      // path is the slower, adjust-before-adding path.
      const addSearchResult = (unit) => {
        send("add_item", {
          side: this.side,
          qty: unit.models_per_box || 1,
          condition: "assembled",
          name: unit.item_name,
          source: "catalog",
          catalog_item_id: unit.id,
        });
        this.searchInput.value = "";
        this.searchResultsEl.hidden = true;
        this.searchResultsEl.innerHTML = "";
        this.searchResults = [];
      };

      const renderSearchResults = (results) => {
        this.searchResults = results;
        this.searchResultsEl.innerHTML = "";
        for (const result of results) {
          const li = document.createElement("li");
          li.textContent = `${result.item_name} — ${result.ip} / ${result.faction} — $${result.box_price.toFixed(2)}${
            result.models_per_box ? ` (${result.models_per_box}/kit)` : ""
          }`;
          li.addEventListener("click", () => addSearchResult(result));
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
          const data = await fetchJson(`/catalog/search?q=${encodeURIComponent(q)}`);
          renderSearchResults(data.results);
        }, 250);
      });

      this.searchInput.addEventListener("keydown", (e) => {
        // Enter inside a <form> field triggers native submission by default —
        // intercept it here so it adds the top search match instead of
        // submitting the form with whatever (possibly unrelated) state the
        // qty/price/condition fields happen to hold.
        if (e.key === "Enter") {
          e.preventDefault();
          if (this.searchResults.length > 0) {
            addSearchResult(this.searchResults[0]);
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

    _wireKitModelsSave() {
      this.kitModelsSave.addEventListener("click", async () => {
        const models = Number(this.kitModelsInput.value);
        if (!this.selectedUnit || !models || models <= 0) return;

        const res = await fetch(`/catalog/units/${this.selectedUnit.id}/models-per-box`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ models_per_box: models }),
        });
        if (!res.ok) {
          statusEl.textContent = "Couldn't save models-per-kit — try again";
          return;
        }
        const updated = await res.json();
        this._refreshUnitOption(updated);
        this.selectUnit(updated);
      });
    }

    _wireManualToggle() {
      this.manualToggle.addEventListener("change", () => {
        const manual = this.manualToggle.checked;
        this.manualFields.hidden = !manual;
        this.catalogPicker.hidden = manual;
        this.form.querySelector(".catalog-search").hidden = manual;
        this.ipSelect.required = !manual;
        this.factionSelect.required = !manual;
        this.unitSelect.required = !manual;
        this.manualNameInput.required = manual;
        this.kitInfo.hidden = manual || !this.selectedUnit;
        if (!manual) {
          this.priceInput.value = "";
        }
      });
    }

    _wireSubmit() {
      this.form.addEventListener("submit", (e) => {
        e.preventDefault();
        const qty = Number(this.qtyInput.value);
        const priceRaw = this.priceInput.value;
        if (!qty) return;

        const payload = { side: this.side, qty, condition: this.conditionSelect.value };

        if (this.manualToggle.checked) {
          const name = this.manualNameInput.value.trim();
          if (!name) return;
          if (priceRaw === "") {
            statusEl.textContent = "Enter a price for a manually-added item";
            return;
          }
          payload.name = name;
          payload.source = "manual";
          payload.unit_price = Number(priceRaw);
        } else {
          if (!this.selectedUnit) {
            statusEl.textContent = "Search or pick a unit, or check \"Enter manually\"";
            return;
          }
          payload.name = this.selectedUnit.item_name;
          payload.source = "catalog";
          payload.catalog_item_id = this.selectedUnit.id;
          if (priceRaw !== "") payload.unit_price = Number(priceRaw);
        }

        send("add_item", payload);
        this.qtyInput.value = "1";
        this.priceInput.value = "";
        this.conditionSelect.value = "assembled";
        if (!this.manualToggle.checked) {
          this.clearSelection(); // keeps the faction dropdown's option list intact so the same faction stays pickable
        } else {
          this.manualNameInput.value = "";
        }
      });
    }
  }

  document.querySelectorAll(".add-item-form").forEach((form) => new AddItemForm(form));

  cashAEl.addEventListener("change", () => {
    send("set_cash", { side: "A", amount: Number(cashAEl.value) });
  });
  cashBEl.addEventListener("change", () => {
    send("set_cash", { side: "B", amount: Number(cashBEl.value) });
  });

  labelAEl.addEventListener("blur", () => {
    send("rename_side", { side: "A", label: labelAEl.textContent.trim() || "Side A" });
  });
  labelBEl.addEventListener("blur", () => {
    send("rename_side", { side: "B", label: labelBEl.textContent.trim() || "Side B" });
  });

  venueSelect.addEventListener("change", () => {
    send("set_venue", { venue: venueSelect.value });
  });
  inPersonDifferentialInput.addEventListener("change", () => {
    send("set_venue", {
      venue: venueSelect.value,
      in_person_differential: Number(inPersonDifferentialInput.value) / 100,
    });
  });
  onlineDifferentialInput.addEventListener("change", () => {
    send("set_venue", {
      venue: venueSelect.value,
      online_differential: Number(onlineDifferentialInput.value) / 100,
    });
  });

  function sendCommission(overrides) {
    send("set_commission", {
      side: commissionSideSelect.value || null,
      commission_type: commissionTypeSelect.value,
      rate: Number(commissionRateInput.value) / 100,
      base: Number(commissionBaseInput.value),
      flat_amount: Number(commissionFlatInput.value),
      ...overrides,
    });
  }

  commissionSideSelect.addEventListener("change", () => sendCommission({}));
  commissionTypeSelect.addEventListener("change", () => sendCommission({}));
  commissionRateInput.addEventListener("change", () => sendCommission({}));
  commissionBaseInput.addEventListener("change", () => sendCommission({}));
  commissionFlatInput.addEventListener("change", () => sendCommission({}));
})();
