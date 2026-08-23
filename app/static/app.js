const pages = [
  ["dashboard", "Dashboard"],
  ["inventory", "Inventory"],
  ["menu", "Dishes"],
  ["sauces", "Sauces"],
  ["purchases", "Purchases"],
  ["bills", "Bills"],
  ["sales", "Sales"],
  ["petpooja", "Pet Pooja"],
  ["waste", "Waste"],
  ["suppliers", "Suppliers"],
  ["accounts", "Accounts"],
  ["profile", "Profile"],
];

const state = {
  page: "dashboard",
  meta: null,
  user: null,
  token: localStorage.getItem("cafe_token"),
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
    menu: ["Recipes", "Dishes", "Each dish uses ingredients and sauces. Price used is the recipe cost."],
    sauces: ["Prep", "Sauces", "A sauce is ingredients in a serving. Dishes can pull a sauce whole."],
    purchases: ["Receiving", "Purchases", "Type the item name, price, quantity, and serving size used in recipes."],
    bills: ["Paper trail", "Bills", "Upload a supplier bill. We read the lines; you confirm before stock moves."],
    sales: ["Counter", "Sales", "Ring a ticket. Inventory and COGS post automatically."],
    petpooja: ["POS", "Pet Pooja", "Map Pet Pooja items to dishes. Incoming orders deduct inventory."],
    profile: ["People", "Profile", "Your login, role, and cafe staff profiles."],
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
        ["SKU", "Item", "On hand", "Serving", "Unit cost", "Value", "Status"],
        items.map(
          (item) => `<tr class="${item.below_reorder ? "low" : ""}">
            <td>${item.sku}</td>
            <td>${item.name}<div class="muted">${item.category}</div></td>
            <td>${item.quantity_on_hand} ${item.unit}</td>
            <td>${item.serving_size} ${item.unit}</td>
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
        <label>Serving size<input name="serving_size" type="number" step="0.0001" value="1" /></label>
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
  const [menu, items, sauces] = await Promise.all([api("/api/menu"), api("/api/items"), api("/api/sauces")]);
  app.innerHTML = `
    <div class="two">
      ${table(
        ["Drink / food", "Price", "Recipe cost", "Recipe"],
        menu.map(
          (item) => `<tr>
            <td>${item.name}<div class="muted">${item.category}</div></td>
            <td>${money(item.price)}</td>
            <td>${money(item.recipe_cost)}</td>
            <td>${item.recipe.map((line) => `${line.quantity} ${line.unit} ${line.name} · used ${money(line.price_used)}`).join("<br>")}</td>
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
          <button class="ghost" type="button" id="add-sauce-line">Add sauce</button>
          <button class="primary" type="submit">Save recipe</button>
        </div>
      </form>
    </div>
  `;
  const lines = document.getElementById("recipe-lines");
  const addLine = (kind = "item") => {
    const row = document.createElement("div");
    row.className = "line";
    row.dataset.kind = kind;
    const options =
      kind === "sauce"
        ? sauces.map((sauce) => `<option value="${sauce.id}">${sauce.name} · ${money(sauce.recipe_cost)}</option>`).join("")
        : itemOptions(items);
    row.innerHTML = `
      <select name="${kind === "sauce" ? "sauce_id" : "item_id"}">${options}</select>
      <input name="quantity" type="number" step="0.0001" placeholder="qty" required />
      <span class="muted">${kind === "sauce" ? "sauce servings" : "per serving"}</span>
      <button class="ghost" type="button">Remove</button>
    `;
    row.querySelector("button").addEventListener("click", () => row.remove());
    lines.appendChild(row);
  };
  document.getElementById("add-recipe-line").addEventListener("click", () => addLine("item"));
  document.getElementById("add-sauce-line").addEventListener("click", () => addLine("sauce"));
  addLine("item");
  document.getElementById("menu-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const recipe = [...form.querySelectorAll(".line")].map((row) => {
      const quantity = row.querySelector('[name="quantity"]').value;
      if (row.dataset.kind === "sauce") {
        return { sauce_id: Number(row.querySelector('[name="sauce_id"]').value), quantity };
      }
      return { item_id: Number(row.querySelector('[name="item_id"]').value), quantity };
    });
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
  const purchases = await api("/api/purchases");
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
        <h3>Manual purchase</h3>
        <label>Supplier name<input name="supplier_name" placeholder="Walk-in or vendor" /></label>
        <label>Invoice<input name="invoice_number" /></label>
        <label><input type="checkbox" name="paid" /> Paid from cash now</label>
        <div class="lines" id="purchase-lines"></div>
        <div class="row">
          <button class="ghost" type="button" id="add-purchase-line">Add item</button>
          <button class="primary" type="submit">Post purchase</button>
        </div>
      </form>
    </div>
  `;
  const lines = document.getElementById("purchase-lines");
  const addLine = () => {
    const row = document.createElement("div");
    row.className = "line";
    row.style.gridTemplateColumns = "1fr 80px 90px 80px 90px auto";
    row.innerHTML = `
      <input name="name" placeholder="Item name" required />
      <input name="quantity" type="number" step="0.0001" placeholder="qty" required />
      <input name="price" type="number" step="0.01" placeholder="price" required />
      <select name="unit">${optionList(state.meta.units)}</select>
      <input name="serving_size" type="number" step="0.0001" placeholder="serving" />
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
    await api("/api/purchases/quick", {
      method: "POST",
      body: JSON.stringify({
        supplier_name: form.supplier_name.value || null,
        invoice_number: form.invoice_number.value || null,
        paid: form.paid.checked,
        lines: [...form.querySelectorAll(".line")].map((row) => ({
          name: row.querySelector('[name="name"]').value,
          quantity: row.querySelector('[name="quantity"]').value,
          price: row.querySelector('[name="price"]').value,
          unit: row.querySelector('[name="unit"]').value,
          serving_size: row.querySelector('[name="serving_size"]').value || null,
        })),
      }),
    });
    showToast("Purchase posted");
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

async function renderSauces() {
  const [sauces, items] = await Promise.all([api("/api/sauces"), api("/api/items")]);
  app.innerHTML = `
    <div class="two">
      ${table(
        ["Sauce", "Cost / serving", "Ingredients"],
        sauces.map(
          (sauce) => `<tr>
            <td>${sauce.name}</td>
            <td>${money(sauce.recipe_cost)}</td>
            <td>${sauce.recipe.map((line) => `${line.quantity} ${line.item_unit} ${line.item_name} · ${money(line.price_used)}`).join("<br>")}</td>
          </tr>`
        )
      )}
      <form class="panel" id="sauce-form">
        <h3>Add sauce</h3>
        <label>Name<input name="name" required /></label>
        <div class="lines" id="sauce-lines"></div>
        <div class="row">
          <button class="ghost" type="button" id="add-sauce-ing">Add ingredient</button>
          <button class="primary" type="submit">Save sauce</button>
        </div>
      </form>
    </div>
  `;
  const lines = document.getElementById("sauce-lines");
  const addLine = () => {
    const row = document.createElement("div");
    row.className = "line";
    row.innerHTML = `
      <select name="item_id">${itemOptions(items)}</select>
      <input name="quantity" type="number" step="0.0001" placeholder="qty / serving" required />
      <span class="muted">used</span>
      <button class="ghost" type="button">Remove</button>
    `;
    row.querySelector("button").addEventListener("click", () => row.remove());
    lines.appendChild(row);
  };
  document.getElementById("add-sauce-ing").addEventListener("click", addLine);
  addLine();
  document.getElementById("sauce-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    await api("/api/sauces", {
      method: "POST",
      body: JSON.stringify({
        name: form.name.value,
        recipe: [...form.querySelectorAll(".line")].map((row) => ({
          item_id: Number(row.querySelector('[name="item_id"]').value),
          quantity: row.querySelector('[name="quantity"]').value,
        })),
      }),
    });
    showToast("Sauce saved");
    render();
  });
}

async function renderBills() {
  const bills = await api("/api/bills");
  app.innerHTML = `
    <div class="two">
      ${table(
        ["File", "Supplier", "Status", "Lines"],
        bills.map(
          (bill) => `<tr>
            <td>${bill.filename}</td>
            <td>${bill.supplier_name || "—"}</td>
            <td>${bill.status}${bill.status === "pending_review" ? ` <button class="ghost confirm-bill" data-id="${bill.id}">Post stock</button>` : ""}</td>
            <td>${(bill.lines || []).map((line) => `${line.quantity} ${line.unit || ""} ${line.name} @ ${line.price}`).join("<br>")}</td>
          </tr>`
        )
      )}
      <form class="panel" id="bill-form">
        <h3>Upload bill</h3>
        <p class="muted">Photo bills need OPENAI_API_KEY. A .txt bill works now: one line like <code>Tomatoes|5|40|kg|30</code>.</p>
        <label>File<input name="file" type="file" required /></label>
        <button class="primary" type="submit">Read bill</button>
      </form>
    </div>
  `;
  document.getElementById("bill-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = event.target.file.files[0];
    const body = new FormData();
    body.append("file", file);
    await api("/api/bills", { method: "POST", body });
    showToast("Bill read — review then post");
    render();
  });
  app.querySelectorAll(".confirm-bill").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/bills/${button.dataset.id}/confirm`, { method: "POST" });
      showToast("Bill posted to inventory");
      render();
    });
  });
}

async function renderPetpooja() {
  const [orders, mappings, menu] = await Promise.all([
    api("/api/petpooja/orders"),
    api("/api/petpooja/mappings"),
    api("/api/menu"),
  ]);
  app.innerHTML = `
    <p class="muted">Pet Pooja sends billed orders to <code>POST /api/integrations/petpooja/orders</code>. Map their item names to dishes so stock comes off automatically.</p>
    <div class="two">
      ${table(
        ["Order", "Status", "Sale"],
        orders.map((order) => `<tr><td>${order.external_order_id}</td><td>${order.status}</td><td>${order.sale_id || "—"}</td></tr>`)
      )}
      <form class="panel" id="map-form">
        <h3>Map a Pet Pooja item</h3>
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
  document.getElementById("map-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
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
  });
}

async function renderProfile() {
  const me = state.user;
  let usersHtml = "";
  if (me.role === "owner") {
    const users = await api("/api/auth/users");
    usersHtml = `
      ${table(["Name", "Email", "Role"], users.map((user) => `<tr><td>${user.name}</td><td>${user.email}</td><td>${user.role}</td></tr>`))}
      <form class="panel" id="invite-form">
        <h3>Add staff profile</h3>
        <label>Name<input name="name" required /></label>
        <label>Email<input name="email" type="email" required /></label>
        <label>Password<input name="password" type="password" required minlength="8" /></label>
        <label>Role<select name="role">${optionList(["staff", "manager", "owner"])}</select></label>
        <label>Title<input name="title" /></label>
        <button class="primary" type="submit">Create profile</button>
      </form>
    `;
  }
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
    ${usersHtml}
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
  const invite = document.getElementById("invite-form");
  if (invite) {
    invite.addEventListener("submit", async (event) => {
      event.preventDefault();
      await api("/api/auth/users", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(event.target).entries())),
      });
      showToast("Profile created");
      render();
    });
  }
}

async function render() {
  try {
    if (state.page === "dashboard") return renderDashboard();
    if (state.page === "inventory") return renderInventory();
    if (state.page === "menu") return renderMenu();
    if (state.page === "sauces") return renderSauces();
    if (state.page === "purchases") return renderPurchases();
    if (state.page === "bills") return renderBills();
    if (state.page === "sales") return renderSales();
    if (state.page === "petpooja") return renderPetpooja();
    if (state.page === "waste") return renderWaste();
    if (state.page === "suppliers") return renderSuppliers();
    if (state.page === "profile") return renderProfile();
    return renderAccounts();
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
