const state = {
  selectedTable: "",
  selectedRowId: null,
  tables: {},
  rows: [],
  optimization: null,
  progress: [],
  socket: null,
  map: null,
  routeLayer: null,
};

const elements = {
  planDate: document.querySelector("#planDate"),
  maxOrders: document.querySelector("#maxOrders"),
  respectWindows: document.querySelector("#respectWindows"),
  persistPlan: document.querySelector("#persistPlan"),
  runOptimization: document.querySelector("#runOptimization"),
  optStatus: document.querySelector("#optStatus"),
  jobBadge: document.querySelector("#jobBadge"),
  progressBar: document.querySelector("#progressBar"),
  progressSteps: document.querySelector("#progressSteps"),
  solverBadge: document.querySelector("#solverBadge"),
  kpiRoutes: document.querySelector("#kpiRoutes"),
  kpiStops: document.querySelector("#kpiStops"),
  kpiDistance: document.querySelector("#kpiDistance"),
  kpiTime: document.querySelector("#kpiTime"),
  kpiPallets: document.querySelector("#kpiPallets"),
  routeCount: document.querySelector("#routeCount"),
  routeMap: document.querySelector("#routeMap"),
  routeSvg: document.querySelector("#routeSvg"),
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
  ordersCsv: document.querySelector("#ordersCsv"),
  ordersDueDate: document.querySelector("#ordersDueDate"),
  importOrders: document.querySelector("#importOrders"),
  clearImported: document.querySelector("#clearImported"),
  ordersStatus: document.querySelector("#ordersStatus"),
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

function resetOptimizationView() {
  state.optimization = null;
  state.progress = [];
  elements.jobBadge.textContent = "No job";
  elements.solverBadge.textContent = "Waiting";
  elements.progressBar.style.width = "0%";
  elements.progressSteps.innerHTML = "";
  elements.kpiRoutes.textContent = "-";
  elements.kpiStops.textContent = "-";
  elements.kpiDistance.textContent = "-";
  elements.kpiTime.textContent = "-";
  elements.kpiPallets.textContent = "-";
  elements.routeCount.textContent = "0 stops";
  elements.loadCount.textContent = "0 pallets";
  elements.routeMap.innerHTML = "";
  elements.routeMap.append(elements.routeSvg);
  elements.routeSvg.innerHTML = "";
  elements.routeList.innerHTML = '<div class="empty">Plan orders to see generated route order.</div>';
  elements.truckViz.innerHTML = '<div class="empty">Plan orders to see truck load layout.</div>';
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
  if (state.map && state.routeLayer) {
    state.routeLayer.clearLayers();
  }
  elements.routeSvg.innerHTML = "";
  elements.routeList.innerHTML = "";

  if (stops.length === 0) {
    elements.routeSvg.innerHTML = '<text x="50%" y="50%" text-anchor="middle" class="route-label">No route yet</text>';
    return;
  }

  const hasAllCoords = stops.every((stop) => stop.lat !== null && stop.lng !== null);
  if (hasAllCoords && window.L) {
    renderLeafletRoute(stops);
  } else {
    renderCoordinateFallback(stops, hasAllCoords);
  }

  for (const [index, stop] of stops.entries()) {
    const item = document.createElement("div");
    item.className = "route-item";
    item.innerHTML = `<strong>${index + 1}</strong><span>${stop.customer_name} | ${stop.city}</span>`;
    elements.routeList.append(item);
  }
}

function renderRouteSelector(routes) {
  if (!routes || routes.length <= 1) {
    return;
  }
  const selector = document.createElement("div");
  selector.className = "route-selector";
  routes.forEach((route, index) => {
    const button = document.createElement("button");
    button.className = `route-tab${index === 0 ? " active" : ""}`;
    button.textContent = `${route.route_code} | ${route.total_stops}`;
    button.addEventListener("click", () => {
      selector.querySelectorAll(".route-tab").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderRoute(route);
      renderTruck(state.optimization.loads?.[index], buildVizForLoad(state.optimization.loads?.[index], route));
      elements.routeList.prepend(selector);
    });
    selector.append(button);
  });
  elements.routeList.prepend(selector);
}

function renderLeafletRoute(stops) {
  elements.routeSvg.style.display = "none";
  if (!state.map) {
    state.map = L.map(elements.routeMap, { scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(state.map);
    state.routeLayer = L.layerGroup().addTo(state.map);
  }
  state.routeLayer.clearLayers();
  const latLngs = stops.map((stop) => [stop.lat, stop.lng]);
  const geojson = state.optimization?.viz?.route_geojson;
  if (geojson) {
    L.geoJSON(geojson, { style: { color: "#2563eb", weight: 5 } }).addTo(state.routeLayer);
  } else {
    L.polyline(latLngs, { color: "#2563eb", weight: 4, dashArray: "8 7" }).addTo(state.routeLayer);
  }
  L.marker([41.5409, 2.2134]).bindPopup("DDI Mollet depot").addTo(state.routeLayer);
  stops.forEach((stop, index) => {
    L.marker([stop.lat, stop.lng])
      .bindPopup(`${index + 1}. ${stop.customer_name}`)
      .addTo(state.routeLayer);
  });
  state.map.fitBounds([[41.5409, 2.2134], ...latLngs], { padding: [32, 32] });
}

function renderCoordinateFallback(stops, hasAllCoords) {
  elements.routeSvg.style.display = "block";
  if (!hasAllCoords) {
    elements.routeSvg.innerHTML =
      '<text x="50%" y="46%" text-anchor="middle" class="route-label">Missing coordinates for this transport.</text><text x="50%" y="54%" text-anchor="middle" class="route-label">Enable geocoding or choose geocoded stops.</text>';
    return;
  }

  const points = stops.map((stop, index) => {
    return {
      stop,
      index,
      lat: stop.lat,
      lng: stop.lng,
      x: 0,
      y: 0,
    };
  });
  const lats = points.map((point) => point.lat);
  const lngs = points.map((point) => point.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  for (const point of points) {
    point.x = 50 + ((point.lng - minLng) / Math.max(maxLng - minLng, 0.0001)) * 620;
    point.y = 370 - ((point.lat - minLat) / Math.max(maxLat - minLat, 0.0001)) * 320;
  }

  const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  polyline.setAttribute("class", "route-line");
  polyline.setAttribute("points", points.map((point) => `${point.x},${point.y}`).join(" "));
  elements.routeSvg.append(polyline);

  for (const point of points) {
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", "route-point");
    circle.setAttribute("cx", point.x);
    circle.setAttribute("cy", point.y);
    circle.setAttribute("r", "13");
    elements.routeSvg.append(circle);

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("class", "route-label");
    label.setAttribute("x", point.x);
    label.setAttribute("y", point.y + 4);
    label.setAttribute("text-anchor", "middle");
    label.textContent = String(point.index + 1);
    elements.routeSvg.append(label);
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

function buildVizForLoad(load, route) {
  if (!load) {
    return null;
  }
  const colors = ["#2563eb", "#16a34a", "#f97316", "#dc2626", "#7c3aed", "#0891b2", "#4b5563"];
  const names = Object.fromEntries((route?.ordered_stops || []).map((stop) => [stop.stop_id, stop.customer_name]));
  return {
    pallets: (load.pallets || []).map((pallet, index) => ({
      pallet_id: pallet.pallet_id,
      label: names[pallet.stop_ids?.[0]] || pallet.pallet_id,
      color: colors[index % colors.length],
      stop_ids: pallet.stop_ids || [],
    })),
  };
}

function renderOptimizationResult(result) {
  state.optimization = result;
  const routes = result.routes?.length ? result.routes : result.route ? [result.route] : [];
  const loads = result.loads?.length ? result.loads : result.load ? [result.load] : [];
  const route = routes[0];
  const load = loads[0];
  if (state.progress.length === 0) {
    renderProgress({
      type: "progress",
      phase: "done",
      pct: 100,
      message: "Optimisation complete",
    });
  }
  elements.solverBadge.textContent = route?.explanation || "Done";
  elements.kpiRoutes.textContent = String(routes.length);
  elements.kpiStops.textContent = String(routes.reduce((total, item) => total + item.total_stops, 0));
  elements.kpiDistance.textContent = `${routes.reduce((total, item) => total + item.total_distance_km, 0).toFixed(1)} km`;
  elements.kpiTime.textContent = `${Math.round(routes.reduce((total, item) => total + item.total_time_min, 0))} min`;
  elements.kpiPallets.textContent = loads.length
    ? `${loads.reduce((total, item) => total + item.pallet_slots_used, 0)}/${loads.reduce((total, item) => total + item.pallet_slots_total, 0)}`
    : "-";
  renderTruck(load, result.viz || buildVizForLoad(load, route));
  renderRoute(route);
  renderRouteSelector(routes);
}

async function runOptimization() {
  const maxOrders = Number(elements.maxOrders.value || 0);
  if (!elements.planDate.value) {
    setOptStatus("Pick due date first.", true);
    return;
  }
  if (!Number.isInteger(maxOrders) || maxOrders < 1 || maxOrders > 5000) {
    setOptStatus("Max orders must be 1-5000.", true);
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
      date: elements.planDate.value,
      max_orders: maxOrders,
      persist_plan: elements.persistPlan.checked,
      respect_time_windows: elements.respectWindows.checked,
      use_real_roads: true,
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
      setOptStatus("Order plan complete.");
      elements.runOptimization.disabled = false;
    }
    if (message.type === "error") {
      terminalMessageReceived = true;
      elements.solverBadge.textContent = "Error";
      elements.kpiRoutes.textContent = "-";
      elements.kpiStops.textContent = "-";
      elements.kpiDistance.textContent = "-";
      elements.kpiTime.textContent = "-";
      elements.kpiPallets.textContent = "-";
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
      setOptStatus("Order plan complete.");
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

function setOrdersStatus(message, isError = false) {
  elements.ordersStatus.textContent = message;
  elements.ordersStatus.classList.toggle("error", isError);
}

async function importOrdersCsv() {
  const file = elements.ordersCsv.files?.[0];
  if (!file) {
    setOrdersStatus("Pick a CSV file first.", true);
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  if (elements.ordersDueDate.value) {
    formData.append("due_date", elements.ordersDueDate.value);
  }

  elements.importOrders.disabled = true;
  setOrdersStatus(`Uploading ${file.name}...`);
  try {
    const response = await fetch("/api/v1/data/orders/import", { method: "POST", body: formData });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || response.statusText);
    }
    const parts = [
      `Inserted ${payload.inserted}`,
      `Skipped ${payload.skipped}`,
      `Unknown customers ${payload.unknown_customers.length}`,
      `Unknown materials ${payload.unknown_materials.length}`,
    ];
    setOrdersStatus(`${parts.join(" | ")} (received ${payload.received}).`);
    elements.ordersCsv.value = "";
    await refreshTables();
    if (state.selectedTable === "orders") {
      await loadRows();
    }
  } catch (error) {
    setOrdersStatus(error.message, true);
  } finally {
    elements.importOrders.disabled = false;
  }
}

async function clearImportedOrders() {
  const ok = window.confirm("Delete every order created by past CSV imports? Seeded orders are kept.");
  if (!ok) {
    return;
  }
  elements.clearImported.disabled = true;
  setOrdersStatus("Deleting imported orders...");
  try {
    const response = await fetch("/api/v1/data/orders/imported", { method: "DELETE" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || response.statusText);
    }
    setOrdersStatus(
      `Deleted ${payload.deleted_orders} orders (and ${payload.deleted_delivery_lines} delivery lines).`,
    );
    await refreshTables();
    if (state.selectedTable === "orders") {
      await loadRows();
    }
  } catch (error) {
    setOrdersStatus(error.message, true);
  } finally {
    elements.clearImported.disabled = false;
  }
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
  elements.importOrders.addEventListener("click", importOrdersCsv);
  elements.clearImported.addEventListener("click", clearImportedOrders);
}

async function init() {
  bindEvents();
  resetOptimizationView();
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
