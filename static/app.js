const state = {
  selectedTable: "",
  selectedRowId: null,
  tables: {},
  rows: [],
};

const elements = {
  tableList: document.querySelector("#tableList"),
  selectedTable: document.querySelector("#selectedTable"),
  rowLimit: document.querySelector("#rowLimit"),
  loadRows: document.querySelector("#loadRows"),
  refreshTables: document.querySelector("#refreshTables"),
  schemaFields: document.querySelector("#schemaFields"),
  rowCount: document.querySelector("#rowCount"),
  rowsTable: document.querySelector("#rowsTable"),
  clearTable: document.querySelector("#clearTable"),
  editorTitle: document.querySelector("#editorTitle"),
  newRow: document.querySelector("#newRow"),
  tableName: document.querySelector("#tableName"),
  jsonEditor: document.querySelector("#jsonEditor"),
  status: document.querySelector("#status"),
  saveRow: document.querySelector("#saveRow"),
  deleteRow: document.querySelector("#deleteRow"),
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || response.statusText);
  }
  return response.json();
}

function setStatus(message, isError = false) {
  elements.status.textContent = message;
  elements.status.classList.toggle("error", isError);
}

function renderTables() {
  elements.tableList.innerHTML = "";
  for (const [table, count] of Object.entries(state.tables)) {
    const button = document.createElement("button");
    button.className = `table-link${table === state.selectedTable ? " active" : ""}`;
    const name = document.createElement("span");
    const total = document.createElement("strong");
    name.textContent = table;
    total.textContent = String(count);
    button.append(name, total);
    button.addEventListener("click", () => selectTable(table));
    elements.tableList.append(button);
  }
}

function renderSchema(schema) {
  elements.schemaFields.innerHTML = "";
  const entries = Object.entries(schema);
  if (entries.length === 0) {
    elements.schemaFields.innerHTML = '<div class="empty">No fields yet.</div>';
    return;
  }
  for (const [field, types] of entries) {
    const pill = document.createElement("span");
    pill.className = "field-pill";
    pill.textContent = `${field}: ${types.join(" | ")}`;
    elements.schemaFields.append(pill);
  }
}

function formatCell(value) {
  if (value === null) {
    return "null";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function renderRows() {
  if (state.rows.length === 0) {
    elements.rowsTable.innerHTML = '<div class="empty">No rows loaded.</div>';
    return;
  }

  const fields = Array.from(new Set(state.rows.flatMap((row) => Object.keys(row))));
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  const tbody = document.createElement("tbody");
  for (const field of fields) {
    const th = document.createElement("th");
    th.textContent = field;
    headerRow.append(th);
  }
  thead.append(headerRow);
  table.append(thead, tbody);
  for (const row of state.rows) {
    const tr = document.createElement("tr");
    for (const field of fields) {
      const td = document.createElement("td");
      const value = formatCell(row[field]);
      td.textContent = value;
      td.title = value;
      tr.append(td);
    }
    tr.addEventListener("click", () => editRow(row));
    tbody.append(tr);
  }
  elements.rowsTable.replaceChildren(table);
}

async function refreshTables() {
  state.tables = await request("/api/v1/db/tables");
  renderTables();
}

async function loadSchema(table) {
  const schema = await request(`/api/v1/db/${encodeURIComponent(table)}/schema`);
  renderSchema(schema);
}

async function loadRows() {
  const table = elements.tableName.value.trim() || state.selectedTable;
  if (!table) {
    setStatus("Pick or type table first.", true);
    return;
  }

  const limit = Number(elements.rowLimit.value || 25);
  state.rows = await request(`/api/v1/db/${encodeURIComponent(table)}?limit=${limit}`);
  state.selectedTable = table;
  elements.selectedTable.textContent = table;
  elements.tableName.value = table;
  elements.rowCount.textContent = `${state.tables[table] ?? state.rows.length} rows`;
  elements.clearTable.disabled = state.rows.length === 0;
  renderTables();
  renderRows();
  await loadSchema(table);
  setStatus(`Loaded ${state.rows.length} rows from ${table}.`);
}

async function selectTable(table) {
  state.selectedTable = table;
  state.selectedRowId = null;
  elements.selectedTable.textContent = table;
  elements.tableName.value = table;
  elements.editorTitle.textContent = "Insert row";
  elements.jsonEditor.value = "{}";
  elements.deleteRow.disabled = true;
  await loadRows();
}

function editRow(row) {
  state.selectedRowId = row.id;
  elements.editorTitle.textContent = `Edit row #${row.id}`;
  elements.jsonEditor.value = JSON.stringify(
    Object.fromEntries(Object.entries(row).filter(([key]) => key !== "id")),
    null,
    2,
  );
  elements.deleteRow.disabled = false;
  setStatus(`Editing ${state.selectedTable}/${row.id}.`);
}

function newRow() {
  state.selectedRowId = null;
  elements.editorTitle.textContent = "Insert row";
  elements.jsonEditor.value = "{}";
  elements.deleteRow.disabled = true;
  setStatus("Ready to insert.");
}

async function saveRow() {
  const table = elements.tableName.value.trim();
  if (!table) {
    setStatus("Table required.", true);
    return;
  }

  let payload;
  try {
    payload = JSON.parse(elements.jsonEditor.value);
  } catch (error) {
    setStatus(`Invalid JSON: ${error.message}`, true);
    return;
  }
  if (!payload || Array.isArray(payload) || typeof payload !== "object") {
    setStatus("Payload must be JSON object.", true);
    return;
  }

  const path = state.selectedRowId
    ? `/api/v1/db/${encodeURIComponent(table)}/${state.selectedRowId}`
    : `/api/v1/db/${encodeURIComponent(table)}`;
  const method = state.selectedRowId ? "PATCH" : "POST";
  const row = await request(path, { method, body: JSON.stringify(payload) });
  state.selectedTable = table;
  state.selectedRowId = row.id;
  await refreshTables();
  await loadRows();
  editRow(row);
  setStatus(`Saved ${table}/${row.id}.`);
}

async function deleteRow() {
  if (!state.selectedTable || state.selectedRowId === null) {
    return;
  }
  const ok = window.confirm(`Delete ${state.selectedTable}/${state.selectedRowId}?`);
  if (!ok) {
    return;
  }
  await request(`/api/v1/db/${encodeURIComponent(state.selectedTable)}/${state.selectedRowId}`, { method: "DELETE" });
  newRow();
  await refreshTables();
  await loadRows();
  setStatus("Deleted row.");
}

async function clearTable() {
  const table = elements.tableName.value.trim() || state.selectedTable;
  if (!table) {
    setStatus("Pick or type table first.", true);
    return;
  }

  const count = state.tables[table] ?? state.rows.length;
  const ok = window.confirm(`Delete all ${count} rows from ${table}? This cannot be undone.`);
  if (!ok) {
    return;
  }

  const result = await request(`/api/v1/db/${encodeURIComponent(table)}`, { method: "DELETE" });
  state.selectedTable = table;
  newRow();
  await refreshTables();
  await loadRows();
  setStatus(`Cleaned ${table}. Deleted ${result.deleted} rows.`);
}

function bindEvents() {
  elements.refreshTables.addEventListener("click", refreshTables);
  elements.loadRows.addEventListener("click", loadRows);
  elements.newRow.addEventListener("click", newRow);
  elements.saveRow.addEventListener("click", () => saveRow().catch((error) => setStatus(error.message, true)));
  elements.deleteRow.addEventListener("click", () => deleteRow().catch((error) => setStatus(error.message, true)));
  elements.clearTable.addEventListener("click", () => clearTable().catch((error) => setStatus(error.message, true)));
}

async function init() {
  bindEvents();
  try {
    await refreshTables();
    const firstTable = Object.keys(state.tables)[0];
    if (firstTable) {
      await selectTable(firstTable);
    }
  } catch (error) {
    setStatus(error.message, true);
  }
}

init();
