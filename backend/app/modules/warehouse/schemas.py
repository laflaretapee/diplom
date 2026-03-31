from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.models.order import SourceChannel

# ── Ingredient ────────────────────────────────────────────────────────────────

class IngredientCreate(BaseModel):
    name: str
    unit: str  # kg | g | l | ml | pcs
    min_stock_level: Decimal = Field(default=Decimal("0"), ge=0)


class IngredientUpdate(BaseModel):
    name: str | None = None
    min_stock_level: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class IngredientResponse(BaseModel):
    id: uuid.UUID
    name: str
    unit: str
    min_stock_level: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


# ── StockItem ─────────────────────────────────────────────────────────────────

class StockItemResponse(BaseModel):
    stock_item_id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    quantity: Decimal
    min_stock_level: Decimal
    is_below_minimum: bool

    model_config = {"from_attributes": True}


# ── StockMovement ─────────────────────────────────────────────────────────────

class MovementCreate(BaseModel):
    point_id: uuid.UUID
    stock_item_id: uuid.UUID
    movement_type: Literal["in", "out", "adjustment"]
    quantity: Decimal = Field(ge=0)
    reason: str | None = None


class MovementResponse(BaseModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    movement_type: str
    quantity: Decimal
    reason: str | None

    model_config = {"from_attributes": True}


# ── Dish ──────────────────────────────────────────────────────────────────────

class DishCreate(BaseModel):
    name: str
    description: str | None = None
    price: Decimal = Field(gt=0)
    available_channels: list[SourceChannel] | None = None


class DishUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None
    available_channels: list[SourceChannel] | None = None


class DishResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    is_active: bool
    available_channels: list[SourceChannel]

    model_config = {"from_attributes": True}


# ── Supply (incoming stock) ───────────────────────────────────────────────────

class SupplyCreate(BaseModel):
    point_id: uuid.UUID
    ingredient_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    supplier_name: str | None = None
    note: str | None = None


class SupplyResponse(BaseModel):
    stock_item_id: uuid.UUID
    ingredient_id: uuid.UUID
    new_quantity: Decimal
    movement_id: uuid.UUID


# ── MovementHistory ───────────────────────────────────────────────────────────

class MovementHistoryItem(BaseModel):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    movement_type: str
    quantity: Decimal
    reason: str | None
    created_at: str  # ISO datetime string
    created_by_id: str | None = None
    created_by_name: str | None = None

    model_config = {"from_attributes": True}


# ── DishIngredient ────────────────────────────────────────────────────────────

class DishIngredientCreate(BaseModel):
    ingredient_id: uuid.UUID
    quantity_per_portion: Decimal = Field(gt=0)


class DishIngredientResponse(BaseModel):
    id: uuid.UUID
    dish_id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    unit: str
    quantity_per_portion: Decimal

    model_config = {"from_attributes": True}
