from __future__ import annotations

import os
from typing import Any

import folium
from geopy.distance import geodesic
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    from streamlit_folium import st_folium
    STREAMLIT_FOLIUM_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover
    STREAMLIT_FOLIUM_AVAILABLE = False

    def st_folium(*_: Any, **__: Any) -> None:
        return None

try:
    from streamlit_autorefresh import st_autorefresh
except ModuleNotFoundError:  # pragma: no cover
    def st_autorefresh(*_: Any, **__: Any) -> None:
        return None


API_BASE_URL = os.getenv("LOGICORE_API_URL", "http://localhost:8000/api").rstrip("/")
BACKEND_BASE_URL = API_BASE_URL.rsplit("/api", 1)[0] if API_BASE_URL.endswith("/api") else API_BASE_URL
LIVE_TRACKING_BASE_URL = os.getenv("LOGICORE_LIVE_TRACKING_URL", "http://localhost:8000/live-tracking/").rstrip("/")
DEFAULT_REFRESH_SECONDS = 10
CRITICAL_FUEL_LEVEL = 20
ATTENTION_FUEL_LEVEL = 35
SPEED_LIMIT_KMH = 90
HIGH_SPEED_KMH = 80
GEOFENCE_RADIUS_METERS = 1200

st.set_page_config(page_title="LogiCore ERP | Painel Operacional", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: radial-gradient(circle at top left, rgba(11, 63, 92, 0.08), transparent 24%), linear-gradient(180deg, #f3f7fa 0%, #fbfcfd 100%); color: #17324d; }
        .hero-card { background: linear-gradient(120deg, #081f31, #0b3f5c 58%, #2a6f97 100%); border-radius: 22px; padding: 1.3rem 1.4rem; color: #f5fbff; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 18px 44px rgba(9, 27, 42, 0.16); margin-bottom: 1rem; }
        .panel-card { background: white; border-radius: 20px; border: 1px solid rgba(17, 34, 68, 0.08); box-shadow: 0 14px 34px rgba(15, 41, 64, 0.08); padding: 1rem 1.05rem; }
        .status-pill { display: inline-block; padding: 0.35rem 0.72rem; border-radius: 999px; font-weight: 700; font-size: 0.8rem; }
        .online { background: rgba(22,163,74,0.14); color: #166534; }
        .offline { background: rgba(220,38,38,0.14); color: #991b1b; }
        div[data-testid="stMetric"] { background: white; border: 1px solid rgba(15, 41, 64, 0.08); border-radius: 18px; padding: 0.85rem 1rem; box-shadow: 0 10px 24px rgba(18, 38, 63, 0.06); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def fetch_json(path: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(f"{API_BASE_URL}{path}", timeout=8, params=params)
    response.raise_for_status()
    return response.json()


def safe_fetch(path: str, params: dict[str, Any] | None = None) -> tuple[Any | None, str | None]:
    try:
        return fetch_json(path, params=params), None
    except requests.RequestException as exc:
        return None, str(exc)


@st.cache_data(ttl=12, show_spinner=False)
def cached_fetch(path: str, params_key: tuple[tuple[str, Any], ...] = ()) -> Any:
    params = dict(params_key) if params_key else None
    return fetch_json(path, params=params)


def vehicle_risk(speed: float, fuel: float) -> str:
    if fuel < CRITICAL_FUEL_LEVEL or speed > SPEED_LIMIT_KMH:
        return "CRITICO"
    if fuel < ATTENTION_FUEL_LEVEL or speed >= HIGH_SPEED_KMH:
        return "ATENCAO"
    return "NORMAL"


def color_hex(status_value: str) -> str:
    return {"CRITICO": "#d62828", "ATENCAO": "#f77f00", "NORMAL": "#2a9d8f"}.get(status_value, "#3a86ff")


def color_name(status_value: str) -> str:
    return {"CRITICO": "red", "ATENCAO": "orange", "NORMAL": "green"}.get(status_value, "blue")


def load_bundle() -> tuple[dict[str, Any] | None, str | None]:
    try:
        snapshot = cached_fetch("/dashboard/snapshot")
        orders = cached_fetch("/orders")
        routes = cached_fetch("/routes")
        invoices = cached_fetch("/invoices")
        vehicle_summary = cached_fetch("/vehicles/summary")
    except requests.RequestException as exc:
        return None, str(exc)
    return {"snapshot": snapshot, "orders": orders, "routes": routes, "invoices": invoices, "vehicle_summary": vehicle_summary}, None


def build_vehicle_df(snapshot: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(snapshot.get("vehicles", []))
    if df.empty:
        return df
    for column in ["latitude", "longitude", "speed_kmh", "fuel_level", "cargo_occupancy"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["route_label"] = df["route_code"].fillna("SEM_ROTA") + " | " + df["route_name"].fillna("Nao atribuida")
    df["operational_status"] = df.apply(lambda row: vehicle_risk(float(row["speed_kmh"] or 0), float(row["fuel_level"] or 0)), axis=1)
    df["status_color"] = df["operational_status"].map(color_hex)
    return df


def build_vehicle_summary_df(items: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(items)
    if df.empty:
        return df
    for column, default in {
        "id": None,
        "code": "SEM_CODIGO",
        "license_plate": "SEM_PLACA",
        "model": "Sem modelo",
        "vehicle_status": "SEM_STATUS",
        "route_id": None,
        "route_code": None,
        "route_name": None,
        "speed_kmh": None,
        "fuel_level": None,
        "cargo_occupancy": None,
        "timestamp": None,
    }.items():
        if column not in df.columns:
            df[column] = default
    for column in ["speed_kmh", "fuel_level", "cargo_occupancy"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["route_label"] = df["route_code"].fillna("SEM_ROTA") + " | " + df["route_name"].fillna("Nao atribuida")
    df["operational_status"] = df.apply(
        lambda row: vehicle_risk(float(row["speed_kmh"] or 0), float(row["fuel_level"] or 0)),
        axis=1,
    )
    return df


def build_alert_df(snapshot: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(snapshot.get("alerts", []))
    if df.empty:
        return df
    for column in ["vehicle_id", "route_id", "severity", "alert_type", "message", "created_at"]:
        if column not in df.columns:
            df[column] = None
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    return df


def build_orders_df(orders: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(orders)
    if df.empty:
        return df
    for column in ["created_at", "expected_delivery_at", "shipped_at", "delivered_at"]:
        df[column] = pd.to_datetime(df[column], errors="coerce")
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce").fillna(0.0)
    return df


def build_routes_df(routes: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(routes)


def build_invoice_df(invoices: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(invoices)
    if df.empty:
        return df
    if "issue_date" in df.columns:
        df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    for column in ["total_value", "unit_price", "quantity"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def route_map(routes: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(route["id"]): route for route in routes}


def format_timestamp(value: pd.Timestamp | Any) -> str:
    if value is None or pd.isna(value):
        return "Sem dados"
    return pd.to_datetime(value).strftime("%d/%m/%Y %H:%M:%S")


def vehicle_online_status(value: pd.Timestamp | Any) -> str:
    if value is None or pd.isna(value):
        return "OFFLINE"
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return "OFFLINE"
    age_seconds = (pd.Timestamp.utcnow() - timestamp).total_seconds()
    return "ONLINE" if age_seconds <= 30 else "OFFLINE"


def build_live_tracking_url(vehicle_id: int) -> str:
    separator = "&" if "?" in LIVE_TRACKING_BASE_URL else "?"
    return f"{LIVE_TRACKING_BASE_URL}{separator}vehicle_id={vehicle_id}"


def build_truck_icon(status_value: str, label: str = "") -> folium.DivIcon:
    accent = color_hex(status_value)
    suffix = f"<div style='font-size:10px;font-weight:700;margin-top:2px;color:#17324d'>{label}</div>" if label else ""
    return folium.DivIcon(
        html=f"""
        <div style="transform: translate(-14px, -18px); text-align:center;">
            <div style="
                width:28px;height:28px;border-radius:50%;
                background:{accent};color:white;
                display:flex;align-items:center;justify-content:center;
                border:2px solid white;box-shadow:0 4px 12px rgba(0,0,0,0.2);
                font-size:15px;
            ">🚚</div>
            {suffix}
        </div>
        """
    )


def filter_alert_dataframe(alert_df: pd.DataFrame, vehicle_id: int | None = None, route_id: int | None = None) -> pd.DataFrame:
    if alert_df.empty:
        return alert_df
    filtered = alert_df.copy()
    if vehicle_id is not None and "vehicle_id" in filtered.columns:
        filtered = filtered[filtered["vehicle_id"] == vehicle_id]
    if route_id is not None and "route_id" in filtered.columns:
        filtered = filtered[filtered["route_id"] == route_id]
    return filtered


def render_header(api_online: bool, generated_at: str | None) -> None:
    updated = "Sem sincronizacao" if not generated_at else pd.to_datetime(generated_at).strftime("%d/%m/%Y %H:%M:%S")
    pill_class = "online" if api_online else "offline"
    pill_text = "API ONLINE" if api_online else "API OFFLINE"
    st.markdown(
        f"""
        <div class="hero-card">
            <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap;">
                <div>
                    <div style="font-size:0.9rem;letter-spacing:0.08em;opacity:0.78;">LOGICORE ERP</div>
                    <div style="font-size:2.05rem;font-weight:800;line-height:1.1;margin-top:0.2rem;">Painel Avancado de Operacao Logistica</div>
                    <div style="margin-top:0.45rem;font-size:1rem;opacity:0.82;">Frota, rotas, telemetria, desvios e desempenho operacional em tempo real.</div>
                </div>
                <div style="min-width:250px;text-align:right;">
                    <span class="status-pill {pill_class}">{pill_text}</span>
                    <div style="margin-top:0.7rem;font-size:0.92rem;">Ultima atualizacao</div>
                    <div style="font-size:1.05rem;font-weight:700;">{updated}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(routes_df: pd.DataFrame) -> tuple[int | None, int, bool, str]:
    st.sidebar.title("Controle Operacional")
    route_options = {"Todas": None}
    if not routes_df.empty:
        for _, row in routes_df.sort_values("code").iterrows():
            route_options[f'{row["code"]} | {row["name"]}'] = int(row["id"])
    route_choice = st.sidebar.selectbox("Rota", list(route_options.keys()))
    map_mode = st.sidebar.radio("Modo do mapa", ["Visao Frota", "Visao Filtrada"], index=0)
    refresh_seconds = st.sidebar.slider("Intervalo de atualizacao (segundos)", 5, 60, DEFAULT_REFRESH_SECONDS, 5)
    auto_refresh = st.sidebar.checkbox("Atualizacao automatica", value=True)
    st.sidebar.caption("Critico: combustivel < 20% ou velocidade > 90 km/h")
    st.sidebar.caption("Atencao: combustivel < 35% ou velocidade >= 80 km/h")
    return route_options[route_choice], refresh_seconds, auto_refresh, map_mode


def filter_vehicles(df: pd.DataFrame, vehicle_id: int | None, route_id: int | None) -> pd.DataFrame:
    filtered = df.copy()
    if vehicle_id is not None:
        filtered = filtered[filtered["id"] == vehicle_id]
    if route_id is not None:
        filtered = filtered[filtered["route_id"] == route_id]
    return filtered


def metric_or_placeholder(value: Any, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "--"
    if isinstance(value, (int, float)):
        return f"{float(value):.1f}{suffix}"
    return f"{value}{suffix}"


def row_value(row: pd.Series, key: str, default: Any = None) -> Any:
    if key not in row.index:
        return default
    value = row.get(key, default)
    if value is None or pd.isna(value):
        return default
    return value


def get_vehicle_summary(vehicle_summary_df: pd.DataFrame, route_id: int | None) -> pd.DataFrame:
    return filter_vehicles(vehicle_summary_df, None, route_id)


def get_vehicle_detail(vehicle_id: int | None) -> dict[str, Any] | None:
    return load_vehicle_overview(vehicle_id)


def set_selected_vehicle(vehicle_id: int) -> None:
    st.session_state["selected_vehicle_id"] = int(vehicle_id)
    st.session_state["vehicle_view_mode"] = "detail"


def clear_selected_vehicle() -> None:
    st.session_state["selected_vehicle_id"] = None
    st.session_state["vehicle_view_mode"] = "list"


def get_selected_vehicle_id(all_vehicle_df: pd.DataFrame, route_id: int | None) -> int | None:
    selected_vehicle_id = st.session_state.get("selected_vehicle_id")
    if selected_vehicle_id is None or all_vehicle_df.empty:
        return None
    valid_ids = set(all_vehicle_df["id"].astype(int).tolist())
    if selected_vehicle_id not in valid_ids:
        st.session_state["selected_vehicle_id"] = None
        return None
    if route_id is not None:
        row = all_vehicle_df[all_vehicle_df["id"] == selected_vehicle_id]
        if row.empty or pd.isna(row.iloc[0]["route_id"]) or int(row.iloc[0]["route_id"]) != route_id:
            return None
    return int(selected_vehicle_id)


def render_vehicle_selector(vehicle_df: pd.DataFrame, route_id: int | None) -> int | None:
    st.subheader("Veiculos Disponiveis")
    filtered_df = get_vehicle_summary(vehicle_df, route_id)
    if filtered_df.empty:
        st.info("Nenhum veiculo disponivel para os filtros globais atuais.")
        clear_selected_vehicle()
        return None

    st.caption("Selecione um veiculo para abrir a visao detalhada.")
    vehicle_options = {
        f"{row['code']} | {row['license_plate']} | {row['route_label']}": int(row["id"])
        for _, row in filtered_df.sort_values("code").iterrows()
    }
    current_selected = get_selected_vehicle_id(vehicle_df, route_id)
    labels = list(vehicle_options.keys())
    default_index = 0
    if current_selected is not None:
        selected_label = next((label for label, vehicle_id in vehicle_options.items() if vehicle_id == current_selected), None)
        if selected_label is not None:
            default_index = labels.index(selected_label)
    selector_cols = st.columns([2, 1])
    with selector_cols[0]:
        chosen_label = st.selectbox("Selecionar veiculo", labels, index=default_index, key="vehicle-tab-selector")
    with selector_cols[1]:
        if st.button("Abrir detalhes", key="open-vehicle-details", use_container_width=True):
            set_selected_vehicle(vehicle_options[chosen_label])
            st.rerun()

    columns = st.columns(3)
    for idx, (_, row) in enumerate(filtered_df.sort_values("code").iterrows()):
        with columns[idx % 3]:
            st.markdown('<div class="panel-card">', unsafe_allow_html=True)
            vehicle_id = row_value(row, "id")
            st.markdown(f"**{row_value(row, 'code', 'SEM_CODIGO')}**")
            st.caption(f"{row_value(row, 'license_plate', 'SEM_PLACA')} | {row_value(row, 'model', 'Sem modelo')}")
            st.write(f"Status operacional: **{row_value(row, 'operational_status', 'SEM_STATUS')}**")
            st.write(f"Velocidade atual: **{metric_or_placeholder(row_value(row, 'speed_kmh'), ' km/h')}**")
            st.write(f"Combustivel atual: **{metric_or_placeholder(row_value(row, 'fuel_level'), '%')}**")
            st.write(f"Rota atual: **{row_value(row, 'route_label', 'SEM_ROTA')}**")
            if vehicle_id is not None and st.button("Visualizar veiculo", key=f"select-vehicle-{int(vehicle_id)}", use_container_width=True):
                set_selected_vehicle(int(vehicle_id))
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    selected_vehicle_id = get_selected_vehicle_id(vehicle_df, route_id)
    if selected_vehicle_id is None:
        st.info("Escolha um veiculo acima para carregar mapa, alertas e indicadores detalhados.")
    return selected_vehicle_id


def render_general_metrics(vehicle_df: pd.DataFrame, alert_df: pd.DataFrame, orders_df: pd.DataFrame, snapshot: dict[str, Any]) -> None:
    metrics = [
        ("Veiculos ativos", str(int(snapshot["kpis"]["active_vehicles"])), "Movimento atual"),
        ("Alertas criticos", str(0 if alert_df.empty or "severity" not in alert_df.columns else int((alert_df["severity"] == "ALTA").sum())), "Severidade alta"),
        ("Velocidade media", f'{0.0 if vehicle_df.empty else vehicle_df["speed_kmh"].mean():.1f} km/h', "Frota filtrada"),
        ("Combustivel medio", f'{0.0 if vehicle_df.empty else vehicle_df["fuel_level"].mean():.1f}%', "Frota filtrada"),
        ("Pedidos em rota", str(int(snapshot["kpis"]["orders_in_route"])), "Distribuicao ativa"),
        ("Entregas concluidas", str(0 if orders_df.empty else int((orders_df["status"] == "ENTREGUE").sum())), "Pedidos entregues"),
    ]
    cols = st.columns(len(metrics))
    for col, (label, value, delta_value) in zip(cols, metrics):
        with col:
            st.metric(label=label, value=value, delta=delta_value)


def draw_fleet_map(vehicle_df: pd.DataFrame, map_key: str = "fleet-map") -> None:
    if not STREAMLIT_FOLIUM_AVAILABLE:
        st.error("O pacote streamlit-folium nao esta instalado. Execute `pip install -r requirements.txt`.")
        return
    valid = vehicle_df.dropna(subset=["latitude", "longitude"])
    if valid.empty:
        st.info("Nenhum dado georreferenciado disponivel.")
        return
    fmap = folium.Map(location=[valid["latitude"].mean(), valid["longitude"].mean()], zoom_start=8, tiles="CartoDB positron")
    for _, row in valid.iterrows():
        popup = f"""
        <div style='min-width:220px'>
            <b>Veiculo:</b> {row['code']} ({row['model']})<br>
            <b>Status:</b> {row['operational_status']}<br>
            <b>Velocidade:</b> {row['speed_kmh']:.1f} km/h<br>
            <b>Combustivel:</b> {row['fuel_level']:.1f}%<br>
            <b>Ocupacao:</b> {row['cargo_occupancy']:.1f}%<br>
            <b>Rota:</b> {row['route_label']}
        </div>
        """
        folium.CircleMarker([row["latitude"], row["longitude"]], radius=9, color=row["status_color"], fill=True, fill_color=row["status_color"], fill_opacity=0.92, tooltip=f'{row["code"]} | {row["operational_status"]}', popup=folium.Popup(popup, max_width=300)).add_to(fmap)
    st_folium(fmap, width=None, height=500, returned_objects=[], key=map_key)


def load_history(vehicle_id: int | None) -> pd.DataFrame:
    if vehicle_id is None:
        return pd.DataFrame()
    history, error = safe_fetch(f"/telemetry/vehicles/{vehicle_id}/history")
    if error:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    if df.empty:
        return df
    for column in ["latitude", "longitude", "speed_kmh", "fuel_level", "cargo_occupancy"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    return df.sort_values("timestamp")


def load_vehicle_alerts(vehicle_id: int | None) -> pd.DataFrame:
    if vehicle_id is None:
        return pd.DataFrame()
    payload, error = safe_fetch("/alerts", params={"vehicle_id": vehicle_id})
    if error:
        return pd.DataFrame()
    df = pd.DataFrame(payload)
    if df.empty:
        return df
    for column in ["vehicle_id", "route_id", "severity", "alert_type", "message", "created_at"]:
        if column not in df.columns:
            df[column] = None
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    return df


def load_vehicle_planned_route(vehicle_id: int | None) -> dict[str, Any] | None:
    if vehicle_id is None:
        return None
    payload, error = safe_fetch(f"/routes/vehicles/{vehicle_id}/planned")
    if error:
        return None
    return payload


def load_vehicle_overview(vehicle_id: int | None) -> dict[str, Any] | None:
    if vehicle_id is None:
        return None
    try:
        return cached_fetch(f"/vehicles/{vehicle_id}/overview")
    except requests.RequestException:
        return None


def calculate_distance_traveled(history_df: pd.DataFrame) -> float:
    if history_df.empty or len(history_df) < 2:
        return 0.0
    points = history_df[["latitude", "longitude"]].dropna().apply(tuple, axis=1).tolist()
    total = 0.0
    for first, second in zip(points, points[1:]):
        total += geodesic(first, second).km
    return round(total, 2)


def calculate_route_deviation(history_df: pd.DataFrame, route_info: dict[str, Any] | None) -> float:
    if history_df.empty or route_info is None:
        return 0.0
    planned_points = [(point["latitude"], point["longitude"]) for point in route_info.get("path_points", [])]
    if not planned_points:
        return 0.0
    deviations = []
    for point in history_df[["latitude", "longitude"]].dropna().apply(tuple, axis=1).tolist():
        deviations.append(min(geodesic(point, planned).km for planned in planned_points))
    return round(sum(deviations) / len(deviations), 2) if deviations else 0.0


def calculate_delay_minutes(route_info: dict[str, Any] | None, history_df: pd.DataFrame) -> float:
    if route_info is None or history_df.empty or len(history_df) < 2:
        return 0.0
    expected = float(route_info.get("expected_duration_minutes", 0))
    actual = max((history_df["timestamp"].iloc[-1] - history_df["timestamp"].iloc[0]).total_seconds() / 60, 0)
    return round(max(actual - expected, 0), 1)


def estimate_eta(vehicle_row: pd.Series, route_info: dict[str, Any] | None, history_df: pd.DataFrame) -> str:
    if route_info is None or history_df.empty:
        return "Indisponivel"
    points = [(point["latitude"], point["longitude"]) for point in route_info.get("path_points", [])]
    if not points:
        return "Indisponivel"
    current_lat = row_value(vehicle_row, "latitude")
    current_lon = row_value(vehicle_row, "longitude")
    if current_lat is None or current_lon is None:
        if {"latitude", "longitude"}.issubset(history_df.columns) and not history_df.empty:
            latest_point = history_df.dropna(subset=["latitude", "longitude"]).tail(1)
            if latest_point.empty:
                return "Indisponivel"
            current_lat = float(latest_point.iloc[0]["latitude"])
            current_lon = float(latest_point.iloc[0]["longitude"])
        else:
            return "Indisponivel"
    current = (float(current_lat), float(current_lon))
    current_speed = float(row_value(vehicle_row, "speed_kmh", 0) or 0)
    destination = points[-1]
    remaining_distance = geodesic(current, destination).km
    if remaining_distance <= 0.1:
        return "Chegando ao destino"
    effective_speed = current_speed if current_speed > 5 else None
    if effective_speed is None:
        if len(history_df) < 2:
            return "Indisponivel"
        effective_speed = float(history_df["speed_kmh"].tail(min(len(history_df), 5)).mean())
    if effective_speed <= 0:
        return "Indisponivel"
    remaining_minutes = (remaining_distance / effective_speed) * 60
    eta = pd.Timestamp.utcnow() + pd.to_timedelta(max(remaining_minutes, 0), unit="m")
    return eta.strftime("%d/%m %H:%M")


def build_vehicle_alert_markers(history_df: pd.DataFrame, alerts_df: pd.DataFrame) -> list[tuple[float, float, str, str]]:
    if history_df.empty or alerts_df.empty or "id" not in history_df.columns or "telemetry_event_id" not in alerts_df.columns:
        return []
    markers: list[tuple[float, float, str, str]] = []
    history_by_id = history_df.set_index("id")
    for _, alert in alerts_df.iterrows():
        if alert["telemetry_event_id"] in history_by_id.index:
            event_row = history_by_id.loc[alert["telemetry_event_id"]]
            markers.append(
                (
                    float(event_row["latitude"]),
                    float(event_row["longitude"]),
                    str(alert.get("alert_type", "ALERTA")),
                    f'{alert.get("severity", "N/A")} | {alert.get("message", "")}',
                )
            )
    return markers


def history_status(history_row: pd.Series) -> str:
    return vehicle_risk(float(history_row.get("speed_kmh", 0) or 0), float(history_row.get("fuel_level", 0) or 0))


def route_efficiency_score(distance_traveled: float, route_deviation: float, delay_minutes: float, route_info: dict[str, Any] | None) -> float:
    if route_info is None:
        return 0.0
    planned_distance = float(route_info.get("estimated_distance_km", 0) or 0)
    distance_penalty = 0.0 if planned_distance <= 0 else max(distance_traveled - planned_distance, 0) / planned_distance * 35
    deviation_penalty = min(route_deviation * 12, 35)
    delay_penalty = min(delay_minutes / 2, 30)
    return round(max(100 - distance_penalty - deviation_penalty - delay_penalty, 0), 1)


def build_vehicle_timeline(history_df: pd.DataFrame, alerts_df: pd.DataFrame, route_info: dict[str, Any] | None) -> pd.DataFrame:
    events: list[dict[str, Any]] = []
    if route_info:
        events.append(
            {
                "timestamp": pd.NaT,
                "evento": "Rota planejada carregada",
                "detalhe": f"{route_info['origin_name']} -> {route_info['destination_name']}",
                "categoria": "ROTA",
            }
        )
    if not history_df.empty:
        for _, row in history_df.tail(12).iterrows():
            status_value = history_status(row)
            events.append(
                {
                    "timestamp": row["timestamp"],
                    "evento": "Telemetria recebida",
                    "detalhe": f"Vel {row['speed_kmh']:.1f} km/h | Comb {row['fuel_level']:.1f}% | {status_value}",
                    "categoria": "TELEMETRIA",
                }
            )
    if not alerts_df.empty:
        for _, row in alerts_df.head(12).iterrows():
            events.append(
                {
                    "timestamp": row.get("created_at"),
                    "evento": f"Alerta {row.get('alert_type', 'OPERACIONAL')}",
                    "detalhe": row.get("message", ""),
                    "categoria": "ALERTA",
                }
            )
    timeline_df = pd.DataFrame(events)
    if timeline_df.empty:
        return timeline_df
    timeline_df["timestamp"] = pd.to_datetime(timeline_df["timestamp"], errors="coerce")
    return timeline_df.sort_values("timestamp", ascending=False, na_position="last")


def draw_vehicle_map(planned_route: dict[str, Any] | None, map_key: str = "vehicle-map") -> None:
    if not STREAMLIT_FOLIUM_AVAILABLE:
        st.error("O pacote streamlit-folium nao esta instalado. Execute `pip install -r requirements.txt`.")
        return
    if planned_route is None:
        st.info("Nao foi possivel carregar a rota planejada do veiculo.")
        return
    coordinates = planned_route.get("coordinates", [])
    if len(coordinates) < 2:
        st.info("A rota planejada nao possui coordenadas suficientes.")
        return
    if any(len(point) < 2 for point in coordinates):
        st.info("A rota planejada retornou coordenadas incompletas.")
        return
    fmap = folium.Map(location=coordinates[0], zoom_start=9, tiles="CartoDB positron")
    folium.PolyLine(coordinates, color="#5f88c2", weight=5, opacity=0.9, tooltip="Rota planejada").add_to(fmap)
    origin_lat = planned_route.get("origin", {}).get("latitude")
    origin_lon = planned_route.get("origin", {}).get("longitude")
    destination_lat = planned_route.get("destination", {}).get("latitude")
    destination_lon = planned_route.get("destination", {}).get("longitude")
    if origin_lat is not None and origin_lon is not None:
        folium.Marker(
            [origin_lat, origin_lon],
            tooltip=f"Origem: {planned_route['origin_name']}",
            icon=folium.Icon(color="green", icon="play", prefix="fa"),
        ).add_to(fmap)
    if destination_lat is not None and destination_lon is not None:
        folium.Marker(
            [destination_lat, destination_lon],
            tooltip=f"Destino: {planned_route['destination_name']}",
            icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
        ).add_to(fmap)
    fmap.fit_bounds(coordinates, padding=(36, 36))
    st_folium(fmap, width=None, height=560, returned_objects=[], key=map_key)


def render_overview_tab(vehicle_df: pd.DataFrame, alert_df: pd.DataFrame, orders_df: pd.DataFrame, snapshot: dict[str, Any], map_mode: str) -> None:
    render_general_metrics(vehicle_df, alert_df, orders_df, snapshot)
    map_col, side_col = st.columns([2.1, 1.0])
    with map_col:
        st.subheader("Mapa da Frota")
        st.caption(map_mode)
        draw_fleet_map(vehicle_df, map_key=f"fleet-map-{map_mode.lower().replace(' ', '-')}")
    with side_col:
        st.subheader("Resumo Operacional")
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.write(f"Veiculos monitorados: **{len(vehicle_df)}**")
        st.write(f"Criticos: **{0 if vehicle_df.empty else int((vehicle_df['operational_status'] == 'CRITICO').sum())}**")
        st.write(f"Em atencao: **{0 if vehicle_df.empty else int((vehicle_df['operational_status'] == 'ATENCAO').sum())}**")
        st.write(f"Tempo medio de entrega: **{snapshot.get('average_delivery_hours', 0)} h**")
        st.write(f"Ocupacao media da frota: **{snapshot['kpis']['average_fleet_occupancy']}%**")
        st.markdown("</div>", unsafe_allow_html=True)
    left, right = st.columns([1.5, 1.2])
    with left:
        st.subheader("Alertas Recentes")
        st.dataframe(alert_df if not alert_df.empty else pd.DataFrame([{"status": "Sem alertas recentes"}]), use_container_width=True, hide_index=True)
    with right:
        st.subheader("Frota Operacional")
        display = vehicle_df[["code", "license_plate", "model", "route_label", "operational_status", "speed_kmh", "fuel_level", "cargo_occupancy", "timestamp"]] if not vehicle_df.empty else pd.DataFrame([{"status": "Sem dados da frota"}])
        st.dataframe(display, use_container_width=True, hide_index=True)


def build_timeline_dataframe(history_df: pd.DataFrame, alerts_df: pd.DataFrame, route_info: dict[str, Any] | None) -> pd.DataFrame:
    events: list[dict[str, Any]] = []
    if route_info:
        events.append({"timestamp": pd.NaT, "evento": "Rota definida", "categoria": "ROTA", "detalhe": f"{route_info['origin_name']} -> {route_info['destination_name']}"})
    if not history_df.empty:
        for _, row in history_df.tail(10).iterrows():
            events.append(
                {
                    "timestamp": row["timestamp"],
                    "evento": "Pacote de telemetria",
                    "categoria": "TELEMETRIA",
                    "detalhe": f"Vel {row['speed_kmh']:.1f} km/h | Comb {row['fuel_level']:.1f}% | {history_status(row)}",
                }
            )
    if not alerts_df.empty:
        for _, row in alerts_df.head(10).iterrows():
            events.append(
                {
                    "timestamp": row.get("created_at"),
                    "evento": f"Alerta {row.get('alert_type', 'OPERACIONAL')}",
                    "categoria": "ALERTA",
                    "detalhe": row.get("message", ""),
                }
            )
    timeline_df = pd.DataFrame(events)
    if timeline_df.empty:
        return timeline_df
    timeline_df["timestamp"] = pd.to_datetime(timeline_df["timestamp"], errors="coerce")
    timeline_df["horario"] = timeline_df["timestamp"].apply(format_timestamp)
    return timeline_df.sort_values("timestamp", ascending=False, na_position="last")


def render_vehicle_tab(vehicle_summary_df: pd.DataFrame, selected_vehicle_id: int | None, route_id: int | None) -> int | None:
    st.markdown("### Monitoramento por Veiculo")
    view_mode = st.session_state.get("vehicle_view_mode", "list")
    if view_mode != "detail" or selected_vehicle_id is None:
        st.session_state["vehicle_view_mode"] = "list"
        return render_vehicle_selector(vehicle_summary_df, route_id)

    if selected_vehicle_id is None:
        return None
    current_df = vehicle_summary_df[vehicle_summary_df["id"] == selected_vehicle_id]
    if current_df.empty:
        st.warning("O veiculo selecionado nao possui dados no recorte atual.")
        clear_selected_vehicle()
        return None
    vehicle_row = current_df.iloc[0]
    with st.spinner("Carregando detalhes do veiculo..."):
        overview = get_vehicle_detail(selected_vehicle_id)
    if overview is None:
        st.error("Nao foi possivel carregar os detalhes do veiculo.")
        return selected_vehicle_id
    planned_route = overview.get("planned_route")
    history_df = pd.DataFrame(overview.get("recent_telemetry", []))
    alerts_df = pd.DataFrame(overview.get("recent_alerts", []))
    if not history_df.empty:
        for column in ["latitude", "longitude", "speed_kmh", "fuel_level", "cargo_occupancy"]:
            if column in history_df.columns:
                history_df[column] = pd.to_numeric(history_df[column], errors="coerce")
        history_df["timestamp"] = pd.to_datetime(history_df["timestamp"], errors="coerce", utc=True)
    else:
        history_df = pd.DataFrame(columns=["timestamp", "latitude", "longitude", "speed_kmh", "fuel_level", "cargo_occupancy"])
    if not alerts_df.empty and "created_at" in alerts_df.columns:
        alerts_df["created_at"] = pd.to_datetime(alerts_df["created_at"], errors="coerce")
    elif alerts_df.empty:
        alerts_df = pd.DataFrame(columns=["created_at", "alert_type", "severity", "message"])
    route_info = None
    if planned_route:
        route_info = {
            "origin_name": planned_route["origin_name"],
            "destination_name": planned_route["destination_name"],
            "expected_duration_minutes": float(planned_route["duration_s"]) / 60,
            "estimated_distance_km": float(planned_route["distance_m"]) / 1000,
            "path_points": [{"latitude": point[0], "longitude": point[1]} for point in planned_route.get("coordinates", [])],
        }
    distance_traveled = calculate_distance_traveled(history_df)
    route_deviation = calculate_route_deviation(history_df, route_info)
    delay_minutes = calculate_delay_minutes(route_info, history_df)
    eta_value = estimate_eta(vehicle_row, route_info, history_df)
    last_update = format_timestamp(vehicle_row["timestamp"])
    route_efficiency = route_efficiency_score(distance_traveled, route_deviation, delay_minutes, route_info)
    timeline_df = build_timeline_dataframe(history_df, alerts_df, route_info)

    primary_cards = [
        ("Veiculo", f"{row_value(vehicle_row, 'code', 'SEM_CODIGO')} | {row_value(vehicle_row, 'model', 'Sem modelo')}"),
        ("Placa", str(row_value(vehicle_row, "license_plate", "SEM_PLACA"))),
        ("Rota Atual", str(row_value(vehicle_row, "route_label", "SEM_ROTA"))),
        ("Status Operacional", str(row_value(vehicle_row, "operational_status", "SEM_STATUS"))),
        ("Status do Veiculo", vehicle_online_status(row_value(vehicle_row, "timestamp"))),
        ("Velocidade Atual", metric_or_placeholder(row_value(vehicle_row, "speed_kmh"), " km/h")),
        ("Combustivel Atual", metric_or_placeholder(row_value(vehicle_row, "fuel_level"), "%")),
        ("Ocupacao da Carga", metric_or_placeholder(row_value(vehicle_row, "cargo_occupancy"), "%")),
        ("Ultima Atualizacao", last_update),
    ]
    secondary_cards = [
        ("Distancia Percorrida", f"{distance_traveled:.2f} km"),
        ("Desvio da Rota", f"{route_deviation:.2f} km"),
        ("ETA Estimado", eta_value),
        ("Atraso Previsto", f"{delay_minutes:.1f} min"),
    ]
    tertiary_cards = [
        ("Eficiência da Rota", f"{route_efficiency:.1f}%"),
        ("Alertas no Percurso", str(0 if alerts_df.empty else len(alerts_df))),
    ]

    cols = st.columns(4)
    for idx, (label, value) in enumerate(primary_cards):
        with cols[idx % 4]:
            st.metric(label=label, value=value)
    detail_cols = st.columns(4)
    for idx, (label, value) in enumerate(secondary_cards):
        with detail_cols[idx]:
            st.metric(label=label, value=value)
    extra_cols = st.columns(2)
    for idx, (label, value) in enumerate(tertiary_cards):
        with extra_cols[idx]:
            st.metric(label=label, value=value)

    action_left, action_right = st.columns([1, 2])
    with action_left:
        if st.button("Voltar para lista de veiculos", key=f"change-vehicle-{selected_vehicle_id}", use_container_width=True):
            clear_selected_vehicle()
            st.rerun()
    with action_right:
        st.caption("A selecao do veiculo permanece ativa ate voce escolher outro.")

    live_tracking_url = build_live_tracking_url(selected_vehicle_id)
    link_col, embed_col = st.columns([1, 2])
    with link_col:
        st.link_button("Abrir Rastreamento ao Vivo", live_tracking_url, use_container_width=True)
    with embed_col:
        embed_live_tracking = st.toggle("Exibir live tracking integrado", value=False, key=f"embed-live-{selected_vehicle_id}")
    if embed_live_tracking:
        components.iframe(live_tracking_url, height=660, scrolling=False)

    map_col, info_col = st.columns([2.0, 1.0])
    with map_col:
        st.subheader("Mapa da Rota Planejada")
        draw_vehicle_map(planned_route, map_key=f"vehicle-map-{selected_vehicle_id}")
    with info_col:
        st.subheader("Resumo da Operacao")
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.write(f"Codigo interno: **{row_value(vehicle_row, 'code', 'SEM_CODIGO')}**")
        st.write(f"Placa: **{row_value(vehicle_row, 'license_plate', 'SEM_PLACA')}**")
        st.write(f"Modelo: **{row_value(vehicle_row, 'model', 'Sem modelo')}**")
        st.write(f"Status ERP: **{row_value(vehicle_row, 'vehicle_status', 'SEM_STATUS')}**")
        st.write(f"Status operacional: **{row_value(vehicle_row, 'operational_status', 'SEM_STATUS')}**")
        if planned_route:
            st.write(f"Origem: **{planned_route['origin_name']}**")
            st.write(f"Destino: **{planned_route['destination_name']}**")
            st.write(f"Distancia planejada: **{float(planned_route['distance_m']) / 1000:.1f} km**")
            st.write(f"Tempo previsto: **{float(planned_route['duration_s']) / 60:.0f} min**")
        st.write(f"Alertas recentes: **{0 if alerts_df.empty else len(alerts_df)}**")
        st.markdown("</div>", unsafe_allow_html=True)
    if not history_df.empty:
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.subheader("Velocidade ao Longo do Tempo")
            st.line_chart(history_df.set_index("timestamp")[["speed_kmh"]].rename(columns={"speed_kmh": "Velocidade"}), color="#0b3f5c")
        with chart_right:
            st.subheader("Combustivel ao Longo do Tempo")
            st.line_chart(history_df.set_index("timestamp")[["fuel_level"]].rename(columns={"fuel_level": "Combustivel"}), color="#f77f00")
    lower_left, lower_right = st.columns([1.2, 1.8])
    with lower_left:
        st.subheader("Eventos de Alerta")
        alert_view = alerts_df.copy()
        if not alert_view.empty and "created_at" in alert_view.columns:
            alert_view = alert_view.sort_values("created_at", ascending=False)
        st.dataframe(alert_view if not alert_view.empty else pd.DataFrame([{"status": "Nenhum alerta encontrado"}]), use_container_width=True, hide_index=True)
    with lower_right:
        st.subheader("Timeline de Eventos")
        st.dataframe(
            timeline_df[["horario", "categoria", "evento", "detalhe"]] if not timeline_df.empty else pd.DataFrame([{"status": "Sem eventos"}]),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Historico de Telemetria")
    history_view = history_df.copy()
    if not history_view.empty:
        history_view["timestamp"] = history_view["timestamp"].apply(format_timestamp)
    st.dataframe(
        history_view[["timestamp", "latitude", "longitude", "speed_kmh", "fuel_level", "cargo_occupancy"]] if not history_view.empty else pd.DataFrame([{"status": "Sem historico"}]),
        use_container_width=True,
        hide_index=True,
    )
    return selected_vehicle_id


def render_alerts_tab(vehicle_df: pd.DataFrame, routes_df: pd.DataFrame) -> None:
    st.subheader("Centro de Alertas")
    filters = st.columns(4)
    vehicle_options = {"Todos": None}
    if not vehicle_df.empty:
        for _, row in vehicle_df.sort_values("code").iterrows():
            vehicle_options[f'{row["code"]} | {row["license_plate"]}'] = int(row["id"])
    route_options = {"Todas": None}
    if not routes_df.empty:
        for _, row in routes_df.sort_values("code").iterrows():
            route_options[f'{row["code"]} | {row["name"]}'] = int(row["id"])
    with filters[0]:
        vehicle_label = st.selectbox("Veiculo", list(vehicle_options.keys()), key="alert_vehicle_filter")
    with filters[1]:
        route_label = st.selectbox("Rota", list(route_options.keys()), key="alert_route_filter")
    with filters[2]:
        severity = st.selectbox("Severidade", ["Todas", "ALTA", "MEDIA", "BAIXA"], key="alert_severity_filter")
    with filters[3]:
        alert_type = st.selectbox("Tipo", ["Todos", "SAIDA_ROTA", "EXCESSO_VELOCIDADE", "COMBUSTIVEL_CRITICO", "ATRASO_PREVISTO"], key="alert_type_filter")
    params: dict[str, Any] = {}
    if vehicle_options[vehicle_label] is not None:
        params["vehicle_id"] = vehicle_options[vehicle_label]
    if route_options[route_label] is not None:
        params["route_id"] = route_options[route_label]
    if severity != "Todas":
        params["severity"] = severity
    if alert_type != "Todos":
        params["alert_type"] = alert_type
    payload, error = safe_fetch("/alerts", params=params)
    if error:
        st.error("Nao foi possivel carregar os alertas filtrados.")
        st.caption(error)
        return
    alert_df = pd.DataFrame(payload)
    st.dataframe(alert_df if not alert_df.empty else pd.DataFrame([{"status": "Nenhum alerta para os filtros"}]), use_container_width=True, hide_index=True)


def render_routes_tab(all_vehicle_df: pd.DataFrame, route_lookup: dict[int, dict[str, Any]], selected_vehicle_id: int | None) -> None:
    st.subheader("Rotas e Performance")
    if selected_vehicle_id is None:
        st.info("Selecione um veiculo na aba Veiculo Individual para comparar rota planejada x rota percorrida.")
        return
    current_df = all_vehicle_df[all_vehicle_df["id"] == selected_vehicle_id]
    if current_df.empty:
        st.warning("O veiculo selecionado nao possui dados para analise.")
        return
    vehicle_row = current_df.iloc[0]
    history_df = load_history(selected_vehicle_id)
    route_info = route_lookup.get(int(vehicle_row["route_id"])) if pd.notna(vehicle_row["route_id"]) else None
    if route_info is None:
        st.warning("Nao ha rota planejada vinculada ao veiculo selecionado.")
        return
    planned_points = [(point["latitude"], point["longitude"]) for point in route_info.get("path_points", [])]
    actual_points = history_df[["latitude", "longitude"]].dropna().apply(tuple, axis=1).tolist() if not history_df.empty else []
    actual_distance = 0.0
    for first, second in zip(actual_points, actual_points[1:]):
        actual_distance += geodesic(first, second).km
    deviations = [min(geodesic(point, planned).km for planned in planned_points) for point in actual_points] if planned_points and actual_points else []
    average_deviation = sum(deviations) / len(deviations) if deviations else 0.0
    real_minutes = 0.0 if history_df.empty else max((history_df["timestamp"].iloc[-1] - history_df["timestamp"].iloc[0]).total_seconds() / 60, 0.0)
    summary = [
        ("Distancia Planejada", f"{float(route_info['estimated_distance_km']):.1f} km"),
        ("Distancia Percorrida", f"{actual_distance:.1f} km"),
        ("Desvio Medio", f"{average_deviation:.2f} km"),
        ("Tempo Estimado x Real", f"{route_info['expected_duration_minutes']} min / {real_minutes:.1f} min"),
    ]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, summary):
        with col:
            st.metric(label=label, value=value)
    operation_status = "Dentro do esperado"
    if average_deviation > 1.2:
        operation_status = "Desvio relevante"
    elif actual_distance > float(route_info["estimated_distance_km"]) * 1.15:
        operation_status = "Percurso acima do planejado"
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.write(f"Status da operacao: **{operation_status}**")
    st.write(f"Origem: **{route_info['origin_name']}**")
    st.write(f"Destino: **{route_info['destination_name']}**")
    st.write(f"Veiculo analisado: **{vehicle_row['code']} | {vehicle_row['model']}**")
    st.markdown("</div>", unsafe_allow_html=True)
    performance_df = pd.DataFrame({"Indicador": ["Distancia Planejada", "Distancia Percorrida", "Tempo Estimado", "Tempo Real"], "Valor": [float(route_info["estimated_distance_km"]), actual_distance, float(route_info["expected_duration_minutes"]), real_minutes]}).set_index("Indicador")
    st.bar_chart(performance_df, color="#1f6f8b")


def render_billing_tab(invoice_df: pd.DataFrame) -> None:
    st.subheader("Faturamento e Notas Fiscais")
    if invoice_df.empty:
        st.info("Nenhuma nota fiscal emitida ate o momento.")
        return

    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("Notas Emitidas", len(invoice_df))
    with metric_cols[1]:
        st.metric("Valor Faturado", f"R$ {invoice_df['total_value'].sum():,.2f}")
    with metric_cols[2]:
        st.metric("Tickets Medios", f"R$ {invoice_df['total_value'].mean():,.2f}")
    with metric_cols[3]:
        st.metric("Pedidos Faturados", invoice_df["order_id"].nunique())

    table_columns = [
        "invoice_number",
        "order_id",
        "customer_name",
        "product_description",
        "total_value",
        "issue_date",
        "status",
    ]
    available_columns = [column for column in table_columns if column in invoice_df.columns]
    st.dataframe(
        invoice_df[available_columns].rename(
            columns={
                "invoice_number": "Nota",
                "order_id": "Pedido",
                "customer_name": "Cliente",
                "product_description": "Produtos",
                "total_value": "Valor Total",
                "issue_date": "Emissao",
                "status": "Status",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    options = {
        f"{row['invoice_number']} | Pedido {row['order_id']} | {row['customer_name']}": int(row["id"])
        for _, row in invoice_df.sort_values("issue_date", ascending=False).iterrows()
    }
    selected_label = st.selectbox("Selecionar nota fiscal", list(options.keys()), key="invoice-selector")
    selected_invoice = invoice_df[invoice_df["id"] == options[selected_label]].iloc[0]

    detail_left, detail_right = st.columns([1.2, 1.8])
    with detail_left:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.write(f"Numero da nota: **{selected_invoice['invoice_number']}**")
        st.write(f"Pedido vinculado: **{selected_invoice['order_id']}**")
        st.write(f"Cliente: **{selected_invoice['customer_name']}**")
        st.write(f"Documento: **{selected_invoice['customer_document']}**")
        st.write(f"Produtos: **{selected_invoice['product_description']}**")
        st.write(f"Quantidade total: **{int(selected_invoice['quantity'])}**")
        st.write(f"Valor unitario medio: **R$ {float(selected_invoice['unit_price']):.2f}**")
        st.write(f"Valor total: **R$ {float(selected_invoice['total_value']):.2f}**")
        st.write(f"Data de emissao: **{format_timestamp(selected_invoice['issue_date'])}**")
        st.write(f"Status: **{selected_invoice['status']}**")
        st.markdown("</div>", unsafe_allow_html=True)
    with detail_right:
        pdf_url = selected_invoice.get("pdf_download_url")
        xml_url = selected_invoice.get("xml_download_url")
        action_cols = st.columns(2)
        with action_cols[0]:
            if pd.notna(pdf_url):
                st.link_button("Baixar PDF", f"{BACKEND_BASE_URL}{pdf_url}", use_container_width=True)
        with action_cols[1]:
            if pd.notna(xml_url):
                st.link_button("Baixar XML", f"{BACKEND_BASE_URL}{xml_url}", use_container_width=True)
        st.caption("As notas sao geradas automaticamente quando um pedido entra em EM_ROTA.")


def main() -> None:
    inject_styles()
    bundle, error = load_bundle()
    if error or bundle is None:
        render_header(api_online=False, generated_at=None)
        st.error("A API do LogiCore ERP nao respondeu. Verifique o backend FastAPI.")
        st.caption(error or "Falha de conexao nao identificada.")
        st.stop()
    snapshot = bundle["snapshot"]
    routes = bundle["routes"]
    all_vehicle_df = build_vehicle_df(snapshot)
    vehicle_summary_df = build_vehicle_summary_df(bundle["vehicle_summary"])
    routes_df = build_routes_df(routes)
    selected_route_id, refresh_seconds, auto_refresh, map_mode = render_sidebar(routes_df)
    vehicle_view_mode = st.session_state.get("vehicle_view_mode", "list")
    if auto_refresh and vehicle_view_mode != "detail":
        st_autorefresh(interval=refresh_seconds * 1000, key="logicore-autorefresh")
    filtered_vehicle_df = filter_vehicles(all_vehicle_df, None, selected_route_id)
    overview_vehicle_df = all_vehicle_df if map_mode == "Visao Frota" else filtered_vehicle_df
    alert_df = build_alert_df(snapshot)
    alert_df = filter_alert_dataframe(alert_df, vehicle_id=None, route_id=selected_route_id)
    orders_df = build_orders_df(bundle["orders"])
    invoice_df = build_invoice_df(bundle["invoices"])
    selected_vehicle_id = get_selected_vehicle_id(vehicle_summary_df, selected_route_id)
    render_header(api_online=True, generated_at=snapshot.get("generated_at"))
    tabs = st.tabs(["Visao Geral", "Veiculo Individual", "Alertas", "Rotas e Performance", "Faturamento"])
    with tabs[0]:
        render_overview_tab(overview_vehicle_df, alert_df, orders_df, snapshot, map_mode)
    with tabs[1]:
        selected_vehicle_id = render_vehicle_tab(vehicle_summary_df, selected_vehicle_id, selected_route_id)
    with tabs[2]:
        render_alerts_tab(all_vehicle_df, routes_df)
    with tabs[3]:
        render_routes_tab(all_vehicle_df, route_map(routes), selected_vehicle_id)
    with tabs[4]:
        render_billing_tab(invoice_df)
    st.caption("Painel compatível com `streamlit run dashboard/app.py` em Windows e ambientes locais profissionais.")
    if st.button("Atualizar agora"):
        st.rerun()


if __name__ == "__main__":
    main()
