const apiBase = `${window.location.origin}/api`;
const map = L.map("map", { zoomControl: true, attributionControl: true }).setView([-23.5, -46.6], 8);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const vehicleSelect = document.getElementById("vehicle-select");
const vehicleInfo = document.getElementById("vehicle-info");
const connectionStatus = document.getElementById("connection-status");
const requestedVehicleId = new URLSearchParams(window.location.search).get("vehicle_id");

let currentSocket = null;
let routeLayer = null;
let traveledLayer = null;
let truckMarker = null;
let originMarker = null;
let destinationMarker = null;
let alertLayer = L.layerGroup().addTo(map);
let traveledPoints = [];
let currentRoute = null;
let currentTruckLatLng = null;
let truckAnimationFrame = null;
let alertSignature = "";

function setConnectionStatus(label, online = false) {
  connectionStatus.textContent = label;
  connectionStatus.style.background = online ? "rgba(42, 157, 143, 0.18)" : "rgba(255,255,255,0.15)";
  connectionStatus.style.color = online ? "#0b6b61" : "#0b3f5c";
}

function truckIcon() {
  return L.divIcon({
    className: "",
    html: '<div class="truck-icon">🚚</div>',
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

function animateTruckTo(targetLatLng) {
  if (!truckMarker) return;
  if (truckAnimationFrame) {
    cancelAnimationFrame(truckAnimationFrame);
    truckAnimationFrame = null;
  }
  if (!currentTruckLatLng) {
    currentTruckLatLng = targetLatLng;
    truckMarker.setLatLng(targetLatLng);
    return;
  }

  const start = [...currentTruckLatLng];
  const end = [...targetLatLng];
  const duration = 1200;
  const startedAt = performance.now();

  function step(now) {
    const progress = Math.min((now - startedAt) / duration, 1);
    const lat = start[0] + (end[0] - start[0]) * progress;
    const lng = start[1] + (end[1] - start[1]) * progress;
    truckMarker.setLatLng([lat, lng]);
    if (progress < 1) {
      truckAnimationFrame = requestAnimationFrame(step);
    } else {
      currentTruckLatLng = end;
      truckAnimationFrame = null;
    }
  }

  truckAnimationFrame = requestAnimationFrame(step);
}

function formatTimestamp(value) {
  if (!value) return "--";
  return new Date(value).toLocaleString("pt-BR");
}

function updateInfo(payload) {
  const { vehicle, position } = payload;
  const route = payload.route || currentRoute;
  vehicleInfo.innerHTML = `
    <div><span>Veiculo:</span> ${vehicle.code} | ${vehicle.model}</div>
    <div><span>Placa:</span> ${vehicle.license_plate}</div>
    <div><span>Velocidade:</span> ${position ? `${position.speed_kmh.toFixed(1)} km/h` : "--"}</div>
    <div><span>Combustivel:</span> ${position ? `${position.fuel_level.toFixed(1)}%` : "--"}</div>
    <div><span>Carga:</span> ${position ? `${position.cargo_occupancy.toFixed(1)}%` : "--"}</div>
    <div><span>Rota:</span> ${route ? `${route.code} | ${route.name}` : "--"}</div>
    <div><span>Atualizacao:</span> ${position ? formatTimestamp(position.timestamp) : "--"}</div>
  `;
}

function resetLayers() {
  [routeLayer, traveledLayer, truckMarker, originMarker, destinationMarker].forEach((layer) => {
    if (layer) map.removeLayer(layer);
  });
  alertLayer.clearLayers();
  routeLayer = null;
  traveledLayer = null;
  truckMarker = null;
  originMarker = null;
  destinationMarker = null;
  traveledPoints = [];
  currentTruckLatLng = null;
  alertSignature = "";
  if (truckAnimationFrame) {
    cancelAnimationFrame(truckAnimationFrame);
    truckAnimationFrame = null;
  }
}

function drawStaticRoute(route) {
  if (!route || routeLayer) return;
  const plannedPoints = route.path_points.map((point) => [point.latitude, point.longitude]);
  routeLayer = L.polyline(plannedPoints, {
    color: "#6c8aa3",
    weight: 5,
    opacity: 0.85,
  }).addTo(map);
  originMarker = L.marker([route.origin_latitude, route.origin_longitude]).bindPopup(`Origem: ${route.origin_name}`).addTo(map);
  destinationMarker = L.marker([route.destination_latitude, route.destination_longitude]).bindPopup(`Destino: ${route.destination_name}`).addTo(map);
  map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
}

function updateTruck(position, vehicle, route) {
  if (!position) return;
  const latlng = [position.latitude, position.longitude];
  if (!truckMarker) {
    truckMarker = L.marker(latlng, { icon: truckIcon() }).addTo(map);
    currentTruckLatLng = latlng;
  } else {
    animateTruckTo(latlng);
  }
  truckMarker.bindPopup(
    `<b>${vehicle.code}</b><br>` +
      `Velocidade: ${position.speed_kmh.toFixed(1)} km/h<br>` +
      `Combustivel: ${position.fuel_level.toFixed(1)}%<br>` +
      `Carga: ${position.cargo_occupancy.toFixed(1)}%<br>` +
      `Horario: ${formatTimestamp(position.timestamp)}<br>` +
      `Rota: ${route ? `${route.code} | ${route.name}` : "--"}`
  );
  if (!map.getBounds().pad(-0.2).contains(latlng)) {
    map.panTo(latlng, { animate: true, duration: 0.7 });
  }
}

function updateTraveledLine(position) {
  if (!position) return;
  const latlng = [position.latitude, position.longitude];
  const lastPoint = traveledPoints[traveledPoints.length - 1];
  if (!lastPoint || lastPoint[0] !== latlng[0] || lastPoint[1] !== latlng[1]) {
    traveledPoints.push(latlng);
  }
  if (!traveledLayer) {
    traveledLayer = L.polyline(traveledPoints, {
      color: "#2a9d8f",
      weight: 5,
      opacity: 0.95,
    }).addTo(map);
  } else {
    traveledLayer.setLatLngs(traveledPoints);
  }
}

function drawAlerts(alerts) {
  const nextSignature = JSON.stringify((alerts || []).map((alert) => [alert.id, alert.latitude, alert.longitude, alert.message]));
  if (nextSignature === alertSignature) return;
  alertSignature = nextSignature;
  alertLayer.clearLayers();
  if (!alerts || !alerts.length) return;
  alerts.forEach((alert) => {
    if (alert.latitude == null || alert.longitude == null) return;
    L.circleMarker([alert.latitude, alert.longitude], {
      radius: 7,
      color: "#d62828",
      fillColor: "#d62828",
      fillOpacity: 0.88,
      weight: 2,
    })
      .bindPopup(`<b>${alert.alert_type}</b><br>${alert.severity} | ${alert.message}`)
      .addTo(alertLayer);
  });
}

function applyBootstrap(payload) {
  resetLayers();
  currentRoute = payload.route || null;
  drawStaticRoute(payload.route);
  traveledPoints = (payload.history || []).map((item) => [item.latitude, item.longitude]);
  if (traveledPoints.length > 0) {
    traveledLayer = L.polyline(traveledPoints, {
      color: "#2a9d8f",
      weight: 5,
      opacity: 0.95,
    }).addTo(map);
  }
  updateTraveledLine(payload.position || null);
  updateTruck(payload.position, payload.vehicle, payload.route);
  drawAlerts(payload.active_alerts || []);
  updateInfo(payload);
}

function applyUpdate(payload) {
  updateTraveledLine(payload.position);
  updateTruck(payload.position, payload.vehicle, currentRoute);
  drawAlerts(payload.active_alerts || []);
  updateInfo({ vehicle: payload.vehicle, position: payload.position, route: currentRoute });
}

async function loadVehicleOptions() {
  const response = await fetch(`${apiBase}/dashboard/snapshot`);
  const payload = await response.json();
  vehicleSelect.innerHTML = "";
  (payload.vehicles || []).forEach((vehicle) => {
    const option = document.createElement("option");
    option.value = vehicle.id;
    option.textContent = `${vehicle.code} | ${vehicle.license_plate}`;
    vehicleSelect.appendChild(option);
  });
}

async function loadBootstrap(vehicleId) {
  const response = await fetch(`${apiBase}/live/vehicles/${vehicleId}/bootstrap`);
  if (!response.ok) throw new Error("Falha ao carregar estado inicial.");
  return response.json();
}

function closeSocket() {
  if (currentSocket) currentSocket.close();
}

function openSocket(vehicleId) {
  closeSocket();
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  currentSocket = new WebSocket(`${protocol}://${window.location.host}/ws/vehicle/${vehicleId}`);
  currentSocket.onopen = () => setConnectionStatus("WebSocket online", true);
  currentSocket.onclose = () => setConnectionStatus("WebSocket desconectado", false);
  currentSocket.onerror = () => setConnectionStatus("Erro de conexao", false);
  currentSocket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.message_type === "heartbeat") return;
    if (payload.message_type === "bootstrap") {
      applyBootstrap(payload);
      return;
    }
    applyUpdate(payload);
  };
}

async function activateVehicle(vehicleId) {
  setConnectionStatus("Carregando...", false);
  const bootstrap = await loadBootstrap(vehicleId);
  applyBootstrap(bootstrap);
  openSocket(vehicleId);
}

async function start() {
  await loadVehicleOptions();
  if (requestedVehicleId && Array.from(vehicleSelect.options).some((option) => option.value === requestedVehicleId)) {
    vehicleSelect.value = requestedVehicleId;
  }
  if (vehicleSelect.value) {
    await activateVehicle(vehicleSelect.value);
  }
  vehicleSelect.addEventListener("change", async (event) => {
    await activateVehicle(event.target.value);
  });
}

start().catch((error) => {
  setConnectionStatus("Falha ao iniciar", false);
  console.error(error);
});
