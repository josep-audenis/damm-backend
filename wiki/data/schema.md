# Data Schema & Field Glossary

## Source Files

All data is provided by Damm/DDI. Files are in `data/raw/`.

---

## Hackaton.xlsx — Sheet: "Detalle entrega" (82,849 rows)

Main delivery lines table. Each row = one product line delivered to one customer on one transport.

| Column | Type | Example | Meaning |
|--------|------|---------|---------|
| `FECHA` | date | 30/01/2026 | Delivery date |
| `Transporte` | int | 11420379 | Transport ID — unique per truck per day |
| `Ruta` | str | DR0006 | Route code (see ZONAS sheet) |
| `Repartidor` | int | 850006 | Driver ID (numerical) |
| `Destinatario mcía.` | int | 91123456 | Customer ID (numeric) |
| `Entrega` | int | 90123456 | Delivery number (unique per stop within transport) |
| `Material` | str | ED13 | SKU code |
| `Denominación` | str | ESTRELLA DAMM 1/3 RET | Product name |
| `Cantidad entrega` | float | 2.0 | Quantity delivered (in sales unit) |
| `Un.medida venta` | str | PAL / CAJ / UN | Sales unit: PAL=pallet, CAJ=case/box, UN=unit |
| `Nombre 1` | str | Bar Granada | Customer name (line 1) |
| `Nombre 2` | str | (empty) | Customer name (line 2, often empty) |
| `Calle` | str | C/ Berguedà 14 | Street address |
| `CP` | str | 08100 | Postal code |
| `Población` | str | Mollet del Vallès | City/town |
| `ZonaTransp` | str | DD13100002 | Zone code (fine-grained geographic zone) |
| `ZonaTransp.1` | str | MOLLET PLANA LLADO | Zone name |

**Key product codes:**
| Code | Description | Returnable? |
|------|-------------|-------------|
| `ED13` | Estrella Damm 1/3 RET (33cl bottle) | Yes |
| `ED15LN` | Estrella Damm 1/5 LN (50cl longneck) | Yes |
| `VO13` | Voll-Damm 1/3 | Yes |
| `FD13` | Free Damm 1/3 (non-alcoholic) | Yes |
| `DL13` | Damm Lemon 1/3 | Yes |
| `ED30` | Estrella Damm 30L barrel | Yes |
| `BRL30V` | Inox barrel 30L | Yes |
| `CJ13` | Empty crate (returnable pickup) | — (this IS the returnable) |
| `0AG0007` | Font d'Or Natural 1.5L | No |
| `0AG0183` | Vichy Catalan Gas 30cl | No |
| `0LT0033` | Letona Gran Creme PET 1.5L | No |
| `0CF0080` | Xplicit Natural Cremoso 1kg | No |
| `0RF0088` | Schweppes Tónica Lata Sleek 24u | No |
| `0RF0091` | Schweppes Limón Lata Sleek 24u | No |

**Returnable detection rule**: Material codes starting with `ED`, `VO`, `FD`, `DL`, `CJ` or containing `RET` in description are returnable.

---

## Hackaton.xlsx — Sheet: "Cabecera Transporte" (8,927 rows)

One row per delivery (one stop, not one transport). Links transport → driver → customer.

| Column | Type | Example | Meaning |
|--------|------|---------|---------|
| `Entrega` | int | 90123456 | Delivery number (links to Detalle entrega) |
| `Nº Transporte` | int | 11420379 | Transport ID |
| `Creado el` | date | 30/01/2026 | Creation date |
| `Repartidor` | int | 850006 | Driver ID |
| *(driver name col)* | str | JOSE VELEZ CASTRO | Driver full name |
| `Destinatario mcía.` | int | 91123456 | Customer ID |
| `Destinatario mcía..1` | str | BAR GRANADA | Customer name |

**Usage**: Join `Cabecera Transporte` on `Entrega` to get all stops for a transport in order.

---

## Hackaton.xlsx — Sheet: "Direcciones" (1,368 rows)

Customer master data — addresses.

| Column | Type | Example | Meaning |
|--------|------|---------|---------|
| `Cliente` | int | 91123456 | Customer ID (same as Destinatario mcía.) |
| `Nombre 1` | str | BAR GRANADA | Customer name |
| `Nombre 2` | str | (empty) | Name line 2 |
| `Calle` | str | C/ Berguedà 14 | Street address |
| `CP` | str | 08100 | Postal code |
| `Población` | str | Mollet del Vallès | City |

**Geocoding**: Combine `Calle + CP + Población + España` for geocoding query. Cache to `data/processed/geocache.json`.

---

## Hackaton.xlsx — Sheet: "ZONAS" (1,203 rows)

Maps geographic zones to routes and drivers.

| Column | Type | Example | Meaning |
|--------|------|---------|---------|
| `ZONAS` | str | DD13100002 | Zone code (matches ZonaTransp in Detalle entrega) |
| `NOMBRE ZONAS` | str | MOLLET PLANA LLADO | Zone name |
| `cliente zona` | int | 91123456 | A representative customer in the zone |
| `ZonaTransp` | str | DD13100002 | Same zone code |
| `ZonaTransp.1` | str | MOLLET PLANA LLADO | Zone name |
| `Zona Entrega` | str | DD13100002 | Delivery zone |
| `RutReal` | str | DR0006 | Route code |
| `Denominación` | str | RP235 MOLLET MIGUEL... | Route + driver name string |

**Key routes in Mollet area:**
| Route | Zone | Description |
|-------|------|-------------|
| `DR0001` | DD13100001, DD13100004 | MOLLET CAN BORRELL / RAMBLA NOVA (driver: JORDI PUIGDELLIRE) |
| `DR0006` | DD13100002, DD13100003 | MOLLET PLANA LLADO / BARRI OLIVA (driver: JOSE VELEZ) |
| `DR0010` | — | Santa Eulàlia de Ronçana, Lliçà d'Amunt area |
| `DR0023` | — | Parets del Vallès, Mollet |
| `DR0040` | — | Granollers, Lliçà de Vall |
| `DR0051` | — | Vic area |
| `DR0054` | — | Manlleu, Tona area |

---

## Hackaton.xlsx — Sheet: "Materiales zubic" (1,489 rows)

Maps each product to its physical warehouse location.

| Column | Type | Example | Meaning |
|--------|------|---------|---------|
| `Material` | str | 0RF0088 | SKU code |
| `Número de material` | str | (same) | Alternative material number |
| `Ce.` | str | D131 | Storage center code (always D131 for DDI Mollet) |
| `Alm.` | str | Alm.1 / Alm.5 | Warehouse section (Alm.1 = main, Alm.5 = secondary) |
| `UMB` | str | CAJ / PAL / UN | Base unit of measure |
| `Fabricante` | str | SCHWEPPES S.A. | Manufacturer |
| `Número de un fabricante` | str | — | Manufacturer product number |
| `Ubic.` | str | FA05A2 | **Warehouse location code** |

**Location code format**: `FA05A2`
- `F` = Aisle letter (A–Z)
- `A` = Sub-aisle (A/B)
- `05` = Bay number (01–99)
- `A` = Column (A/B)
- `2` = Level (1=floor, 2=height 2, 3=height 3, 4=height 4, 9=top)

Special code `ZCG` = external/temporary storage area.

---

## Horarios Entrega.XLSX — Sheet: "Sheet1" (1,015 rows)

Customer delivery time windows. Each row = one customer on one weekday.

| Column | Type | Example | Meaning |
|--------|------|---------|---------|
| `Deudor` | int | 91123456 | Customer ID |
| `Día semana` | int | 1–5 | 1=Monday, 2=Tuesday, ..., 5=Friday |
| `Turno` | int | 1 or 2 | 1=morning shift, 2=afternoon shift |
| `Nombre 1` | str | BAR GRANADA | Customer name |
| `Horario inicia a` | time | 08:00:00 | Delivery window opens |
| `Horario termina a` | time | 11:00:00 | Delivery window closes |
| `Cierre Si/No` | str | X or empty | X = closed that day, don't deliver |

**Loading time windows into model:**
```python
def get_time_window(customer_id: int, weekday: int) -> TimeWindow | None:
    """weekday: 0=Mon, 1=Tue, ..., 4=Fri (Python convention)"""
    row = time_windows_df[
        (time_windows_df["Deudor"] == customer_id) & 
        (time_windows_df["Día semana"] == weekday + 1)  # Excel uses 1-based
    ]
    if row.empty or row.iloc[0]["Cierre Si/No"] == "X":
        return None  # closed or no window defined → flexible
    return TimeWindow(
        open=row.iloc[0]["Horario inicia a"],
        close=row.iloc[0]["Horario termina a"]
    )
```

**Important edge cases:**
- PIZZA VALLES: 09:00–09:15 (15-minute window!) — must be first stop in morning
- CF. MOLLET: 06:45–07:15 (very early, 30-minute window) — must start route before 7am
- BAR LA SALA: 06:30–08:30 — early morning
- PENYA BARCELONISTA: 17:00–21:00 (afternoon only — turno=2)
- GRANJA GROC: two windows same day (08:00–10:00 AND 13:00–15:00) — model as two separate rows

---

## Layout Mollet.xlsx

### Sheet: "DDI MOLLET" (182 rows × 62 cols)

Physical warehouse grid. Each cell = a pallet position. Values represent stacking heights allowed:
- `3` = max 3 pallets high
- `4` = max 4 pallets high  
- `9` = max 9 pallets high
- Empty = aisle/corridor (no storage)

Use this grid to:
1. Visualize the warehouse layout for the pitch
2. Determine travel distances within the warehouse for pick path optimization
3. Identify if warehouse reorganization could improve pick efficiency

### Sheet: "RESUMEN DDI MOLLET"

| Type | Ground | H2 | H3 | H4 | H9 | Total |
|------|--------|----|----|----|----|-------|
| Shelving (Estanteria) | 342 | — | 348 | 504 | — | 1,194 |
| Compact shelving | 10 | — | — | 230 | — | 240 |
| Floor (SUELO) | 151 | — | 246 | — | 224 | 621 |
| Exterior | 105 | — | 200 | — | — | 305 |
| **TOTAL** | **608** | — | **794** | **734** | **224** | **2,360** |

Interior capacity: 2,055 pallet positions. Exterior: 305.

---

## ZM040.XLSX (48,457 rows)

Product dimensions and weights. Multiple rows per product (one row per packaging unit type).

| Column | Type | Example | Meaning |
|--------|------|---------|---------|
| `Material` | str | 0CF0054 | SKU code |
| `TpMt` | str | ZFIN | Material type (ZFIN = finished goods) |
| `UMA` | str | CAJ/PAL/UN/BOT | Packaging unit |
| `Contador` | int | 60 | Units per packaging |
| `Denom.` | str | — | Description |
| `Longitud` | float | 100 | Length in `Unidad dimensión` units |
| `Unidad dimensión` | str | CM | Dimension unit |
| `Ancho` | float | 120 | Width (cm) |
| `Altura` | float | 169 | Height (cm) |
| `Volumen` | float | 475.2 | Volume in litres |
| `Peso bruto` | float | 1020 | Gross weight in KG |
| `Peso neto` | float | — | Net weight in KG |
| `Jquía.productos` | str | 00CF30ZZPCA1E4 | Product hierarchy code |

**Querying dimensions for bin packing:**
```python
def get_case_dimensions(material_code: str) -> tuple[float, float, float]:
    """Returns (length_cm, width_cm, height_cm) for one CAJ (case)."""
    row = dims_df[
        (dims_df["Material"] == material_code) & 
        (dims_df["UMA"] == "CAJ")
    ]
    if row.empty:
        return (40.0, 30.0, 25.0)  # default box dimensions if unknown
    r = row.iloc[0]
    return (r["Longitud"], r["Ancho"], r["Altura"])

def get_case_weight(material_code: str) -> float:
    """Returns gross weight (kg) for one CAJ."""
    row = dims_df[
        (dims_df["Material"] == material_code) & 
        (dims_df["UMA"] == "CAJ")
    ]
    if row.empty:
        return 15.0  # default
    return row.iloc[0]["Peso bruto"]
```

**Product hierarchy codes** (`Jquía.productos`): encode product family. First 4 chars after `00` identify product category:
- `CF` = food/coffee products
- `AG` = water (agua)
- `LT` = dairy/beverages (leche/letona)
- `RF` = soft drinks (refrescos)
- Beers don't appear in ZM040 directly under those codes — look up by material code.

---

## Key Data Relationships

```
Detalle entrega
    ├── Transporte ──────────── Cabecera Transporte (Nº Transporte)
    ├── Destinatario mcía. ──── Direcciones (Cliente)
    ├── Material ────────────── Materiales zubic (Material) → Ubic.
    │                           ZM040 (Material) → dimensions
    ├── ZonaTransp ──────────── ZONAS (ZONAS) → RutReal → Route
    └── (customer + weekday) ── Horarios Entrega (Deudor + Día semana)
```

---

## Sample Query: Build a Full Transport

```python
def build_transport(transport_id: int, date: str) -> list[Stop]:
    """Build the full list of stops for a transport with all product data."""
    # 1. Get all delivery lines for this transport
    lines = detalle[detalle["Transporte"] == transport_id].copy()
    
    # 2. Group by customer (Destinatario mcía.)
    stops = []
    for customer_id, group in lines.groupby("Destinatario mcía."):
        # 3. Get customer address
        addr = direcciones[direcciones["Cliente"] == customer_id].iloc[0]
        
        # 4. Get time window for this customer on this weekday
        weekday = pd.Timestamp(date).weekday()
        tw = get_time_window(customer_id, weekday)
        
        # 5. Build product lines with dimensions
        products = []
        for _, row in group.iterrows():
            dims = get_case_dimensions(row["Material"])
            weight = get_case_weight(row["Material"])
            wh_location = get_warehouse_location(row["Material"])
            products.append(ProductLine(
                material_code=row["Material"],
                description=row["Denominación"],
                quantity=int(row["Cantidad entrega"]),
                unit=row["Un.medida venta"],
                is_returnable=is_returnable(row["Material"]),
                dimensions_cm=dims,
                weight_kg=weight,
                warehouse_location=wh_location,
            ))
        
        # 6. Geocode address (cached)
        lat, lng = geocode(f"{addr['Calle']}, {addr['CP']} {addr['Población']}, Spain")
        
        stops.append(Stop(
            stop_id=str(group["Entrega"].iloc[0]),
            customer_id=str(customer_id),
            customer_name=addr["Nombre 1"],
            address=f"{addr['Calle']}, {addr['Población']}",
            lat=lat, lng=lng,
            time_window=tw,
            products=products,
        ))
    
    return stops
```
