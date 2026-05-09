from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import pandas as pd

from models.domain import (
    DeliveryStop,
    ProductCategory,
    ProductDimensions,
    ProductLine,
    ProductUnit,
    TimeWindow,
    TruckType,
)
from models.schemas import CustomerDetail, RouteSummary, TransportDetail, TransportSummary


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = ROOT_DIR / "data" / "raw"
DEFAULT_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
RAW_FILES = {
    "hackaton": "Hackaton.xlsx",
    "horarios": "Horarios Entrega.XLSX",
    "zm040": "ZM040.XLSX",
}


@dataclass(frozen=True)
class DataSnapshot:
    transports: dict[str, TransportDetail]
    customers: dict[str, CustomerDetail]
    routes: dict[str, RouteSummary]
    material_location_count: int
    delivery_count: int


class DataRepository:
    def __init__(
        self,
        raw_dir: Path = DEFAULT_RAW_DIR,
        processed_dir: Path = DEFAULT_PROCESSED_DIR,
    ) -> None:
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self._snapshot: DataSnapshot | None = None

    def load(self, force_refresh: bool = False) -> DataSnapshot:
        if self._snapshot is not None and not force_refresh:
            return self._snapshot

        if not force_refresh:
            cached = self._load_processed()
            if cached is not None:
                self._snapshot = cached
                return cached

        snapshot = self._parse_raw()
        self._write_processed(snapshot)
        self._snapshot = snapshot
        return snapshot

    def health(self) -> dict[str, int | bool]:
        snapshot = self.load()
        geocoded_count = sum(
            1
            for customer in snapshot.customers.values()
            if customer.lat is not None and customer.lng is not None
        )
        return {
            "data_loaded": True,
            "customer_count": len(snapshot.customers),
            "transport_count": len(snapshot.transports),
            "geocoded_count": geocoded_count,
        }

    def list_transports(self) -> list[TransportSummary]:
        snapshot = self.load()
        return sorted(
            (
                TransportSummary(
                    transport_id=transport.transport_id,
                    route_code=transport.route_code,
                    driver_name=transport.driver_name,
                    date=transport.date,
                    stop_count=len(transport.stops),
                    truck_type=transport.truck_type,
                )
                for transport in snapshot.transports.values()
            ),
            key=lambda item: (item.date, item.route_code, item.transport_id),
        )

    def list_routes(self) -> list[RouteSummary]:
        snapshot = self.load()
        return sorted(snapshot.routes.values(), key=lambda item: item.route_code)

    def get_transport(self, transport_id: str) -> TransportDetail | None:
        return self.load().transports.get(str(transport_id))

    def get_customer(self, customer_id: str) -> CustomerDetail | None:
        return self.load().customers.get(_clean_id(customer_id))

    def _load_processed(self) -> DataSnapshot | None:
        manifest_path = self.processed_dir / "manifest.json"
        transports_path = self.processed_dir / "transports.json"
        customers_path = self.processed_dir / "customers.json"
        routes_path = self.processed_dir / "routes.json"

        if not all(path.exists() for path in [manifest_path, transports_path, customers_path, routes_path]):
            return None

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("raw_files") != self._raw_manifest():
                return None
            transports_payload = json.loads(transports_path.read_text(encoding="utf-8"))
            customers_payload = json.loads(customers_path.read_text(encoding="utf-8"))
            routes_payload = json.loads(routes_path.read_text(encoding="utf-8"))
            return DataSnapshot(
                transports={
                    row["transport_id"]: TransportDetail.model_validate(row)
                    for row in transports_payload
                },
                customers={
                    row["customer_id"]: CustomerDetail.model_validate(row)
                    for row in customers_payload
                },
                routes={row["route_code"]: RouteSummary.model_validate(row) for row in routes_payload},
                material_location_count=int(manifest["counts"]["material_locations"]),
                delivery_count=int(manifest["counts"]["deliveries"]),
            )
        except (KeyError, json.JSONDecodeError, ValueError):
            return None

    def _write_processed(self, snapshot: DataSnapshot) -> None:
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "raw_files": self._raw_manifest(),
            "counts": {
                "transports": len(snapshot.transports),
                "deliveries": snapshot.delivery_count,
                "customers": len(snapshot.customers),
                "routes": len(snapshot.routes),
                "material_locations": snapshot.material_location_count,
            },
        }
        (self.processed_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (self.processed_dir / "transports.json").write_text(
            _dump_models(snapshot.transports.values()),
            encoding="utf-8",
        )
        (self.processed_dir / "customers.json").write_text(
            _dump_models(snapshot.customers.values()),
            encoding="utf-8",
        )
        (self.processed_dir / "routes.json").write_text(
            _dump_models(snapshot.routes.values()),
            encoding="utf-8",
        )

    def _raw_manifest(self) -> dict[str, dict[str, float | int | str]]:
        manifest: dict[str, dict[str, float | int | str]] = {}
        for key, filename in RAW_FILES.items():
            path = self.raw_dir / filename
            stat = path.stat()
            manifest[key] = {
                "path": str(path.relative_to(ROOT_DIR)),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
        return manifest

    def _parse_raw(self) -> DataSnapshot:
        hackaton_path = self.raw_dir / RAW_FILES["hackaton"]
        horarios_path = self.raw_dir / RAW_FILES["horarios"]
        zm040_path = self.raw_dir / RAW_FILES["zm040"]

        delivery_df = pd.read_excel(hackaton_path, sheet_name="Detalle entrega")
        address_df = pd.read_excel(hackaton_path, sheet_name="Direcciones")
        location_df = pd.read_excel(hackaton_path, sheet_name="Materiales zubic")
        schedule_df = pd.read_excel(horarios_path)
        dimensions_df = pd.read_excel(zm040_path)

        addresses = _build_addresses(address_df)
        material_locations = _build_material_locations(location_df)
        dimensions = _build_dimensions(dimensions_df)
        schedules = _build_schedules(schedule_df)

        delivery_df = delivery_df.copy()
        delivery_df["_source_order"] = range(len(delivery_df))
        delivery_df["_date"] = pd.to_datetime(delivery_df["FECHA"], dayfirst=True, errors="coerce")
        if delivery_df["_date"].isna().any():
            bad_dates = int(delivery_df["_date"].isna().sum())
            raise ValueError(f"Detalle entrega contains {bad_dates} unparseable FECHA values")

        customers: dict[str, CustomerDetail] = {}
        transports: dict[str, TransportDetail] = {}
        route_accumulator: dict[str, dict[str, set[str] | int]] = {}

        for transport_id, transport_rows in delivery_df.groupby("Transporte", sort=False):
            rows = transport_rows.sort_values("_source_order")
            first = rows.iloc[0]
            transport_key = _clean_id(transport_id)
            route_code = _clean_text(first["Ruta"])
            driver_id = _clean_id(first["Repartidor"])
            driver_name = _clean_text(first["Destinatario mcía."])
            transport_date = first["_date"].date()

            stops: list[DeliveryStop] = []
            for sequence, (delivery_id, stop_rows) in enumerate(rows.groupby("Entrega", sort=False), start=1):
                stop_first = stop_rows.iloc[0]
                customer_id = _clean_id(stop_first["Destinatario mcía..1"])
                address = addresses.get(customer_id) or _address_from_delivery(stop_first)
                weekday = int(stop_first["_date"].dayofweek) + 1
                shift = 1
                time_window = schedules.get((customer_id, weekday, shift))
                customer = customers.get(customer_id)
                if customer is None:
                    customer = CustomerDetail(
                        customer_id=customer_id,
                        name=address["name"],
                        address=address["address"],
                        city=address["city"],
                        postal_code=address["postal_code"],
                        lat=None,
                        lng=None,
                        time_windows={},
                    )
                    customers[customer_id] = customer
                if time_window is not None and weekday not in customer.time_windows:
                    customer.time_windows[weekday] = time_window

                products = [
                    _product_from_row(row, material_locations, dimensions)
                    for _, row in stop_rows.iterrows()
                ]
                stops.append(
                    DeliveryStop(
                        stop_id=_clean_id(delivery_id),
                        sequence=sequence,
                        customer_id=customer_id,
                        customer_name=address["name"],
                        address=address["address"],
                        postal_code=address["postal_code"],
                        city=address["city"],
                        lat=None,
                        lng=None,
                        time_window=time_window,
                        shift=shift,
                        products=products,
                        returnables=[],
                        albaran_numbers=[_clean_id(delivery_id)],
                    )
                )

            transports[transport_key] = TransportDetail(
                transport_id=transport_key,
                route_code=route_code,
                driver_id=driver_id,
                driver_name=driver_name,
                date=transport_date,
                truck_type=TruckType.TRUCK_6,
                stops=stops,
            )
            route_stats = route_accumulator.setdefault(
                route_code,
                {"transports": set(), "stop_count": 0},
            )
            route_stats["transports"].add(transport_key)  # type: ignore[union-attr]
            route_stats["stop_count"] += len(stops)  # type: ignore[operator]

        routes = {
            route_code: RouteSummary(
                route_code=route_code,
                transport_count=len(stats["transports"]),  # type: ignore[arg-type]
                stop_count=int(stats["stop_count"]),
            )
            for route_code, stats in route_accumulator.items()
        }
        return DataSnapshot(
            transports=transports,
            customers=customers,
            routes=routes,
            material_location_count=len(material_locations),
            delivery_count=delivery_df["Entrega"].nunique(),
        )


repository = DataRepository()


def _dump_models(models: Any) -> str:
    payload = [model.model_dump(mode="json") for model in models]
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _clean_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _to_int(value: Any, default: int = 0) -> int:
    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_addresses(df: pd.DataFrame) -> dict[str, dict[str, str]]:
    addresses: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        customer_id = _clean_id(row["Cliente"])
        addresses[customer_id] = {
            "name": _clean_text(row["Nombre 1"] or row["Nombre 2"]),
            "address": _clean_text(row["Calle"]),
            "postal_code": _clean_id(row["CP"]),
            "city": _clean_text(row["Población"]),
        }
    return addresses


def _address_from_delivery(row: pd.Series) -> dict[str, str]:
    return {
        "name": _clean_text(row["Nombre 1"] or row["Nombre 2"]),
        "address": _clean_text(row["Calle"]),
        "postal_code": _clean_id(row["CP"]),
        "city": _clean_text(row["Población"]),
    }


def _build_material_locations(df: pd.DataFrame) -> dict[str, str]:
    locations: dict[str, str] = {}
    for _, row in df.iterrows():
        material = _clean_text(row["Material"])
        location = _clean_text(row["Ubic."])
        if material and location:
            locations[material] = location
    return locations


def _build_dimensions(df: pd.DataFrame) -> dict[tuple[str, str], ProductDimensions]:
    dimensions: dict[tuple[str, str], ProductDimensions] = {}
    for _, row in df.iterrows():
        material = _clean_text(row["Material"])
        unit = _clean_text(row["UMA"])
        if not material or not unit:
            continue
        length = _convert_length(_to_float(row["Longitud"]), _clean_text(row["Unidad dimensión"]))
        width = _convert_length(_to_float(row["Ancho"]), _clean_text(row["Unidad dimensión.1"]))
        height = _convert_length(_to_float(row["Altura"]), _clean_text(row["Unidad dimensión.2"]))
        weight_gross = _convert_weight(_to_float(row["Peso bruto"]), _clean_text(row["Un"]))
        weight_net = _convert_weight(_to_float(row["Peso neto"]), _clean_text(row["Un.2"]))
        volume = _to_float(row["Volumen"])
        if not any([length, width, height, weight_gross, weight_net, volume]):
            continue
        base = ProductDimensions()
        dimensions[(material, unit)] = ProductDimensions(
            length_cm=length or base.length_cm,
            width_cm=width or base.width_cm,
            height_cm=height or base.height_cm,
            volume_l=volume if volume and volume > 0 else None,
            weight_gross_kg=weight_gross or base.weight_gross_kg,
            weight_net_kg=weight_net,
        )
    return dimensions


def _build_schedules(df: pd.DataFrame) -> dict[tuple[str, int, int], TimeWindow]:
    schedules: dict[tuple[str, int, int], TimeWindow] = {}
    for _, row in df.iterrows():
        customer_id = _clean_id(row["Deudor"])
        weekday = _to_int(row["Día semana"])
        shift = _to_int(row["Turno"], default=1)
        start = _parse_time(row["Horario inicia a"])
        end = _parse_time(row["Horario termina a"])
        if not customer_id or weekday == 0 or start is None or end is None or start == end:
            continue
        schedules[(customer_id, weekday, shift)] = TimeWindow(open=start, close=end)
    return schedules


def _parse_time(value: Any) -> time | None:
    if isinstance(value, time):
        return value.replace(microsecond=0)
    if pd.isna(value):
        return None
    parsed = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.time().replace(microsecond=0)


def _convert_length(value: float | None, unit: str) -> float | None:
    if value is None or value <= 0:
        return None
    unit = unit.upper()
    if unit == "MM":
        return value / 10
    if unit == "M":
        return value * 100
    return value


def _convert_weight(value: float | None, unit: str) -> float | None:
    if value is None or value <= 0:
        return None
    unit = unit.upper()
    if unit in {"G", "GR"}:
        return value / 1000
    return value


def _product_from_row(
    row: pd.Series,
    material_locations: dict[str, str],
    dimensions: dict[tuple[str, str], ProductDimensions],
) -> ProductLine:
    material = _clean_text(row["Material"])
    description = _clean_text(row["Denominación"])
    unit = ProductUnit(_clean_text(row["Un.medida venta"]))
    product_dimensions = (
        dimensions.get((material, unit.value))
        or dimensions.get((material, ProductUnit.CAJ.value))
        or dimensions.get((material, ProductUnit.UN.value))
        or ProductDimensions()
    )
    return ProductLine(
        material_code=material,
        description=description,
        quantity=_to_int(row["Cantidad entrega"]),
        unit=unit,
        category=_categorize_product(material, description, unit),
        is_returnable=_is_returnable(material, description),
        warehouse_location=material_locations.get(material),
        dimensions=product_dimensions,
    )


def _is_returnable(material: str, description: str) -> bool:
    upper = f"{material} {description}".upper()
    return bool(
        material.upper().startswith("CJ")
        or re.search(r"\bRET\b|RET\.|RETORN|VACIO|ENVASE|CAJA\+BOT|CAJA DAMM", upper)
    )


def _categorize_product(material: str, description: str, unit: ProductUnit) -> ProductCategory:
    upper = f"{material} {description}".upper()
    if material.upper().startswith("CJ") or "VACIO" in upper:
        return ProductCategory.RETURNABLE_EMPTY
    if unit in {ProductUnit.BRL, ProductUnit.TUB} or "BARRIL" in upper:
        return ProductCategory.BEER_BARREL
    if any(token in upper for token in ["AGUA", "FONT D", "VICHY", "VERI", "PIRINEA"]):
        return ProductCategory.WATER
    if any(token in upper for token in ["SCHWEPPES", "KAS", "COLA", "FANTA", "SPRITE", "TONICA", "BITTER"]):
        return ProductCategory.SOFT_DRINK
    if any(token in upper for token in ["LECHE", "CACAOLAT", "YOGUR"]):
        return ProductCategory.DAIRY
    if any(token in upper for token in ["CAFE", "CAFÉ", "BONKA"]):
        return ProductCategory.COFFEE
    if any(token in upper for token in ["VINO", "CAVA", "WHISKY", "LICOR", "RON", "GINEBRA"]):
        return ProductCategory.WINE_SPIRITS
    if "GAS" in upper and "GASEOSA" not in upper:
        return ProductCategory.GAS
    if any(token in upper for token in ["DAMM", "ESTRELLA", "VOLL", "FREE", "TURIA", "XIBECA", "BOCK"]):
        return ProductCategory.BEER_BOTTLE
    if any(token in upper for token in ["VASO", "PLATO", "SERVILLETA", "GUANTE", "BOLSA"]):
        return ProductCategory.DISPOSABLE
    return ProductCategory.FOOD
