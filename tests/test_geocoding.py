from services.geocoding import _coordinates_from_payload, build_location_queries, build_location_query


def test_build_location_query_normalizes_spanish_postal_code() -> None:
    assert (
        build_location_query(
            {
                "address": "Carrer Llevant 2",
                "postal_code": "8110",
                "city": "Montcada i Reixac",
            }
        )
        == "Carrer Llevant 2, 08110, Montcada i Reixac, Spain"
    )


def test_build_location_query_falls_back_to_name_when_address_is_missing() -> None:
    assert (
        build_location_query(
            {
                "name": "DDI Mollet",
                "city": "Mollet del Vallès",
            }
        )
        == "DDI Mollet, Mollet del Vallès, Spain"
    )


def test_build_location_queries_include_warehouse_and_city_fallbacks() -> None:
    assert build_location_queries(
        {
            "name": "DDI Mollet",
            "city": "Mollet del Vallès",
        }
    ) == [
        "DDI Mollet, Mollet del Vallès, Spain",
        "Damm Mollet del Vallès, Spain",
        "Mollet del Vallès, Spain",
    ]


def test_coordinates_from_payload_maps_nominatim_lon_to_lng() -> None:
    coordinates = _coordinates_from_payload([{"lat": "41.5409", "lon": "2.2134"}])

    assert coordinates is not None
    assert coordinates.lat == 41.5409
    assert coordinates.lng == 2.2134


def test_coordinates_from_payload_rejects_out_of_range_values() -> None:
    assert _coordinates_from_payload([{"lat": "141.5409", "lon": "2.2134"}]) is None
    assert _coordinates_from_payload([{"lat": "41.5409", "lon": "202.2134"}]) is None
