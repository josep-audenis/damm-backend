# 2026-05-09 Preserve Real Delivery Units

**Status:** accepted

## Context

The real `Detalle entrega` workbook contains delivery units beyond the initial API enum: `TB`, `EST`, `PQ`, `TIR`, `BID`, and `ZPR`.

## Decision

Extend `ProductUnit` to preserve observed source units instead of coercing or dropping affected product lines.

## Frontend Impact

Frontend enum handling must accept the new unit values when rendering product lines, pick lists, and load details.

## Backend Impact

The data loader can validate all observed source delivery lines without unit coercion.

## Migration Notes

Existing values are unchanged. Consumers that exhaustively switch on `ProductUnit` should add a fallback label or explicit labels for the new values.
