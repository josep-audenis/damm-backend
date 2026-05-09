const state = {
  selectedTable: "",
  selectedRowId: null,
  tables: {},
  rows: [],
  transports: [],
  optimization: null,
  progress: [],
  socket: null,
};

const elements = {
  transportSelect: document.querySelector("#transportSelect"),
  truckType: document.querySelector("#truckType"),
  respectWindows: document.querySelector("#respectWindows"),
  runOptimization: document.querySelector("#runOptimization"),
  optStatus: document.querySelector("#optStatus"),
  jobBadge: document.querySelector("#jobBadge"),
  progressBar: document.querySelector("#progressBar"),
  progressSteps: document.querySelector("#progressSteps"),
  solverBadge: document.querySelector("#solverBadge"),
  kpiStops: document.querySelector("#kpiStops"),
  kpiDistance: document.querySelector("#kpiDistance"),
  kpiTime: document.querySelector("#kpiTime"),
  kpiPallets: document.querySelector("#kpiPallets"),
  routeCount: document.querySelector("#routeCount"),
  routeMap: document.querySelector("#routeMap"),
  routeList: document.querySelector("#routeList"),
  loadCount: document.querySelector("#loadCount"),
  truckViz: document.querySelector("#truckViz"),
  pickList: document.querySelector("#pickList"),
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

function setOptStatus(message, isError = false) {
  elements.optStatus.textContent = message;
  elements.optStatus.classList.toggle("error", isError);
}

function renderTransports() {
  elements.transportSelect.innerHTML = "";
  for (const transport of state.transports) {
    const option = document.createElement("option");
    option.value = transport.transport_id;
    option.textContent = `${transport.transport_id} | ${transport.route_code} | ${transport.driver_name} | ${transport.stop_count} stops`;
    elements.transportSelect.append(option);
  }
}

async function loadTransports() {
  state.transports = await request("/api/v1/data/transports");
  renderTransports();
  const demoOption = Array.from(elements.transportSelect.options).find((option) => option.value === "11420379");
  if (demoOption) {
    elements.transportSelect.value = demoOption.value;
  }
  setOptStatus(state.transports.length ? "Ready." : "No transports found.", state.transports.length === 0);
}

function resetOptimizationView() {
  state.optimization = null;
  state.progress = [];
  elements.jobBadge.textContent = "No job";
  elements.solverBadge.textContent = "Waiting";
  elements.progressBar.style.width = "0%";
  elements.progressSteps.innerHTML = "";
  elements.kpiStops.textContent = "-";
  elements.kpiDistance.textContent = "-";
  elements.kpiTime.textContent = "-";
  elements.kpiPallets.textContent = "-";
  elements.routeCount.textContent = "0 stops";
  elements.loadCount.textContent = "0 pallets";
  elements.routeMap.innerHTML = "";
  elements.routeList.innerHTML = '<div class="empty">Run optimization to see stop order.</div>';
  elements.truckViz.innerHTML = '<div class="empty">Run optimization to see pallet layout.</div>';
  elements.pickList.innerHTML = "";
}

function renderProgress(message) {
  if (message.type !== "progress") {
    return;
  }
  state.progress.push(message);
  elements.progressBar.style.width = `${message.pct}%`;
  elements.progressSteps.innerHTML = "";
  for (const step of state.progress) {
    const pill = document.createElement("span");
    pill.className = `step-pill${step.phase === message.phase ? " active" : ""}`;
    pill.textContent = `${step.pct}% ${step.phase}`;
    pill.title = step.message;
    elements.progressSteps.append(pill);
  }
  setOptStatus(message.message);
}

function renderRoute(route) {
  const stops = route?.ordered_stops || [];
  elements.routeCount.textContent = `${stops.length} stops`;
  elements.routeMap.innerHTML = "";
  elements.routeList.innerHTML = "";

  if (stops.length === 0) {
    elements.routeMap.innerHTML = '<text x="50%" y="50%" text-anchor="middle" class="route-label">No route yet</text>';
    return;
  }

  const points = stops.map((stop, index) => {
    const fallbackX = 80 + (index % 6) * 105;
    const fallbackY = 80 + Math.floor(index / 6) * 110;
    return {
      stop,
      index,
      lat: stop.lat,
      lng: stop.lng,
      x: fallbackX,
      y: fallbackY,
    };
  });
  const withCoords = points.filter((point) => point.lat !== null && point.lng !== null);
  if (withCoords.length > 1) {
    const lats = withCoords.map((point) => point.lat);
    const lngs = withCoords.map((point) => point.lng);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    for (const point of points) {
      if (point.lat === null || point.lng === null) {
        continue;
      }
      point.x = 50 + ((point.lng - minLng) / Math.max(maxLng - minLng, 0.0001)) * 620;
      point.y = 370 - ((point.lat - minLat) / Math.max(maxLat - minLat, 0.0001)) * 320;
    }
  }

  const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  polyline.setAttribute("class", "route-line");
  polyline.setAttribute("points", points.map((point) => `${point.x},${point.y}`).join(" "));
  elements.routeMap.append(polyline);

  for (const point of points) {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", "route-point");
    circle.setAttribute("cx", point.x);
    circle.setAttribute("cy", point.y);
    circle.setAttribute("r", "13");
    elements.routeMap.append(circle);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("class", "route-label");
    label.setAttribute("x", point.x);
    label.setAttribute("y", point.y + 4);
    label.setAttribute("text-anchor", "middle");
    label.textContent = String(point.index + 1);
    elements.routeMap.append(label);

    const item = document.createElement("div");
    item.className = "route-item";
    item.innerHTML = `<strong>${point.index + 1}</strong><span>${point.stop.customer_name} | ${point.stop.city}</span>`;
    elements.routeList.append(item);
  }
}

function renderTruck(load, viz) {
  const pallets = viz?.pallets || [];
  elements.loadCount.textContent = `${pallets.length} pallets`;
  elements.truckViz.innerHTML = "";
  elements.pickList.innerHTML = "";

  if (pallets.length === 0) {
    elements.truckViz.innerHTML = '<div class="empty">No pallets yet.</div>';
    return;
  }

  for (const pallet of pallets) {
    const tile = document.createElement("div");
    tile.className = "pallet-tile";
    tile.style.background = pallet.color;
    tile.title = `${pallet.pallet_id} | ${pallet.label}`;
    tile.innerHTML = `<span>${pallet.pallet_id}</span><small>${pallet.label}</small>`;
    elements.truckViz.append(tile);
  }

  for (const item of (load?.pick_list || []).slice(0, 30)) {
    const row = document.createElement("div");
    row.className = "pick-item";
    row.innerHTML = `<strong>${item.sequence}</strong><span>${item.warehouse_location} | ${item.quantity} ${item.unit} | ${item.description}</span>`;
    elements.pickList.append(row);
  }
}

function renderOptimizationResult(result) {
  state.optimization = result;
  const route = result.route;
  const load = result.load;
  if (state.progress.length === 0) {
    renderProgress({
      type: "progress",
      phase: "done",
      pct: 100,
      message: "Optimisation complete",
    });
  }
  elements.solverBadge.textContent = route?.explanation || "Done";
  elements.kpiStops.textContent = route ? String(route.total_stops) : "-";
  elements.kpiDistance.textContent = route ? `${route.total_distance_km} km` : "-";
  elements.kpiTime.textContent = route ? `${Math.round(route.total_time_min)} min` : "-";
  elements.kpiPallets.textContent = load ? `${load.pallet_slots_used}/${load.pallet_slots_total}` : "-";
  renderRoute(route);
  renderTruck(load, result.viz);
}

async function runOptimization() {
  const transportId = elements.transportSelect.value;
  if (!transportId) {
    setOptStatus("Pick transport first.", true);
    return;
  }

  if (state.socket) {
    state.socket.close();
  }
  resetOptimizationView();
  elements.runOptimization.disabled = true;
  setOptStatus("Starting optimization.");
  const accepted = await request("/api/v1/optimize/full", {
    method: "POST",
    body: JSON.stringify({
      transport_id: transportId,
      truck_type: elements.truckType.value,
      respect_time_windows: elements.respectWindows.checked,
      solver_time_limit_s: 5,
    }),
  });
  elements.jobBadge.textContent = accepted.job_id;
  let terminalMessageReceived = false;
  const wsUrl = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${accepted.ws_url}`;
  state.socket = new WebSocket(wsUrl);
  state.socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "progress") {
      renderProgress(message);
    }
    if (message.type === "partial") {
      renderRoute(message.route);
    }
    if (message.type === "result") {
      renderOptimizationResult(message.result);
    }
    if (message.type === "done") {
      terminalMessageReceived = true;
      setOptStatus("Optimization complete.");
      elements.runOptimization.disabled = false;
    }
    if (message.type === "error") {
      terminalMessageReceived = true;
      setOptStatus(`${message.code}: ${message.message}`, true);
      elements.runOptimization.disabled = false;
    }
  };
  state.socket.onerror = () => {
    setOptStatus("WebSocket closed before final result. Fetching job.");
  };
  state.socket.onclose = async () => {
    if (terminalMessageReceived || state.optimization) {
      return;
    }
    try {
      const result = await request(`/api/v1/jobs/${accepted.job_id}`);
      renderOptimizationResult(result);
      setOptStatus("Optimization complete.");
    } catch (error) {
      setOptStatus(error.message, true);
    } finally {
      elements.runOptimization.disabled = false;
    }
  };
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
  elements.runOptimization.addEventListener("click", () =>
    runOptimization().catch((error) => {
      setOptStatus(error.message, true);
      elements.runOptimization.disabled = false;
    }),
  );
  elements.refreshTables.addEventListener("click", refreshTables);
  elements.loadRows.addEventListener("click", loadRows);
  elements.newRow.addEventListener("click", newRow);
  elements.saveRow.addEventListener("click", () => saveRow().catch((error) => setStatus(error.message, true)));
  elements.deleteRow.addEventListener("click", () => deleteRow().catch((error) => setStatus(error.message, true)));
  elements.clearTable.addEventListener("click", () => clearTable().catch((error) => setStatus(error.message, true)));
}

async function init() {
  bindEvents();
  resetOptimizationView();
  try {
    await loadTransports();
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
