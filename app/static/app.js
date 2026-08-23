const pages = [
  ["dashboard", "Dashboard"],
  ["inventory", "Inventory"],
  ["menu", "Menu & recipes"],
  ["purchases", "Purchases"],
  ["sales", "Sales"],
  ["waste", "Waste"],
  ["suppliers", "Suppliers"],
  ["accounts", "Accounts"],
];

const state = {
  page: "dashboard",
  meta: null,
};

const app = document.getElementById("app");
const nav = document.getElementById("nav");
const toast = document.getElementById("toast");

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
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function optionList(values, selected = "") {
  return values.map((value) => `<option value="${value}" ${value === selected ? "selected" : ""}>${value}</option>`).join("");
}

function itemOptions(items, selected = "") {
  return items
    .map((item) => `<option value="${item.id}" ${String(item.id) === String(selected) ? "selected" : ""}>${item.name} (${item.unit})</option>`)
    .join("");
}

function setPage(page) {
  state.page = page;
  const titles = {
    dashboard: ["Operations", "Dashboard", "Today's money, low stock, and what needs a reorder."],
    inventory: ["Stock room", "Inventory", "Ingredients and packaging. Costs update from purchases."],
    menu: ["Recipes", "Menu", "Each drink pulls stock through its recipe."],
    purchases: ["Receiving", "Purchases", "Receive stock, update weighted average cost, and post AP."],
    sales: ["Counter", "Sales", "Ring a ticket. Inventory and COGS post automatically."],
    waste: ["Loss", "Waste", "Spoilage and mistakes leave the shelf and hit the P&L."],
    suppliers: ["Vendors", "Suppliers", "Roasters, dairy, bakery, and packaging."],
    accounts: ["Ledger", "Accounts", "Double-entry balances and a running profit and loss."],
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

async function renderDashboard() {
  const data = await api("/api/dashboard");
  app.innerHTML = `
    <div class="grid cards">
      <article class="card"><p class="label">Today's sales</p><strong>${money(data.today_sales)}</strong><p class="muted">${data.today_tickets} tickets</p></article>
      <article class="card"><p class="label">Cash</p><strong>${money(data.cash_balance)}</strong></article>
      <article class="card"><p class="label">Inventory value</p><strong>${money(data.inventory_value)}</strong></article>
      <article class="card"><p class="label">Accounts payable</p><strong>${money(data.accounts_payable)}</strong></article>
    </div>
    <h3>Low stock</h3>
    ${table(
      ["Item", "On hand", "Reorder at", "Value"],
      data.low_stock.map(
        (item) => `<tr class="low"><td>${item.name}</td><td>${item.quantity_on_hand} ${item.unit}</td><td>${item.reorder_point}</td><td>${money(item.inventory_value)}</td></tr>`
      )
    )}
  `;
}

async function renderInventory() {
  const items = await api("/api/items");
  app.innerHTML = `
    <div class="two">
      ${table(
        ["SKU", "Item", "On hand", "Unit cost", "Value", "Status"],
        items.map(
          (item) => `<tr class="${item.below_reorder ? "low" : ""}">
            <td>${item.sku}</td>
            <td>${item.name}<div class="muted">${item.category}</div></td>
            <td>${item.quantity_on_hand} ${item.unit}</td>
            <td>${money(item.unit_cost)}</td>
            <td>${money(item.inventory_value)}</td>
            <td>${item.below_reorder ? "Reorder" : "OK"}</td>
          </tr>`
        )
      )}
      <form class="panel" id="item-form">
        <h3>Add item</h3>
        <label>SKU<input name="sku" required /></label>
        <label>Name<input name="name" required /></label>
        <label>Category<select name="category">${optionList(state.meta.item_categories)}</select></label>
        <label>Unit<select name="unit">${optionList(state.meta.units)}</select></label>
        <label>Reorder point<input name="reorder_point" type="number" step="0.0001" value="0" /></label>
        <label>Par level<input name="par_level" type="number" step="0.0001" value="0" /></label>
        <button class="primary" type="submit">Save item</button>
      </form>
    </div>
    <form class="panel" id="adjust-form">
      <h3>Count adjustment</h3>
      <div class="row">
        <label>Item<select name="item_id">${itemOptions(items)}</select></label>
        <label>Qty change<input name="quantity_delta" type="number" step="0.0001" required /></label>
        <label>Note<input name="note" required placeholder="Cycle count, found stock..." /></label>
        <button class="primary" type="submit">Post adjustment</button>
      </div>
    </form>
  `;
  document.getElementById("item-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    await api("/api/items", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form.entries())),
    });
    showToast("Item added");
    render();
  });
  document.getElementById("adjust-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    await api("/api/adjustments", {
      method: "POST",
      body: JSON.stringify({
        item_id: Number(form.get("item_id")),
        quantity_delta: form.get("quantity_delta"),
        note: form.get("note"),
      }),
    });
    showToast("Adjustment posted");
    render();
  });
}

async function renderMenu() {
  const [menu, items] = await Promise.all([api("/api/menu"), api("/api/items")]);
  app.innerHTML = `
    <div class="two">
      ${table(
        ["Drink / food", "Price", "Recipe cost", "Recipe"],
        menu.map(
          (item) => `<tr>
            <td>${item.name}<div class="muted">${item.category}</div></td>
            <td>${money(item.price)}</td>
            <td>${money(item.recipe_cost)}</td>
            <td>${item.recipe.map((line) => `${line.quantity} ${line.item_unit} ${line.item_name}`).join("<br>")}</td>
          </tr>`
        )
      )}
      <form class="panel" id="menu-form">
        <h3>Add menu item</h3>
        <label>Name<input name="name" required /></label>
        <label>Category<select name="category">${optionList(state.meta.menu_categories)}</select></label>
        <label>Price<input name="price" type="number" step="0.01" required /></label>
        <div class="lines" id="recipe-lines"></div>
        <div class="row">
          <button class="ghost" type="button" id="add-recipe-line">Add ingredient</button>
          <button class="primary" type="submit">Save recipe</button>
        </div>
      </form>
    </div>
  `;
  const lines = document.getElementById("recipe-lines");
  const addLine = () => {
    const row = document.createElement("div");
    row.className = "line";
    row.innerHTML = `
      <select name="item_id">${itemOptions(items)}</select>
      <input name="quantity" type="number" step="0.0001" placeholder="qty" required />
      <span class="muted">per serving</span>
      <button class="ghost" type="button">Remove</button>
    `;
    row.querySelector("button").addEventListener("click", () => row.remove());
    lines.appendChild(row);
  };
  document.getElementById("add-recipe-line").addEventListener("click", addLine);
  addLine();
  document.getElementById("menu-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const recipe = [...form.querySelectorAll(".line")].map((row) => ({
      item_id: Number(row.querySelector('[name="item_id"]').value),
      quantity: row.querySelector('[name="quantity"]').value,
    }));
    await api("/api/menu", {
      method: "POST",
      body: JSON.stringify({
        name: form.name.value,
        category: form.category.value,
        price: form.price.value,
        recipe,
      }),
    });
    showToast("Menu item saved");
    render();
  });
}

async function renderPurchases() {
  const [purchases, suppliers, items] = await Promise.all([
    api("/api/purchases"),
    api("/api/suppliers"),
    api("/api/items"),
  ]);
  app.innerHTML = `
    <div class="two">
      ${table(
        ["When", "Supplier", "Invoice", "Total", "Paid"],
        purchases.map(
          (purchase) => `<tr>
            <td>${new Date(purchase.purchased_at).toLocaleString()}</td>
            <td>${purchase.supplier_name}</td>
            <td>${purchase.invoice_number || "—"}</td>
            <td>${money(purchase.total)}</td>
            <td>${purchase.paid ? '<span class="good">Paid</span>' : `<button class="ghost pay" data-id="${purchase.id}">Mark paid</button>`}</td>
          </tr>`
        )
      )}
      <form class="panel" id="purchase-form">
        <h3>Receive purchase</h3>
        <label>Supplier<select name="supplier_id">${suppliers.map((s) => `<option value="${s.id}">${s.name}</option>`).join("")}</select></label>
        <label>Invoice<input name="invoice_number" /></label>
        <label><input type="checkbox" name="paid" /> Paid from cash now</label>
        <div class="lines" id="purchase-lines"></div>
        <div class="row">
          <button class="ghost" type="button" id="add-purchase-line">Add line</button>
          <button class="primary" type="submit">Receive stock</button>
        </div>
      </form>
    </div>
  `;
  const lines = document.getElementById("purchase-lines");
  const addLine = () => {
    const row = document.createElement("div");
    row.className = "line";
    row.innerHTML = `
      <select name="item_id">${itemOptions(items)}</select>
      <input name="quantity" type="number" step="0.0001" placeholder="qty" required />
      <input name="unit_cost" type="number" step="0.01" placeholder="unit cost" required />
      <button class="ghost" type="button">Remove</button>
    `;
    row.querySelector("button").addEventListener("click", () => row.remove());
    lines.appendChild(row);
  };
  document.getElementById("add-purchase-line").addEventListener("click", addLine);
  addLine();
  document.getElementById("purchase-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    await api("/api/purchases", {
      method: "POST",
      body: JSON.stringify({
        supplier_id: Number(form.supplier_id.value),
        invoice_number: form.invoice_number.value || null,
        paid: form.paid.checked,
        lines: [...form.querySelectorAll(".line")].map((row) => ({
          item_id: Number(row.querySelector('[name="item_id"]').value),
          quantity: row.querySelector('[name="quantity"]').value,
          unit_cost: row.querySelector('[name="unit_cost"]').value,
        })),
      }),
    });
    showToast("Purchase received");
    render();
  });
  app.querySelectorAll(".pay").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/purchases/${button.dataset.id}/pay`, { method: "POST" });
      showToast("Supplier paid");
      render();
    });
  });
}

async function renderSales() {
  const [sales, menu] = await Promise.all([api("/api/sales"), api("/api/menu")]);
  app.innerHTML = `
    <div class="two">
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
      <form class="panel" id="sale-form">
        <h3>New ticket</h3>
        <label>Payment<select name="payment_method">${optionList(state.meta.payment_methods)}</select></label>
        <div class="lines" id="sale-lines"></div>
        <div class="row">
          <button class="ghost" type="button" id="add-sale-line">Add item</button>
          <button class="primary" type="submit">Ring sale</button>
        </div>
      </form>
    </div>
  `;
  const lines = document.getElementById("sale-lines");
  const addLine = () => {
    const row = document.createElement("div");
    row.className = "line";
    row.innerHTML = `
      <select name="menu_item_id">${menu.map((item) => `<option value="${item.id}">${item.name} · ${money(item.price)}</option>`).join("")}</select>
      <input name="quantity" type="number" min="1" value="1" required />
      <span class="muted">qty</span>
      <button class="ghost" type="button">Remove</button>
    `;
    row.querySelector("button").addEventListener("click", () => row.remove());
    lines.appendChild(row);
  };
  document.getElementById("add-sale-line").addEventListener("click", addLine);
  addLine();
  document.getElementById("sale-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    await api("/api/sales", {
      method: "POST",
      body: JSON.stringify({
        payment_method: form.payment_method.value,
        lines: [...form.querySelectorAll(".line")].map((row) => ({
          menu_item_id: Number(row.querySelector('[name="menu_item_id"]').value),
          quantity: Number(row.querySelector('[name="quantity"]').value),
        })),
      }),
    });
    showToast("Sale recorded");
    render();
  });
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

async function renderSuppliers() {
  const suppliers = await api("/api/suppliers");
  app.innerHTML = `
    <div class="two">
      ${table(
        ["Supplier", "Contact", "Phone", "Email"],
        suppliers.map((row) => `<tr><td>${row.name}</td><td>${row.contact_name || "—"}</td><td>${row.phone || "—"}</td><td>${row.email || "—"}</td></tr>`)
      )}
      <form class="panel" id="supplier-form">
        <h3>Add supplier</h3>
        <label>Name<input name="name" required /></label>
        <label>Contact<input name="contact_name" /></label>
        <label>Phone<input name="phone" /></label>
        <label>Email<input name="email" type="email" /></label>
        <button class="primary" type="submit">Save supplier</button>
      </form>
    </div>
  `;
  document.getElementById("supplier-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await api("/api/suppliers", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(event.target).entries())),
    });
    showToast("Supplier saved");
    render();
  });
}

async function renderAccounts() {
  const [accounts, ledger, pnl] = await Promise.all([
    api("/api/accounts"),
    api("/api/ledger"),
    api("/api/reports/profit-loss"),
  ]);
  app.innerHTML = `
    <div class="grid cards">
      <article class="card"><p class="label">Revenue</p><strong>${money(pnl.revenue)}</strong></article>
      <article class="card"><p class="label">COGS</p><strong>${money(pnl.cogs)}</strong></article>
      <article class="card"><p class="label">Gross profit</p><strong>${money(pnl.gross_profit)}</strong></article>
      <article class="card"><p class="label">Net income</p><strong>${money(pnl.net_income)}</strong></article>
    </div>
    ${table(
      ["Code", "Account", "Type", "Balance"],
      accounts.map((account) => `<tr><td>${account.code}</td><td>${account.name}</td><td>${account.type}</td><td>${money(account.balance)}</td></tr>`)
    )}
    <h3>Recent journal</h3>
    ${table(
      ["Date", "Memo", "Lines"],
      ledger.map(
        (entry) => `<tr>
          <td>${entry.occurred_on}</td>
          <td>${entry.memo}</td>
          <td>${entry.lines.map((line) => `${line.account_code} ${line.debit > 0 ? "Dr " + money(line.debit) : "Cr " + money(line.credit)}`).join("<br>")}</td>
        </tr>`
      )
    )}
  `;
}

async function render() {
  try {
    if (state.page === "dashboard") return renderDashboard();
    if (state.page === "inventory") return renderInventory();
    if (state.page === "menu") return renderMenu();
    if (state.page === "purchases") return renderPurchases();
    if (state.page === "sales") return renderSales();
    if (state.page === "waste") return renderWaste();
    if (state.page === "suppliers") return renderSuppliers();
    return renderAccounts();
  } catch (error) {
    app.innerHTML = `<div class="panel">${error.message}</div>`;
    showToast(error.message);
  }
}

async function boot() {
  renderNav();
  state.meta = await api("/api/meta");
  await render();
}

boot();
