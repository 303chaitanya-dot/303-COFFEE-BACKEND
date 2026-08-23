const pages = [
  ["dashboard", "Dashboard"],
  ["inventory", "Inventory"],
  ["accounting", "Accounting"],
  ["recipes", "Recipe making"],
  ["menu", "Dishes"],
  ["sales", "Sales"],
  ["petpooja", "Pet Pooja"],
  ["sauces", "Sauces"],
  ["waste", "Waste"],
  ["profile", "Profile"],
];

const state = {
  page: "dashboard",
  meta: null,
  user: null,
  token: localStorage.getItem("cafe_token"),
  inventoryMode: localStorage.getItem("inventory_mode") || "view",
};

const app = document.getElementById("app");
const nav = document.getElementById("nav");
const toast = document.getElementById("toast");

const UNIT_BASE = {
  g: ["mass", 1],
  kg: ["mass", 1000],
  ml: ["vol", 1],
  l: ["vol", 1000],
  pcs: ["count", 1],
};

function money(value) {
  const symbol = state.meta?.currency_symbol || "₹";
  return `${symbol}${Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function showToast(message) {
  toast.hidden = false;
  toast.textContent = message;
  setTimeout(() => {
    toast.hidden = true;
  }, 2800);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && path !== "/api/auth/login") {
    logout(false);
    throw new Error("Sign in required");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  }
  return data;
}

function logout(reload = true) {
  state.token = null;
  state.user = null;
  localStorage.removeItem("cafe_token");
  document.body.classList.add("locked");
  document.getElementById("login-screen").hidden = false;
  if (reload) showToast("Signed out");
}

function optionList(values, selected = "") {
  return values.map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`).join("");
}

function vendorOptions(vendors, selected = "") {
  return (
    `<option value="" ${selected === "" ? "selected" : ""}>Others</option>` +
    vendors
      .map(
        (vendor) =>
          `<option value="${vendor.id}" ${String(vendor.id) === String(selected) ? "selected" : ""}>${vendor.name}</option>`
      )
      .join("")
  );
}

function itemOptions(items, selected = "") {
  return items
    .map((item) => `<option value="${item.id}" ${String(item.id) === String(selected) ? "selected" : ""}>${item.name} (${item.unit})</option>`)
    .join("");
}

function formatExpiry(value) {
  if (!value) return "—";
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return value;
  return `${match[3]}/${match[2]}/${match[1]}`;
}

function parseExpiry(value) {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return raw;
  const indian = raw.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/);
  if (!indian) throw new Error("Expiry should look like 23/08/2026");
  const day = Number(indian[1]);
  const month = Number(indian[2]);
  const year = Number(indian[3]);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    throw new Error("That expiry date is not a real day");
  }
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function convertQty(amount, fromUnit, toUnit) {
  if (fromUnit === toUnit) return Number(amount);
  const source = UNIT_BASE[fromUnit];
  const dest = UNIT_BASE[toUnit];
  if (!source || !dest || source[0] !== dest[0]) return null;
  return (Number(amount) * source[1]) / dest[1];
}

function totalStock(qtyPerUnit, units) {
  return Number(qtyPerUnit || 0) * Number(units || 0);
}

function pricePerServing(price, qtyPerUnit, units, servingSize, servingUnit, stockUnit) {
  const servingInStock = convertQty(servingSize, servingUnit, stockUnit);
  const stock = totalStock(qtyPerUnit, units);
  if (servingInStock === null) return null;
  if (stock <= 0) return 0;
  return (Number(price) * servingInStock) / stock;
}

function compatibleUnits(stockUnit) {
  const kind = UNIT_BASE[stockUnit]?.[0];
  return Object.keys(UNIT_BASE).filter((unit) => UNIT_BASE[unit][0] === kind);
}

function defaultServingUnit(stockUnit) {
  if (stockUnit === "kg") return "g";
  if (stockUnit === "l") return "ml";
  return stockUnit;
}

function syncServingUnits(form, preferred = "") {
  const stockUnit = form.unit.value;
  const allowed = compatibleUnits(stockUnit);
  const current = preferred || form.serving_unit.value;
  const selected = allowed.includes(current) ? current : defaultServingUnit(stockUnit);
  form.serving_unit.innerHTML = optionList(allowed, selected);
}

function setPage(page) {
  state.page = page;
  const titles = {
    dashboard: ["Stock", "Dashboard", "Value on the shelf, today's POS sales, and what is going off."],
    inventory: ["Stock room", "Inventory", "View the shelf, or switch to Edit to change a row. Pick a vendor when stock comes in so Accounting knows who you owe."],
    accounting: ["Books", "Accounting", "Add vendors here. Inventory bought from a vendor adds to what you owe. Settle pays down that balance."],
    recipes: ["Kitchen", "Recipe making", "Sold dishes and their ingredients. Sauces and marinades live under Sauces."],
    menu: ["POS dishes", "Dishes", "Names Pet Pooja matches when a ticket is punched."],
    sales: ["Counter", "Sales", "Upload the day's Pet Pooja Item Wise Sales Report to deduct recipes."],
    petpooja: ["POS", "Pet Pooja", "Pet Pooja pushes billed tickets here. Matching dish names deduct stock."],
    sauces: ["Prep", "Sauces", "Sauces, marinades, dressings, and other prep recipes."],
    waste: ["Loss", "Waste", "Spoilage and mistakes leave the shelf."],
    profile: ["You", "Profile", "Your login details. Team accounts come later."],
  };
  const [kicker, title, hint] = titles[page];
  document.getElementById("page-kicker").textContent = kicker;
  document.getElementById("page-title").textContent = title;
  document.getElementById("page-hint").textContent = hint;
  for (const button of nav.querySelectorAll("button")) {
    button.classList.toggle("active", button.dataset.page === page);
  }
  render();
}

function renderNav() {
  nav.innerHTML = pages
    .map(([id, label]) => `<button data-page="${id}" class="${state.page === id ? "active" : ""}">${label}</button>`)
    .join("");
  nav.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => setPage(button.dataset.page));
  });
}

function table(headers, rows) {
  return `
    <div class="panel">
      <table>
        <thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
        <tbody>${rows.join("") || `<tr><td colspan="${headers.length}" class="muted">Nothing here yet.</td></tr>`}</tbody>
      </table>
    </div>
  `;
}

function trimQty(value) {
  return String(Number(Number(value).toFixed(4)));
}

function formatStock(value, unit) {
  const amount = Number(value);
  const label = `${trimQty(amount)} ${unit}`;
  if (amount < 0) return `<span class="negative">${label}</span>`;
  return label;
}

function expiryClass(item) {
  const expired = Number(item.expired_quantity) > 0;
  const good = Number(item.good_quantity);
  if (expired && good <= 0) return "expired";
  if (item.expiry_status === "expiring") return "expiring";
  if (item.below_reorder || Number(item.quantity_on_hand) < 0) return "low";
  return "";
}

function stockStatus(item) {
  const expired = Number(item.expired_quantity);
  const good = Number(item.good_quantity);
  if (Number(item.quantity_on_hand) < 0) return "Below zero";
  if (expired > 0 && good <= 0) return "Expired";
  if (expired > 0) return `${trimQty(expired)} ${item.unit} expired`;
  if (item.expiry_status === "expiring") return "Use soon";
  if (item.below_reorder) return `Reorder at ${Number(item.reorder_point)} units`;
  return "OK";
}

function closeExpiryMenu() {
  document.getElementById("expiry-menu")?.remove();
}

function showExpiryMenu(item, x, y) {
  closeExpiryMenu();
  const expired = Number(item.expired_quantity);
  if (expired <= 0) {
    showToast("Nothing expired on this item");
    return;
  }
  const menu = document.createElement("div");
  menu.id = "expiry-menu";
  menu.className = "expiry-menu";
  menu.style.left = `${x}px`;
  menu.style.top = `${y}px`;
  menu.innerHTML = `
    <p class="expiry-menu-title">${item.name}</p>
    <p class="muted help">${trimQty(expired)} ${item.unit} expired. Discard sends it to waste. Not expired moves that much into Good.</p>
    <label>Quantity<input name="qty" type="number" step="0.0001" min="0.0001" value="${expired}" /></label>
    <div class="row">
      <button class="ghost" type="button" data-action="discard">Discard</button>
      <button class="primary" type="button" data-action="mark_good">Not expired</button>
    </div>
  `;
  document.body.appendChild(menu);
  const box = menu.getBoundingClientRect();
  if (box.right > window.innerWidth - 8) menu.style.left = `${Math.max(8, window.innerWidth - box.width - 8)}px`;
  if (box.bottom > window.innerHeight - 8) menu.style.top = `${Math.max(8, window.innerHeight - box.height - 8)}px`;
  const run = async (action) => {
    try {
      await api(`/api/items/${item.id}/expired`, {
        method: "POST",
        body: JSON.stringify({ action, quantity: menu.querySelector("[name=qty]").value }),
      });
      showToast(action === "discard" ? "Expired stock discarded as waste" : "Moved that quantity to good");
      closeExpiryMenu();
      render();
    } catch (error) {
      showToast(error.message);
    }
  };
  menu.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => run(button.dataset.action));
  });
  const dismiss = (event) => {
    if (!menu.contains(event.target)) {
      closeExpiryMenu();
      document.removeEventListener("click", dismiss);
    }
  };
  setTimeout(() => document.addEventListener("click", dismiss), 0);
}

async function saveInventoryRow(row, item, adding) {
  const addUnits = adding ? row.querySelector("[name=add_units]").value || 0 : 0;
  await api(`/api/items/${item.id}`, {
    method: "PUT",
    body: JSON.stringify({
      name: row.querySelector("[name=name]").value,
      category: row.querySelector("[name=category]").value,
      unit: row.querySelector("[name=unit]").value,
      qty_per_unit: row.querySelector("[name=qty_per_unit]").value,
      units_on_hand: item.units_on_hand,
      add_units: addUnits,
      add_price: adding ? row.querySelector("[name=add_price]").value || 0 : 0,
      price: item.price,
      serving_size: row.querySelector("[name=serving_size]").value,
      serving_unit: row.querySelector("[name=serving_unit]").value,
      reorder_point: row.querySelector("[name=reorder_point]").value,
      expiry_date: parseExpiry(row.querySelector("[name=expiry_date]").value),
      replace_stock: false,
      vendor_id: adding && row.querySelector("[name=vendor_id]").value ? Number(row.querySelector("[name=vendor_id]").value) : null,
    }),
  });
}

function bindInventoryRows(items) {
  app.querySelectorAll(".item-row").forEach((row) => {
    const item = items.find((entry) => String(entry.id) === row.dataset.itemId);
    if (!item) return;
    row.querySelector(".save-row").addEventListener("click", async () => {
      try {
        await saveInventoryRow(row, item, false);
        showToast("Row saved");
        render();
      } catch (error) {
        showToast(error.message);
      }
    });
    row.querySelector(".add-stock").addEventListener("click", async () => {
      const added = Number(row.querySelector("[name=add_units]").value);
      if (!added) {
        showToast("Enter how many units just came in");
        return;
      }
      try {
        await saveInventoryRow(row, item, true);
        showToast(`Added ${added} units to ${item.name}`);
        render();
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

function bindExpiredCells(items) {
  app.querySelectorAll(".expired-cell").forEach((cell) => {
    const item = items.find((entry) => String(entry.id) === cell.dataset.itemId);
    if (!item) return;
    cell.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      showExpiryMenu(item, event.clientX, event.clientY);
    });
    let press;
    cell.addEventListener(
      "touchstart",
      (event) => {
        const touch = event.changedTouches[0];
        press = setTimeout(() => {
          press = null;
          showExpiryMenu(item, touch.clientX, touch.clientY);
        }, 480);
      },
      { passive: true }
    );
    const cancel = () => {
      if (press) clearTimeout(press);
      press = null;
    };
    cell.addEventListener("touchend", cancel);
    cell.addEventListener("touchmove", cancel);
    cell.addEventListener("touchcancel", cancel);
  });
}

async function renderDashboard() {
  const data = await api("/api/dashboard");
  app.innerHTML = `
    <div class="grid cards">
      <article class="card"><p class="label">Today's sales</p><strong>${money(data.today_sales)}</strong><p class="muted">${data.today_tickets} tickets</p></article>
      <article class="card"><p class="label">Inventory value</p><strong>${money(data.inventory_value)}</strong></article>
      <article class="card"><p class="label">Low stock</p><strong>${data.low_stock_count}</strong></article>
      <article class="card"><p class="label">Nearing expiry</p><strong>${data.expiring.length}</strong></article>
      <article class="card"><p class="label">Expired</p><strong>${data.expired.length}</strong></article>
    </div>
    <h3>Expired</h3>
    ${table(
      ["Item", "Good", "Expired", "Expiry"],
      data.expired.map((item) => `<tr class="expired"><td>${item.name}</td><td>${formatStock(item.good_quantity, item.unit)}</td><td>${formatStock(item.expired_quantity, item.unit)}</td><td>${formatExpiry(item.expiry_date)}</td></tr>`)
    )}
    <h3>Nearing expiry</h3>
    ${table(
      ["Item", "Good", "Expired", "Expiry"],
      data.expiring.map((item) => `<tr class="expiring"><td>${item.name}</td><td>${formatStock(item.good_quantity, item.unit)}</td><td>${formatStock(item.expired_quantity, item.unit)}</td><td>${formatExpiry(item.expiry_date)}</td></tr>`)
    )}
    <h3>Low stock</h3>
    ${table(
      ["Item", "On hand", "Reorder at"],
      data.low_stock.map((item) => `<tr class="low"><td>${item.name}</td><td>${item.units_on_hand} units</td><td>${item.reorder_point} units</td></tr>`)
    )}
  `;
}

function bindStockPreview(form) {
  const stockLine = form.querySelector("#stock-total");
  const priceLine = form.querySelector("#serving-price");
  const update = () => {
    const stock = totalStock(form.qty_per_unit.value, form.units_on_hand.value);
    stockLine.textContent = `Total stock: ${stock} ${form.unit.value}`;
    const value = pricePerServing(
      form.price.value,
      form.qty_per_unit.value,
      form.units_on_hand.value,
      form.serving_size.value,
      form.serving_unit.value,
      form.unit.value
    );
    if (value === null) {
      priceLine.textContent = "Serving unit must match the stock unit (g with kg, ml with l, pcs with pcs).";
      return;
    }
    priceLine.textContent = `Price per serving: ${money(value)}`;
  };
  form.unit.addEventListener("change", () => {
    syncServingUnits(form);
    update();
  });
  for (const field of ["price", "qty_per_unit", "units_on_hand", "serving_size", "serving_unit"]) {
    form[field].addEventListener("input", update);
    form[field].addEventListener("change", update);
  }
  update();
}

function escapeAttr(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function itemPayload(form) {
  return {
    name: form.name.value,
    category: form.category.value,
    unit: form.unit.value,
    qty_per_unit: form.qty_per_unit.value,
    units_on_hand: form.units_on_hand.value,
    price: form.price.value,
    serving_size: form.serving_size.value,
    serving_unit: form.serving_unit.value,
    reorder_point: form.reorder_point.value,
    expiry_date: parseExpiry(form.expiry_date.value),
    replace_stock: Boolean(form.dataset.itemId),
    vendor_id: form.vendor_id?.value ? Number(form.vendor_id.value) : null,
  };
}

function fillItemForm(form, item) {
  form.dataset.itemId = String(item.id);
  form.querySelector("h3").textContent = `Edit ${item.name}`;
  form.querySelector("button[type=submit]").textContent = "Update item";
  document.getElementById("cancel-edit").hidden = false;
  form.name.value = item.name;
  form.category.value = item.category;
  form.unit.value = item.unit;
  form.qty_per_unit.value = Number(item.qty_per_unit);
  form.units_on_hand.value = Number(item.units_on_hand);
  form.price.value = Number(item.price);
  form.serving_size.value = Number(item.serving_size);
  form.reorder_point.value = Number(item.reorder_point);
  form.expiry_date.value = formatExpiry(item.expiry_date) === "—" ? "" : formatExpiry(item.expiry_date);
  const vendorField = form.querySelector(".vendor-field");
  if (vendorField) vendorField.hidden = true;
  syncServingUnits(form, item.serving_unit);
  form.price.dispatchEvent(new Event("input"));
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

function selectedItemIds() {
  return [...app.querySelectorAll(".item-check:checked")].map((box) => Number(box.value));
}

async function downloadSheetTemplate(path = "/api/sheet/template", filename = "303-inventory-sheet.csv") {
  const response = await fetch(path, {
    headers: state.token ? { Authorization: `Bearer ${state.token}` } : {},
  });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function inventoryViewRows(items) {
  return items.map(
    (item) => `<tr class="${expiryClass(item)} item-row" data-item-id="${item.id}" data-search="${escapeAttr((item.name + " " + item.category).toLowerCase())}">
      <td><input class="item-check" type="checkbox" value="${item.id}" /></td>
      <td>${item.name}<div class="muted">${item.category} · ${item.sku}</div></td>
      <td>${item.qty_per_unit} ${item.unit}</td>
      <td>${item.units_on_hand}</td>
      <td>${formatStock(item.quantity_on_hand, item.unit)}</td>
      <td class="good-cell">${formatStock(item.good_quantity, item.unit)}</td>
      <td class="expired-cell${Number(item.expired_quantity) > 0 ? " has-expired" : ""}" data-item-id="${item.id}">${formatStock(item.expired_quantity, item.unit)}</td>
      <td>${money(item.price)}</td>
      <td>${item.serving_size} ${item.serving_unit}</td>
      <td>${money(item.price_per_serving)}</td>
      <td>${formatExpiry(item.expiry_date)}</td>
      <td>${stockStatus(item)}</td>
      <td><button class="ghost edit-item" type="button" data-item-id="${item.id}">Edit</button></td>
    </tr>`
  );
}

function inventoryEditRows(items, vendors) {
  return items.map(
    (item) => `<tr class="${expiryClass(item)} item-row" data-item-id="${item.id}" data-search="${escapeAttr((item.name + " " + item.category).toLowerCase())}">
      <td><input class="item-check" type="checkbox" value="${item.id}" /></td>
      <td>
        <input class="cell-input" name="name" value="${escapeAttr(item.name)}" />
        <select class="cell-input" name="category">${optionList(state.meta.item_categories, item.category)}</select>
      </td>
      <td class="pack-cell">
        <input class="cell-input narrow" name="qty_per_unit" type="number" step="0.0001" value="${Number(item.qty_per_unit)}" />
        <select class="cell-input narrow" name="unit">${optionList(state.meta.units, item.unit)}</select>
      </td>
      <td>${trimQty(item.units_on_hand)}</td>
      <td class="add-cell">
        <input class="cell-input narrow" name="add_units" type="number" step="0.0001" placeholder="+ units" />
        <input class="cell-input narrow" name="add_price" type="number" step="0.01" placeholder="₹ spent" />
        <select class="cell-input vendor-select" name="vendor_id">${vendorOptions(vendors)}</select>
        <button class="ghost add-stock" type="button">Add</button>
      </td>
      <td>${formatStock(item.quantity_on_hand, item.unit)}</td>
      <td class="good-cell">${formatStock(item.good_quantity, item.unit)}</td>
      <td class="expired-cell${Number(item.expired_quantity) > 0 ? " has-expired" : ""}" data-item-id="${item.id}">${formatStock(item.expired_quantity, item.unit)}</td>
      <td><input class="cell-input" name="expiry_date" type="text" inputmode="numeric" placeholder="DD/MM/YYYY" value="${formatExpiry(item.expiry_date) === "—" ? "" : formatExpiry(item.expiry_date)}" /></td>
      <td>
        <input class="cell-input narrow" name="serving_size" type="number" step="0.0001" value="${Number(item.serving_size)}" title="Serving" />
        <select class="cell-input narrow" name="serving_unit">${optionList(compatibleUnits(item.unit), item.serving_unit)}</select>
        <input class="cell-input narrow" name="reorder_point" type="number" step="0.0001" value="${Number(item.reorder_point)}" title="Reorder units" />
        <button class="ghost save-row" type="button">Save</button>
      </td>
    </tr>`
  );
}

function itemComposer(vendors) {
  return `
    <form class="panel composer" id="item-form">
      <h3>Add inventory</h3>
      <label>Name<input name="name" required placeholder="Soy sauce" /></label>
      <label>Category<select name="category">${optionList(state.meta.item_categories)}</select></label>
      <label>Stock unit<select name="unit">${optionList(state.meta.units, "ml")}</select></label>
      <div class="row">
        <label>Qty per unit<input name="qty_per_unit" type="number" step="0.0001" value="250" required /></label>
        <label>Units on hand<input name="units_on_hand" type="number" step="0.0001" value="0" required /></label>
      </div>
      <p id="stock-total" class="muted help">Total stock: 0 ml</p>
      <label>Price (total spent)<input name="price" type="number" step="0.01" value="0" required /></label>
      <label class="vendor-field">Vendor<select name="vendor_id">${vendorOptions(vendors)}</select></label>
      <div class="row">
        <label>Serving size<input name="serving_size" type="number" step="0.0001" value="15" required /></label>
        <label>Serving unit<select name="serving_unit">${optionList(compatibleUnits("ml"), "ml")}</select></label>
      </div>
      <p id="serving-price" class="muted help">Price per serving: ${money(0)}</p>
      <label>Reorder point (units)<input name="reorder_point" type="number" step="0.0001" value="0" /></label>
      <label>Expiry<input name="expiry_date" type="text" inputmode="numeric" placeholder="23/08/2026" /></label>
      <div class="row">
        <button class="primary" type="submit">Save item</button>
        <button class="ghost" type="button" id="cancel-edit" hidden>Cancel edit</button>
      </div>
    </form>
  `;
}

async function renderInventory() {
  const [items, vendors] = await Promise.all([api("/api/items"), api("/api/vendors")]);
  const editing = state.inventoryMode === "edit";
  app.innerHTML = `
    <div class="toolbar">
      <label class="check-all"><input type="checkbox" id="select-all" /> Select all</label>
      <input id="item-search" class="cell-input search" type="search" placeholder="Search items" />
      <div class="mode-toggle">
        <button type="button" data-mode="view" class="${editing ? "" : "active"}">View</button>
        <button type="button" data-mode="edit" class="${editing ? "active" : ""}">Edit</button>
      </div>
      <button class="ghost" type="button" id="delete-selected">Delete selected</button>
    </div>
    ${
      editing
        ? `${table(["", "Item", "Pack", "Now", "New in", "On hand", "Good", "Expired", "Expiry", ""], inventoryEditRows(items, vendors))}
           <p class="muted help">Edit mode: change a row and Save. New in adds units on top of Now. Pick a vendor to add the ₹ spent to what you owe them. Others does not go on anyone's balance.</p>
           ${itemComposer(vendors)}`
        : `<div class="split-page">
            ${table(["", "Item", "Pack", "Units", "On hand", "Good", "Expired", "Price", "Serving", "Per serving", "Expiry", "Status", ""], inventoryViewRows(items))}
            ${itemComposer(vendors)}
          </div>
          <p class="muted help">Right-click or long-press Expired to discard it as waste, or mark some of it as not expired.</p>`
    }
  `;
  const form = document.getElementById("item-form");
  bindStockPreview(form);
  bindExpiredCells(items);
  if (editing) bindInventoryRows(items);
  document.getElementById("item-search").addEventListener("input", (event) => {
    const needle = event.target.value.trim().toLowerCase();
    app.querySelectorAll(".item-row").forEach((row) => {
      row.hidden = Boolean(needle) && !row.dataset.search.includes(needle);
    });
  });
  app.querySelectorAll(".mode-toggle button").forEach((button) => {
    button.addEventListener("click", () => {
      state.inventoryMode = button.dataset.mode;
      localStorage.setItem("inventory_mode", state.inventoryMode);
      render();
    });
  });
  app.querySelectorAll(".edit-item").forEach((button) => {
    button.addEventListener("click", () => {
      const item = items.find((entry) => String(entry.id) === button.dataset.itemId);
      if (item) fillItemForm(form, item);
    });
  });
  document.getElementById("cancel-edit").addEventListener("click", () => render());
  document.getElementById("select-all").addEventListener("change", (event) => {
    app.querySelectorAll(".item-check").forEach((box) => {
      box.checked = event.target.checked;
    });
  });
  document.getElementById("delete-selected").addEventListener("click", async () => {
    const ids = selectedItemIds();
    if (!ids.length) {
      showToast("Select at least one item");
      return;
    }
    try {
      await api("/api/items/delete", { method: "POST", body: JSON.stringify({ ids }) });
      showToast(ids.length === 1 ? "Item deleted" : `${ids.length} items deleted`);
      render();
    } catch (error) {
      showToast(error.message);
    }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const itemId = form.dataset.itemId;
      await api(itemId ? `/api/items/${itemId}` : "/api/items", {
        method: itemId ? "PUT" : "POST",
        body: JSON.stringify(itemPayload(form)),
      });
      showToast(itemId ? "Item updated" : "Item added");
      render();
    } catch (error) {
      showToast(error.message);
    }
  });
}

function vendorBalanceLabel(balance) {
  const amount = Number(balance);
  if (amount < 0) return `<span class="balance-credit">Credit ${money(-amount)}</span>`;
  return money(amount);
}

function vendorHistory(entries) {
  if (!entries?.length) return "";
  return `<div class="muted help vendor-history">${entries
    .map((entry) => {
      const added = entry.kind === "charge";
      const label = entry.note || (added ? "Added" : "Settled");
      return `<span>${added ? "+" : "−"}${money(entry.amount)} ${escapeAttr(label)}</span>`;
    })
    .join(" · ")}</div>`;
}

function vendorEntryPayload(row, kind) {
  const amount = row.querySelector("[name=entry_amount]").value;
  if (!Number(amount)) {
    showToast("Enter an amount");
    return null;
  }
  return {
    amount,
    kind,
    note: row.querySelector("[name=entry_note]").value.trim() || null,
  };
}

async function renderAccounting() {
  const vendors = await api("/api/vendors");
  const owed = vendors.reduce((sum, vendor) => sum + Math.max(0, Number(vendor.balance)), 0);
  app.innerHTML = `
    <div class="page-stack">
      <form class="panel composer" id="vendor-form">
        <h3>Add a vendor</h3>
        <label>Name<input name="name" required placeholder="Metro, local farm, …" /></label>
        <label>Phone<input name="phone" placeholder="Optional" /></label>
        <label>Notes<input name="notes" placeholder="Optional" /></label>
        <button class="primary" type="submit">Add vendor</button>
        <p class="muted help">Registered vendors appear in Inventory. Add or reduce a balance here without touching stock. Others on that dropdown does not keep a balance.</p>
      </form>
      <div class="cards">
        <article class="card"><p class="label">Vendors</p><strong>${vendors.length}</strong></article>
        <article class="card"><p class="label">You owe</p><strong>${money(owed)}</strong></article>
      </div>
      ${table(
        ["Vendor", "Balance", "Manual entry", ""],
        vendors.map(
          (vendor) => `<tr data-vendor-id="${vendor.id}" data-vendor-name="${escapeAttr(vendor.name)}">
            <td>${vendor.name}${vendor.phone ? `<div class="muted">${vendor.phone}</div>` : ""}${vendorHistory(vendor.entries)}</td>
            <td>${vendorBalanceLabel(vendor.balance)}</td>
            <td class="settle-cell">
              <input class="cell-input narrow" name="entry_amount" type="number" step="0.01" min="0.01" placeholder="₹ amount" />
              <input class="cell-input" name="entry_note" placeholder="Note (optional)" />
              <button class="ghost add-balance" type="button">Add to balance</button>
              <button class="primary settle-vendor" type="button">Settle</button>
            </td>
            <td><button class="ghost delete-vendor" type="button">Delete</button></td>
          </tr>`
        )
      )}
    </div>
  `;
  document.getElementById("vendor-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api("/api/vendors", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.value,
          phone: form.phone.value || null,
          notes: form.notes.value || null,
        }),
      });
      showToast(`Added ${form.name.value.trim()}`);
      render();
    } catch (error) {
      showToast(error.message);
    }
  });
  const bindVendorActions = () => {
    app.querySelectorAll(".add-balance").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.preventDefault();
        const row = button.closest("tr");
        const payload = vendorEntryPayload(row, "add");
        if (!payload) return;
        try {
          const vendor = await api(`/api/vendors/${row.dataset.vendorId}/entries`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          showToast(`Added ${money(payload.amount)}. Balance now ${money(vendor.balance)}`);
          render();
        } catch (error) {
          showToast(error.message);
        }
      });
    });
    app.querySelectorAll(".settle-vendor").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.preventDefault();
        const row = button.closest("tr");
        const payload = vendorEntryPayload(row, "reduce");
        if (!payload) return;
        try {
          const vendor = await api(`/api/vendors/${row.dataset.vendorId}/entries`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          showToast(`Settled ${money(payload.amount)}. Balance now ${money(vendor.balance)}`);
          render();
        } catch (error) {
          showToast(error.message);
        }
      });
    });
    app.querySelectorAll(".delete-vendor").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.preventDefault();
        const row = button.closest("tr");
        const name = row.dataset.vendorName;
        if (!confirm(`Delete ${name}? Their balance and entries go with them.`)) return;
        try {
          await api(`/api/vendors/${row.dataset.vendorId}`, { method: "DELETE" });
          showToast(`Deleted ${name}`);
          render();
        } catch (error) {
          showToast(error.message);
        }
      });
    });
  };
  setTimeout(bindVendorActions, 400);
}

async function renderWaste() {
  const [waste, items] = await Promise.all([api("/api/waste"), api("/api/items")]);
  app.innerHTML = `
    <div class="two">
      ${table(
        ["When", "Item", "Qty", "Reason", "Cost"],
        waste.map(
          (row) => `<tr>
            <td>${new Date(row.wasted_at).toLocaleString()}</td>
            <td>${row.item_name}</td>
            <td>${row.quantity} ${row.unit}</td>
            <td>${row.reason}</td>
            <td>${money(row.cost)}</td>
          </tr>`
        )
      )}
      <form class="panel" id="waste-form">
        <h3>Log waste</h3>
        <label>Item<select name="item_id">${itemOptions(items)}</select></label>
        <label>Quantity<input name="quantity" type="number" step="0.0001" required /></label>
        <label>Reason<input name="reason" required placeholder="Spoilage, spill, expired" /></label>
        <button class="primary" type="submit">Write off</button>
      </form>
    </div>
  `;
  document.getElementById("waste-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    await api("/api/waste", {
      method: "POST",
      body: JSON.stringify({
        item_id: Number(form.get("item_id")),
        quantity: form.get("quantity"),
        reason: form.get("reason"),
      }),
    });
    showToast("Waste posted");
    render();
  });
}

function sauceLineRow(items, line = null) {
  const row = document.createElement("div");
  row.className = "line";
  row.innerHTML = `
    <select name="item_id">${itemOptions(items, line?.item_id || "")}</select>
    <input name="quantity" type="number" step="0.0001" placeholder="qty" required value="${line ? Number(line.quantity) : ""}" />
    <button class="ghost" type="button">Remove</button>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  return row;
}

async function renderSauces() {
  const [sauces, items] = await Promise.all([api("/api/sauces"), api("/api/items")]);
  app.innerHTML = `
    <div class="page-stack">
      <form class="panel composer" id="sauce-form">
        <h3>Add sauce</h3>
        <label>Name<input name="name" required placeholder="Garlic aioli" /></label>
        <div class="lines" id="sauce-lines"></div>
        <div class="row">
          <button class="ghost" type="button" id="add-sauce-ing">Add ingredient</button>
          <button class="primary" type="submit">Save sauce</button>
          <button class="ghost" type="button" id="cancel-sauce" hidden>Cancel</button>
        </div>
      </form>
      <div class="toolbar">
        <input id="sauce-search" class="cell-input search" type="search" placeholder="Search sauces" />
        <span class="muted">${sauces.length} sauces</span>
      </div>
      ${table(
        ["Sauce", "Cost / serving", "Ingredients", ""],
        sauces.map(
          (sauce) => `<tr class="sauce-row" data-search="${escapeAttr(sauce.name.toLowerCase())}">
            <td>${sauce.name}</td>
            <td>${money(sauce.recipe_cost)}</td>
            <td>${sauce.recipe.map((line) => `${line.quantity} ${line.item_unit} ${line.item_name}`).join("<br>")}</td>
            <td><button class="ghost edit-sauce" type="button" data-sauce-id="${sauce.id}">Edit</button></td>
          </tr>`
        )
      )}
    </div>
  `;
  const form = document.getElementById("sauce-form");
  const lines = document.getElementById("sauce-lines");
  const addLine = (line = null) => lines.appendChild(sauceLineRow(items, line));
  addLine();
  document.getElementById("add-sauce-ing").addEventListener("click", () => addLine());
  document.getElementById("cancel-sauce").addEventListener("click", () => render());
  document.getElementById("sauce-search").addEventListener("input", (event) => {
    const needle = event.target.value.trim().toLowerCase();
    app.querySelectorAll(".sauce-row").forEach((row) => {
      row.hidden = Boolean(needle) && !row.dataset.search.includes(needle);
    });
  });
  app.querySelectorAll(".edit-sauce").forEach((button) => {
    button.addEventListener("click", () => {
      const sauce = sauces.find((entry) => String(entry.id) === button.dataset.sauceId);
      if (!sauce) return;
      form.dataset.sauceId = String(sauce.id);
      form.querySelector("h3").textContent = `Edit ${sauce.name}`;
      form.querySelector("button[type=submit]").textContent = "Update sauce";
      document.getElementById("cancel-sauce").hidden = false;
      form.name.value = sauce.name;
      lines.innerHTML = "";
      sauce.recipe.forEach((line) => addLine(line));
      form.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const sauceId = form.dataset.sauceId;
    try {
      await api(sauceId ? `/api/sauces/${sauceId}` : "/api/sauces", {
        method: sauceId ? "PUT" : "POST",
        body: JSON.stringify({
          name: form.name.value,
          recipe: [...form.querySelectorAll(".line")].map((row) => ({
            item_id: Number(row.querySelector('[name="item_id"]').value),
            quantity: row.querySelector('[name="quantity"]').value,
          })),
        }),
      });
      showToast(sauceId ? "Sauce updated" : "Sauce saved");
      render();
    } catch (error) {
      showToast(error.message);
    }
  });
}

function recipeLineRow(items, line = null) {
  const row = document.createElement("div");
  row.className = "line";
  row.innerHTML = `
    <select name="item_id">${itemOptions(items, line?.item_id || "")}</select>
    <input name="quantity" type="number" step="0.0001" placeholder="qty" required value="${line ? Number(line.quantity) : ""}" />
    <select name="unit">${optionList(state.meta.units, line?.unit || "")}</select>
    <button class="ghost" type="button">Remove</button>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  return row;
}

function fillRecipeForm(form, dish, items) {
  form.dataset.recipeId = String(dish.id);
  form.querySelector("h3").textContent = `Edit ${dish.name}`;
  form.querySelector("button[type=submit]").textContent = "Update recipe";
  document.getElementById("cancel-recipe").hidden = false;
  form.name.value = dish.name;
  form.category.value = dish.category;
  form.price.value = Number(dish.price);
  const lines = document.getElementById("recipe-edit-lines");
  lines.innerHTML = "";
  (dish.recipe || []).filter((line) => line.item_id).forEach((line) => lines.appendChild(recipeLineRow(items, line)));
  if (!lines.children.length) lines.appendChild(recipeLineRow(items));
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function renderRecipes() {
  const [menu, items] = await Promise.all([api("/api/menu"), api("/api/items")]);
  app.innerHTML = `
    <div class="page-stack">
      <form class="panel composer" id="recipe-form">
        <h3>Add recipe</h3>
        <label>Name<input name="name" required /></label>
        <div class="row">
          <label>Category<select name="category">${optionList(state.meta.menu_categories, "food")}</select></label>
          <label>Sell price<input name="price" type="number" step="0.01" value="0" required /></label>
        </div>
        <div class="lines" id="recipe-edit-lines"></div>
        <div class="row">
          <button class="ghost" type="button" id="add-recipe-edit-line">Add ingredient</button>
          <button class="primary" type="submit">Save recipe</button>
          <button class="ghost" type="button" id="cancel-recipe" hidden>Cancel</button>
        </div>
      </form>
      <div class="toolbar">
        <input id="recipe-search" class="cell-input search" type="search" placeholder="Search recipes" />
        <span class="muted">${menu.length} dishes</span>
      </div>
      ${table(
        ["Recipe", "Price", "Cost", "Ingredients", ""],
        menu.map(
          (dish) => `<tr class="recipe-row" data-search="${escapeAttr(dish.name.toLowerCase())}">
            <td>${dish.name}<div class="muted">${dish.category} · ${dish.recipe.length} lines</div></td>
            <td>${money(dish.price)}</td>
            <td>${money(dish.recipe_cost)}</td>
            <td>${dish.recipe.map((line) => `${line.quantity} ${line.unit} ${line.name}`).join("<br>") || "—"}</td>
            <td><button class="ghost edit-recipe" type="button" data-recipe-id="${dish.id}">Edit</button></td>
          </tr>`
        )
      )}
    </div>
  `;
  const form = document.getElementById("recipe-form");
  const lines = document.getElementById("recipe-edit-lines");
  const addLine = (line = null) => lines.appendChild(recipeLineRow(items, line));
  addLine();
  document.getElementById("add-recipe-edit-line").addEventListener("click", () => addLine());
  document.getElementById("cancel-recipe").addEventListener("click", () => render());
  document.getElementById("recipe-search").addEventListener("input", (event) => {
    const needle = event.target.value.trim().toLowerCase();
    app.querySelectorAll(".recipe-row").forEach((row) => {
      row.hidden = Boolean(needle) && !row.dataset.search.includes(needle);
    });
  });
  app.querySelectorAll(".edit-recipe").forEach((button) => {
    button.addEventListener("click", () => {
      const dish = menu.find((entry) => String(entry.id) === button.dataset.recipeId);
      if (dish) fillRecipeForm(form, dish, items);
    });
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const recipeId = form.dataset.recipeId;
    try {
      await api(recipeId ? `/api/menu/${recipeId}` : "/api/menu", {
        method: recipeId ? "PUT" : "POST",
        body: JSON.stringify({
          name: form.name.value,
          category: form.category.value,
          price: form.price.value,
          recipe: [...form.querySelectorAll(".line")].map((row) => ({
            item_id: Number(row.querySelector('[name="item_id"]').value),
            quantity: row.querySelector('[name="quantity"]').value,
            unit: row.querySelector('[name="unit"]').value,
          })),
        }),
      });
      showToast(recipeId ? "Recipe updated" : "Recipe added");
      render();
    } catch (error) {
      showToast(error.message);
    }
  });
}

async function renderMenu() {
  const [menu, items] = await Promise.all([api("/api/menu"), api("/api/items")]);
  app.innerHTML = `
    <div class="page-stack">
      <form class="panel composer" id="menu-form">
        <h3>Add dish</h3>
        <label>Name<input name="name" required /></label>
        <div class="row">
          <label>Category<select name="category">${optionList(state.meta.menu_categories)}</select></label>
          <label>Sell price<input name="price" type="number" step="0.01" required /></label>
        </div>
        <div class="lines" id="recipe-lines"></div>
        <div class="row">
          <button class="ghost" type="button" id="add-recipe-line">Add ingredient</button>
          <button class="primary" type="submit">Save dish</button>
        </div>
      </form>
      ${table(
        ["Dish", "Price", "Recipe cost", "Recipe"],
        menu.map(
          (item) => `<tr>
            <td>${item.name}<div class="muted">${item.category}</div></td>
            <td>${money(item.price)}</td>
            <td>${money(item.recipe_cost)}</td>
            <td>${item.recipe.map((line) => `${line.quantity} ${line.unit} ${line.name}`).join("<br>")}</td>
          </tr>`
        )
      )}
    </div>
  `;
  const lines = document.getElementById("recipe-lines");
  const addLine = () => lines.appendChild(recipeLineRow(items));
  document.getElementById("add-recipe-line").addEventListener("click", () => addLine());
  addLine();
  document.getElementById("menu-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api("/api/menu", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.value,
          category: form.category.value,
          price: form.price.value,
          recipe: [...form.querySelectorAll(".line")].map((row) => ({
            item_id: Number(row.querySelector('[name="item_id"]').value),
            quantity: row.querySelector('[name="quantity"]').value,
            unit: row.querySelector('[name="unit"]').value,
          })),
        }),
      });
      showToast("Dish saved");
      render();
    } catch (error) {
      showToast(error.message);
    }
  });
}

async function renderSales() {
  const sales = await api("/api/sales");
  app.innerHTML = `
    <form class="panel sheet-panel" id="sales-import">
      <h3>Upload Pet Pooja day report</h3>
      <p class="muted help">Export Item Wise Sales Report from Pet Pooja as Excel or CSV. Each sold dish with a recipe here comes off inventory. Items without a recipe are skipped.</p>
      <label>File<input name="file" type="file" accept=".xlsx,.csv,.txt" required /></label>
      <button class="primary" type="submit">Apply to inventory</button>
      <p id="import-result" class="muted help"></p>
    </form>
    ${table(
      ["When", "Ticket", "Tender", "Total", "COGS"],
      sales.map(
        (sale) => `<tr>
          <td>${new Date(sale.sold_at).toLocaleString()}</td>
          <td>${sale.lines.map((line) => `${line.quantity} × ${line.menu_item_name}`).join("<br>")}</td>
          <td>${sale.payment_method}</td>
          <td>${money(sale.total)}</td>
          <td>${money(sale.cogs)}</td>
        </tr>`
      )
    )}
  `;
  document.getElementById("sales-import").addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = event.target.file.files[0];
    const body = new FormData();
    body.append("file", file);
    const resultBox = document.getElementById("import-result");
    try {
      const result = await api("/api/sales/import", { method: "POST", body });
      const skipped = (result.skipped || []).map((row) => `${row.name} (${row.reason})`).join(" · ");
      resultBox.textContent = `${result.message}${skipped ? ". Skipped: " + skipped : ""}`;
      showToast(result.message);
      if (result.applied.length) render();
    } catch (error) {
      resultBox.textContent = error.message;
      showToast(error.message);
    }
  });
}

async function renderPetpooja() {
  const [orders, mappings, menu] = await Promise.all([
    api("/api/petpooja/orders"),
    api("/api/petpooja/mappings"),
    api("/api/menu"),
  ]);
  const webhook = `${window.location.origin}/api/integrations/petpooja/orders`;
  app.innerHTML = `
    <div class="panel sheet-panel">
      <h3>How POS updates stock</h3>
      <p class="muted help">When a ticket is billed in Pet Pooja, they must push it to this webhook. Matching dish names (same spelling as Dishes) deduct the recipe and log a sale.</p>
      <label>Webhook<input value="${webhook}" readonly /></label>
      <p class="muted help">Email Pet Pooja: enable outbound billed-order webhook for 303 Coffee, push to the URL above. There is no self-serve switch in their app.</p>
    </div>
    <div class="two">
      ${table(
        ["Order", "Status", "Sale"],
        orders.map((order) => `<tr><td>${order.external_order_id}</td><td>${order.status}</td><td>${order.sale_id || "—"}</td></tr>`)
      )}
      <form class="panel" id="map-form">
        <h3>Map a POS name if it differs</h3>
        <label>Pet Pooja name<input name="external_name" required /></label>
        <label>Pet Pooja item id<input name="external_item_id" /></label>
        <label>Our dish<select name="menu_item_id">${menu.map((item) => `<option value="${item.id}">${item.name}</option>`).join("")}</select></label>
        <button class="primary" type="submit">Save mapping</button>
      </form>
    </div>
    <h3>Mappings</h3>
    ${table(
      ["Pet Pooja", "ID", "Dish"],
      mappings.map((row) => `<tr><td>${row.external_name}</td><td>${row.external_item_id || "—"}</td><td>${row.menu_item_name}</td></tr>`)
    )}
  `;
  const mapForm = document.getElementById("map-form");
  if (mapForm) {
    mapForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      try {
        await api("/api/petpooja/mappings", {
          method: "POST",
          body: JSON.stringify({
            external_name: form.get("external_name"),
            external_item_id: form.get("external_item_id") || null,
            menu_item_id: Number(form.get("menu_item_id")),
          }),
        });
        showToast("Mapping saved");
        render();
      } catch (error) {
        showToast(error.message);
      }
    });
  }
}

async function renderProfile() {
  const me = state.user;
  app.innerHTML = `
    <div class="two">
      <form class="panel" id="profile-form">
        <h3>${me.name}</h3>
        <p class="muted">${me.email} · ${me.role}</p>
        <label>Name<input name="name" value="${me.name}" required /></label>
        <label>Phone<input name="phone" value="${me.phone || ""}" /></label>
        <label>Title<input name="title" value="${me.title || ""}" /></label>
        <button class="primary" type="submit">Save profile</button>
      </form>
      <form class="panel" id="password-form">
        <h3>Password</h3>
        <label>Current<input name="current_password" type="password" required /></label>
        <label>New<input name="new_password" type="password" required minlength="8" /></label>
        <button class="primary" type="submit">Change password</button>
      </form>
    </div>
  `;
  document.getElementById("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    state.user = await api("/api/auth/me", {
      method: "PUT",
      body: JSON.stringify(Object.fromEntries(new FormData(event.target).entries())),
    });
    document.getElementById("whoami").textContent = `${state.user.name} · ${state.user.role}`;
    showToast("Profile saved");
    render();
  });
  document.getElementById("password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await api("/api/auth/me/password", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(event.target).entries())),
    });
    event.target.reset();
    showToast("Password updated");
  });
}

async function render() {
  try {
    if (state.page === "dashboard") return renderDashboard();
    if (state.page === "inventory") return renderInventory();
    if (state.page === "accounting") return renderAccounting();
    if (state.page === "recipes") return renderRecipes();
    if (state.page === "menu") return renderMenu();
    if (state.page === "sales") return renderSales();
    if (state.page === "petpooja") return renderPetpooja();
    if (state.page === "sauces") return renderSauces();
    if (state.page === "waste") return renderWaste();
    return renderProfile();
  } catch (error) {
    app.innerHTML = `<div class="panel">${error.message}</div>`;
    showToast(error.message);
  }
}

async function enterApp() {
  document.body.classList.remove("locked");
  document.getElementById("login-screen").hidden = true;
  state.user = await api("/api/auth/me");
  state.meta = await api("/api/meta");
  document.getElementById("whoami").textContent = `${state.user.name} · ${state.user.role}`;
  renderNav();
  await render();
}

async function boot() {
  document.getElementById("signout").addEventListener("click", () => logout());
  document.getElementById("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = document.getElementById("login-error");
    error.hidden = true;
    try {
      const form = new FormData(event.target);
      const token = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      state.token = token.access_token;
      localStorage.setItem("cafe_token", state.token);
      await enterApp();
    } catch (err) {
      error.hidden = false;
      error.textContent = err.message;
    }
  });
  if (!state.token) {
    document.body.classList.add("locked");
    document.getElementById("login-screen").hidden = false;
    return;
  }
  try {
    await enterApp();
  } catch (_error) {
    logout(false);
  }
}

boot();
