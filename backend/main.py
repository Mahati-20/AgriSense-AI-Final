from __future__ import annotations

import os
import sqlite3
import asyncio
import json
import urllib.parse
import urllib.error
import urllib.request
import time
import logging
import socket
import math
import mimetypes
import uuid
import threading
import hashlib
import hmac
import secrets
import re
from collections import OrderedDict
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

DB_PATH = os.path.join(os.path.dirname(__file__), "agrisense.db")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
logger = logging.getLogger("agrisense.assistant")
_gnews_lock = threading.Lock()
_gnews_cache: OrderedDict[str, tuple[float, List[Dict[str, Any]]]] = OrderedDict()
_GNEWS_CACHE_MAX_ENTRIES = 64
_GNEWS_CACHE_DEFAULT_TTL_SECONDS = 300
_MANDI_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_MANDI_CACHE_TTL_SECONDS = 300
_MANDI_OPTIONS_CACHE_TTL_SECONDS = 3600
_MANDI_CACHE_LOCK = threading.Lock()
_GNEWS_LANGUAGES = {
    "ar", "bn", "bg", "ca", "zh", "cs", "nl", "en", "et", "fi", "fr", "de", "el", "gu", "he", "hi", "hu", "id", "it", "ja", "ko", "lv", "lt", "ml", "mr", "no", "pl", "pt", "pa", "ro", "ru", "sk", "sl", "es", "sv", "ta", "te", "th", "tr", "uk", "vi",
}
_GNEWS_COUNTRIES = {
    "ar", "au", "at", "bd", "be", "bw", "br", "bg", "ca", "cl", "cn", "co", "cu", "cz", "eg", "ee", "et", "fi", "fr", "de", "gh", "gr", "hk", "hu", "in", "id", "ie", "il", "it", "jp", "ke", "lv", "lb", "lt", "my", "mx", "ma", "na", "nl", "nz", "ng", "no", "pk", "pe", "ph", "pl", "pt", "ru", "sa", "sn", "sg", "sk", "si", "za", "kr", "es", "se", "ch", "tw", "tz", "th", "tr", "ug", "ua", "ae", "gb", "us", "ve", "vn", "zw",
}
_gnews_last_request = 0.0
_auth_rate_limit_lock = threading.Lock()
_auth_attempts: Dict[str, list[float]] = {}
_AUTH_RATE_LIMIT_WINDOW_SECONDS = 900
_AUTH_RATE_LIMIT_MAX_ATTEMPTS = 10
_PASSWORD_HASH_ITERATIONS = 600_000
_AUTH_SESSION_HOURS = 24


def get_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        with open(ENV_PATH, encoding="utf-8") as env_file:
            for line in env_file:
                key, sep, item = line.strip().partition("=")
                if sep and key == name:
                    return item.strip().strip("\"'")
    except OSError:
        pass
    return ""


def external_json(
    url: str,
    headers: Dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 12,
) -> Any:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": "AgriSenseAI/1.0", **(headers or {})})
    # urllib applies this socket timeout to connection establishment and response reads,
    # and honors the configured system proxy on developer machines.
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def safe_external_error(error: Exception, service: str = "External service") -> str:
    status = getattr(error, "code", None)
    if status == 429:
        return f"{service} rate limited the request or quota is exhausted (HTTP 429); check quota and retry later"
    if status in (401, 403):
        return f"{service} rejected the API key (HTTP 401/403); verify the key and API access"
    if status and status >= 500:
        return f"{service} temporarily unavailable (HTTP 5xx); retry shortly"
    if status == 404 and service == "Gemini":
        return "Gemini model or endpoint was not found (HTTP 404); verify GEMINI_MODEL"
    if status == 400 and service == "Gemini":
        return "Gemini rejected the request format (HTTP 400); check the request configuration"
    if status:
        return f"{service} request rejected (HTTP {status})"
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, (TimeoutError, asyncio.TimeoutError, socket.timeout)):
        return "request timed out; retry shortly"
    if isinstance(reason, socket.gaierror):
        return f"{service} hostname could not be resolved; check DNS connectivity"
    if isinstance(reason, (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError)):
        return f"could not connect to {service}; check network or firewall settings"
    if isinstance(error, json.JSONDecodeError):
        return f"{service} returned invalid JSON; retry shortly"
    if isinstance(error, (KeyError, IndexError, TypeError, ValueError)):
        return f"{service} returned an unexpected response; retry shortly"
    return "network connection failed; check connectivity and retry"


def get_gemini_model() -> str:
    configured_model = get_secret("GEMINI_MODEL")
    if (
        configured_model.startswith("gemini-")
        and len(configured_model) <= 80
        and all(character.isalnum() or character in "._-" for character in configured_model)
    ):
        return configured_model
    return "gemini-3.8-flash"


def request_gemini_json(url: str, headers: Dict[str, str], data: bytes) -> Any:
    """Call Gemini with one bounded retry for transient errors only."""
    for attempt in range(2):
        try:
            return external_json(url, headers, data, timeout=15)
        except urllib.error.HTTPError as error:
            retry_delay = None
            if 500 <= error.code <= 599 and attempt == 0:
                retry_delay = 0.5
            elif error.code == 429 and attempt == 0:
                # Respect Google's Retry-After when a short wait is practical.
                # A 429 without that hint may represent exhausted quota, so do not
                # make an immediate duplicate request.
                try:
                    requested_delay = float(error.headers.get("Retry-After", ""))
                    if 0 <= requested_delay <= 2:
                        retry_delay = requested_delay
                except (TypeError, ValueError, AttributeError):
                    pass
            if retry_delay is None:
                raise
            error.close()
        except (TimeoutError, asyncio.TimeoutError, urllib.error.URLError, ConnectionError) as error:
            reason = error.reason if isinstance(error, urllib.error.URLError) else error
            transient = isinstance(reason, (TimeoutError, asyncio.TimeoutError, socket.timeout,
                                            ConnectionResetError, ConnectionAbortedError,
                                            ConnectionRefusedError))
            if attempt == 1 or not transient:
                raise
            retry_delay = 0.5
        time.sleep(retry_delay)
    raise RuntimeError("Gemini retries exhausted")

app = FastAPI(title="AgriSense AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    
allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://agrisense-ai-frontend-x9of.onrender.com",
],
,
    # Vite automatically moves to the next port when 5173 is occupied.
    # Keep the development exception limited to loopback hostnames.
    allow_origin_regex=r"^http://(?:localhost|127\.0\.0\.1)(?::\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FarmerModel(BaseModel):
    id: int
    name: str
    location: str
    preferred_language: str
    farm_size: float
    primary_crop: str


class DecisionRequest(BaseModel):
    crop_readiness_score: float | None = Field(default=None, ge=0, le=100)
    current_price: float | None = Field(default=None, ge=0)
    price_trend: float | None = Field(default=None, ge=-100, le=100)
    demand_level: float | None = Field(default=None, ge=0, le=100)
    rainfall_risk: float | None = Field(default=None, ge=0, le=100)
    storage_cost: float | None = Field(default=None, ge=0)
    storage_availability: float | None = Field(default=None, ge=0, le=100)
    quantity: float | None = Field(default=None, gt=0)
    transport_cost: float | None = Field(default=None, ge=0)
    expected_future_price: float | None = Field(default=None, ge=0)
    production_cost: float | None = Field(default=None, ge=0)
    other_expenses: float | None = Field(default=None, ge=0)
    storage_duration_days: float | None = Field(default=None, ge=0)
    input_sources: Dict[str, str | None] = Field(default_factory=dict)
    crop: str = "Tomato"
    location: str = "Bengaluru"


class ProfitRequest(BaseModel):
    crop: str = "Tomato"
    quantity: float = Field(gt=0)
    current_price: float = Field(ge=0)
    expected_selling_price: float = Field(ge=0)
    transport_cost: float = Field(ge=0)
    storage_cost: float = Field(ge=0, description="Storage cost per day")
    storage_duration_days: float = Field(ge=0)
    other_expenses: float = Field(default=0, ge=0)
    production_cost: float = Field(default=0, ge=0)


class AssistantRequest(BaseModel):
    message: str
    crop: str = "Tomato"
    location: str = "Bengaluru"
    language: str = "en"


class CalendarTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    crop: str = Field(default="Tomato", min_length=1, max_length=80)
    date: date
    priority: Literal["Low", "Medium", "High"] = "Medium"
    completed: bool = False

    @field_validator("title", "crop", mode="before")
    @classmethod
    def strip_required_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("This field cannot be blank.")
            return stripped
        return value


class FarmToolRecordRequest(BaseModel):
    data: Dict[str, Any]


def _farm_tool_validate(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {"planner-crops", "planner-tasks", "crop-journal", "harvest", "profit"}
    if kind not in allowed:
        raise HTTPException(status_code=404, detail="Farm tool record type not found.")
    fields = {
        "planner-crops": {"crop", "planting_date", "area", "area_unit", "stage", "harvest_date"},
        "planner-tasks": {"title", "crop", "description", "date", "priority", "status"},
        "crop-journal": {"crop", "date", "stage", "symptoms", "observations", "action", "follow_up", "notes"},
        "harvest": {"crop", "date", "quantity", "unit", "sold", "stored", "spoiled", "notes"},
        "profit": {"crop", "scenario", "quantity", "unit", "price", "price_unit", "transport", "labour", "packaging", "storage", "other", "loss_percent"},
    }
    if set(data) - fields[kind]:
        raise HTTPException(status_code=422, detail="Unexpected fields were supplied.")
    result = dict(data)
    def required_text(key: str, limit: int = 120) -> str:
        value = result.get(key)
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise HTTPException(status_code=422, detail=f"{key.replace('_', ' ').capitalize()} is required (maximum {limit} characters).")
        result[key] = value.strip()
        return result[key]
    def valid_date(key: str, optional: bool = False) -> None:
        value = result.get(key)
        if optional and value in (None, ""):
            result[key] = ""
            return
        try:
            date.fromisoformat(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{key.replace('_', ' ').capitalize()} must be an ISO date.") from None
    if kind == "planner-crops":
        required_text("crop", 80); required_text("stage", 80); valid_date("planting_date"); valid_date("harvest_date", True)
        try: area = float(result.get("area"));
        except (TypeError, ValueError): raise HTTPException(status_code=422, detail="Area must be a positive number.") from None
        if not math.isfinite(area) or not 0 < area <= 1_000_000: raise HTTPException(status_code=422, detail="Area must be a positive number.")
        result["area"] = area
    elif kind == "planner-tasks":
        required_text("title"); required_text("crop", 80); valid_date("date")
        result["description"] = str(result.get("description", "")).strip()[:500]
        if result.get("priority") not in ("Low", "Medium", "High") or result.get("status") not in ("Pending", "Completed"):
            raise HTTPException(status_code=422, detail="Select a valid task priority and status.")
    elif kind == "crop-journal":
        required_text("crop", 80); required_text("stage", 80); valid_date("date"); valid_date("follow_up", True)
        for key in ("symptoms", "observations", "notes", "action"):
            value = result.get(key, "")
            if not isinstance(value, str) or len(value) > 4000: raise HTTPException(status_code=422, detail="Journal text is too long or invalid.")
            result[key] = value.strip()
    elif kind == "harvest":
        required_text("crop", 80); valid_date("date"); required_text("unit", 12)
        if result["unit"] not in ("kg", "tonnes"): raise HTTPException(status_code=422, detail="Use kg or tonnes consistently.")
        values = {}
        for key in ("quantity", "sold", "stored", "spoiled"):
            try: values[key] = float(result.get(key, 0))
            except (TypeError, ValueError): raise HTTPException(status_code=422, detail="Harvest quantities must be numbers.") from None
            if not math.isfinite(values[key]) or not 0 <= values[key] <= 1e12: raise HTTPException(status_code=422, detail="Harvest quantities must be finite and non-negative.")
        if values["quantity"] <= 0 or sum(values[k] for k in ("sold", "stored", "spoiled")) > values["quantity"] + 1e-9:
            raise HTTPException(status_code=422, detail="Sold, stored and spoiled quantities cannot exceed harvested quantity.")
        result.update(values, remaining=round(values["quantity"] - values["sold"] - values["stored"] - values["spoiled"], 6))
        result["notes"] = str(result.get("notes", ""))[:2000]
    else:
        required_text("crop", 80); required_text("scenario", 80)
        try:
            qty = float(result.get("quantity")); price = float(result.get("price")); costs = [float(result.get(k, 0)) for k in ("transport", "labour", "packaging", "storage", "other")]; loss = float(result.get("loss_percent", 0))
        except (TypeError, ValueError): raise HTTPException(status_code=422, detail="Enter valid numeric values for the estimate.") from None
        if result.get("unit") not in ("kg", "tonnes") or result.get("price_unit") not in ("kg", "quintal") or not math.isfinite(qty) or not math.isfinite(price) or any(not math.isfinite(v) for v in costs) or not math.isfinite(loss) or not 0 < qty <= 1e12 or not 0 <= price <= 1e12 or any(not 0 <= v <= 1e12 for v in costs) or not 0 <= loss <= 100:
            raise HTTPException(status_code=422, detail="Quantity must be positive; prices/costs non-negative and loss between 0 and 100%.")
        kilograms = qty * (1000 if result["unit"] == "tonnes" else 1) * (1 - loss / 100)
        per_kg = price / (100 if result["price_unit"] == "quintal" else 1)
        expenses = sum(costs); revenue = kilograms * per_kg
        result.update({"quantity_kg_after_loss": kilograms, "gross_revenue": round(revenue, 2), "total_expenses": round(expenses, 2), "net": round(revenue-expenses, 2), "profit_per_kg": round((revenue-expenses)/kilograms, 4) if kilograms else 0, "break_even_per_kg": round(expenses/kilograms, 4) if kilograms else 0, "break_even_per_quintal": round(expenses/kilograms*100, 2) if kilograms else 0, "price_label": "USER ENTERED"})
    return result


def _farm_tool_rows(user_id: int, kind: str) -> List[Dict[str, Any]]:
    rows = fetch_all("SELECT id, kind, payload, created_at, updated_at FROM farm_tool_record WHERE user_id = ? AND kind = ? ORDER BY created_at DESC, id DESC", (user_id, kind))
    records = [{"id": row["id"], "kind": row["kind"], **json.loads(row["payload"]), "created_at": row["created_at"], "updated_at": row["updated_at"], "data_status": "USER ENTERED"} for row in rows]
    if kind in {"planner-tasks", "crop-journal"}:
        records.sort(key=lambda item: (item.get("date", ""), item["id"]), reverse=True)
    elif kind == "planner-crops":
        records.sort(key=lambda item: (item.get("planting_date", ""), item["id"]), reverse=True)
    return records


class AuthSignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not (re.search(r"[a-z]", value) and re.search(r"[A-Z]", value) and re.search(r"\d", value) and re.search(r"[^A-Za-z\d]", value)):
            raise ValueError("Use upper and lowercase letters, a number, and a symbol.")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = " ".join(value.split())
            if not value:
                raise ValueError("Name cannot be blank.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class ProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = " ".join(value.split())
            if not value:
                raise ValueError("Name cannot be blank.")
        return value


def calculate_profit_scenarios(payload: ProfitRequest) -> Dict[str, float]:
    storage_total = payload.storage_cost * payload.storage_duration_days
    common = payload.production_cost + payload.transport_cost + payload.other_expenses
    sell_revenue = payload.quantity * payload.current_price
    store_revenue = payload.quantity * payload.expected_selling_price
    sell_profit = sell_revenue - common
    store_profit = store_revenue - common - storage_total
    expenses = common + storage_total
    return {
        "sell_revenue": sell_revenue, "store_revenue": store_revenue,
        "sell_profit": sell_profit, "store_profit": store_profit,
        "expenses": expenses, "storage_total": storage_total,
    }


SEED_MARKET = [
    {"crop": "Tomato", "market": "Bengaluru APMC", "price": 28.0, "unit": "kg", "date": "2026-10-07", "demand_level": 85, "trend": 8.4},
    {"crop": "Tomato", "market": "Bengaluru APMC", "price": 26.5, "unit": "kg", "date": "2026-10-06", "demand_level": 80, "trend": 6.9},
    {"crop": "Tomato", "market": "Bengaluru APMC", "price": 25.8, "unit": "kg", "date": "2026-10-05", "demand_level": 78, "trend": 5.1},
    {"crop": "Tomato", "market": "Bengaluru APMC", "price": 24.8, "unit": "kg", "date": "2026-10-04", "demand_level": 76, "trend": 4.2},
    {"crop": "Tomato", "market": "Bengaluru APMC", "price": 27.1, "unit": "kg", "date": "2026-10-03", "demand_level": 82, "trend": 7.4},
    {"crop": "Tomato", "market": "Bengaluru APMC", "price": 26.0, "unit": "kg", "date": "2026-10-02", "demand_level": 79, "trend": 3.4},
    {"crop": "Tomato", "market": "Bengaluru APMC", "price": 25.4, "unit": "kg", "date": "2026-10-01", "demand_level": 75, "trend": 2.8},
    {"crop": "Rice", "market": "Mysuru Market", "price": 22.5, "unit": "kg", "date": "2026-10-07", "demand_level": 70, "trend": 2.9},
    {"crop": "Cotton", "market": "Bellary Market", "price": 58.0, "unit": "kg", "date": "2026-10-07", "demand_level": 73, "trend": 5.1},
    {"crop": "Maize", "market": "Hubballi Market", "price": 19.7, "unit": "kg", "date": "2026-10-07", "demand_level": 69, "trend": 1.7},
]

SEED_STORAGE = [
    {"id": 1, "name": "Bengaluru Cold Storage", "location": "Bengaluru East", "distance": 12, "capacity": 1800, "available_capacity": 1200, "storage_type": "Cold Storage", "price_per_day": 22, "rating": 4.8},
    {"id": 2, "name": "Nandi Agro Warehouse", "location": "Devanahalli", "distance": 18, "capacity": 1600, "available_capacity": 1050, "storage_type": "Warehouse", "price_per_day": 16, "rating": 4.5},
    {"id": 3, "name": "GreenLeaf Dry Store", "location": "Whitefield", "distance": 10, "capacity": 990, "available_capacity": 760, "storage_type": "Dry Storage", "price_per_day": 14, "rating": 4.3},
    {"id": 4, "name": "FreshNet Refrigerated Hub", "location": "Kengeri", "distance": 21, "capacity": 1500, "available_capacity": 1310, "storage_type": "Cold Storage", "price_per_day": 25, "rating": 4.9},
    {"id": 5, "name": "Krishna Logistics Depot", "location": "Rajajinagar", "distance": 8, "capacity": 1100, "available_capacity": 850, "storage_type": "Warehouse", "price_per_day": 11, "rating": 4.2},
]

SEED_WEATHER = [
    {"location": "Bengaluru", "date": "2026-10-07", "temperature": 28, "rainfall_probability": 72, "humidity": 75, "weather_condition": "Partly Cloudy"},
    {"location": "Bengaluru", "date": "2026-10-08", "temperature": 27, "rainfall_probability": 81, "humidity": 80, "weather_condition": "Rain Likely"},
    {"location": "Bengaluru", "date": "2026-10-09", "temperature": 26, "rainfall_probability": 86, "humidity": 82, "weather_condition": "Heavy Rain"},
    {"location": "Bengaluru", "date": "2026-10-10", "temperature": 29, "rainfall_probability": 61, "humidity": 72, "weather_condition": "Cloudy"},
    {"location": "Bengaluru", "date": "2026-10-11", "temperature": 30, "rainfall_probability": 44, "humidity": 66, "weather_condition": "Sunny"},
]

SEED_TASKS = [
    {"id": 1, "title": "Pest monitoring", "crop": "Tomato", "date": "2026-10-08", "priority": "High", "completed": False},
    {"id": 2, "title": "Fertilizer check", "crop": "Tomato", "date": "2026-10-09", "priority": "Medium", "completed": False},
    {"id": 3, "title": "Harvest planning", "crop": "Tomato", "date": "2026-10-10", "priority": "High", "completed": False},
    {"id": 4, "title": "Irrigation cycle", "crop": "Tomato", "date": "2026-10-07", "priority": "Medium", "completed": True},
    {"id": 5, "title": "Market check", "crop": "Tomato", "date": "2026-10-08", "priority": "Low", "completed": False},
]

SEED_NEWS = [
    {"id": 1, "headline": "Tomato prices rise across Karnataka mandis", "category": "Markets", "date": "2026-10-07", "summary": "Demand is strengthening after a week of low arrivals in southern markets."},
    {"id": 2, "headline": "Rain warnings issued for parts of Bengaluru", "category": "Weather", "date": "2026-10-07", "summary": "Farmers are advised to monitor harvest readiness and drainage before the next rainfall spell."},
    {"id": 3, "headline": "Government subsidy extended for drip irrigation", "category": "Government", "date": "2026-10-06", "summary": "New support is available for efficient irrigation and increased resilience."},
    {"id": 4, "headline": "Smart storage helps reduce spoilage in fruit crops", "category": "Technology", "date": "2026-10-05", "summary": "Cold storage scheduling is increasingly being used to reduce post-harvest losses."},
    {"id": 5, "headline": "Cotton growers focus on pest management", "category": "Farming", "date": "2026-10-04", "summary": "Weather conditions favor a faster pest monitoring cycle in the next week."},
]

SEED_NOTIFICATIONS = [
    {"id": 1, "title": "Heavy rainfall expected", "message": "Harvest-ready tomatoes in Bengaluru may face spoilage risk in 48 hours.", "severity": "High", "timestamp": "2026-10-07T08:30:00", "read": False},
    {"id": 2, "title": "Tomato prices increased", "message": "Current market price is now â‚¹28/kg in Bengaluru APMC.", "severity": "Medium", "timestamp": "2026-10-07T07:00:00", "read": False},
    {"id": 3, "title": "Crop health needs attention", "message": "Leaf disease signs were detected during the latest crop check.", "severity": "Medium", "timestamp": "2026-10-07T06:10:00", "read": True},
    {"id": 4, "title": "Cold storage available", "message": "Nearby cold storage with a 1,200 kg capacity is available for next 3 days.", "severity": "Low", "timestamp": "2026-10-07T05:30:00", "read": False},
]

SEED_FARMER = [
    {"id": 1, "name": "Ravi Kumar", "location": "Bengaluru", "preferred_language": "en", "farm_size": 2.5, "primary_crop": "Tomato"},
]

SEED_CROPS = [
    {"id": 1, "name": "Tomato", "variety": "Hybrid Raj", "planting_date": "2026-08-01", "expected_harvest_date": "2026-10-15", "current_stage": "Maturity", "quantity": 500},
    {"id": 2, "name": "Rice", "variety": "Sona Masuri", "planting_date": "2026-07-15", "expected_harvest_date": "2026-11-01", "current_stage": "Flowering", "quantity": 1200},
    {"id": 3, "name": "Cotton", "variety": "Bt Cotton", "planting_date": "2026-06-20", "expected_harvest_date": "2026-10-28", "current_stage": "Boll formation", "quantity": 900},
]


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS farmer (
                id INTEGER PRIMARY KEY,
                name TEXT,
                location TEXT,
                preferred_language TEXT,
                farm_size REAL,
                primary_crop TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crop (
                id INTEGER PRIMARY KEY,
                name TEXT,
                variety TEXT,
                planting_date TEXT,
                expected_harvest_date TEXT,
                current_stage TEXT,
                quantity INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market (
                crop TEXT,
                market TEXT,
                price REAL,
                unit TEXT,
                date TEXT,
                demand_level INTEGER,
                trend REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS storage (
                id INTEGER PRIMARY KEY,
                name TEXT,
                location TEXT,
                distance INTEGER,
                capacity INTEGER,
                available_capacity INTEGER,
                storage_type TEXT,
                price_per_day INTEGER,
                rating REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS weather (
                location TEXT,
                date TEXT,
                temperature REAL,
                rainfall_probability INTEGER,
                humidity INTEGER,
                weather_condition TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS farming_task (
                id INTEGER PRIMARY KEY,
                title TEXT,
                crop TEXT,
                date TEXT,
                priority TEXT,
                completed INTEGER,
                data_source TEXT NOT NULL DEFAULT 'DEMO DATA'
            )
            """
        )
        task_columns = {row[1] for row in conn.execute("PRAGMA table_info(farming_task)").fetchall()}
        if "data_source" not in task_columns:
            conn.execute("ALTER TABLE farming_task ADD COLUMN data_source TEXT NOT NULL DEFAULT 'USER DATA'")
        if "user_id" not in task_columns:
            # Existing calendar records stay in place as shared, read-only examples.
            conn.execute("ALTER TABLE farming_task ADD COLUMN user_id INTEGER REFERENCES app_user(id) ON DELETE CASCADE")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification (
                id INTEGER PRIMARY KEY,
                title TEXT,
                message TEXT,
                severity TEXT,
                timestamp TEXT,
                read INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY,
                headline TEXT,
                category TEXT,
                date TEXT,
                summary TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_iterations INTEGER NOT NULL,
                email_verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS farm_tool_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_farm_tool_user_kind ON farm_tool_record(user_id, kind, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_session_user ON auth_session(user_id)")
        # Calendar rows without an owner predate account scoping; keep them visible but read-only.
        conn.execute("UPDATE farming_task SET data_source = 'DEMO DATA' WHERE user_id IS NULL")

        def seed_if_empty(table: str, statement: str, rows: list[tuple]) -> None:
            if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is None:
                conn.executemany(statement, rows)

        seed_if_empty("farmer",
            "INSERT INTO farmer (id, name, location, preferred_language, farm_size, primary_crop) VALUES (?, ?, ?, ?, ?, ?)",
            [(item["id"], item["name"], item["location"], item["preferred_language"], item["farm_size"], item["primary_crop"]) for item in SEED_FARMER],
        )
        seed_if_empty("crop",
            "INSERT INTO crop (id, name, variety, planting_date, expected_harvest_date, current_stage, quantity) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(item["id"], item["name"], item["variety"], item["planting_date"], item["expected_harvest_date"], item["current_stage"], item["quantity"]) for item in SEED_CROPS],
        )
        seed_if_empty("market",
            "INSERT INTO market (crop, market, price, unit, date, demand_level, trend) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(item["crop"], item["market"], item["price"], item["unit"], item["date"], item["demand_level"], item["trend"]) for item in SEED_MARKET],
        )
        seed_if_empty("storage",
            "INSERT INTO storage (id, name, location, distance, capacity, available_capacity, storage_type, price_per_day, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(item["id"], item["name"], item["location"], item["distance"], item["capacity"], item["available_capacity"], item["storage_type"], item["price_per_day"], item["rating"]) for item in SEED_STORAGE],
        )
        seed_if_empty("weather",
            "INSERT INTO weather (location, date, temperature, rainfall_probability, humidity, weather_condition) VALUES (?, ?, ?, ?, ?, ?)",
            [(item["location"], item["date"], item["temperature"], item["rainfall_probability"], item["humidity"], item["weather_condition"]) for item in SEED_WEATHER],
        )
        seed_if_empty("farming_task",
            "INSERT INTO farming_task (id, title, crop, date, priority, completed, data_source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(item["id"], item["title"], item["crop"], item["date"], item["priority"], 1 if item["completed"] else 0, "DEMO DATA") for item in SEED_TASKS],
        )
        seed_if_empty("notification",
            "INSERT INTO notification (id, title, message, severity, timestamp, read) VALUES (?, ?, ?, ?, ?, ?)",
            [(item["id"], item["title"], item["message"], item["severity"], item["timestamp"], 1 if item["read"] else 0) for item in SEED_NOTIFICATIONS],
        )
        seed_if_empty("news",
            "INSERT INTO news (id, headline, category, date, summary) VALUES (?, ?, ?, ?, ?)",
            [(item["id"], item["headline"], item["category"], item["date"], item["summary"]) for item in SEED_NEWS],
        )

        conn.commit()


def fetch_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def normalize(value: float, low: float, high: float) -> float:
    if high == low:
        return 50.0
    return max(0.0, min(100.0, ((value - low) / (high - low)) * 100))


def score_to_decision(payload: DecisionRequest) -> Dict[str, Any]:
    required = {
        "crop_readiness_score": payload.crop_readiness_score,
        "current_price": payload.current_price,
        "price_trend": payload.price_trend,
        "demand_level": payload.demand_level,
        "rainfall_risk": payload.rainfall_risk,
        "storage_cost": payload.storage_cost,
        "storage_availability": payload.storage_availability,
        "quantity": payload.quantity,
        "transport_cost": payload.transport_cost,
        "expected_future_price": payload.expected_future_price,
        "storage_duration_days": payload.storage_duration_days,
        "production_cost": payload.production_cost,
        "other_expenses": payload.other_expenses,
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        return {
            "recommendation": "WAIT", "confidence": 0, "score": 0,
            "status": "insufficient_data", "data_source": "INCOMPLETE INPUTS",
            "data_date": None, "missing_inputs": missing,
            "score_breakdown": {},
            "reasons": ["There is not enough verified information to make a sell/store recommendation."],
            "risks": ["Do not treat WAIT as a market recommendation; key inputs are missing."],
            "alternative": None, "profit_now": None, "profit_future": None,
        }

    qty = float(payload.quantity)
    profit_values = calculate_profit_scenarios(ProfitRequest(
        crop=payload.crop, quantity=qty, current_price=float(payload.current_price),
        expected_selling_price=float(payload.expected_future_price), transport_cost=float(payload.transport_cost),
        storage_cost=float(payload.storage_cost), storage_duration_days=float(payload.storage_duration_days),
        production_cost=float(payload.production_cost), other_expenses=float(payload.other_expenses),
    ))
    sell_profit, store_profit = profit_values["sell_profit"], profit_values["store_profit"]
    profit_scale = max(qty * max(float(payload.current_price), float(payload.expected_future_price)), 1)
    sell_profit_score = normalize(sell_profit, 0, profit_scale)
    store_profit_score = normalize(store_profit, 0, profit_scale)
    trend = float(payload.price_trend)
    trend_signal = max(-50.0, min(50.0, trend * 2))
    readiness = float(payload.crop_readiness_score)
    rain = float(payload.rainfall_risk)
    demand = float(payload.demand_level)
    storage_cost_score = 100 - normalize(float(payload.storage_cost) * float(payload.storage_duration_days), 0, max(qty * float(payload.current_price) * 0.2, 1))
    storage_cost_score = max(0, storage_cost_score)
    storage_access_score = float(payload.storage_availability)
    weights = {"market_trend": 0.25, "expected_profit": 0.25, "weather": 0.20, "crop_readiness": 0.15, "demand": 0.10, "storage_cost": 0.05}
    factors = {
        "SELL": {"market_trend": 50 - trend_signal, "expected_profit": sell_profit_score, "weather": rain, "crop_readiness": readiness, "demand": demand, "storage_cost": storage_cost_score},
        "STORE": {"market_trend": 50 + trend_signal, "expected_profit": store_profit_score, "weather": 100 - rain, "crop_readiness": readiness, "demand": 100 - demand * 0.5, "storage_cost": min(storage_cost_score, storage_access_score)},
        "WAIT": {"market_trend": 50 + trend_signal * 0.5, "expected_profit": 50, "weather": 100 - rain, "crop_readiness": 100 - readiness, "demand": 50, "storage_cost": storage_cost_score},
    }
    scores = {action: round(sum(values[name] * weights[name] for name in weights), 1) for action, values in factors.items()}
    recommendation = max(scores, key=scores.get)
    ordered_scores = sorted(scores.values(), reverse=True)
    confidence = round(min(95, 50 + (ordered_scores[0] - ordered_scores[1]) * 0.75), 1)
    source_values = [value for value in payload.input_sources.values() if isinstance(value, str)]
    if not source_values:
        data_source = "UNVERIFIED INPUT SOURCES"
        status = "unverified"
    elif any("MISSING" in value.upper() or "UNVERIFIED" in value.upper() for value in source_values):
        data_source = "UNVERIFIED INPUT SOURCES"
        status = "unverified"
    elif any("DEMO" in value.upper() for value in source_values):
        data_source = "DEMO DATA"
        status = "demo"
    elif any("FARMER INPUT" in value.upper() or "ESTIMATE" in value.upper() for value in source_values):
        data_source = "LIVE DATA + FARMER INPUT"
        status = "mixed"
    else:
        data_source = "LIVE DATA"
        status = "ready"
    reasons = [f"{factor.replace('_', ' ').title()} score: {factors[recommendation][factor]:.0f}/100." for factor in weights]
    reasons.append(f"Estimated {recommendation.lower()} return is â‚¹{sell_profit if recommendation == 'SELL' else store_profit:,.0f} for {qty:g} kg.")
    risks = []
    if status == "demo":
        risks.append("At least one recommendation input is demo data.")
    elif status == "mixed":
        risks.append("Some recommendation inputs are farmer-entered estimates, not live observations.")
    elif status == "unverified":
        risks.append("Recommendation input sources were not provided.")
    if payload.input_sources.get("crop_readiness_score", "").upper().find("DEMO") >= 0:
        risks.append("Crop readiness is estimated from the recorded growth stage, not an image or field measurement.")
    return {
        "recommendation": recommendation, "confidence": confidence, "score": scores[recommendation],
        "status": status, "data_source": data_source,
        "data_date": payload.input_sources.get("market_date") or payload.input_sources.get("weather_date"),
        "missing_inputs": [], "score_breakdown": {action: {**{name: round(value, 1) for name, value in factors[action].items()}, "total": scores[action]} for action in factors},
        "reasons": reasons, "risks": risks,
        "alternative": {"recommendation": sorted(scores, key=scores.get, reverse=True)[1], "score": ordered_scores[1]},
        "profit_now": round(sell_profit, 2), "profit_future": round(store_profit, 2),
    }


async def build_dashboard_payload() -> Dict[str, Any]:
    farmer = {**fetch_all("SELECT * FROM farmer LIMIT 1")[0], "data_source": "DEMO DATA"}
    crop = {**fetch_all("SELECT * FROM crop WHERE name = 'Tomato' LIMIT 1")[0], "data_source": "DEMO DATA"}
    weather = await get_weather()
    market_error = None
    try:
        market = await get_market_rows("Tomato", "Karnataka")
    except HTTPException as error:
        market = []
        market_error = error.detail
    notifications = [{**item, "data_source": "DEMO DATA"} for item in fetch_all("SELECT * FROM notification ORDER BY id DESC LIMIT 5")]
    tasks = [{**item, "completed": bool(item["completed"]), "data_source": item.get("data_source", "DEMO DATA")} for item in fetch_all("SELECT * FROM farming_task WHERE completed = 0 ORDER BY date LIMIT 4")]
    try:
        trend = await get_market_trend_data("Tomato", "Karnataka", "", "")
    except HTTPException as error:
        trend = {"trend_available": False, "forecast_available": False, "observations": [], "message": error.detail}
        market_error = market_error or error.detail
    storage = await get_storage()
    stage_readiness = {"maturity": 90, "flowering": 55, "boll formation": 65}
    market_row = market[0] if market else {}
    weather_row = weather[0] if weather else {}
    storage_row = storage[0] if storage else {}
    source = market_row.get("data_source", "MISSING DATA")
    readiness = stage_readiness.get(str(crop.get("current_stage", "")).lower())
    same_market_unit = market_row.get("price") is not None and trend.get("price_unit") == market_row.get("unit")
    forecast = trend.get("forecast_range") if same_market_unit else None
    expected_price = ((forecast["lower"] + forecast["upper"]) / 2) if forecast else None
    decision_sources = {
        "current_price": source,
        "market_date": market_row.get("date"),
        "price_trend": trend.get("data_source") if trend.get("trend_available") and same_market_unit else "MISSING DATA",
        "expected_future_price": trend.get("data_source") if forecast else "MISSING DATA",
        "demand_level": source if market_row.get("demand_level", 0) else "MISSING DATA",
        "rainfall_risk": weather_row.get("data_source", "MISSING DATA"),
        "weather_date": weather_row.get("date"),
        "crop_readiness_score": "DEMO DATA (growth-stage estimate)",
        "storage_cost": storage_row.get("data_source", "MISSING DATA"),
        "storage_availability": storage_row.get("data_source", "MISSING DATA"),
        "quantity": "farmer profile",
        "transport_cost": "farmer input required",
        "production_cost": "farmer input required",
        "other_expenses": "farmer input required",
        "storage_duration_days": "farmer input required",
    }
    decision = score_to_decision(DecisionRequest(
        crop_readiness_score=readiness,
        current_price=market_row.get("price"),
        price_trend=trend.get("trend_percent") if trend.get("trend_available") and same_market_unit else None,
        demand_level=market_row.get("demand_level") if market_row.get("demand_level", 0) else None,
        rainfall_risk=weather_row.get("rainfall_probability"),
        storage_cost=float(storage_row.get("price_per_day", 0)) * 3 if storage_row else None,
        storage_availability=(float(storage_row.get("available_capacity", 0)) / max(float(storage_row.get("capacity", 1)), 1) * 100) if storage_row else None,
        quantity=crop.get("quantity"),
        transport_cost=None,
        expected_future_price=expected_price,
        production_cost=None,
        other_expenses=None,
        storage_duration_days=None,
        input_sources=decision_sources,
    ))
    return {
        "farmer": farmer,
        "crop": crop,
        "weather": weather,
        "market": market,
        "market_error": market_error,
        "notifications": notifications,
        "tasks": tasks,
        "decision": decision,
        "decision_data_source": decision["data_source"],
        "decision_inputs": decision_sources,
    }


@app.on_event("startup")
async def startup_event() -> None:
    init_db()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _password_digest(password: str, salt: bytes, iterations: int = _PASSWORD_HASH_ITERATIONS) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()


def _public_user(row: sqlite3.Row | Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": str(row["name"] or "").strip() or "Farmer",
        "email": row["email"],
        "email_verified": bool(row["email_verified"]),
        "created_at": row["created_at"],
    }


def _check_auth_rate_limit(request: Request, email: str) -> None:
    client_host = request.client.host if request.client else "unknown"
    key = f"{client_host}:{email}"
    now = time.monotonic()
    cutoff = now - _AUTH_RATE_LIMIT_WINDOW_SECONDS
    with _auth_rate_limit_lock:
        expired = [item for item, attempts in _auth_attempts.items() if not attempts or attempts[-1] < cutoff]
        for item in expired:
            _auth_attempts.pop(item, None)
        attempts = [attempt for attempt in _auth_attempts.get(key, []) if attempt >= cutoff]
        if len(attempts) >= _AUTH_RATE_LIMIT_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many account attempts. Please wait and try again.")
        attempts.append(now)
        _auth_attempts[key] = attempts


def _new_session(conn: sqlite3.Connection, user_id: int) -> Dict[str, Any]:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=_AUTH_SESSION_HOURS)
    conn.execute(
        "INSERT INTO auth_session (user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, hashlib.sha256(token.encode("ascii")).hexdigest(), now.isoformat(), expires_at.isoformat()),
    )
    return {"access_token": token, "token_type": "bearer", "expires_at": expires_at.isoformat()}


def _authenticated_user(authorization: str | None) -> Dict[str, Any]:
    scheme, separator, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not re.fullmatch(r"[A-Za-z0-9_-]{40,64}", token):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
    rows = fetch_all(
        """
        SELECT app_user.id, app_user.name, app_user.email, app_user.email_verified,
               app_user.created_at, auth_session.expires_at
        FROM auth_session JOIN app_user ON app_user.id = auth_session.user_id
        WHERE auth_session.token_hash = ? AND auth_session.revoked_at IS NULL
        """,
        (token_hash,),
    )
    if not rows:
        raise HTTPException(status_code=401, detail="Session is invalid or expired. Please sign in again.")
    try:
        expires_at = datetime.fromisoformat(rows[0]["expires_at"])
    except ValueError:
        raise HTTPException(status_code=401, detail="Session is invalid or expired. Please sign in again.") from None
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session is invalid or expired. Please sign in again.")
    return rows[0]


@app.post("/api/auth/signup", status_code=201)
def signup(payload: AuthSignupRequest, request: Request) -> Dict[str, Any]:
    _check_auth_rate_limit(request, payload.email)
    salt = secrets.token_bytes(16)
    password_hash = _password_digest(payload.password, salt)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                INSERT INTO app_user (name, email, password_salt, password_hash, password_iterations, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (payload.name, payload.email, salt.hex(), password_hash, _PASSWORD_HASH_ITERATIONS, now),
            )
            user_id = cursor.lastrowid
            session = _new_session(conn, user_id)
            user = conn.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone()
            conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
    return {**session, "user": _public_user(user)}


@app.post("/api/auth/login")
def login(payload: AuthLoginRequest, request: Request) -> Dict[str, Any]:
    _check_auth_rate_limit(request, payload.email)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT * FROM app_user WHERE email = ?", (payload.email,)).fetchone()
        if user is None:
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        try:
            salt = bytes.fromhex(user["password_salt"])
            candidate = _password_digest(payload.password, salt, user["password_iterations"])
        except (ValueError, TypeError):
            raise HTTPException(status_code=401, detail="Email or password is incorrect.") from None
        if not hmac.compare_digest(candidate, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        session = _new_session(conn, user["id"])
        conn.commit()
    return {**session, "user": _public_user(user)}


@app.get("/api/auth/me")
def auth_me(authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    return _public_user(_authenticated_user(authorization))


@app.put("/api/auth/profile")
def update_profile(payload: ProfileUpdateRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    user = _authenticated_user(authorization)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("UPDATE app_user SET name = ? WHERE id = ?", (payload.name, user["id"]))
        updated = conn.execute("SELECT * FROM app_user WHERE id = ?", (user["id"],)).fetchone()
        conn.commit()
    return _public_user(updated)


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> Dict[str, str]:
    user = _authenticated_user(authorization)
    _, _, token = (authorization or "").partition(" ")
    token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            "UPDATE auth_session SET revoked_at = ? WHERE user_id = ? AND token_hash = ? AND revoked_at IS NULL",
            (now, user["id"], token_hash),
        )
        conn.commit()
    return {"status": "logged_out"}


@app.get("/api/dashboard")
async def dashboard() -> Dict[str, Any]:
    return await build_dashboard_payload()


async def build_plantnet_multipart(images: List[UploadFile], organs: List[str]) -> tuple[str, bytes]:
    if not 1 <= len(images) <= 5:
        raise HTTPException(status_code=400, detail="Upload at most 5 images of the same plant.")
    supported_organs = {"leaf", "flower", "fruit", "bark", "auto"}
    if organs and (len(organs) != len(images) or any(organ not in supported_organs for organ in organs)):
        raise HTTPException(status_code=400, detail="Choose one supported plant organ for each image.")
    if not organs:
        organs = ["auto"] * len(images)
    if any(image.content_type not in {"image/jpeg", "image/png"} for image in images):
        raise HTTPException(status_code=400, detail="Upload JPEG or PNG images only.")
    boundary = "----AgriSense" + uuid.uuid4().hex
    chunks: List[bytes] = []
    total_size = 0
    for image, organ in zip(images, organs):
        content = await image.read()
        valid_signature = content.startswith(b"\xff\xd8\xff") if image.content_type == "image/jpeg" else content.startswith(b"\x89PNG\r\n\x1a\n")
        if not valid_signature:
            raise HTTPException(status_code=400, detail="The uploaded file contents do not match a valid JPEG or PNG image.")
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Each image must be 10 MB or smaller.")
        total_size += len(content)
        if total_size > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Combined image size must be 25 MB or smaller.")
        filename = os.path.basename(image.filename or "plant-image.jpg").replace('"', "").replace("\r", "").replace("\n", "")
        mime = image.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.extend([
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"images\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode(),
            content, b"\r\n",
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"organs\"\r\n\r\n{organ}\r\n".encode(),
        ])
    chunks.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(chunks)


def plantnet_configuration() -> str:
    api_key = get_secret("PLANTNET_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Pl@ntNet is not configured. Add PLANTNET_API_KEY to the root .env file.")
    if any(character.isspace() for character in api_key) or len(api_key) > 512:
        raise HTTPException(status_code=503, detail="PLANTNET_API_KEY has invalid formatting. Check the root .env entry.")
    return api_key


def plantnet_request_url(path: str, api_key: str) -> str:
    return f"https://my-api.plantnet.org{path}?" + urllib.parse.urlencode({"api-key": api_key})


def plantnet_error(error: Exception, feature: str) -> HTTPException:
    status = getattr(error, "code", None)
    if status == 429:
        return HTTPException(status_code=429, detail="Pl@ntNet daily identification quota is exhausted. It resets at 00:00 UTC; please try later.")
    if status == 401:
        return HTTPException(status_code=502, detail="Pl@ntNet rejected the configured API key (HTTP 401). Check the root .env key.")
    if status == 403:
        detail = "Pl@ntNet disease screening is unavailable for this account (HTTP 403)." if feature == "disease screening" else "Pl@ntNet denied this identification request (HTTP 403). Check account access."
        return HTTPException(status_code=502, detail=detail)
    if status == 400:
        return HTTPException(status_code=422, detail=f"Pl@ntNet rejected the image or {feature} request (HTTP 400). Try a clear JPEG or PNG image and confirm the selected plant part.")
    if status and status >= 500:
        return HTTPException(status_code=502, detail="Pl@ntNet is temporarily unavailable (HTTP 5xx). Please retry later.")
    message = safe_external_error(error, "Pl@ntNet")
    return HTTPException(status_code=504 if "timed out" in message else 502, detail=f"Pl@ntNet {feature} failed: {message}.")


async def call_plantnet(path: str, images: List[UploadFile], organs: List[str], feature: str) -> Dict[str, Any]:
    boundary, body = await build_plantnet_multipart(images, organs)
    api_key = plantnet_configuration()
    url = plantnet_request_url(path, api_key)
    try:
        result = await asyncio.to_thread(external_json, url, {"Content-Type": f"multipart/form-data; boundary={boundary}"}, body, 15)
    except Exception as error:
        raise plantnet_error(error, feature) from error
    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        raise HTTPException(status_code=502, detail=f"Pl@ntNet returned an unexpected {feature} response. Please retry later.")
    return result


def map_plantnet_candidates(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_candidates = result["results"]
    best_match = result.get("bestMatch") if isinstance(result.get("bestMatch"), str) else None
    mapped: List[Dict[str, Any]] = []
    for index, candidate in enumerate(raw_candidates[:5]):
        if not isinstance(candidate, dict):
            raise HTTPException(status_code=502, detail="Pl@ntNet returned a malformed species candidate.")
        species = candidate.get("species") if isinstance(candidate.get("species"), dict) else {}
        scientific_name = species.get("scientificNameWithoutAuthor") or species.get("scientificName")
        if not isinstance(scientific_name, str):
            scientific_name = None
        names = species.get("commonNames")
        common_names = [name for name in names if isinstance(name, str) and name.strip()] if isinstance(names, list) else []
        name = common_names[0] if common_names else scientific_name
        if not name and index == 0:
            name = best_match
            scientific_name = best_match
        if not name:
            continue
        try:
            score = float(candidate.get("score")) if candidate.get("score") is not None else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=502, detail="Pl@ntNet returned an invalid species score.")
        if score is not None and not 0 <= score <= 1:
            raise HTTPException(status_code=502, detail="Pl@ntNet returned an invalid species score.")
        mapped.append({"name": name, "scientific_name": scientific_name, "common_names": common_names,
                       "score": score, "score_percent": round(score * 100, 1) if score is not None else None})
    if not raw_candidates and best_match:
        mapped.append({"name": best_match, "scientific_name": best_match, "common_names": [], "score": None, "score_percent": None})
    return mapped


@app.post("/api/crop/analyze")
async def analyze_crop(
    images: List[UploadFile] = File(...),
    crop: str = Form(default=""),
    location: str = Form(default=""),
    organs: List[str] = Form(default=[]),
) -> Dict[str, Any]:
    result = await call_plantnet("/v2/identify/all", images, organs, "species identification")
    candidates = map_plantnet_candidates(result)
    top = candidates[0] if candidates else None
    common_names = top["common_names"] if top else []
    scientific_name = top["scientific_name"] if top else None
    identified_name = top["name"] if top else None
    identification_score = top["score"] if top else None
    return {
        "crop": identified_name,
        "identified_species": {"scientific_name": scientific_name, "common_names": common_names, "score": identification_score,
                               "score_percent": top["score_percent"]} if top else None,
        "candidates": candidates,
        "best_match": result.get("bestMatch") if isinstance(result.get("bestMatch"), str) else identified_name,
        "scientific_name": scientific_name,
        "common_names": common_names,
        "health": None,
        "status": "Plant species identified" if identified_name else "No plant species identified",
        "identification_score": identification_score,
        "identification_score_percent": top["score_percent"] if top else None,
        "disease_detection": "unavailable",
        "remaining_identification_requests": result.get("remainingIdentificationRequests") if isinstance(result.get("remainingIdentificationRequests"), int) else None,
        "severity": None,
        "observations": [],
        "recommended_next_steps": [],
        "suggested_action": [],
        "disclaimer": "Plant species identification only. Disease detection is a separate optional screening; this result does not assess plant health or diagnose disease.",
        "data_source": "Pl@ntNet plant identification",
        "image_name": images[0].filename,
    }


@app.post("/api/crop/disease-screening")
async def screen_crop_disease(
    images: List[UploadFile] = File(...),
    organs: List[str] = Form(default=[]),
) -> Dict[str, Any]:
    result = await call_plantnet("/v2/diseases/identify", images, organs, "disease screening")
    diseases = []
    for item in result["results"][:5]:
        if not isinstance(item, dict):
            raise HTTPException(status_code=502, detail="Pl@ntNet returned a malformed disease-screening candidate.")
        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            continue
        try:
            score = float(item.get("score")) if item.get("score") is not None else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=502, detail="Pl@ntNet returned an invalid screening score.")
        if score is not None and not 0 <= score <= 1:
            raise HTTPException(status_code=502, detail="Pl@ntNet returned an invalid screening score.")
        diseases.append({"description": description, "eppo_code": item.get("name") if isinstance(item.get("name"), str) else None,
                         "score": score, "score_percent": round(score * 100, 1) if score is not None else None})
    return {
        "status": "Possible disease screening matches returned" if diseases else "No supported disease screening match returned",
        "candidates": diseases,
        "screening_available": True,
        "disclaimer": "This is a limited informational screening for supported species and conditions, not a diagnosis. Have uncertain or severe symptoms assessed by a qualified local agricultural expert.",
        "data_source": "Pl@ntNet disease screening",
        "remaining_identification_requests": result.get("remainingIdentificationRequests") if isinstance(result.get("remainingIdentificationRequests"), int) else None,
    }


@app.get("/api/crops")
async def get_crops() -> List[Dict[str, Any]]:
    return [{**row, "data_source": "DEMO DATA"} for row in fetch_all("SELECT * FROM crop ORDER BY id")]


@app.get("/api/markets")
async def get_markets() -> List[Dict[str, Any]]:
    return await get_market_rows("Tomato", "Karnataka")


async def get_market_rows(commodity: str, state: str) -> List[Dict[str, Any]]:
    result = await market_prices(commodity, state)
    records = result.get("records", [])
    return [{**normalize_mandi_record(row), "crop": row.get("commodity") or commodity,
             "data_source": result["data_source"], "date": row.get("arrival_date"),
             "demand_level": None, "trend": None} for row in records if isinstance(row, dict)]


def normalize_mandi_record(record: Dict[str, Any]) -> Dict[str, Any]:
    source_unit = record.get("price_unit") or record.get("unit")
    normalized_unit = str(source_unit).strip().lower().replace(" ", "") if source_unit is not None else ""
    per_kg_units = {"₹/kg", "rs/kg", "inr/kg", "rupees/kg", "rs./kg", "₹/kilogram", "inr/kilogram"}
    per_quintal_units = {"₹/quintal", "rs/quintal", "inr/quintal", "rupees/quintal", "rs./quintal", "₹/qtl", "rs/qtl", "inr/qtl"}
    if normalized_unit in per_kg_units:
        factor, converted_unit = 1.0, "₹/kg"
    elif normalized_unit in per_quintal_units:
        factor, converted_unit = 0.01, "₹/kg"
    else:
        factor, converted_unit = None, None

    def convert(field: str) -> float | None:
        value = record.get(field)
        if factor is None or value is None:
            return None
        try:
            return round(float(value) * factor, 2)
        except (TypeError, ValueError):
            return None

    converted_modal = convert("modal_price")
    return {
        **record,
        "source_price_unit": source_unit,
        "converted_price_unit": converted_unit,
        "converted_min_price": convert("min_price"),
        "converted_max_price": convert("max_price"),
        "converted_modal_price": converted_modal,
        "price": converted_modal,
        "unit": converted_unit,
        "price_compatible": converted_modal is not None and converted_unit == "₹/kg",
        "source_price": record.get("modal_price"),
        "price_label": f"Converted from {source_unit}" if converted_modal is not None else "Source price; provider did not specify a supported unit",
    }


def mandi_api_url(endpoint: str, params: Dict[str, str] | None = None) -> str:
    base_url = get_secret("MANDI_API_BASE_URL").rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise HTTPException(status_code=503, detail="Mandi prices are unavailable because MANDI_API_BASE_URL is missing or invalid in the backend environment.")
    return f"{base_url}/{endpoint.lstrip('/')}" + ("?" + urllib.parse.urlencode(params) if params else "")


def mandi_api_get(endpoint: str, params: Dict[str, str] | None = None, *, options: bool = False, force_refresh: bool = False) -> Dict[str, Any]:
    url = mandi_api_url(endpoint, params)
    cache_key = url
    ttl = _MANDI_OPTIONS_CACHE_TTL_SECONDS if options else _MANDI_CACHE_TTL_SECONDS
    now = time.monotonic()
    with _MANDI_CACHE_LOCK:
        cached = _MANDI_CACHE.get(cache_key)
        if not force_refresh and cached and now - cached[0] < ttl:
            return {**cached[1], "cached": True, "cache_age_seconds": int(now - cached[0])}
        if cached:
            _MANDI_CACHE.pop(cache_key, None)

    try:
        payload = external_json(url, headers={"Accept": "application/json"}, timeout=12)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise HTTPException(status_code=429, detail="Mandi prices are rate limited by the provider. Wait a little before retrying.") from error
        if error.code >= 500:
            raise HTTPException(status_code=502, detail="Mandi price provider is temporarily unavailable. Retry shortly.") from error
        raise HTTPException(status_code=502, detail=f"Mandi price provider rejected the request (HTTP {error.code}).") from error
    except (TimeoutError, asyncio.TimeoutError, socket.timeout, urllib.error.URLError) as error:
        category = safe_external_error(error, "Mandi price provider")
        status = 504 if "timed out" in category else 502
        message = "Mandi price request timed out. Retry shortly." if status == 504 else "Could not connect to the Mandi price provider. Check the backend network and retry."
        raise HTTPException(status_code=status, detail=message) from error
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail="Mandi price provider returned invalid JSON.") from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Mandi price provider returned an unreadable response.") from error

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Mandi price provider returned an invalid response envelope.")
    if payload.get("success") is not True:
        provider_error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        code = provider_error.get("code")
        if code in {"RATE_LIMIT", "RATE_LIMITED", "TOO_MANY_REQUESTS"}:
            raise HTTPException(status_code=429, detail="Mandi price provider rate limit reached. Wait a little before retrying.")
        message = provider_error.get("message")
        raise HTTPException(status_code=502, detail=f"Mandi price provider reported an error: {message}" if isinstance(message, str) else "Mandi price provider reported an error.")
    if not isinstance(payload.get("data"), list):
        raise HTTPException(status_code=502, detail="Mandi price provider returned an invalid data list.")
    result = {"records": payload["data"], "meta": payload.get("meta") if isinstance(payload.get("meta"), dict) else {}, "data_source": "Mandi Price API"}
    with _MANDI_CACHE_LOCK:
        _MANDI_CACHE[cache_key] = (time.monotonic(), result)
    return {**result, "cached": False, "cache_age_seconds": 0}


def mandi_freshness(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    parsed_dates: List[date] = []
    for record in records:
        value = record.get("arrival_date")
        try:
            if isinstance(value, str):
                parsed_dates.append(date.fromisoformat(value[:10]))
        except ValueError:
            continue
    if not parsed_dates:
        return {"freshness": "unknown", "stale": None, "latest_arrival_date": None, "age_days": None, "freshness_message": "Freshness cannot be verified because no valid arrival date was returned."}
    latest = max(parsed_dates)
    age_days = (date.today() - latest).days
    if age_days < 0:
        return {"freshness": "unknown", "stale": None, "latest_arrival_date": latest.isoformat(), "age_days": age_days, "freshness_message": "Arrival date is in the future; freshness cannot be verified."}
    stale = age_days > 7
    return {"freshness": "stale" if stale else "current", "stale": stale, "latest_arrival_date": latest.isoformat(), "age_days": age_days, "freshness_message": f"Latest mandi arrival is {age_days} days old."}


@app.get("/api/markets/options")
async def get_market_options(state: str = Query("Karnataka", min_length=1, max_length=80)) -> Dict[str, Any]:
    states_result, commodities_result = await asyncio.gather(
        asyncio.to_thread(mandi_api_get, "states", None, options=True),
        asyncio.to_thread(mandi_api_get, "commodities", {"state": state}, options=True),
    )
    states = [value for value in states_result["records"] if isinstance(value, str) and value.strip()]
    commodities = [value for value in commodities_result["records"] if isinstance(value, str) and value.strip()]
    return {"states": states, "commodities": commodities, "selected_state": state, "data_source": "Mandi Price API"}


@app.get("/api/markets/prices")
async def market_prices(commodity: str = "Tomato", state: str = "Karnataka", district: str = "", market: str = "", refresh: bool = False) -> Dict[str, Any]:
    if not commodity.strip() or not state.strip():
        raise HTTPException(status_code=422, detail="Select both a state and commodity.")
    params: Dict[str, str] = {"state": state.strip(), "commodity": commodity.strip()}
    if district:
        params["district"] = district
    if market:
        params["market"] = market
    result = await asyncio.to_thread(mandi_api_get, "prices", params, force_refresh=refresh)
    if any(not isinstance(record, dict) for record in result["records"]):
        raise HTTPException(status_code=502, detail="Mandi price provider returned a malformed price record.")
    records = [normalize_mandi_record(record) for record in result["records"]]
    metadata = result.get("meta", {})
    source_timestamp = metadata.get("latest_fetched_at") if isinstance(metadata.get("latest_fetched_at"), str) else max((record.get("fetched_at") for record in records if isinstance(record.get("fetched_at"), str)), default=None)
    freshness = mandi_freshness(records)
    has_unknown_units = any(record.get("converted_price_unit") is None for record in records)
    unit_status = "At least one record has an unknown or unsupported unit; those raw values are not converted or used as ₹/kg." if has_unknown_units else "The provider supplied a recognized unit; converted values are explicitly labelled."
    return {"success": True, "data": records, "meta": metadata, "data_source": result["data_source"], "retrieved_at": datetime.now().astimezone().isoformat(), "source_fetched_at": source_timestamp, "cached": result["cached"], "cache_age_seconds": result["cache_age_seconds"], "unit_status": unit_status, **freshness}

async def get_market_trend_data(commodity: str = "Tomato", state: str = "Karnataka", district: str = "", market: str = "") -> Dict[str, Any]:
    result = await market_prices(commodity, state, district, market)
    records = [row for row in result.get("records", []) if isinstance(row, dict)]
    by_date: Dict[str, List[float]] = {}
    parsed_dates: Dict[str, datetime] = {}
    all_units_confirmed = bool(records)
    for row in records:
        raw_date, raw_price = row.get("arrival_date"), row.get("modal_price")
        if not raw_date or raw_price is None:
            all_units_confirmed = False
            continue
        normalized = normalize_mandi_record(row)
        source_price = normalized["price"] if normalized["price_compatible"] else raw_price
        if not normalized["price_compatible"]:
            all_units_confirmed = False
        try:
            observed_price = float(source_price)
        except (TypeError, ValueError):
            all_units_confirmed = False
            continue
        parsed = None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(raw_date, fmt)
                break
            except (TypeError, ValueError):
                continue
        if parsed is None:
            continue
        by_date.setdefault(parsed.date().isoformat(), []).append(observed_price)
        parsed_dates[parsed.date().isoformat()] = parsed
    unit = "₹/kg" if all_units_confirmed else None
    observations = [{"date": key, "price": round(sum(values) / len(values), 2), "unit": unit, "market_count": len(values)} for key, values in by_date.items()]
    observations.sort(key=lambda item: parsed_dates[item["date"]])
    history = observations[-7:]
    prices = [item["price"] for item in history]
    if len(history) < 7:
        return {"data_source": result.get("data_source"), "observations": history, "trend_available": False, "forecast_available": False, "price_unit": unit, "message": "At least seven valid dated observations are needed for a trend estimate."}
    average = sum(prices) / len(prices)
    change = ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] else 0
    forecast = max(0, average * (1 + change / 100))
    return {"data_source": result["data_source"], "observations": history, "average_7": round(average, 2), "trend_percent": round(change, 2), "trend_direction": "up" if change > 1 else "down" if change < -1 else "stable", "minimum": min(prices), "maximum": max(prices), "trend_available": True, "forecast_available": True, "price_unit": unit, "forecast_method": "Illustrative estimate from seven dated provider observations; not a mandi quote", "forecast_range": {"lower": round(forecast * 0.9, 2), "upper": round(forecast * 1.1, 2)}}

@app.get("/api/markets/trend")
async def market_trend(commodity: str = "Tomato", state: str = "Karnataka", district: str = "", market: str = "") -> Dict[str, Any]:
    return await get_market_trend_data(commodity, state, district, market)


@app.get("/api/markets/{crop}")
async def get_market_for_crop(crop: str) -> List[Dict[str, Any]]:
    rows = await get_market_rows(crop, "Karnataka")
    if not rows:
        raise HTTPException(status_code=404, detail="No market data found")
    return rows


@app.post("/api/profit/calculate")
async def calculate_profit(payload: ProfitRequest) -> Dict[str, Any]:
    values = calculate_profit_scenarios(payload)
    revenue, expenses, net_profit = values["store_revenue"], values["expenses"], values["store_profit"]
    profit_per_kg = net_profit / payload.quantity
    profit_percentage = net_profit / revenue * 100 if revenue else 0
    return {
        "crop": payload.crop,
        "quantity": payload.quantity,
        "current_price": payload.current_price,
        "expected_selling_price": payload.expected_selling_price,
        "revenue": round(revenue, 2),
        "expenses": round(expenses, 2),
        "net_profit": round(net_profit, 2),
        "profit_per_kg": round(profit_per_kg, 2),
        "profit_percentage": round(profit_percentage, 2),
        "total_cost": round(expenses, 2),
        "roi": round(net_profit / max(expenses, 1) * 100, 2),
        "storage_duration_days": payload.storage_duration_days,
        "storage_total": round(values["storage_total"], 2),
        "sell_now_profit": round(values["sell_profit"], 2),
        "store_profit": round(values["store_profit"], 2),
        "store_vs_sell_difference": round(values["store_profit"] - values["sell_profit"], 2),
    }


@app.post("/api/decision/analyze")
async def analyze_decision(payload: DecisionRequest) -> Dict[str, Any]:
    return score_to_decision(payload)


def weather_description(code: int | None) -> str:
    return {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers", 81: "Rain showers", 82: "Heavy rain showers", 95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail"}.get(code, "Conditions unavailable")


@app.get("/api/weather")
async def get_weather(latitude: float = 12.9716, longitude: float = 77.5946, location: str = "Bengaluru, Karnataka") -> List[Dict[str, Any]]:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=422, detail="Latitude or longitude is out of range.")
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,weather_code",
        "forecast_days": 7, "timezone": "auto",
    })
    try:
        data = await asyncio.to_thread(external_json, url)
        daily = data.get("daily", {})
        current = data.get("current", {})
        return [{
            "location": location,
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "date": day,
            "temperature": daily.get("temperature_2m_max", [])[index],
            "temperature_min": daily.get("temperature_2m_min", [])[index],
            "rainfall_probability": daily.get("precipitation_probability_max", [])[index],
            "rainfall_mm": daily.get("precipitation_sum", [])[index],
            "current_temperature": current.get("temperature_2m") if index == 0 else None,
            "current_humidity": current.get("relative_humidity_2m") if index == 0 else None,
            "humidity": current.get("relative_humidity_2m") if index == 0 else None,
            "current_precipitation": current.get("precipitation") if index == 0 else None,
            "wind_kmh": current.get("wind_speed_10m") if index == 0 else None,
            "weather_condition": weather_description(daily.get("weather_code", [])[index]),
            "data_source": "Open-Meteo",
            "data_status": "LIVE",
            "observation_time": current.get("time"),
            "forecast_time": day,
        } for index, day in enumerate(daily.get("time", []))]
    except Exception:
        # This records demo data explicitly so callers cannot mistake it for a forecast.
        return [{**item, "current_temperature": None, "current_humidity": None, "wind_kmh": None, "data_source": "DEMO DATA (Open-Meteo unavailable)", "data_status": "DEMO", "location": location, "forecast_time": item.get("date"), "observation_time": None} for item in fetch_all("SELECT * FROM weather ORDER BY date")]


@app.get("/api/weather/risk")
async def get_weather_risk() -> Dict[str, Any]:
    weather = await get_weather()
    if not weather:
        return {"risk_level": "UNKNOWN", "alerts": [], "data_source": "UNAVAILABLE", "message": "No forecast data is available."}
    rainfall_values = [item.get("rainfall_probability") for item in weather[:3] if item.get("rainfall_probability") is not None]
    rainfall = max(rainfall_values) if rainfall_values else None
    current_temp = weather[0].get("current_temperature")
    wind = weather[0].get("wind_kmh")
    risk = "UNKNOWN" if rainfall is None else "HIGH" if rainfall >= 75 else "MODERATE" if rainfall >= 50 else "LOW"
    alerts = []
    if rainfall is not None and rainfall >= 70:
        alerts.append({"type": "rain", "severity": "High", "message": f"Rain probability reaches {rainfall}% in the next three forecast days."})
    if current_temp is not None and current_temp >= 35:
        alerts.append({"type": "heat", "severity": "Medium", "message": f"Current temperature is {current_temp}Â°C."})
    if wind is not None and wind >= 35:
        alerts.append({"type": "wind", "severity": "Medium", "message": f"Current wind speed is {wind} km/h."})
    return {
        "risk_level": risk,
        "rainfall_probability": rainfall,
        "temperature": current_temp,
        "humidity": weather[0].get("current_humidity"),
        "alerts": alerts,
        "data_source": weather[0].get("data_source"),
        "location": weather[0].get("location"),
        "observation_time": weather[0].get("observation_time"),
        "message": "Weather risk is based on the fetched forecast." if alerts else "No threshold-based risk alert from the fetched forecast.",
    }


@app.get("/api/storage")
async def get_storage() -> List[Dict[str, Any]]:
    items = fetch_all("SELECT * FROM storage ORDER BY distance")
    return [{**item, "data_source": "DEMO DATA", "directions_url": storage_directions_url(item.get("location"))} for item in items]


def storage_directions_url(location: str | None) -> str | None:
    destination = location.strip() if isinstance(location, str) else ""
    if not destination:
        return None
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode({"api": "1", "destination": destination})


@app.get("/api/storage/{storage_id}")
async def get_storage_by_id(storage_id: int) -> Dict[str, Any]:
    rows = fetch_all("SELECT * FROM storage WHERE id = ?", (storage_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Storage not found")
    return {**rows[0], "data_source": "DEMO DATA", "directions_url": storage_directions_url(rows[0].get("location"))}


@app.get("/api/calendar")
async def get_calendar(authorization: str | None = Header(default=None)) -> List[Dict[str, Any]]:
    user = _authenticated_user(authorization)
    rows = fetch_all("SELECT * FROM farming_task WHERE user_id IS NULL OR user_id = ? ORDER BY date", (user["id"],))
    return [{**row, "completed": bool(row["completed"]), "data_source": row.get("data_source", "DEMO DATA")} for row in rows]


@app.post("/api/calendar/tasks")
async def add_task(payload: CalendarTaskRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    user = _authenticated_user(authorization)
    title, crop, task_date, priority, completed = payload.title.strip(), payload.crop.strip(), payload.date.isoformat(), payload.priority, payload.completed

    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute(
            "INSERT INTO farming_task (title, crop, date, priority, completed, data_source, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, crop, task_date, priority, 1 if completed else 0, "USER DATA", user["id"]),
        )
        conn.commit()
        task_id = cursor.lastrowid
        return {"id": task_id, "title": title, "crop": crop, "date": task_date, "priority": priority, "completed": completed, "data_source": "USER DATA"}


@app.put("/api/calendar/tasks/{task_id}")
async def update_task(task_id: int, payload: CalendarTaskRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    user = _authenticated_user(authorization)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            "UPDATE farming_task SET title = ?, crop = ?, date = ?, priority = ?, completed = ? WHERE id = ? AND user_id = ?",
            (
                payload.title.strip(), payload.crop.strip(), payload.date.isoformat(), payload.priority,
                1 if payload.completed else 0,
                task_id,
                user["id"],
            ),
        )
        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="Calendar task not found")
        conn.commit()
    return {"status": "updated", "id": task_id}


@app.delete("/api/calendar/tasks/{task_id}")
async def delete_task(task_id: int, authorization: str | None = Header(default=None)) -> Dict[str, str]:
    user = _authenticated_user(authorization)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute("DELETE FROM farming_task WHERE id = ? AND user_id = ?", (task_id, user["id"]))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Calendar task not found")
        conn.commit()
    return {"status": "deleted", "id": str(task_id)}


def _gnews_cache_ttl() -> int:
    """Successful searches stay fresh for five minutes by default; deployments may tune this."""
    try:
        return max(30, min(900, int(os.getenv("GNEWS_CACHE_TTL_SECONDS", str(_GNEWS_CACHE_DEFAULT_TTL_SECONDS)))))
    except ValueError:
        return _GNEWS_CACHE_DEFAULT_TTL_SECONDS


@app.get("/api/news")
async def get_news(
    q: str = Query(..., min_length=1, max_length=200),
    lang: str = Query("en", min_length=2, max_length=2),
    country: str = Query("", max_length=2),
    sortby: str = Query("publishedAt", alias="sortBy"),
) -> List[Dict[str, Any]]:
    query = " ".join(q.split())
    if not query:
        raise HTTPException(status_code=422, detail="Enter a news search term.")
    if lang not in _GNEWS_LANGUAGES:
        raise HTTPException(status_code=422, detail="Choose a supported news language.")
    if country and country not in _GNEWS_COUNTRIES:
        raise HTTPException(status_code=422, detail="Choose a supported country or leave it unrestricted.")
    if sortby not in {"publishedAt", "relevance"}:
        raise HTTPException(status_code=422, detail="Sort by relevance or publication date.")

    key = get_secret("GNEWS_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="Agri News is unavailable because GNEWS_API_KEY is not configured on the backend.")

    cache_key = "|".join((query.casefold(), lang, country, sortby))
    request_id = uuid.uuid4().hex[:12]

    def fetch_gnews() -> List[Dict[str, Any]]:
        global _gnews_last_request
        with _gnews_lock:
            now = time.monotonic()
            cached = _gnews_cache.get(cache_key)
            if cached and now - cached[0] < _gnews_cache_ttl():
                _gnews_cache.move_to_end(cache_key)
                return cached[1]
            if cached:
                _gnews_cache.pop(cache_key, None)
            if now - _gnews_last_request < 1:
                raise HTTPException(status_code=429, detail="Agri News was searched just now. Wait a moment, then retry.")
            _gnews_last_request = now
            params = {"q": query, "lang": lang, "max": 10, "sortby": sortby, "apikey": key}
            if country:
                params["country"] = country
            url = "https://gnews.io/api/v4/search?" + urllib.parse.urlencode(params)
            started = time.monotonic()
            try:
                data = external_json(url, timeout=10)
                if not isinstance(data, dict) or not isinstance(data.get("articles"), list):
                    raise ValueError("unexpected article response")
                articles: List[Dict[str, Any]] = []
                for index, item in enumerate(data["articles"]):
                    if not isinstance(item, dict):
                        continue
                    source = item.get("source") if isinstance(item.get("source"), dict) else {}
                    article_url = item.get("url")
                    if not isinstance(article_url, str) or urllib.parse.urlparse(article_url).scheme not in {"http", "https"}:
                        article_url = None
                    image = item.get("image")
                    if not isinstance(image, str) or urllib.parse.urlparse(image).scheme not in {"http", "https"}:
                        image = None
                    articles.append({
                        "id": item.get("id") if isinstance(item.get("id"), str) else index + 1,
                        "headline": item.get("title") if isinstance(item.get("title"), str) else None,
                        "date": item.get("publishedAt") if isinstance(item.get("publishedAt"), str) else None,
                        "summary": item.get("description") if isinstance(item.get("description"), str) else None,
                        "image": image,
                        "source": source.get("name") if isinstance(source.get("name"), str) else None,
                        "url": article_url,
                        "data_source": "GNews",
                    })
                _gnews_cache[cache_key] = (time.monotonic(), articles)
                _gnews_cache.move_to_end(cache_key)
                while len(_gnews_cache) > _GNEWS_CACHE_MAX_ENTRIES:
                    _gnews_cache.popitem(last=False)
                logger.info("GNews request_id=%s endpoint=/api/v4/search status=200 duration_ms=%d articles=%d", request_id, int((time.monotonic() - started) * 1000), len(articles))
                return articles
            except Exception as error:
                status = getattr(error, "code", None)
                logger.warning("GNews request_id=%s endpoint=/api/v4/search status=%s category=%s duration_ms=%d", request_id, status or "network", type(error).__name__, int((time.monotonic() - started) * 1000))
                raise

    try:
        return await asyncio.to_thread(fetch_gnews)
    except HTTPException:
        raise
    except Exception as error:
        status = getattr(error, "code", None)
        if status == 400:
            code, message = 422, "GNews could not process that search. Check the keywords and try a simpler query."
        elif status == 401:
            code, message = 502, "GNews did not authorize this request. The configured server key may be invalid or expired."
        elif status == 403:
            code, message = 429, "GNews daily quota or subscription limit has been reached. Try after the quota resets."
        elif status == 429:
            code, message = 429, "GNews request rate limit reached. Wait briefly, then retry."
        elif status and status >= 500:
            code, message = 502, "GNews is temporarily unavailable. Please retry in a little while."
        else:
            category = safe_external_error(error, "GNews")
            code = 504 if "timed out" in category else 502
            if code == 504:
                message = "Agri News request timed out. Please retry."
            elif "invalid JSON" in category or "unexpected response" in category:
                message = "GNews returned an unreadable response. Please retry shortly."
            elif "hostname could not be resolved" in category:
                message = "Agri News could not reach GNews because its address could not be resolved. Check the server network and retry."
            elif "connect to GNews" in category:
                message = "Agri News could not connect to GNews. Check the server network and retry."
            else:
                message = "Agri News could not connect to GNews. Check the connection and retry."
        raise HTTPException(status_code=code, detail=message) from error


@app.post("/api/assistant")
async def ask_assistant(payload: AssistantRequest) -> Dict[str, Any]:
    decision = score_to_decision(DecisionRequest(crop=payload.crop, location=payload.location))
    key = get_secret("GEMINI_API_KEY")
    async def safe_market_context() -> Dict[str, Any]:
        try:
            return {"records": await get_market_rows(payload.crop, "Karnataka"), "error": None}
        except HTTPException as error:
            return {"records": [], "error": error.detail}

    weather, market_result = await asyncio.gather(get_weather(), safe_market_context())
    market = market_result["records"]
    context = {
        "farm_record": [
            {key: value for key, value in row.items() if key not in {"id", "name"}}
            for row in fetch_all("SELECT * FROM farmer LIMIT 1")
        ],
        "crop": fetch_all("SELECT * FROM crop WHERE name = ? LIMIT 1", (payload.crop,)),
        "weather": weather,
        "market": market,
        "market_data_status": "unavailable" if market_result["error"] else "available" if market else "no matching records",
        "market_error": market_result["error"],
        "storage": [{**item, "data_source": "DEMO DATA"} for item in fetch_all("SELECT * FROM storage ORDER BY distance LIMIT 5")],
        "decision": decision,
    }
    if not key:
        return {"answer": "AgriSense AI assistant is unavailable because GEMINI_API_KEY is not configured. Current market and weather information may be demo data; no live recommendation or diagnosis is being generated.", "recommendation": decision["recommendation"], "confidence": decision["confidence"], "reasons": decision["reasons"], "data_source": "DEMO CONTEXT; AI unavailable", "status": "unavailable"}

    prompt = f"""
You are AgriSense AI, a helpful agricultural assistant for farmers.

LANGUAGE AND COMMUNICATION:
- Respond in the language specified by this language code: {payload.language}.
- Use simple, clear, respectful, farmer-friendly language.
- Explain technical terms briefly.
- Be practical, accurate, and concise.
- Answer the farmer's actual question first.
- Avoid unnecessary introductions and unrelated information.

FARM AND CROP CONTEXT:
- Crop: {payload.crop}
- Location: {payload.location}
- Use the supplied context to understand the farmer's records, crop stage,
  weather, market information, storage options, and existing recommendation.
- Do not assume that every record is complete, current, or verified.
- Do not invent missing farm information.

GENERAL FARMING GUIDANCE:
- For questions about crop growth, irrigation, soil health, nutrients,
  pests, diseases, flowering, fruit development, and harvesting, provide
  useful guidance based on established general agricultural knowledge,
  even when the supplied context contains no farming instructions.
- Do not refuse to answer a general farming question simply because
  the farm records do not contain the answer.
- Clearly distinguish general agricultural guidance from information
  retrieved from the supplied farm records.
- Tailor guidance to the specified crop, location, and growth stage
  when those details are available.
- If the growth stage is unknown, do not assume one.
- For crop-growing questions, provide 3 to 5 practical steps where
  appropriate, explaining what to do and why.
- Explain what the farmer should monitor and what signs may indicate
  that further investigation is needed.
- If important details are missing, provide safe general guidance
  where possible and ask one relevant follow-up question.
- Consider soil type, crop variety, irrigation method, climate,
  and growth stage when these materially affect the recommendation.
- Never invent crop symptoms, soil test results, farm measurements,
  diagnoses, yield estimates, or field conditions.
- Treat possible pest or disease causes as possibilities, not confirmed
  diagnoses, unless sufficient evidence supports a diagnosis.
- Give precise fertilizer doses, pesticide dosages, chemical treatments,
  and irrigation schedules only when sufficient information supports
  a safe and appropriate recommendation.
- If a precise recommendation cannot be made safely, explain what
  additional information is required.
- Do not claim that general agricultural knowledge came from farm
  records, laboratory tests, live weather data, or local authorities.

WEATHER INFORMATION:
- Use supplied weather information for current weather claims.
- Identify its source and date when available.
- Do not invent weather measurements or forecasts.
- If weather information is missing, say that current conditions
  have not been verified rather than making up values.

MARKET AND STORAGE INFORMATION:
- Use the supplied context for market prices and storage information.
- Clearly identify all records marked DEMO DATA as illustrative,
  not live or verified information.
- Never present demo prices, storage facilities, or rates as confirmed
  current offers.
- Do not invent prices, market trends, transport costs, storage costs,
  production costs, or profit estimates.
- If verified information is missing, explain the limitation clearly.

DETERMINISTIC SELL/STORE RECOMMENDATION:
- Explain the recommendation provided in the supplied decision context.
- Preserve the supplied recommendation, confidence, score, and reasons.
- Do not independently change the deterministic recommendation.
- If the recommendation is WAIT because information is insufficient,
  explain which inputs are missing.
- Clarify that WAIT due to missing information is not a prediction
  that prices will rise or a recommendation to delay selling.
- Do not promise profits or present unsupported financial claims.
- Keep crop-care advice separate from commercial sell/store decisions.

RESPONSE STRUCTURE:
- Start with a direct answer to the farmer's question.
- Use short headings and bullet points when helpful.
- For farming questions, explain practical actions, monitoring,
  relevant limitations, and any necessary follow-up question.
- For market questions, distinguish verified information from demo data
  and explain any uncertainty.
- Include weather, market, or storage details only when relevant.
- Avoid repeating the entire supplied context unnecessarily.
- Do not claim to have performed an action or checked a source
  that was not actually used.

SUPPLIED AGRISENSE CONTEXT:
{json.dumps(context, ensure_ascii=False, default=str)}

FARMER'S QUESTION:
{payload.message}

Provide a helpful, direct, evidence-aware answer in the requested
language. Never invent missing facts.
"""

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{get_gemini_model()}:generateContent"

    try:
        data = await asyncio.to_thread(
            request_gemini_json,
            endpoint,
            {"Content-Type": "application/json", "x-goog-api-key": key},
            json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "thinkingConfig": {"thinkingLevel": "low"},
                    "maxOutputTokens": 768,
                },
            }).encode(),
        )
        answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if not answer:
            raise ValueError("empty Gemini response")
        source = "Gemini; supplied AgriSense context"
    except urllib.error.HTTPError as error:
        status = 503 if error.code >= 500 else 429 if error.code == 429 else 401 if error.code in (401, 403) else 502
        message = safe_external_error(error, "Gemini")
        logger.warning("Gemini request failed: %s", message)
        error.close()
        raise HTTPException(status_code=status, detail=message) from error
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as error:
        message = safe_external_error(error, "Gemini")
        logger.warning("Gemini response was invalid: %s", message)
        raise HTTPException(status_code=502, detail=message) from error
    except Exception as error:
        timeout_failure = isinstance(error, (TimeoutError, asyncio.TimeoutError)) or (
            isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError)
        )
        message = safe_external_error(error, "Gemini")
        logger.warning("Gemini request failed: %s", message)
        raise HTTPException(status_code=504 if timeout_failure else 502, detail=message) from error
    return {
        "answer": answer,
        "recommendation": decision["recommendation"],
        "confidence": decision["confidence"],
        "reasons": decision["reasons"],
        "data_source": source,
    }


@app.get("/api/assistant/status")
async def assistant_status() -> Dict[str, Any]:
    configured = bool(get_secret("GEMINI_API_KEY"))
    return {"available": configured, "configured": configured, "status": "configured" if configured else "unavailable", "model": get_gemini_model(), "data_source": "Key configured; connection is checked on request" if configured else "DEMO / AI UNAVAILABLE"}


@app.get("/api/notifications")
async def get_notifications() -> List[Dict[str, Any]]:
    return [{**item, "data_source": "DEMO DATA"} for item in fetch_all("SELECT * FROM notification ORDER BY id DESC")]


@app.get("/api/farm-tools/{kind}")
def get_farm_tool_records(kind: str, authorization: str | None = Header(default=None)) -> Any:
    user = _authenticated_user(authorization)
    if kind == "report":
        return {"farmer": _public_user(user), "crop_profiles": _farm_tool_rows(user["id"], "planner-crops"), "tasks": _farm_tool_rows(user["id"], "planner-tasks"), "inspections": _farm_tool_rows(user["id"], "crop-journal"), "harvests": _farm_tool_rows(user["id"], "harvest"), "profit_calculations": _farm_tool_rows(user["id"], "profit"), "data_quality": ["Only farmer-entered records linked to this account are included.", "Existing shared crop and farm records are DEMO DATA and are excluded."], "generated_at": datetime.now(timezone.utc).isoformat()}
    if kind not in {"planner-crops", "planner-tasks", "crop-journal", "harvest", "profit"}:
        raise HTTPException(status_code=404, detail="Farm tool record type not found.")
    return _farm_tool_rows(user["id"], kind)


@app.post("/api/farm-tools/{kind}", status_code=201)
def create_farm_tool_record(kind: str, payload: FarmToolRecordRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    user = _authenticated_user(authorization)
    data = _farm_tool_validate(kind, payload.data)
    now = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        if kind == "profit" and conn.execute("SELECT COUNT(*) FROM farm_tool_record WHERE user_id = ? AND kind = 'profit'", (user["id"],)).fetchone()[0] >= 3:
            raise HTTPException(status_code=409, detail="You can save up to three scenarios. Delete an old scenario to save another.")
        cursor = conn.execute("INSERT INTO farm_tool_record(user_id, kind, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", (user["id"], kind, json.dumps(data, ensure_ascii=False), now, now))
        record_id = cursor.lastrowid
        conn.commit()
    return {"id": record_id, "kind": kind, **data, "created_at": now, "updated_at": now, "data_status": "USER ENTERED"}


@app.put("/api/farm-tools/{kind}/{record_id}")
def update_farm_tool_record(kind: str, record_id: int, payload: FarmToolRecordRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    user = _authenticated_user(authorization)
    data = _farm_tool_validate(kind, payload.data)
    now = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute("UPDATE farm_tool_record SET payload = ?, updated_at = ? WHERE id = ? AND user_id = ? AND kind = ?", (json.dumps(data, ensure_ascii=False), now, record_id, user["id"], kind))
        if cursor.rowcount == 0: raise HTTPException(status_code=404, detail="Record not found.")
        conn.commit()
    return {"id": record_id, "kind": kind, **data, "updated_at": now, "data_status": "USER ENTERED"}


@app.delete("/api/farm-tools/{kind}/{record_id}")
def delete_farm_tool_record(kind: str, record_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    user = _authenticated_user(authorization)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute("DELETE FROM farm_tool_record WHERE id = ? AND user_id = ? AND kind = ?", (record_id, user["id"], kind))
        if cursor.rowcount == 0: raise HTTPException(status_code=404, detail="Record not found.")
        conn.commit()
    return {"status": "deleted", "id": record_id}


@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int) -> Dict[str, Any]:
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute("UPDATE notification SET read = 1 WHERE id = ?", (notification_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        conn.commit()
    return {"status": "read", "id": notification_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
