import os
import re
import time
import json
from datetime import datetime
from io import BytesIO
from numbers import Number
from pathlib import Path

import mysql.connector
import pandas as pd
import streamlit as st
from dotenv import dotenv_values

APP_TITLE = "Pulsecounter Offset Tool"

LOG_TABLE = "pulsecounterlog"
SLAVE_TABLE = "slavedevice"
DEVICE_TABLE = "device"
LOCATION_TABLE = "location"
BUILDINGTYPE_TABLE = "buildingtype"
DEVICETYPE_TABLE = "devicetype"
OFFSET_TABLE = "pulsecounteroffset"
SENDLIST_TABLE = "sendlist"

APP_FILE = Path(__file__).resolve()
APP_DIR = APP_FILE.parent
LOGO_PATH = APP_DIR / "logo_icy.svg"
OFFSET_CONVENTIONS_PATH = APP_DIR / "offset_conventions.json"
SCRIPTS_ROOT = APP_FILE.parents[3] if len(APP_FILE.parents) >= 4 else APP_DIR
DEFAULT_RUNTIME_LOG_DIR = Path.home() / "Documents" / "ICY-Logs"
RUNTIME_LOG_DIR = DEFAULT_RUNTIME_LOG_DIR
RUNTIME_LOG_PATH = RUNTIME_LOG_DIR / "pulse_counter_offset_tool.log"

ENV_PATHS = [
    SCRIPTS_ROOT / "Toolkit" / ".env",
    SCRIPTS_ROOT / "DBscript" / ".env",
    SCRIPTS_ROOT / "python" / "DBscript" / ".env",
    APP_FILE.parents[1] / "DBscript" / ".env" if len(APP_FILE.parents) >= 2 else APP_DIR / ".env",
    APP_FILE.parents[2] / ".env" if len(APP_FILE.parents) >= 3 else APP_DIR / ".env",
    Path.cwd() / ".env",
    APP_DIR / ".env",
    APP_DIR / ".env.local",
]

LOADED_ENV_FILES = []
_seen_env_paths = set()
for env_path in ENV_PATHS:
    resolved_path = str(Path(env_path).resolve())
    if resolved_path in _seen_env_paths:
        continue
    _seen_env_paths.add(resolved_path)

    if Path(env_path).exists():
        env_values = dotenv_values(env_path)
        for key, value in env_values.items():
            if value is not None and str(value).strip() != "":
                os.environ[key] = str(value)
        LOADED_ENV_FILES.append(str(env_path))


DEVICETYPE_VARIABLES = {
    "PLE": {"meter_variable": "acu_kwh_meter", "meter_type_key": "electricity_import", "meter_type_label": "kWh meter", "meter_unit": "kWh"},
    "PLE8": {"meter_variable": "pl8_kwh_meter", "meter_type_key": "electricity_import", "meter_type_label": "kWh meter", "meter_unit": "kWh"},
    "PLEB": {"meter_variable": "acu_export_kwh_meter", "meter_type_key": "electricity_export", "meter_type_label": "Teruglevering kWh", "meter_unit": "kWh"},
    "PLG": {"meter_variable": "acu_gas_meter", "meter_type_key": "gas", "meter_type_label": "Gas meter m³", "meter_unit": "m³"},
    "PLG8": {"meter_variable": "pl8_gas_meter", "meter_type_key": "gas", "meter_type_label": "Gas meter m³", "meter_unit": "m³"},
    "PLW": {"meter_variable": "acu_water_meter", "meter_type_key": "water", "meter_type_label": "Water meter m³", "meter_unit": "m³"},
    "PLW8": {"meter_variable": "pl8_water_meter", "meter_type_key": "water", "meter_type_label": "Water meter m³", "meter_unit": "m³"},
    "PLHW": {"meter_variable": "acu_hot_water_meter", "meter_type_key": "hot_water", "meter_type_label": "Warmwater meter m³", "meter_unit": "m³"},
    "PLHGJ": {"meter_variable": "acu_heat_gj_meter", "meter_type_key": "heat_gj", "meter_type_label": "Warmtemeter GJ", "meter_unit": "GJ"},
    "PLHMWH": {"meter_variable": "acu_heat_mwh_meter", "meter_type_key": "heat_mwh", "meter_type_label": "Warmtemeter MWh", "meter_unit": "MWh"},
    "PLCGJ": {"meter_variable": "acu_cooling_gj_meter", "meter_type_key": "cooling_gj", "meter_type_label": "Koelmeter GJ", "meter_unit": "GJ"},
    "PLCMWH": {"meter_variable": "acu_cooling_mwh_meter", "meter_type_key": "cooling_mwh", "meter_type_label": "Koelmeter MWh", "meter_unit": "MWh"},
    "P1EL": {"meter_variable": "p1_electricity_low", "meter_type_key": "electricity_import_low", "meter_type_label": "P1 elektra laag", "meter_unit": "kWh"},
    "P1EH": {"meter_variable": "p1_electricity_high", "meter_type_key": "electricity_import_high", "meter_type_label": "P1 elektra hoog", "meter_unit": "kWh"},
    "P1BEL": {"meter_variable": "p1_export_low", "meter_type_key": "electricity_export_low", "meter_type_label": "P1 teruglever laag", "meter_unit": "kWh"},
    "P1BEH": {"meter_variable": "p1_export_high", "meter_type_key": "electricity_export_high", "meter_type_label": "P1 teruglever hoog", "meter_unit": "kWh"},
    "P1GAS": {"meter_variable": "p1_gas_meter", "meter_type_key": "gas", "meter_type_label": "P1 gasmeter", "meter_unit": "m³"},
    "CAMPSLAVE": {"meter_variable": "campere_meter", "meter_type_key": "camping", "meter_type_label": "Campère meter", "meter_unit": "kWh"},
    "CAMPCTRL": {"meter_variable": "campere_controller", "meter_type_key": "controller", "meter_type_label": "ICY4942 Campère controller", "meter_unit": ""},
    "CAMPEREMOD": {"meter_variable": "campere_module", "meter_type_key": "camping", "meter_type_label": "ICY4518 Campère module", "meter_unit": "kWh"},
    "CAMPEREWS": {"meter_variable": "campere_wall_socket", "meter_type_key": "camping", "meter_type_label": "ICY4518 Campère wall socket", "meter_unit": "kWh"},
    "PRMKWH": {"meter_variable": "prm_kwh_meter", "meter_type_key": "electricity_import", "meter_type_label": "PRM kWh meter", "meter_unit": "kWh"},
    "PRMWATER": {"meter_variable": "prm_water_meter", "meter_type_key": "water", "meter_type_label": "PRM watermeter", "meter_unit": "m³"},
    "PRMGAS": {"meter_variable": "prm_gas_meter", "meter_type_key": "gas", "meter_type_label": "PRM gasmeter", "meter_unit": "m³"},
    "PRMEXPORTKWH": {"meter_variable": "prm_export_kwh_meter", "meter_type_key": "electricity_export", "meter_type_label": "PRM teruglever kWh meter", "meter_unit": "kWh"},
    "PRMDHKWH": {"meter_variable": "prm_heat_kwh_meter", "meter_type_key": "heat_kwh", "meter_type_label": "PRM stadswarmte kWh", "meter_unit": "kWh"},
    "PRMDHGJ": {"meter_variable": "prm_heat_gj_meter", "meter_type_key": "heat_gj", "meter_type_label": "PRM stadswarmte GJ", "meter_unit": "GJ"},
    "PRMEXPORTM3": {"meter_variable": "prm_export_m3_meter", "meter_type_key": "export_m3", "meter_type_label": "PRM export m³", "meter_unit": "m³"},
    "PRMEXPORTGJ": {"meter_variable": "prm_export_gj_meter", "meter_type_key": "export_gj", "meter_type_label": "PRM export GJ", "meter_unit": "GJ"},
    "PRMPRODUCTIONKWH": {"meter_variable": "prm_production_kwh_meter", "meter_type_key": "production_kwh", "meter_type_label": "PRM productie kWh", "meter_unit": "kWh"},
    "PRMPRODUCTIONM3": {"meter_variable": "prm_production_m3_meter", "meter_type_key": "production_m3", "meter_type_label": "PRM productie m³", "meter_unit": "m³"},
    "PRMPRODUCTIONGJ": {"meter_variable": "prm_production_gj_meter", "meter_type_key": "production_gj", "meter_type_label": "PRM productie GJ", "meter_unit": "GJ"},
    "PRMHOTWATER": {"meter_variable": "prm_hot_water_meter", "meter_type_key": "hot_water", "meter_type_label": "PRM warmwatermeter", "meter_unit": "m³"},
    "PRMCAMPERE": {"meter_variable": "prm_campere_meter", "meter_type_key": "camping", "meter_type_label": "PRM campère meter", "meter_unit": "kWh"},
    "PRMWATERTAP": {"meter_variable": "prm_watertap_meter", "meter_type_key": "water", "meter_type_label": "PRM watertapmeter", "meter_unit": "m³"},
}

PERSISTED_STATE_DEFAULTS = {
    "db_host_override": "auto",
    "db_host_manual": "",
    "db_name": "",
    "db_user": "",
    "user_initials": "",
    "location_filter": "",
    "device_filter": "",
    "slave_filter": "",
    "mid_filter": "Alle meters",
    "selected_location": "Alle locaties",
    "search_text": "",
    "db_ready": False,
    "current_record_index": 0,
}

URL_SAFE_STATE_KEYS = {
    "mid_filter",
    "selected_location",
    "current_record_index",
}

ENV_BACKED_STATE_KEYS = {
    "db_host_manual": "DB_HOST",
    "db_name": "DB_NAME",
    "db_user": "DB_USER",
    "db_password": "DB_PASSWORD",
    "user_initials": "USER_INITIALS",
}

MID_PROTECTED_METER_MESSAGE = "Offsets voor MID gecertificeerde ICY 4850 Campère meters zijn geblokkeerd. Tonen mag wel, aanpassen niet."
MID_PROTECTED_DEVICETYPE_CODES = {
    "campslave",
    "campctrl",
}

DEFAULT_OFFSET_CONVENTIONS = {
    "additive_devicetype_codes": ["CAMPEREWS", "CAMPEREMOD", "PRMCAMPERE"],
    "additive_meter_variables": ["campere_wall_socket", "campere_module", "prm_campere_meter"],
    "subtract_devicetype_codes": [],
    "subtract_meter_variables": [],
    "factor_overrides": [
        {
            "deviceid": "14",
            "slavedeviceid": "55",
            "factor": 5.0,
            "note": "Confirmed ICY4940/ICY5247 Campere factor convention on 2026-08-25.",
        }
    ],
}


def _normalize_convention_items(values):
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {normalize_protection_text(value) for value in values if normalize_protection_text(value)}


def load_offset_conventions():
    conventions = dict(DEFAULT_OFFSET_CONVENTIONS)
    try:
        if OFFSET_CONVENTIONS_PATH.exists():
            with OFFSET_CONVENTIONS_PATH.open("r", encoding="utf-8") as fh:
                configured = json.load(fh)
            if isinstance(configured, dict):
                conventions.update({key: value for key, value in configured.items() if value is not None})
    except Exception as exc:
        write_runtime_log(f"Offsetconventie-config kon niet worden gelezen; standaardregels gebruikt: {exc}", level="WARN")
    return conventions


def get_offset_factor_override(device_id="", slave_id=""):
    """Return the confirmed offset-factor override for this exact device/slave pair, or None otherwise."""
    key = (normalize_id_value(device_id), normalize_id_value(slave_id))
    for override in load_offset_conventions().get("factor_overrides", []):
        if not isinstance(override, dict):
            continue
        override_key = (
            normalize_id_value(override.get("deviceid", "")),
            normalize_id_value(override.get("slavedeviceid", "")),
        )
        if override_key == key:
            try:
                return float(override.get("factor"))
            except (TypeError, ValueError):
                return None
    return None


def get_offset_mode(row=None, devicetype_code="", meter_variable=""):
    """Return how the regular stored offset should be applied for this meter."""
    if row is not None:
        devicetype_code = row.get("devicetype_code", row.get("devicename", devicetype_code))
        meter_variable = row.get("meter_variable", meter_variable)

    code = normalize_protection_text(devicetype_code)
    variable = normalize_protection_text(meter_variable)
    conventions = load_offset_conventions()
    subtract_codes = _normalize_convention_items(conventions.get("subtract_devicetype_codes", []))
    subtract_variables = _normalize_convention_items(conventions.get("subtract_meter_variables", []))
    if code in subtract_codes or variable in subtract_variables:
        return "subtract"

    additive_codes = _normalize_convention_items(conventions.get("additive_devicetype_codes", []))
    additive_variables = _normalize_convention_items(conventions.get("additive_meter_variables", []))
    if code in additive_codes or variable in additive_variables:
        return "add"
    return "subtract"


def normalize_protection_text(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().lower().replace("è", "e").replace("é", "e")


def is_offset_edit_blocked(row):
    if row is None:
        return False

    values = {
        "meter_type_label": normalize_protection_text(row.get("meter_type_label", "")),
        "devicetype_name": normalize_protection_text(row.get("devicetype_name", "")),
        "devicetype_code": normalize_protection_text(row.get("devicetype_code", row.get("devicename", ""))),
        "meter_variable": normalize_protection_text(row.get("meter_variable", "")),
        "meter_type_key": normalize_protection_text(row.get("meter_type_key", "")),
        "device_name": normalize_protection_text(row.get("device_name", "")),
        "icyname": normalize_protection_text(row.get("icyname", "")),
    }

    combined = " ".join(values.values())

    explicitly_not_blocked = any(token in combined for token in [
        "icy4518",
        "icy5247",
        "prm",
        "campere module",
        "campere wall socket",
    ])
    if explicitly_not_blocked:
        return False

    has_4850_marker = "icy4850" in combined or "4850" in combined
    has_protected_code = values["devicetype_code"] in MID_PROTECTED_DEVICETYPE_CODES

    return has_protected_code or has_4850_marker


def parse_persisted_state_value(key, value):
    if isinstance(value, list):
        value = value[0] if value else ""

    if key == "db_ready":
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    if key == "current_record_index":
        try:
            return max(0, int(float(str(value).strip() or "0")))
        except Exception:
            return 0

    return "" if value is None else str(value).strip()


def build_persisted_state(state):
    persisted = {}
    for key in URL_SAFE_STATE_KEYS:
        default_value = PERSISTED_STATE_DEFAULTS.get(key, "")
        value = parse_persisted_state_value(key, state.get(key, default_value))

        if key == "current_record_index":
            persisted[key] = str(value)
        elif value != "":
            persisted[key] = value

    return persisted


def restore_persisted_state():
    try:
        query_params = st.query_params
    except Exception:
        query_params = {}

    for key, default_value in PERSISTED_STATE_DEFAULTS.items():
        raw_value = query_params.get(key, default_value) if key in URL_SAFE_STATE_KEYS else default_value
        parsed_value = parse_persisted_state_value(key, raw_value)

        if parsed_value in {"", None} and key in ENV_BACKED_STATE_KEYS:
            env_value = cfg(ENV_BACKED_STATE_KEYS[key], default_value)
            parsed_value = parse_persisted_state_value(key, env_value)
            if key == "user_initials":
                parsed_value = str(parsed_value).upper()

        if key not in st.session_state:
            st.session_state[key] = parsed_value

    db_password_value = st.session_state.get("db_password", "") or cfg("DB_PASSWORD", "")
    st.session_state["db_password"] = db_password_value

    if "manual" not in st.session_state:
        st.session_state["manual"] = None
    if "batch_staging" not in st.session_state:
        st.session_state["batch_staging"] = []


def sync_persisted_state():
    try:
        query_params = st.query_params
    except Exception:
        return

    target = build_persisted_state(st.session_state)
    current = {}
    for key in URL_SAFE_STATE_KEYS:
        if key in query_params:
            current[key] = parse_persisted_state_value(key, query_params.get(key))

    normalized_target = {key: parse_persisted_state_value(key, value) for key, value in target.items()}

    if current != normalized_target:
        query_params.clear()
        for key, value in target.items():
            query_params[key] = value


# =========================
# DB
# =========================

def cfg(key, default=""):
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


def get_available_db_hosts():
    hosts = []
    for host in [
        st.session_state.get("db_host_manual", ""),
        cfg("DB_HOST", ""),
        cfg("DB_HOST2", ""),
    ]:
        host = str(host).strip()
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def normalize_id_series(series):
    if not isinstance(series, pd.Series):
        series = pd.Series(series)
    return (
        series.fillna("")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .replace(r"^(?i:nan|none|<na>|null)$", "", regex=True)
    )


def ensure_series(value, index, default=""):
    if isinstance(value, pd.Series):
        return value.reindex(index)
    if value is None:
        value = default
    return pd.Series([value] * len(index), index=index)


def normalize_meterdivider_series(value, index):
    divider = pd.to_numeric(ensure_series(value, index, 1), errors="coerce").fillna(1)
    divider = divider.where(divider.ne(0), 1).abs()
    return divider


def get_normalized_meterdivider(value, default=1.0):
    try:
        divider = abs(float(value))
    except (TypeError, ValueError):
        return float(default)
    if divider == 0:
        return float(default)
    return divider


def calculate_effective_reading(raw_value, offset_value_raw=0, meterdivider=1, offset_factor=None, offset_mode="subtract"):
    """Calculate the displayed (effective) meter reading.

    Default subtract convention:
        effective = (raw_value - offset_value_raw) / meterdivider

    Additive convention, used by confirmed Campère Plug/module meters:
        effective = (raw_value + offset_value_raw) / meterdivider

    - `raw_value` is the stored raw counter (pulses/ticks).
    - `offset_value_raw` is the stored baseline/correction in raw units.
    - `meterdivider` scales raw -> displayed units (displayed = raw / meterdivider).

    Override (ICY factor) convention, when `offset_factor` is given (see OFFSET_FACTOR_OVERRIDES):
        effective = (raw_value / meterdivider) + offset_factor * offset_value_raw

    Here the stored offset is already in "kWh / offset_factor" units, unrelated to meterdivider.

    Notes / edge cases:
    - `meterdivider` is normalized to a positive non-zero value (defaults to 1).
    - If inputs are None/NaN they are treated as 0.
    - Returns a float representing the displayed meter value.
    """
    divider = get_normalized_meterdivider(meterdivider)
    if offset_factor:
        return (float(raw_value or 0) / divider) + (float(offset_factor) * float(offset_value_raw or 0))
    if offset_mode == "add":
        return (float(raw_value or 0) + float(offset_value_raw or 0)) / divider
    return (float(raw_value or 0) - float(offset_value_raw or 0)) / divider


def calculate_new_offset_raw(desired_meter_reading, raw_value, meterdivider=1, offset_factor=None, offset_mode="subtract"):
    """Compute the offset that must be stored so the displayed reading equals `desired_meter_reading`.

    Default subtract convention:
        desired = (raw_value - new_offset_raw) / meterdivider
        => new_offset_raw = raw_value - desired * meterdivider

    Additive convention, used by confirmed Campère Plug/module meters:
        desired = (raw_value + new_offset_raw) / meterdivider
        => new_offset_raw = desired * meterdivider - raw_value

    Override (ICY factor) convention, when `offset_factor` is given (see OFFSET_FACTOR_OVERRIDES):
        desired = (raw_value / meterdivider) + offset_factor * new_offset
        => new_offset = (desired - raw_value / meterdivider) / offset_factor

    Behaviour:
    - `desired_meter_reading` must be provided (None/NaN is rejected).
    - `meterdivider` is normalized to a positive non-zero value.
    - The returned value is suitable to write directly to the DB `offset` column.

    Example (default convention):
    - raw_value=3406060, meterdivider=1000, desired=0.634
      new_offset_raw = 3406060 - 0.634*1000 = 3405426
    """
    divider = get_normalized_meterdivider(meterdivider)
    if desired_meter_reading is None or pd.isna(desired_meter_reading):
        return 0.0
    if offset_factor:
        return (float(desired_meter_reading) - (float(raw_value or 0) / divider)) / float(offset_factor)
    if offset_mode == "add":
        return (float(desired_meter_reading) * divider) - float(raw_value or 0)
    return float(raw_value or 0) - (float(desired_meter_reading) * divider)


def calculate_target_meter_reading(input_value, current_effective_reading=0, adjustment_mode="set"):
    value = float(input_value or 0)
    if adjustment_mode == "add":
        return float(current_effective_reading or 0) + value
    return value


def get_default_initials():
    return str(cfg("USER_INITIALS", "")).strip().upper()


def build_comment_value():
    initials = str(st.session_state.get("user_initials", "")).strip().upper()
    if not initials:
        raise ValueError("Initialen zijn verplicht.")
    date_part = datetime.now().strftime("%d-%m-%Y")
    return f"{date_part} {initials}"


def build_record_reference(record):
    if record is None:
        return "onbekend record"
    get_value = record.get if hasattr(record, "get") else lambda key, default="": default
    slave_id = str(get_value("slavedeviceid", "")).strip()
    device_id = str(get_value("deviceid", "")).strip()
    channel = str(get_value("channel", "")).strip()
    parts = []
    if slave_id:
        parts.append(f"slavedeviceid={slave_id}")
    if device_id:
        parts.append(f"deviceid={device_id}")
    if channel:
        parts.append(f"channel={channel}")
    return ", ".join(parts) if parts else "onbekend record"


def get_runtime_log_path():
    runtime_log_path = Path(RUNTIME_LOG_PATH)
    if os.getenv("PYTEST_CURRENT_TEST") and runtime_log_path == (DEFAULT_RUNTIME_LOG_DIR / "pulse_counter_offset_tool.log"):
        runtime_log_path = APP_DIR / ".pytest-logs" / "pulse_counter_offset_tool.log"
    return runtime_log_path


def start_batch_log(label="Batch opslaan"):
    try:
        runtime_log_path = get_runtime_log_path()
        runtime_log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with runtime_log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"=== BATCH START {timestamp} | {label} ===\n")
    except Exception:
        pass


def write_runtime_log(message, level="INFO", record=None):
    try:
        runtime_log_path = get_runtime_log_path()
        runtime_log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record_ref = build_record_reference(record)
        line = f"[{timestamp}] [{level}] {message} | {record_ref}\n"
        with runtime_log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception:
        pass


def read_runtime_log_tail(max_lines=200):
    try:
        runtime_log_path = get_runtime_log_path()
        if not runtime_log_path.exists():
            return "Nog geen logregels beschikbaar."
        lines = runtime_log_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return "Nog geen logregels beschikbaar."
        batch_start_indexes = [index for index, line in enumerate(lines) if line.startswith("=== BATCH START ")]
        if batch_start_indexes:
            lines = lines[batch_start_indexes[-1]:]
        return "\n".join(lines[-max_lines:]) if lines else "Nog geen logregels beschikbaar."
    except Exception:
        return "Log kon niet worden gelezen."


def _collect_catalog_debug_snapshot(log_df, latest_df, merged_df):
    """Collect compact debug info for the currently filtered device/slave.

    This helps diagnose cases where the selected catalog reading differs from the
    most recent raw pulsecounterlog value.
    """
    try:
        device_filter = normalize_id_value(st.session_state.get("device_filter", ""))
        slave_filter = normalize_id_value(st.session_state.get("slave_filter", ""))
    except Exception:
        device_filter = ""
        slave_filter = ""

    if not device_filter and not slave_filter:
        st.session_state["catalog_debug"] = None
        return

    def _apply_filters(df):
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()
        subset = df.copy()
        if "deviceid" in subset.columns and device_filter:
            subset = subset[normalize_id_series(subset["deviceid"]) == device_filter]
        if "slavedeviceid" in subset.columns and slave_filter:
            subset = subset[normalize_id_series(subset["slavedeviceid"]) == slave_filter]
        return subset

    log_subset = _apply_filters(log_df)
    latest_subset = _apply_filters(latest_df)
    merged_subset = _apply_filters(merged_df)

    log_cols = [col for col in ["pulsecounterlogid", "deviceid", "slavedeviceid", "channel", "value", "timestamp", "last_reading_timestamp_sort", "latest_row_order", "record_key"] if col in log_subset.columns]
    latest_cols = [col for col in ["pulsecounterlogid", "deviceid", "slavedeviceid", "channel", "value", "timestamp", "last_reading_timestamp_sort", "latest_row_order", "record_key"] if col in latest_subset.columns]
    merged_cols = [col for col in ["deviceid", "slavedeviceid", "channel", "raw_value", "raw_reading", "meterdivider", "offset_value_raw", "current_offset", "effective_reading", "last_reading_timestamp", "last_reading_timestamp_sort", "record_key"] if col in merged_subset.columns]

    if not log_subset.empty:
        log_subset = log_subset.sort_values(
            by=[col for col in ["last_reading_timestamp_sort", "latest_row_order", "pulsecounterlogid"] if col in log_subset.columns],
            ascending=True,
            na_position="last",
        )
    if not latest_subset.empty:
        latest_subset = latest_subset.sort_values(
            by=[col for col in ["last_reading_timestamp_sort", "latest_row_order", "pulsecounterlogid"] if col in latest_subset.columns],
            ascending=True,
            na_position="last",
        )
    if not merged_subset.empty and "last_reading_timestamp_sort" in merged_subset.columns:
        merged_subset = merged_subset.sort_values(by=["last_reading_timestamp_sort"], ascending=True, na_position="last")

    snapshot = {
        "filters": {
            "deviceid": device_filter,
            "slavedeviceid": slave_filter,
        },
        "log_tail": log_subset[log_cols].tail(8).to_dict("records") if log_cols else [],
        "latest_tail": latest_subset[latest_cols].tail(8).to_dict("records") if latest_cols else [],
        "merged_tail": merged_subset[merged_cols].tail(8).to_dict("records") if merged_cols else [],
        "counts": {
            "log_rows": int(len(log_subset)),
            "latest_rows": int(len(latest_subset)),
            "merged_rows": int(len(merged_subset)),
        },
    }
    st.session_state["catalog_debug"] = snapshot

    if snapshot["log_tail"] and snapshot["merged_tail"]:
        newest_log = snapshot["log_tail"][-1]
        newest_merged = snapshot["merged_tail"][-1]
        write_runtime_log(
            f"Catalog debug: nieuwste log value={newest_log.get('value', '')} @ {newest_log.get('timestamp', '')}; geselecteerde raw_value={newest_merged.get('raw_value', '')}, raw_reading={newest_merged.get('raw_reading', '')}, divider={newest_merged.get('meterdivider', '')}.",
            level="INFO",
            record={"deviceid": device_filter, "slavedeviceid": slave_filter},
        )


def to_plain_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def clean_display_text(value):
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "<na>", "null"}:
        return ""
    if text in {"0", "0.0", "0.00", "0.000"}:
        return ""
    return text


def normalize_display_text_series(value, index):
    series = ensure_series(value, index, "")
    return series.map(clean_display_text)


def normalize_searchable_text(value):
    text = clean_display_text(value).lower()
    text = re.sub(r"[-_/|]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_searchable_text_series(value, index):
    series = ensure_series(value, index, "")
    return series.map(normalize_searchable_text)


def get_meter_type_variables(devicetypeid="", devicename="", icyname="", metertype=""):
    def clean_text(value):
        return clean_display_text(value)

    devicetypeid = normalize_id_series([devicetypeid]).iloc[0]
    devicename = clean_text(devicename).upper()
    icyname = clean_text(icyname)
    metertype = clean_text(metertype)

    info = DEVICETYPE_VARIABLES.get(devicename, {}).copy()

    fallback_label = icyname or devicename or metertype or (f"Devicetype {devicetypeid}" if devicetypeid else "Onbekend metertype")

    if not info:
        info = {
            "meter_variable": f"devicetype_{devicetypeid}" if devicetypeid else "unknown_meter",
            "meter_type_key": devicename.lower() if devicename else "unknown",
            "meter_type_label": fallback_label,
            "meter_unit": "",
        }

    info["devicetype_code"] = devicename or devicetypeid
    display_label = info.get("meter_type_label") or fallback_label
    if icyname and display_label and icyname.strip().lower() != display_label.strip().lower():
        info["devicetype_name"] = f"{icyname} - {display_label}"
    else:
        info["devicetype_name"] = display_label or icyname or fallback_label
    return info


def get_text_series(df, column_name):
    if not isinstance(df, pd.DataFrame):
        return pd.Series(dtype="object")
    if column_name in df.columns:
        return ensure_series(df[column_name], df.index, "").fillna("").astype(str)
    return pd.Series([""] * len(df), index=df.index, dtype="object")


def format_table_value(value):
    if value is None or pd.isna(value):
        return ""

    if isinstance(value, bool):
        return value

    if isinstance(value, Number):
        numeric = float(value)
        if abs(numeric - round(numeric)) < 1e-12:
            return str(int(round(numeric)))
        return f"{numeric:.6f}".rstrip("0").rstrip(".")

    return value


def dataframe_to_excel_bytes(sheets):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            safe_name = str(sheet_name)[:31] or "Sheet"
            sheet_df = df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
            sheet_df.to_excel(writer, index=False, sheet_name=safe_name)
    return buffer.getvalue()


def append_session_audit(action, record=None, **details):
    try:
        get_value = record.get if hasattr(record, "get") else lambda key, default="": default
        row = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "deviceid": normalize_id_value(details.pop("deviceid", get_value("deviceid", ""))),
            "slavedeviceid": normalize_id_value(details.pop("slavedeviceid", get_value("slavedeviceid", ""))),
            "channel": normalize_id_value(details.pop("channel", get_value("channel", ""))),
            "location_label": get_value("location_label", ""),
            "meter_type_label": get_value("meter_type_label", ""),
        }
        row.update(details)
        st.session_state.setdefault("session_audit", []).append(row)
    except Exception:
        pass


def get_session_audit_df():
    audit_rows = st.session_state.get("session_audit", [])
    return pd.DataFrame(audit_rows) if audit_rows else pd.DataFrame()


def get_batch_preview_display_df(df):
    if not isinstance(df, pd.DataFrame):
        return df

    visible_columns = [
        "deviceid",
        "slavedeviceid",
        "channel",
        "new_meter_reading",
        "new_meterdivider",
        "match_status",
        "location_label",
        "meter_type_label",
        "raw_reading",
        "current_offset",
        "effective_reading",
        "resulting_effective_reading",
        "new_offset",
    ]
    available_columns = [col for col in visible_columns if col in df.columns]
    return df[available_columns].copy() if available_columns else df.copy()


def get_refresh_status_display_df(statuses):
    if not statuses:
        return pd.DataFrame()
    df = pd.DataFrame(statuses)
    visible_columns = [
        "status",
        "deviceid",
        "slavedeviceid",
        "channel",
        "previous_raw_value",
        "new_raw_value",
        "stored_offset_raw",
        "expected_effective",
        "actual_effective",
        "effective_diff",
        "pulsecounterlogid",
        "timestamp",
    ]
    available_columns = [col for col in visible_columns if col in df.columns]
    return df[available_columns].copy()


def get_batch_staging_editor_df(rows):
    desired_columns = ["deviceid", "slavedeviceid", "new_meter_reading", "new_meterdivider"]

    if isinstance(rows, pd.DataFrame):
        df = rows.copy()
    elif isinstance(rows, list):
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(columns=desired_columns)

    for col in desired_columns:
        if col not in df.columns:
            df[col] = None if col == "new_meter_reading" else (1 if col == "new_meterdivider" else "")

    df = df[desired_columns].copy()
    for col in ["deviceid", "slavedeviceid"]:
        df[col] = normalize_id_series(df[col])

    df["new_meter_reading"] = pd.to_numeric(df["new_meter_reading"], errors="coerce")
    df["new_meterdivider"] = pd.to_numeric(df["new_meterdivider"], errors="coerce").fillna(1)
    df["new_meterdivider"] = df["new_meterdivider"].where(df["new_meterdivider"].ne(0), 1).abs()
    return df


def normalize_id_value(value):
    series = normalize_id_series(pd.Series([value]))
    return str(series.iloc[0]) if not series.empty else ""


def build_batch_staging_key(record):
    if record is None:
        return ("", "", "")
    return (
        normalize_id_value(record.get("deviceid", "")),
        normalize_id_value(record.get("slavedeviceid", "")),
        normalize_id_value(record.get("channel", "")),
    )


def build_batch_staging_row(record, desired_meter_reading=None, new_meterdivider=None):
    if record is None:
        raise ValueError("Geen record geselecteerd om toe te voegen aan de batchwachtrij.")
    if is_offset_edit_blocked(record):
        raise ValueError(MID_PROTECTED_METER_MESSAGE)

    device_id, slave_id, channel = build_batch_staging_key(record)
    if not device_id and not slave_id:
        raise ValueError("Het geselecteerde record mist een DeviceID en SlavedeviceID.")

    divider_value = new_meterdivider
    if divider_value is None or divider_value == "" or pd.isna(divider_value):
        divider_value = record.get("new_meterdivider", record.get("meterdivider", record.get("current_meterdivider", 1)))

    desired_value = desired_meter_reading
    if desired_value is None or (isinstance(desired_value, str) and desired_value.strip() == "") or pd.isna(desired_value):
        desired_value = ""

    staged_row = {
        "deviceid": device_id,
        "slavedeviceid": slave_id,
        "channel": channel,
        "new_meter_reading": to_plain_value(desired_value) if desired_value != "" else "",
        "new_meterdivider": to_plain_value(get_normalized_meterdivider(divider_value)),
    }
    return staged_row


def upsert_batch_staging_rows(existing_rows, new_row):
    rows = []
    if isinstance(existing_rows, pd.DataFrame):
        rows = existing_rows.to_dict("records")
    elif isinstance(existing_rows, list):
        rows = [dict(row) for row in existing_rows]

    target_key = build_batch_staging_key(new_row)
    updated_rows = []
    replaced = False

    for row in rows:
        row_key = build_batch_staging_key(row)
        if row_key == target_key:
            if not replaced:
                updated_rows.append(dict(new_row))
                replaced = True
        else:
            updated_rows.append(dict(row))

    if not replaced:
        updated_rows.append(dict(new_row))

    return updated_rows, "updated" if replaced else "added"


def build_batch_staging_rows_from_df(df, existing_rows=None):
    if isinstance(existing_rows, pd.DataFrame):
        staged_rows = existing_rows.to_dict("records")
    elif isinstance(existing_rows, list):
        staged_rows = [dict(row) for row in existing_rows]
    else:
        staged_rows = []

    added_count = 0
    updated_count = 0
    blocked_count = 0

    if not isinstance(df, pd.DataFrame) or df.empty:
        return staged_rows, added_count, updated_count, blocked_count

    for _, record in df.iterrows():
        try:
            staged_row = build_batch_staging_row(record)
            staged_rows, action = upsert_batch_staging_rows(staged_rows, staged_row)
            if action == "updated":
                updated_count += 1
            else:
                added_count += 1
        except ValueError as exc:
            if MID_PROTECTED_METER_MESSAGE in str(exc):
                blocked_count += 1
            else:
                raise

    return staged_rows, added_count, updated_count, blocked_count


def render_static_table(df, max_height=460):
    if df is None:
        return

    safe_df = df.copy()
    for col in safe_df.columns:
        safe_df[col] = safe_df[col].map(format_table_value)
    safe_df = safe_df.fillna("")

    table_html = safe_df.to_html(index=False, escape=False)
    st.markdown(
        f'<div class="icy-static-table" style="max-height: {int(max_height)}px;">{table_html}</div>',
        unsafe_allow_html=True,
    )


def db_config(database_name=None, host=None):
    hosts = get_available_db_hosts()
    manual_host = str(st.session_state.get("db_host_manual", "")).strip()
    fallback_host = host or manual_host or (hosts[0] if hosts else "")
    return {
        "host": fallback_host,
        "port": int(st.session_state.get("db_port", cfg("DB_PORT", "3306"))),
        "user": str(st.session_state.get("db_user", "")).strip() or cfg("DB_USER", "root"),
        "password": st.session_state.get("db_password", "") or cfg("DB_PASSWORD", ""),
        "database": database_name or str(st.session_state.get("db_name", "")).strip() or cfg("DB_NAME", ""),
    }


def conn(database_name=None):
    selected_host = st.session_state.get("db_host_override", "auto")
    manual_host = str(st.session_state.get("db_host_manual", "")).strip()
    hosts = get_available_db_hosts()

    if manual_host:
        hosts = [manual_host] + [host for host in hosts if host != manual_host]

    if selected_host and selected_host != "auto":
        hosts = [selected_host]

    if not hosts:
        raise ValueError("Database host ontbreekt. Vul een host in bij de database-instellingen of zet DB_HOST in de .env.")

    errors = []
    for host in hosts:
        c = db_config(database_name, host=host)
        if not c["database"]:
            raise ValueError("Database naam ontbreekt")
        try:
            connection = mysql.connector.connect(**c)
            st.session_state["active_db_host"] = host
            return connection
        except Exception as exc:
            errors.append(f"{host}: {exc}")

    raise ConnectionError("Geen verbinding mogelijk met de database hosts: " + " | ".join(errors))


# =========================
# LOAD
# =========================

@st.cache_data(ttl=60)
def load(table, database_name, host_choice="auto"):
    c = conn(database_name)
    cur = None
    try:
        cur = c.cursor(dictionary=True)
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        return pd.DataFrame(rows)
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        c.close()


def load_optional(table, database_name, host_choice="auto"):
    try:
        return load(table, database_name, host_choice)
    except Exception:
        return pd.DataFrame()


# =========================
# BUILD CATALOG (FIXED CORE)
# =========================

def build_catalog(log_df, slave_df, offset_df, device_df=None, location_df=None, buildingtype_df=None, devicetype_df=None):

    log_df = log_df.copy()
    slave_df = slave_df.copy()
    offset_df = offset_df.copy()
    device_df = device_df.copy() if isinstance(device_df, pd.DataFrame) else pd.DataFrame()
    location_df = location_df.copy() if isinstance(location_df, pd.DataFrame) else pd.DataFrame()
    buildingtype_df = buildingtype_df.copy() if isinstance(buildingtype_df, pd.DataFrame) else pd.DataFrame()
    devicetype_df = devicetype_df.copy() if isinstance(devicetype_df, pd.DataFrame) else pd.DataFrame()

    device_key = "deviceid"
    slave_key = "slavedeviceid"
    reading_col = "value"

    if reading_col not in log_df.columns:
        raise ValueError("Geen meterstand kolom")

    for df in [log_df, slave_df, offset_df, device_df, location_df, buildingtype_df, devicetype_df]:
        for col in ["deviceid", "slavedeviceid", "locationid", "buildingtypeid", "devicetypeid"]:
            if col in df.columns:
                df[col] = normalize_id_series(df[col])
        if "channel" in df.columns:
            df["channel"] = normalize_id_series(df["channel"])

    if device_key not in log_df.columns:
        log_df[device_key] = ""
    if slave_key not in log_df.columns:
        log_df[slave_key] = ""
    if "channel" not in log_df.columns:
        log_df["channel"] = ""

    log_df[reading_col] = pd.to_numeric(log_df[reading_col], errors="coerce")
    log_df["record_key"] = log_df[slave_key].where(log_df[slave_key].ne(""), log_df[device_key])

    if "timestamp" in log_df.columns:
        log_df["last_reading_timestamp_sort"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
    else:
        log_df["last_reading_timestamp_sort"] = pd.NaT

    if "pulsecounterlogid" in log_df.columns:
        log_df["latest_row_order"] = pd.to_numeric(log_df["pulsecounterlogid"], errors="coerce")
    else:
        log_df["latest_row_order"] = pd.Series(range(len(log_df)), index=log_df.index, dtype="int64")

    log_df = log_df.sort_values(
        by=["record_key", "channel", "last_reading_timestamp_sort", "latest_row_order"],
        ascending=[True, True, True, True],
        na_position="last",
        kind="stable",
    )

    latest = (
        log_df.dropna(subset=[reading_col])
        .drop_duplicates(subset=["record_key", "channel"], keep="last")
    )

    merged = latest.copy()
    merged["logged_deviceid"] = normalize_id_series(merged[device_key])

    if slave_key in slave_df.columns:
        slave_cols = [
            col for col in [
                slave_key,
                "deviceid",
                "locationid",
                "name",
                "slavedevicetypeid",
                "devicetypeid",
                "metertype",
                "meterdivider",
            ] if col in slave_df.columns
        ]
        if slave_cols:
            slave_lookup = slave_df[slave_cols].drop_duplicates(subset=[slave_key], keep="last").rename(
                columns={
                    "deviceid": "slave_parent_deviceid",
                    "locationid": "slave_locationid",
                    "name": "slave_name",
                    "slavedevicetypeid": "slave_slavedevicetypeid",
                    "devicetypeid": "slave_devicetypeid",
                    "metertype": "slave_metertype",
                    "meterdivider": "slave_meterdivider",
                }
            )
            merged = merged.merge(slave_lookup, on=slave_key, how="left")

    merged["deviceid"] = merged["logged_deviceid"]
    if "slave_parent_deviceid" in merged.columns:
        fallback_mask = merged["deviceid"].eq("")
        merged.loc[fallback_mask, "deviceid"] = merged.loc[fallback_mask, "slave_parent_deviceid"]
    merged["deviceid"] = normalize_id_series(merged["deviceid"])

    if device_key in device_df.columns:
        device_cols = [col for col in ["deviceid", "locationid", "name", "devicetypeid", "meterdivider"] if col in device_df.columns]
        if device_cols:
            device_lookup = device_df[device_cols].drop_duplicates(subset=[device_key], keep="last").rename(
                columns={
                    "locationid": "device_locationid",
                    "name": "device_name",
                    "devicetypeid": "device_devicetypeid",
                    "meterdivider": "device_meterdivider",
                }
            )
            merged = merged.merge(device_lookup, on="deviceid", how="left")

    if "slave_locationid" in merged.columns:
        merged["locationid"] = normalize_id_series(merged["slave_locationid"])
    if "device_locationid" in merged.columns:
        if "locationid" not in merged.columns:
            merged["locationid"] = normalize_id_series(merged["device_locationid"])
        else:
            merged["locationid"] = merged["locationid"].where(merged["locationid"].ne(""), normalize_id_series(merged["device_locationid"]))

    if "locationid" in merged.columns and "locationid" in location_df.columns:
        location_cols = [col for col in ["locationid", "locationname", "buildingtypeid"] if col in location_df.columns]
        if location_cols:
            merged = merged.merge(
                location_df[location_cols].drop_duplicates(subset=["locationid"], keep="last"),
                on="locationid",
                how="left",
                suffixes=("", "_location")
            )

    merged["devicetypeid"] = ""
    if "slave_slavedevicetypeid" in merged.columns:
        merged["devicetypeid"] = normalize_id_series(merged["slave_slavedevicetypeid"])
    if "slave_devicetypeid" in merged.columns:
        merged["devicetypeid"] = merged["devicetypeid"].where(
            merged["devicetypeid"].ne(""),
            normalize_id_series(merged["slave_devicetypeid"])
        )
    if "device_devicetypeid" in merged.columns:
        merged["devicetypeid"] = merged["devicetypeid"].where(
            merged["devicetypeid"].ne(""),
            normalize_id_series(merged["device_devicetypeid"])
        )

    if "buildingtypeid" in merged.columns and "buildingtypeid" in buildingtype_df.columns:
        building_cols = [col for col in ["buildingtypeid", "buildingname"] if col in buildingtype_df.columns]
        if building_cols:
            merged = merged.merge(
                buildingtype_df[building_cols].drop_duplicates(subset=["buildingtypeid"], keep="last"),
                on="buildingtypeid",
                how="left",
                suffixes=("", "_building")
            )

    if "devicetypeid" in merged.columns and "devicetypeid" in devicetype_df.columns:
        devicetype_cols = [col for col in ["devicetypeid", "devid", "devicename", "icyname"] if col in devicetype_df.columns]
        if devicetype_cols:
            merged = merged.merge(
                devicetype_df[devicetype_cols].drop_duplicates(subset=["devicetypeid"], keep="last"),
                on="devicetypeid",
                how="left",
                suffixes=("", "_devicetype")
            )

    if "device_devicetypeid" in merged.columns and "devicetypeid" in devicetype_df.columns:
        device_type_cols = [col for col in ["devicetypeid", "icyname", "devicename"] if col in devicetype_df.columns]
        if device_type_cols:
            device_type_lookup = devicetype_df[device_type_cols].drop_duplicates(subset=["devicetypeid"], keep="last").rename(
                columns={
                    "devicetypeid": "device_devicetypeid",
                    "icyname": "device_type_icyname",
                    "devicename": "device_type_name",
                }
            )
            merged = merged.merge(device_type_lookup, on="device_devicetypeid", how="left")

    if device_key in offset_df.columns or slave_key in offset_df.columns:
        offset_df["offset_value"] = pd.to_numeric(offset_df.get("offset"), errors="coerce")

        if slave_key in offset_df.columns and slave_key in merged.columns:
            slave_offsets = offset_df[[slave_key, "offset_value"]].copy()
            slave_offsets[slave_key] = normalize_id_series(slave_offsets[slave_key])
            slave_offsets = slave_offsets[slave_offsets[slave_key] != ""]
            slave_offsets = slave_offsets.drop_duplicates(subset=[slave_key], keep="last").rename(
                columns={"offset_value": "slave_offset_value"}
            )
            merged = merged.merge(slave_offsets, on=slave_key, how="left")

        if device_key in offset_df.columns and device_key in merged.columns:
            direct_offsets = offset_df[[device_key, slave_key, "offset_value"]].copy() if slave_key in offset_df.columns else offset_df[[device_key, "offset_value"]].copy()
            direct_offsets[device_key] = normalize_id_series(direct_offsets[device_key])
            if slave_key in direct_offsets.columns:
                direct_offsets[slave_key] = normalize_id_series(direct_offsets[slave_key])
                direct_offsets = direct_offsets[direct_offsets[slave_key] == ""]
                direct_offsets = direct_offsets.drop(columns=[slave_key])
            direct_offsets = direct_offsets[direct_offsets[device_key] != ""]
            direct_offsets = direct_offsets.drop_duplicates(subset=[device_key], keep="last").rename(
                columns={"offset_value": "device_offset_value"}
            )
            merged = merged.merge(direct_offsets, on=device_key, how="left")

        merged["offset_value"] = pd.to_numeric(merged.get("slave_offset_value"), errors="coerce")
        merged["offset_value"] = merged["offset_value"].combine_first(
            pd.to_numeric(merged.get("device_offset_value"), errors="coerce")
        )

    slave_meterdivider_series = pd.to_numeric(ensure_series(merged.get("slave_meterdivider", pd.NA), merged.index, pd.NA), errors="coerce")
    device_meterdivider_series = pd.to_numeric(ensure_series(merged.get("device_meterdivider", pd.NA), merged.index, pd.NA), errors="coerce")
    existing_meterdivider_series = pd.to_numeric(ensure_series(merged.get("meterdivider", pd.NA), merged.index, pd.NA), errors="coerce")
    merged["meterdivider"] = normalize_meterdivider_series(
        slave_meterdivider_series.combine_first(device_meterdivider_series).combine_first(existing_meterdivider_series).fillna(1),
        merged.index,
    )
    merged["raw_value"] = pd.to_numeric(ensure_series(merged.get(reading_col, 0), merged.index, 0), errors="coerce").fillna(0)
    merged["offset_value_raw"] = pd.to_numeric(ensure_series(merged.get("offset_value", 0), merged.index, 0), errors="coerce").fillna(0)
    merged["raw_reading"] = merged["raw_value"] / merged["meterdivider"]

    last_reading_timestamp = ensure_series(merged.get("timestamp", ""), merged.index, "").fillna("").astype(str).str.strip()
    merged["last_reading_timestamp"] = last_reading_timestamp.replace(r"^(?i:nat|nan|none|<na>|null)$", "", regex=True)
    merged["last_reading_timestamp_sort"] = pd.to_datetime(
        ensure_series(merged.get("last_reading_timestamp_sort", merged["last_reading_timestamp"]), merged.index, ""),
        errors="coerce",
    )

    merged[slave_key] = normalize_id_series(merged.get(slave_key, pd.Series([""] * len(merged), index=merged.index)))

    location_name = merged.get("locationname", pd.Series([""] * len(merged), index=merged.index))
    if not isinstance(location_name, pd.Series):
        location_name = pd.Series([location_name] * len(merged), index=merged.index)
    merged["locationname"] = normalize_display_text_series(location_name, merged.index)

    building_name = merged.get("buildingname", pd.Series([""] * len(merged), index=merged.index))
    if not isinstance(building_name, pd.Series):
        building_name = pd.Series([building_name] * len(merged), index=merged.index)
    merged["buildingname"] = normalize_display_text_series(building_name, merged.index)
    merged["location_label"] = (merged["buildingname"] + " - " + merged["locationname"]).str.strip(" -")
    merged.loc[merged["location_label"] == "", "location_label"] = merged["locationname"]

    device_name_series = normalize_display_text_series(merged.get("device_name", ""), merged.index)

    device_type_icy_series = normalize_display_text_series(merged.get("device_type_icyname", ""), merged.index)

    merged["device_name"] = device_name_series.where(device_name_series.ne(""), device_type_icy_series)

    fallback_name = normalize_display_text_series(
        merged.get("slave_name", merged.get("device_name", merged.get("name", ""))),
        merged.index,
    )

    merged.loc[merged["location_label"] == "", "location_label"] = fallback_name
    merged.loc[merged["location_label"] == "", "location_label"] = "Onbekende locatie"

    channel_series = merged.get("channel", pd.Series([""] * len(merged), index=merged.index))
    if not isinstance(channel_series, pd.Series):
        channel_series = pd.Series([channel_series] * len(merged), index=merged.index)
    merged["channel"] = channel_series.fillna("").astype(str).str.strip()

    merged["status"] = ""
    if "slave_parent_deviceid" in merged.columns:
        inferred_mask = merged["logged_deviceid"].eq("") & merged["slave_parent_deviceid"].notna()
        merged.loc[inferred_mask, "status"] = "Afgeleid via SlaveDeviceID"

        mismatch_mask = (
            merged["logged_deviceid"].ne("")
            & merged["slave_parent_deviceid"].notna()
            & (normalize_id_series(merged["logged_deviceid"]) != normalize_id_series(merged["slave_parent_deviceid"]))
        )
        merged.loc[mismatch_mask, "status"] = "Mismatch tussen log en slavedevice"

    if merged.empty:
        for col, default_value in {
            "meter_variable": "",
            "meter_type_key": "",
            "meter_type_label": "",
            "meter_unit": "",
            "devicetype_code": "",
            "devicetype_name": "",
        }.items():
            merged[col] = default_value
    else:
        meter_info_df = merged.apply(
            lambda row: pd.Series(
                get_meter_type_variables(
                    row.get("devicetypeid", ""),
                    row.get("devicename", ""),
                    row.get("icyname", ""),
                    row.get("slave_metertype", ""),
                )
            ),
            axis=1,
        )
        merged = pd.concat([merged, meter_info_df], axis=1)

    merged["offset_factor"] = merged.apply(
        lambda row: get_offset_factor_override(row.get("deviceid", ""), row.get("slavedeviceid", "")), axis=1
    )
    merged["offset_mode"] = merged.apply(get_offset_mode, axis=1)
    _offset_factor_num = pd.to_numeric(merged["offset_factor"], errors="coerce")
    _has_offset_factor = _offset_factor_num.notna() & (_offset_factor_num != 0)
    _additive_offset = merged["offset_mode"].eq("add")
    merged["current_offset"] = merged["offset_value_raw"] / merged["meterdivider"]
    merged["effective_reading"] = merged["raw_reading"] - merged["current_offset"]
    merged.loc[_additive_offset, "effective_reading"] = (
        merged.loc[_additive_offset, "raw_reading"] + merged.loc[_additive_offset, "current_offset"]
    )
    merged.loc[_has_offset_factor, "effective_reading"] = (
        merged.loc[_has_offset_factor, "raw_reading"]
        + _offset_factor_num[_has_offset_factor] * merged.loc[_has_offset_factor, "offset_value_raw"]
    )
    merged.loc[_has_offset_factor, "current_offset"] = (
        merged.loc[_has_offset_factor, "effective_reading"] - merged.loc[_has_offset_factor, "raw_reading"]
    )

    merged["display_name"] = merged["location_label"]
    merged.loc[merged["display_name"] == "", "display_name"] = fallback_name
    merged.loc[merged["display_name"] == "", "display_name"] = merged["deviceid"]

    merged["search_text"] = (
        normalize_searchable_text_series(merged.get("display_name", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("location_label", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("locationname", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("buildingname", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("deviceid", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get(slave_key, ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("channel", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("status", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("devicetype_code", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("devicetype_name", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("meter_type_label", ""), merged.index) + " " +
        normalize_searchable_text_series(merged.get("meter_variable", ""), merged.index)
    ).str.strip()

    active_link_mask = (
        get_text_series(merged, "deviceid").ne("") |
        get_text_series(merged, "slavedeviceid").isin(set(normalize_id_series(slave_df.get("slavedeviceid", pd.Series(dtype=str)))))
    )
    active_link_mask = active_link_mask & get_text_series(merged, "location_label").ne("Onbekende locatie")
    merged = merged[active_link_mask].copy()

    merged = merged.drop_duplicates(
        subset=["deviceid", "slavedeviceid", "channel"],
        keep="first"
    ).reset_index(drop=True)

    merged["offset_edit_blocked"] = merged.apply(is_offset_edit_blocked, axis=1)
    merged["offset_edit_status"] = merged["offset_edit_blocked"].apply(
        lambda blocked: "Geblokkeerd (MID Campère)" if blocked else "Toegestaan"
    )

    _collect_catalog_debug_snapshot(log_df, latest, merged)

    return merged


# =========================
# SAVE / DELETE OFFSET
# =========================

def find_existing_offset(cur, device_id=None, slave_id=None):
    if slave_id:
        device_id = None
        cur.execute(
            f"SELECT pulsecounteroffsetid FROM {OFFSET_TABLE} WHERE slavedeviceid = %s LIMIT 1",
            (slave_id,)
        )
    else:
        cur.execute(
            f"SELECT pulsecounteroffsetid FROM {OFFSET_TABLE} WHERE deviceid = %s AND (slavedeviceid IS NULL OR slavedeviceid = '') LIMIT 1",
            (device_id,)
        )
    return cur.fetchone(), device_id, slave_id


def find_orphaned_parent_offset(cur, device_id=None, slave_id=None):
    """Find a stale device-level offset row left over for a device that now has a slave-level offset.

    Without this, saving a slave-scoped offset can leave an older device-scoped offset row in
    place for the same physical device, so any consumer reading by deviceid alone (instead of
    combining slave-first like this tool does) can pick up the wrong, stale offset value.
    """
    if not slave_id or not device_id:
        return None
    cur.execute(
        f"SELECT pulsecounteroffsetid FROM {OFFSET_TABLE} WHERE deviceid = %s AND (slavedeviceid IS NULL OR slavedeviceid = '') LIMIT 1",
        (device_id,),
    )
    return cur.fetchone()


def scan_duplicate_offsets(database_name, host_choice="auto"):
    """Scan the whole pulsecounteroffset table for meters with more than one active offset row.

    Covers two cases: (1) multiple rows sharing the same slavedeviceid/deviceid+channel scope, and
    (2) a leftover device-level offset row that overlaps a slave-level offset for the same physical
    device. Returns (flagged_df, delete_ids) where delete_ids are the recommended rows to remove,
    always keeping the newest row (highest pulsecounteroffsetid) per meter scope.
    """
    c = conn(database_name)
    try:
        cur = c.cursor(dictionary=True)
        cur.execute(f"SELECT pulsecounteroffsetid, deviceid, slavedeviceid, channel, `offset`, comment FROM {OFFSET_TABLE}")
        offset_rows = cur.fetchall()
        cur.execute(f"SELECT slavedeviceid, deviceid FROM {SLAVE_TABLE}")
        slave_rows = cur.fetchall()
        cur.close()
    finally:
        c.close()

    offset_df = pd.DataFrame(offset_rows)
    if offset_df.empty:
        return pd.DataFrame(), []

    offset_df["deviceid"] = normalize_id_series(offset_df.get("deviceid"))
    offset_df["slavedeviceid"] = normalize_id_series(offset_df.get("slavedeviceid"))
    offset_df["channel"] = normalize_id_series(offset_df.get("channel"))

    slave_to_device = {}
    slave_df = pd.DataFrame(slave_rows)
    if not slave_df.empty:
        slave_df["slavedeviceid"] = normalize_id_series(slave_df.get("slavedeviceid"))
        slave_df["deviceid"] = normalize_id_series(slave_df.get("deviceid"))
        slave_to_device = dict(zip(slave_df["slavedeviceid"], slave_df["deviceid"]))

    offset_df["parent_deviceid"] = offset_df["slavedeviceid"].map(slave_to_device).fillna("")
    offset_df["scope_key"] = offset_df.apply(
        lambda row: f"slave:{row['slavedeviceid']}:{row['channel']}" if row["slavedeviceid"] else f"device:{row['deviceid']}:{row['channel']}",
        axis=1,
    )

    flagged = []

    for _, group in offset_df.groupby("scope_key"):
        if len(group) > 1:
            keep_id = group["pulsecounteroffsetid"].max()
            for _, row in group.iterrows():
                flagged.append({
                    **row.to_dict(),
                    "conflict_type": "Meerdere offsets voor dezelfde meter",
                    "recommended_action": "Behouden (nieuwste)" if row["pulsecounteroffsetid"] == keep_id else "Verwijderen",
                })

    slave_scope_devices = set(offset_df.loc[offset_df["slavedeviceid"] != "", "parent_deviceid"]) - {""}
    device_scope_rows = offset_df[offset_df["slavedeviceid"] == ""]
    for _, row in device_scope_rows.iterrows():
        if row["deviceid"] and row["deviceid"] in slave_scope_devices:
            flagged.append({
                **row.to_dict(),
                "conflict_type": "Verweesde device-offset naast slavedevice-offset",
                "recommended_action": "Verwijderen",
            })

    if not flagged:
        return pd.DataFrame(), []

    flagged_df = pd.DataFrame(flagged).drop_duplicates(subset=["pulsecounteroffsetid", "conflict_type"])
    delete_ids = sorted(set(
        flagged_df.loc[flagged_df["recommended_action"] == "Verwijderen", "pulsecounteroffsetid"].tolist()
    ))
    return flagged_df, delete_ids


def delete_offset_rows(database_name, pulsecounteroffsetids):
    if not pulsecounteroffsetids:
        return
    c = conn(database_name)
    try:
        cur = c.cursor()
        cur.executemany(
            f"DELETE FROM {OFFSET_TABLE} WHERE pulsecounteroffsetid = %s",
            [(i,) for i in pulsecounteroffsetids],
        )
        c.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        c.close()


def queue_counter_request_command(cur, device_id, record=None):
    """Queue a 0x15 Request Counter Value command in the current DB transaction."""
    if not device_id:
        raise ValueError("DeviceID ontbreekt; RCV commando kan niet worden klaargezet.")

    cur.execute(
        f"SELECT address FROM {DEVICE_TABLE} WHERE deviceid = %s LIMIT 1",
        (int(device_id),),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Device {device_id} niet gevonden in de database.")
    address = row[0]

    cur.execute(
        f"""
        INSERT INTO {SENDLIST_TABLE}
            (devid, address, command, comment, priority, sureness,
             starttime, lasttry, msgdata, retrystodo, newpincode)
        VALUES
            (0x21, %s, 0x15, 'erp RCV', 70, 1,
             NOW(), '1970-01-01 00:00:01', '', 10, 3424)
        """,
        (address,),
    )
    write_runtime_log(
        f"Request Counter Value commando automatisch klaargezet na offsetwijziging voor device {device_id} (address={address}).",
        level="INFO",
        record=record if record is not None else {"deviceid": str(device_id)},
    )
    return address


def update_meterdivider(cur, device_id=None, slave_id=None, new_meterdivider=None, current_meterdivider=None):
    if new_meterdivider is None or pd.isna(new_meterdivider):
        return

    divider = get_normalized_meterdivider(new_meterdivider)
    current_divider = get_normalized_meterdivider(current_meterdivider or 1)

    if abs(divider - current_divider) < 1e-12:
        return

    if slave_id:
        cur.execute(
            f"UPDATE {SLAVE_TABLE} SET meterdivider = %s WHERE slavedeviceid = %s",
            (divider, slave_id),
        )
        write_runtime_log(f"Meterdivider gewijzigd van {current_divider} naar {divider}.", level="INFO", record={"slavedeviceid": slave_id, "deviceid": device_id})
    elif device_id:
        cur.execute(
            f"UPDATE {DEVICE_TABLE} SET meterdivider = %s WHERE deviceid = %s",
            (divider, device_id),
        )
        write_runtime_log(f"Meterdivider gewijzigd van {current_divider} naar {divider}.", level="INFO", record={"deviceid": device_id})


def fetch_latest_raw_log_entry(cur, device_id=None, slave_id=None, channel=None):
    """Return latest pulsecounterlog row for the record scope used by this tool."""
    clauses = []
    params = []

    if slave_id:
        clauses.append("slavedeviceid = %s")
        params.append(slave_id)
    elif device_id:
        clauses.append("deviceid = %s")
        params.append(device_id)
        clauses.append("(slavedeviceid IS NULL OR slavedeviceid = '')")
    else:
        return None

    if channel:
        clauses.append("channel = %s")
        params.append(channel)

    query = f"""
        SELECT pulsecounterlogid, value, timestamp
        FROM {LOG_TABLE}
        WHERE {' AND '.join(clauses)}
        ORDER BY timestamp DESC, pulsecounterlogid DESC
        LIMIT 1
    """
    cur.execute(query, tuple(params))
    row = cur.fetchone()
    if not row:
        return None

    return {
        "pulsecounterlogid": row[0],
        "value": float(row[1] or 0),
        "timestamp": row[2],
    }


def fetch_stored_offset_raw(cur, device_id=None, slave_id=None):
    """Read the currently stored raw offset value for verification after write."""
    if slave_id:
        cur.execute(
            f"SELECT `offset` FROM {OFFSET_TABLE} WHERE slavedeviceid = %s LIMIT 1",
            (slave_id,),
        )
    elif device_id:
        cur.execute(
            f"SELECT `offset` FROM {OFFSET_TABLE} WHERE deviceid = %s AND (slavedeviceid IS NULL OR slavedeviceid = '') LIMIT 1",
            (device_id,),
        )
    else:
        return None

    row = cur.fetchone()
    if not row:
        return None
    return float(row[0] or 0)


def has_newer_log_entry(latest_entry, previous_entry):
    if latest_entry is None:
        return False
    if previous_entry is None:
        return True

    latest_id = latest_entry.get("pulsecounterlogid")
    previous_id = previous_entry.get("pulsecounterlogid")
    if latest_id is not None and previous_id is not None:
        try:
            return int(latest_id) > int(previous_id)
        except (TypeError, ValueError):
            pass

    latest_timestamp = pd.to_datetime(latest_entry.get("timestamp"), errors="coerce")
    previous_timestamp = pd.to_datetime(previous_entry.get("timestamp"), errors="coerce")
    if pd.notna(latest_timestamp) and pd.notna(previous_timestamp):
        return latest_timestamp > previous_timestamp

    return False


def build_refresh_status(request, latest_entry=None, status="timeout", timeout_seconds=75):
    previous_entry = request.get("previous_entry") or {}
    raw_value = latest_entry.get("value") if latest_entry else None
    actual_effective = None
    expected_effective = request.get("expected_effective")
    effective_diff = None
    if raw_value is not None and request.get("stored_offset_raw") is not None:
        actual_effective = calculate_effective_reading(
            raw_value,
            request.get("stored_offset_raw"),
            request.get("meterdivider", 1),
            request.get("offset_factor"),
            request.get("offset_mode", "subtract"),
        )
        if expected_effective is not None and not pd.isna(expected_effective):
            effective_diff = float(actual_effective) - float(expected_effective)

    return {
        "status": status,
        "deviceid": request.get("deviceid") or "",
        "slavedeviceid": request.get("slavedeviceid") or "",
        "channel": request.get("channel") or "",
        "previous_pulsecounterlogid": previous_entry.get("pulsecounterlogid"),
        "previous_raw_value": previous_entry.get("value"),
        "pulsecounterlogid": latest_entry.get("pulsecounterlogid") if latest_entry else None,
        "new_raw_value": raw_value,
        "value": raw_value,
        "timestamp": str(latest_entry.get("timestamp", "")) if latest_entry else "",
        "stored_offset_raw": request.get("stored_offset_raw"),
        "expected_effective": expected_effective,
        "actual_effective": actual_effective,
        "effective_diff": effective_diff,
        "timeout_seconds": timeout_seconds if status == "timeout" else None,
    }


def wait_for_counter_refreshes(refresh_requests, timeout_seconds=75, poll_interval_seconds=2):
    pending = [dict(request) for request in refresh_requests]
    completed = []
    latest_by_key = {}
    deadline = time.monotonic() + max(1, float(timeout_seconds))

    while pending and time.monotonic() < deadline:
        c = conn(st.session_state.get("db_name"))
        cur = c.cursor()
        try:
            still_pending = []
            for request in pending:
                latest_entry = fetch_latest_raw_log_entry(
                    cur,
                    device_id=request.get("deviceid"),
                    slave_id=request.get("slavedeviceid"),
                    channel=request.get("channel"),
                )
                request_key = (
                    request.get("deviceid") or "",
                    request.get("slavedeviceid") or "",
                    request.get("channel") or "",
                )
                latest_by_key[request_key] = latest_entry
                if has_newer_log_entry(latest_entry, request.get("previous_entry")):
                    completed.append(build_refresh_status(request, latest_entry, status="updated", timeout_seconds=timeout_seconds))
                else:
                    still_pending.append(request)
            pending = still_pending
        finally:
            try:
                cur.close()
            except Exception:
                pass
            c.close()

        if pending:
            time.sleep(max(0.1, float(poll_interval_seconds)))

    for request in pending:
        request_key = (
            request.get("deviceid") or "",
            request.get("slavedeviceid") or "",
            request.get("channel") or "",
        )
        completed.append(build_refresh_status(request, latest_by_key.get(request_key), status="timeout", timeout_seconds=timeout_seconds))

    return completed


def wait_for_counter_refresh(device_id=None, slave_id=None, channel=None, previous_entry=None, timeout_seconds=75, poll_interval_seconds=2):
    statuses = wait_for_counter_refreshes(
        [{
            "deviceid": device_id,
            "slavedeviceid": slave_id,
            "channel": channel,
            "previous_entry": previous_entry,
        }],
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    return statuses[0] if statuses else build_refresh_status({}, None, timeout_seconds=timeout_seconds)


def save_offset(df, wait_for_refresh=True):
    c = conn(st.session_state.get("db_name"))
    cur = c.cursor()
    comment_value = build_comment_value()
    verification_tolerance = 1e-6
    rounding_warnings = []
    refresh_requests = []

    try:
        for _, r in df.iterrows():
            if is_offset_edit_blocked(r):
                write_runtime_log(MID_PROTECTED_METER_MESSAGE, level="WARN", record=r)
                raise ValueError(MID_PROTECTED_METER_MESSAGE)

            device_id = str(r.get("deviceid", "")).strip() or None
            slave_id = str(r.get("slavedeviceid", "")).strip() or None
            channel = str(r.get("channel", "")).strip() or None
            current_meterdivider = get_normalized_meterdivider(r.get("current_meterdivider", r.get("meterdivider", 1)))
            new_meterdivider = r.get("new_meterdivider", current_meterdivider)
            offset_factor = get_offset_factor_override(r.get("deviceid", ""), r.get("slavedeviceid", ""))
            offset_mode = get_offset_mode(r)

            fallback_raw_value = float(r.get("raw_value", float(r.get("raw_reading", 0) or 0) * current_meterdivider) or 0)
            current_offset_raw = r.get("offset_value_raw", None)
            if current_offset_raw is None or pd.isna(current_offset_raw):
                current_offset_raw = float(r.get("current_offset", 0) or 0) * current_meterdivider

            desired_meter_reading = r.get("new_meter_reading", None)
            if desired_meter_reading is not None and pd.isna(desired_meter_reading):
                desired_meter_reading = None

            live_log_entry = None
            raw_value_for_calc = fallback_raw_value
            if desired_meter_reading is not None:
                live_log_entry = fetch_latest_raw_log_entry(
                    cur,
                    device_id=device_id,
                    slave_id=slave_id,
                    channel=channel,
                )
                raw_value_for_calc = float(live_log_entry["value"]) if live_log_entry else fallback_raw_value
                new_offset = calculate_new_offset_raw(
                    desired_meter_reading,
                    raw_value_for_calc,
                    new_meterdivider,
                    offset_factor,
                    offset_mode,
                )
            else:
                new_offset = r.get("new_offset", current_offset_raw)
                if new_offset is None or pd.isna(new_offset):
                    new_offset = current_offset_raw
                if wait_for_refresh:
                    live_log_entry = fetch_latest_raw_log_entry(
                        cur,
                        device_id=device_id,
                        slave_id=slave_id,
                        channel=channel,
                    )
                    raw_value_for_calc = float(live_log_entry["value"]) if live_log_entry else fallback_raw_value

            # pulsecounteroffset.offset is int(11); round explicitly instead of relying on MySQL's implicit cast.
            new_offset = float(round(float(new_offset)))

            rcv_device_id = device_id
            parent_device_id_for_orphan_check = device_id
            existing, device_id, slave_id = find_existing_offset(cur, device_id=device_id, slave_id=slave_id)
            orphaned_parent = (
                find_orphaned_parent_offset(cur, device_id=parent_device_id_for_orphan_check, slave_id=slave_id)
                if desired_meter_reading is not None else None
            )

            if orphaned_parent and orphaned_parent != existing:
                cur.execute(
                    f"DELETE FROM {OFFSET_TABLE} WHERE pulsecounteroffsetid = %s",
                    (orphaned_parent[0],),
                )
                write_runtime_log(
                    f"Verweesde device-level offset verwijderd (id={orphaned_parent[0]}) voor deviceid={device_id}, "
                    f"om dubbele/verouderde offsets naast de slavedevice-offset te voorkomen.",
                    level="WARN",
                    record=r,
                )

            if desired_meter_reading is not None and orphaned_parent:
                if existing:
                    pass
                # Re-fetch raw value after orphan cleanup so calculation is based on clean state.
                live_log_entry = fetch_latest_raw_log_entry(
                    cur,
                    device_id=device_id,
                    slave_id=slave_id,
                    channel=channel,
                )
                raw_value_for_calc = float(live_log_entry["value"]) if live_log_entry else fallback_raw_value
                new_offset = calculate_new_offset_raw(
                    desired_meter_reading,
                    raw_value_for_calc,
                    new_meterdivider,
                    offset_factor,
                    offset_mode,
                )
                new_offset = float(round(new_offset))

            update_meterdivider(
                cur,
                device_id=device_id,
                slave_id=slave_id,
                new_meterdivider=new_meterdivider,
                current_meterdivider=current_meterdivider,
            )

            should_write_offset = existing or desired_meter_reading is not None or abs(new_offset) > 0
            if should_write_offset:
                if existing:
                    cur.execute(
                        f"""
                        UPDATE {OFFSET_TABLE}
                        SET deviceid = %s, slavedeviceid = %s, channel = %s, `offset` = %s, comment = %s
                        WHERE pulsecounteroffsetid = %s
                        """,
                        (device_id, slave_id, channel, new_offset, comment_value, existing[0]),
                    )
                else:
                    cur.execute(
                        f"""
                        INSERT INTO {OFFSET_TABLE} (deviceid, slavedeviceid, channel, `offset`, comment)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (device_id, slave_id, channel, new_offset, comment_value)
                    )
                write_runtime_log(
                    f"Offset opgeslagen: huidig={r.get('effective_reading', '')}, doel={desired_meter_reading if desired_meter_reading is not None else r.get('new_meter_reading', '')}, divider={r.get('new_meterdivider', current_meterdivider)}, offset_factor={offset_factor or 1}, raw_offset={new_offset}, raw_bij_opslaan={raw_value_for_calc}, logid={live_log_entry.get('pulsecounterlogid', '') if live_log_entry else ''}, resultaat={r.get('resulting_effective_reading', '')}.",
                    level="INFO",
                    record=r,
                )
                queue_counter_request_command(cur, rcv_device_id, record=r)
                refresh_requests.append({
                    "deviceid": rcv_device_id,
                    "slavedeviceid": slave_id,
                    "channel": channel,
                    "previous_entry": live_log_entry,
                    "record": r,
                    "stored_offset_raw": new_offset,
                    "meterdivider": new_meterdivider,
                    "offset_factor": offset_factor,
                    "offset_mode": offset_mode,
                    "expected_effective": (
                        float(desired_meter_reading)
                        if desired_meter_reading is not None
                        else r.get("resulting_effective_reading")
                    ),
                })
                append_session_audit(
                    "offset_saved",
                    r,
                    deviceid=rcv_device_id,
                    slavedeviceid=slave_id,
                    channel=channel,
                    old_effective=r.get("effective_reading", ""),
                    target_effective=desired_meter_reading if desired_meter_reading is not None else r.get("new_meter_reading", ""),
                    raw_at_save=raw_value_for_calc,
                    stored_offset_raw=new_offset,
                    meterdivider=new_meterdivider,
                    offset_mode=offset_mode,
                    offset_factor=offset_factor or "",
                    rcv_command="0x15 queued",
                )

            if desired_meter_reading is not None:
                stored_offset_raw = fetch_stored_offset_raw(cur, device_id=device_id, slave_id=slave_id)
                if stored_offset_raw is None:
                    raise RuntimeError("Offset verificatie mislukt: opgeslagen offset kon niet worden teruggelezen.")

                verified_effective = calculate_effective_reading(raw_value_for_calc, stored_offset_raw, new_meterdivider, offset_factor, offset_mode)
                verified_diff = abs(float(verified_effective) - float(desired_meter_reading))
                # pulsecounteroffset.offset is int(11): a factor-scoped offset (small stored values) can be
                # off by up to 0.5 raw unit after rounding, which becomes 0.5*offset_factor kWh once applied.
                rounding_tolerance = verification_tolerance
                if offset_factor:
                    rounding_tolerance = max(verification_tolerance, 0.5 * float(offset_factor) + 1e-6)
                if verified_diff > rounding_tolerance:
                    raise RuntimeError(
                        "Offset verificatie mislukt: doelstand niet bereikt bij opslaan "
                        f"(doel={float(desired_meter_reading):.12g}, bereikt={float(verified_effective):.12g}, "
                        f"raw={float(raw_value_for_calc):.12g}, offset={float(stored_offset_raw):.12g}, "
                        f"divider={float(new_meterdivider):.12g})."
                    )
                if verified_diff > verification_tolerance:
                    warning_message = (
                        f"Let op: `offset` is een geheel getal in de database, dus is de berekende offset "
                        f"afgerond (offset factor {offset_factor:g}). Opgeslagen meterstand is {float(verified_effective):.6g} "
                        f"in plaats van de exact gevraagde {float(desired_meter_reading):.6g} "
                        f"(verschil {verified_diff:.6g}). DeviceID={device_id or '-'}, SlaveDeviceID={slave_id or '-'}."
                    )
                    rounding_warnings.append(warning_message)
                    write_runtime_log(warning_message, level="WARN", record=r)

        c.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        c.close()

    refresh_statuses = []
    if wait_for_refresh and refresh_requests:
        refresh_statuses = wait_for_counter_refreshes(refresh_requests)
        request_by_key = {
            (request.get("deviceid") or "", request.get("slavedeviceid") or "", request.get("channel") or ""): request
            for request in refresh_requests
        }
        for status in refresh_statuses:
            request = request_by_key.get((status.get("deviceid") or "", status.get("slavedeviceid") or "", status.get("channel") or ""), {})
            if status["status"] == "updated":
                write_runtime_log(
                    f"RCV antwoord verwerkt: nieuwe pulsecounterlog id={status.get('pulsecounterlogid')} value={status.get('value')} timestamp={status.get('timestamp')} actual={status.get('actual_effective')} expected={status.get('expected_effective')}.",
                    level="INFO",
                    record=request.get("record"),
                )
            else:
                write_runtime_log(
                    f"Timeout bij wachten op RCV antwoord na {status.get('timeout_seconds')} seconden.",
                    level="WARN",
                    record=request.get("record"),
                )
            append_session_audit(
                f"rcv_{status.get('status')}",
                request.get("record"),
                deviceid=status.get("deviceid", ""),
                slavedeviceid=status.get("slavedeviceid", ""),
                channel=status.get("channel", ""),
                previous_raw_value=status.get("previous_raw_value"),
                new_raw_value=status.get("new_raw_value"),
                stored_offset_raw=status.get("stored_offset_raw"),
                expected_effective=status.get("expected_effective"),
                actual_effective=status.get("actual_effective"),
                effective_diff=status.get("effective_diff"),
                pulsecounterlogid=status.get("pulsecounterlogid"),
            )
    st.session_state["last_save_refresh_statuses"] = refresh_statuses
    return rounding_warnings


def delete_offset(df, wait_for_refresh=True):
    c = conn(st.session_state.get("db_name"))
    cur = c.cursor()
    deleted_count = 0
    refresh_requests = []

    try:
        for _, r in df.iterrows():
            if is_offset_edit_blocked(r):
                raise ValueError(MID_PROTECTED_METER_MESSAGE)

            device_id = str(r.get("deviceid", "")).strip() or None
            slave_id = str(r.get("slavedeviceid", "")).strip() or None
            channel = str(r.get("channel", "")).strip() or None
            rcv_device_id = device_id
            previous_entry = None
            if wait_for_refresh:
                previous_entry = fetch_latest_raw_log_entry(
                    cur,
                    device_id=device_id,
                    slave_id=slave_id,
                    channel=channel,
                )

            existing, _, _ = find_existing_offset(cur, device_id=device_id, slave_id=slave_id)
            if existing:
                cur.execute(
                    f"DELETE FROM {OFFSET_TABLE} WHERE pulsecounteroffsetid = %s",
                    (existing[0],)
                )
                deleted_count += 1
                queue_counter_request_command(cur, rcv_device_id, record=r)
                refresh_requests.append({
                    "deviceid": rcv_device_id,
                    "slavedeviceid": slave_id,
                    "channel": channel,
                    "previous_entry": previous_entry,
                    "record": r,
                    "stored_offset_raw": 0,
                    "meterdivider": r.get("new_meterdivider", r.get("meterdivider", r.get("current_meterdivider", 1))),
                    "offset_factor": get_offset_factor_override(r.get("deviceid", ""), r.get("slavedeviceid", "")),
                    "offset_mode": get_offset_mode(r),
                    "expected_effective": None,
                })
                append_session_audit(
                    "offset_deleted",
                    r,
                    deviceid=rcv_device_id,
                    slavedeviceid=slave_id,
                    channel=channel,
                    rcv_command="0x15 queued",
                )

        c.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        c.close()

    refresh_statuses = []
    if wait_for_refresh and refresh_requests:
        refresh_statuses = wait_for_counter_refreshes(refresh_requests)
        request_by_key = {
            (request.get("deviceid") or "", request.get("slavedeviceid") or "", request.get("channel") or ""): request
            for request in refresh_requests
        }
        for status in refresh_statuses:
            request = request_by_key.get((status.get("deviceid") or "", status.get("slavedeviceid") or "", status.get("channel") or ""), {})
            append_session_audit(
                f"rcv_after_delete_{status.get('status')}",
                request.get("record"),
                deviceid=status.get("deviceid", ""),
                slavedeviceid=status.get("slavedeviceid", ""),
                channel=status.get("channel", ""),
                previous_raw_value=status.get("previous_raw_value"),
                new_raw_value=status.get("new_raw_value"),
                actual_effective=status.get("actual_effective"),
                pulsecounterlogid=status.get("pulsecounterlogid"),
            )
    st.session_state["last_delete_refresh_statuses"] = refresh_statuses
    return deleted_count


def send_counter_request_command(device_id):
    """Insert a 'Request Counter Value' command into the sendlist for the given device.

    The bridge picks up this row and sends command 0x15 (erp RCV) to the device,
    which causes the device to report its current raw counter value.
    The device address is resolved from the device table.
    """
    db_name = st.session_state.get("db_name")
    c = conn(db_name)
    cur = c.cursor()
    try:
        address = queue_counter_request_command(cur, device_id, record={"deviceid": str(device_id)})
        c.commit()
        return address
    finally:
        try:
            cur.close()
        except Exception:
            pass
        c.close()


def prepare_batch_preview(df, catalog):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    if "new_meterdivider" not in df.columns and "meterdivider" in df.columns:
        df["new_meterdivider"] = df["meterdivider"]

    if "new_meter_reading" not in df.columns:
        df["new_meter_reading"] = pd.NA
    if "new_meterdivider" not in df.columns:
        df["new_meterdivider"] = pd.NA

    for col in ["deviceid", "slavedeviceid", "channel"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = normalize_id_series(df[col])

    df["desired"] = pd.to_numeric(df["new_meter_reading"], errors="coerce")
    df["target_meterdivider"] = pd.to_numeric(df["new_meterdivider"], errors="coerce")

    catalog = catalog.copy()
    for col in ["deviceid", "slavedeviceid", "channel"]:
        if col not in catalog.columns:
            catalog[col] = ""
        catalog[col] = normalize_id_series(catalog[col])

    preview_rows = []

    for _, src in df.iterrows():
        candidates = catalog.copy()
        device_has_slave_rows = False

        if src["slavedeviceid"]:
            candidates = candidates[candidates["slavedeviceid"] == src["slavedeviceid"]]
            if src["deviceid"]:
                candidates = candidates[candidates["deviceid"] == src["deviceid"]]
        elif src["deviceid"]:
            device_rows = candidates[candidates["deviceid"] == src["deviceid"]]
            device_has_slave_rows = bool((device_rows["slavedeviceid"].astype(str).str.strip() != "").any()) if not device_rows.empty else False
            candidates = device_rows[device_rows["slavedeviceid"].astype(str).str.strip() == ""]

        if src["channel"]:
            candidates = candidates[candidates["channel"] == src["channel"]]

        row = {
            "deviceid": src.get("deviceid", ""),
            "slavedeviceid": src.get("slavedeviceid", ""),
            "channel": src.get("channel", ""),
            "new_meter_reading": src.get("new_meter_reading", ""),
            "new_meterdivider": src.get("new_meterdivider", ""),
            "match_count": int(len(candidates)),
            "match_status": "",
            "status_detail": "",
            "location_label": "",
            "raw_reading": None,
            "raw_value": None,
            "current_meterdivider": 1,
            "meterdivider": 1,
            "current_offset": None,
            "effective_reading": None,
            "resulting_effective_reading": None,
            "new_offset": None,
            "meter_type_label": "",
            "devicetype_name": "",
            "devicetype_code": "",
            "meter_variable": "",
        }

        desired_value = src.get("new_meter_reading", "")
        divider_value = src.get("new_meterdivider", "")
        desired_input = "" if pd.isna(desired_value) else str(desired_value).strip()
        divider_input = "" if pd.isna(divider_value) else str(divider_value).strip()
        desired_provided = desired_input != ""
        divider_provided = divider_input != ""

        if desired_provided and pd.isna(src["desired"]):
            row["match_status"] = "Ongeldige meterstand"
            row["status_detail"] = "Kolom new_meter_reading bevat geen geldige numerieke waarde."
        elif divider_provided and pd.isna(src["target_meterdivider"]):
            row["match_status"] = "Ongeldige meterdivider"
            row["status_detail"] = "Kolom new_meterdivider bevat geen geldige positieve waarde."
        elif not desired_provided and not divider_provided:
            row["match_status"] = "Geen wijzigingen opgegeven"
            row["status_detail"] = "Er is geen nieuwe meterstand opgegeven."
        elif len(candidates) == 1:
            match = candidates.iloc[0]
            current_meterdivider = get_normalized_meterdivider(match.get("meterdivider", 1))
            target_meterdivider = get_normalized_meterdivider(src["target_meterdivider"], current_meterdivider) if divider_provided else current_meterdivider
            offset_factor = get_offset_factor_override(match.get("deviceid", ""), match.get("slavedeviceid", ""))
            offset_mode = get_offset_mode(match)
            raw_value = float(match.get("raw_value", float(match.get("raw_reading", 0) or 0) * current_meterdivider) or 0)
            current_offset_raw = float(match.get("offset_value_raw", float(match.get("current_offset", 0) or 0) * current_meterdivider) or 0)
            if desired_provided:
                new_offset_raw = calculate_new_offset_raw(src["desired"], raw_value, target_meterdivider, offset_factor, offset_mode)
            else:
                new_offset_raw = current_offset_raw
            if desired_provided:
                # pulsecounteroffset.offset is int(11); preview the actually-achievable (rounded) result.
                new_offset_raw = float(round(new_offset_raw))
            row.update({
                "deviceid": match.get("deviceid", src.get("deviceid", "")),
                "slavedeviceid": match.get("slavedeviceid", src.get("slavedeviceid", "")),
                "channel": match.get("channel", src.get("channel", "")),
                "location_label": match.get("location_label", ""),
                "raw_reading": to_plain_value(match.get("raw_reading", 0)),
                "raw_value": to_plain_value(raw_value),
                "current_meterdivider": to_plain_value(current_meterdivider),
                "meterdivider": to_plain_value(target_meterdivider),
                "new_meterdivider": to_plain_value(target_meterdivider),
                "current_offset": to_plain_value(match.get("current_offset", 0)),
                "effective_reading": to_plain_value(match.get("effective_reading", 0)),
                "resulting_effective_reading": to_plain_value(calculate_effective_reading(raw_value, new_offset_raw, target_meterdivider, offset_factor, offset_mode)),
                "offset_value_raw": to_plain_value(current_offset_raw),
                "new_offset": to_plain_value(new_offset_raw),
                "meter_type_label": match.get("meter_type_label", ""),
                "devicetype_name": match.get("devicetype_name", ""),
                "devicetype_code": match.get("devicetype_code", ""),
                "meter_variable": match.get("meter_variable", ""),
                "match_status": "Geblokkeerd - MID Campère meter" if is_offset_edit_blocked(match) else "Klaar om op te slaan",
                "status_detail": "MID-gecertificeerde Campère meter; tonen mag, aanpassen niet." if is_offset_edit_blocked(match) else "Deze wijziging voldoet aan de controles en kan worden opgeslagen.",
            })
        elif len(candidates) == 0:
            if src.get("deviceid", "") and not src.get("slavedeviceid", "") and device_has_slave_rows:
                row["match_status"] = "DeviceID heeft Slavedevices - gebruik SlavedeviceID"
                row["status_detail"] = "Dit DeviceID hoort bij een controller met meerdere slaves; gebruik daarom SlavedeviceID."
            else:
                row["match_status"] = "Niet gevonden"
                row["status_detail"] = "Geen match gevonden in de huidige database voor de opgegeven invoer."
        else:
            sample_locations = [str(v).strip() for v in candidates.get("location_label", pd.Series(dtype=str)).dropna().tolist() if str(v).strip()]
            row["location_label"] = " | ".join(sample_locations[:3])
            row["match_status"] = "Meerdere directe matches - controleer invoer"
            row["status_detail"] = "Er zijn meerdere mogelijke matches gevonden; maak de invoer specifieker met SlavedeviceID of channel."

        preview_rows.append(row)

    return pd.DataFrame(preview_rows)


# =========================
# MAIN
# =========================

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🧊", layout="wide")

    st.markdown(
        """
        <style>
        .icy-title {
            text-align: left;
            margin-top: 0.15rem;
            margin-bottom: 0;
        }
        .icy-subtitle {
            text-align: left;
            color: #6b7280;
            margin-top: 0.15rem;
            margin-bottom: 1rem;
        }
        .icy-static-table {
            overflow: auto;
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 0.6rem;
            margin-bottom: 0.75rem;
        }
        .icy-static-table table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.92rem;
        }
        .icy-static-table thead th {
            position: sticky;
            top: 0;
            z-index: 1;
            background: #0f172a;
            color: #f8fafc;
            text-align: left;
            padding: 0.55rem 0.7rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.35);
        }
        .icy-static-table tbody td {
            padding: 0.45rem 0.7rem;
            border-bottom: 1px solid rgba(128, 128, 128, 0.12);
        }
        .icy-static-table tbody tr:nth-child(even) {
            background: rgba(148, 163, 184, 0.05);
        }
        .offset-suspect-badge {
            display: inline-block;
            background: #f59e0b;
            color: #1c1917;
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.1rem 0.35rem;
            border-radius: 0.25rem;
            margin-left: 0.35rem;
            cursor: help;
            vertical-align: middle;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=150)

    st.markdown(f"<h1 class='icy-title'>{APP_TITLE}</h1>", unsafe_allow_html=True)
    st.markdown("<div class='icy-subtitle'>ICY Pulse Counter meterstanden beheren via offsets</div>", unsafe_allow_html=True)

    restore_persisted_state()

    pending_rounding_warnings = st.session_state.pop("last_save_rounding_warnings", None)
    if pending_rounding_warnings:
        for warning_message in pending_rounding_warnings:
            st.warning(warning_message)
    pending_refresh_statuses = st.session_state.pop("last_save_refresh_statuses", None)
    if pending_refresh_statuses:
        updated_count = sum(1 for status in pending_refresh_statuses if status.get("status") == "updated")
        timeout_count = sum(1 for status in pending_refresh_statuses if status.get("status") == "timeout")
        if updated_count:
            st.success(f"RCV verwerkt voor {updated_count} meter(s).")
        if timeout_count:
            st.warning(f"Timeout bij wachten op RCV voor {timeout_count} meter(s). Ververs later opnieuw of controleer de bridge.")
        with st.expander("Laatste RCV-resultaat", expanded=True):
            render_static_table(get_refresh_status_display_df(pending_refresh_statuses), max_height=240)
    pending_delete_refresh_statuses = st.session_state.pop("last_delete_refresh_statuses", None)
    if pending_delete_refresh_statuses:
        updated_count = sum(1 for status in pending_delete_refresh_statuses if status.get("status") == "updated")
        timeout_count = sum(1 for status in pending_delete_refresh_statuses if status.get("status") == "timeout")
        if updated_count:
            st.success(f"RCV na verwijderen verwerkt voor {updated_count} meter(s).")
        if timeout_count:
            st.warning(f"Timeout bij wachten op RCV na verwijderen voor {timeout_count} meter(s).")
        with st.expander("Laatste RCV-resultaat na verwijderen", expanded=True):
            render_static_table(get_refresh_status_display_df(pending_delete_refresh_statuses), max_height=240)

    audit_df = get_session_audit_df()
    if not audit_df.empty:
        with st.expander(f"Sessie-audit ({len(audit_df)} events)"):
            render_static_table(audit_df.tail(50), max_height=260)
            audit_col1, audit_col2 = st.columns(2)
            audit_col1.download_button(
                "Download audit CSV",
                data=audit_df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"pulse_counter_session_audit_{datetime.now():%Y%m%d_%H%M%S}.csv",
                mime="text/csv",
            )
            audit_col2.download_button(
                "Download audit Excel",
                data=dataframe_to_excel_bytes({"Audit": audit_df}),
                file_name=f"pulse_counter_session_audit_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with st.expander("Database selectie", expanded=True):
        available_hosts = get_available_db_hosts()
        host_options = ["auto"] + available_hosts

        with st.form("db_selection_form"):
            selected_host = st.selectbox(
                "Database host selectie",
                options=host_options,
                format_func=lambda x: "Automatisch: probeer alle gevonden hosts" if x == "auto" else x,
                index=host_options.index(st.session_state.get("db_host_override", "auto")) if st.session_state.get("db_host_override", "auto") in host_options else 0,
            )
            manual_host_input = st.text_input("Database host", value=str(st.session_state.get("db_host_manual", "")).strip() or cfg("DB_HOST", ""), placeholder="bijvoorbeeld icyccdb.icy.nl")
            db_name_input = st.text_input("Database naam", value=str(st.session_state.get("db_name", "")).strip() or cfg("DB_NAME", ""), placeholder="bijvoorbeeld nl_ackersate")
            db_user_input = st.text_input("Database gebruiker", value=str(st.session_state.get("db_user", "")).strip() or cfg("DB_USER", "root"))
            db_password_input = st.text_input("Database wachtwoord", value=st.session_state.get("db_password", "") or cfg("DB_PASSWORD", ""), type="password")
            initials_input = st.text_input("Initialen", value=str(st.session_state.get("user_initials", "")).strip() or get_default_initials(), max_chars=6)
            location_input = st.text_input("Locatiefilter (optioneel)", value=st.session_state.get("location_filter", ""))
            device_id_input = st.text_input("DeviceID (optioneel)", value=st.session_state.get("device_filter", ""))
            slave_device_id_input = st.text_input("SlaveDeviceID (optioneel)", value=st.session_state.get("slave_filter", ""))
            mid_filter_input = st.selectbox(
                "MID-filter",
                options=["Alle meters", "Alleen NON MID", "Alleen MID"],
                index=["Alle meters", "Alleen NON MID", "Alleen MID"].index(
                    st.session_state.get("mid_filter", "Alle meters")
                ) if st.session_state.get("mid_filter", "Alle meters") in ["Alle meters", "Alleen NON MID", "Alleen MID"] else 0,
            )
            submitted = st.form_submit_button("Database laden")

        if submitted:
            previous_db_name = str(st.session_state.get("db_name", "")).strip()
            new_db_name = db_name_input.strip()

            st.session_state["db_host_override"] = selected_host
            st.session_state["db_host_manual"] = manual_host_input.strip()
            st.session_state["db_name"] = new_db_name
            st.session_state["db_user"] = db_user_input.strip()
            st.session_state["db_password"] = db_password_input
            st.session_state["user_initials"] = initials_input.strip().upper()
            st.session_state["location_filter"] = location_input.strip()
            st.session_state["device_filter"] = device_id_input.strip()
            st.session_state["slave_filter"] = slave_device_id_input.strip()
            st.session_state["mid_filter"] = mid_filter_input
            st.session_state["db_ready"] = True
            st.session_state["manual"] = None
            st.session_state["current_record_index"] = 0

            if previous_db_name and previous_db_name != new_db_name:
                st.session_state["search_text"] = ""
                st.session_state["selected_location"] = "Alle locaties"

            sync_persisted_state()

    if not st.session_state.get("db_ready"):
        st.info("Vul eerst de database naam in. Eventueel kun je direct DeviceID en SlaveDeviceID meegeven.")
        st.stop()

    if not st.session_state.get("db_name"):
        st.warning("Database naam is verplicht.")
        st.stop()

    if not str(st.session_state.get("db_host_manual", "")).strip() and not get_available_db_hosts():
        st.warning("Database host is verplicht. Vul een host in of zet DB_HOST in de .env.")
        st.stop()

    if not str(st.session_state.get("user_initials", "")).strip():
        st.warning("Initialen zijn verplicht.")
        st.stop()

    try:
        db_name = st.session_state["db_name"]
        host_choice = st.session_state.get("db_host_override", "auto")
        log = load(LOG_TABLE, db_name, host_choice)
        slave = load_optional(SLAVE_TABLE, db_name, host_choice)
        device = load_optional(DEVICE_TABLE, db_name, host_choice)
        location = load_optional(LOCATION_TABLE, db_name, host_choice)
        buildingtype = load_optional(BUILDINGTYPE_TABLE, db_name, host_choice)
        devicetype = load_optional(DEVICETYPE_TABLE, db_name, host_choice)
        offset = load_optional(OFFSET_TABLE, db_name, host_choice)

        catalog = build_catalog(log, slave, offset, device, location, buildingtype, devicetype)

    except Exception as e:
        st.error(e)
        st.stop()

    active_host = st.session_state.get("active_db_host", "onbekend")
    info_col, refresh_col = st.columns([6, 1])
    info_col.caption(f"Actieve database: {st.session_state['db_name']} | Host: {active_host}")
    if refresh_col.button(
        "🔄 Data verversen",
        help="Laad de tabel opnieuw uit de database",
        type="secondary",
        width="stretch",
    ):
        st.cache_data.clear()
        st.session_state["manual"] = None
        st.rerun()

    search = st.text_input("Zoek op locatie, device of meter type", key="search_text")

    filtered = catalog.copy()

    device_filter = st.session_state.get("device_filter", "").strip().lower()
    if device_filter:
        filtered = filtered[
            filtered["deviceid"].astype(str).str.lower().str.contains(device_filter, na=False)
        ]

    slave_filter = st.session_state.get("slave_filter", "").strip().lower()
    if slave_filter and "slavedeviceid" in filtered.columns:
        filtered = filtered[
            filtered["slavedeviceid"].astype(str).str.lower().str.contains(slave_filter, na=False)
        ]

    location_filter = normalize_searchable_text(st.session_state.get("location_filter", ""))
    if location_filter and "location_label" in filtered.columns:
        location_search_series = (
            normalize_searchable_text_series(filtered.get("location_label", ""), filtered.index) + " " +
            normalize_searchable_text_series(filtered.get("locationname", ""), filtered.index) + " " +
            normalize_searchable_text_series(filtered.get("buildingname", ""), filtered.index)
        ).str.strip()
        filtered = filtered[
            location_search_series.str.contains(location_filter, na=False)
        ]

    if search:
        s = normalize_searchable_text(search)
        filtered = filtered[
            filtered["search_text"].fillna("").astype(str).str.contains(s, na=False)
        ]

    mid_filter = st.session_state.get("mid_filter", "Alle meters")
    if mid_filter == "Alleen NON MID" and "offset_edit_blocked" in filtered.columns:
        filtered = filtered[~filtered["offset_edit_blocked"].fillna(False)]
    elif mid_filter == "Alleen MID" and "offset_edit_blocked" in filtered.columns:
        filtered = filtered[filtered["offset_edit_blocked"].fillna(False)]

    if "location_label" in filtered.columns:
        location_options = ["Alle locaties"] + sorted([loc for loc in filtered["location_label"].dropna().astype(str).unique().tolist() if loc.strip()])
        if st.session_state.get("selected_location", "Alle locaties") not in location_options:
            st.session_state["selected_location"] = "Alle locaties"
        selected_location = st.selectbox("Geselecteerde locatie", options=location_options, key="selected_location")
        if selected_location != "Alle locaties":
            filtered = filtered[filtered["location_label"].astype(str) == selected_location]

    sort_options = {}
    if "location_label" in filtered.columns:
        sort_options["Locatie"] = "location_label"
    elif "locationname" in filtered.columns:
        sort_options["Locatie"] = "locationname"
    if "deviceid" in filtered.columns:
        sort_options["DeviceID"] = "deviceid"
    if "device_name" in filtered.columns:
        sort_options["Device naam"] = "device_name"
    if "slavedeviceid" in filtered.columns:
        sort_options["SlaveDeviceID"] = "slavedeviceid"
    if "devicetype_name" in filtered.columns:
        sort_options["Meter Type"] = "devicetype_name"
    if "meterdivider" in filtered.columns:
        sort_options["Meterdivider"] = "meterdivider"
    if "raw_reading" in filtered.columns:
        sort_options["Effectieve meterstand"] = "raw_reading"
    if "last_reading_timestamp_sort" in filtered.columns:
        sort_options["Laatste meterstand"] = "last_reading_timestamp_sort"
    elif "last_reading_timestamp" in filtered.columns:
        sort_options["Laatste meterstand"] = "last_reading_timestamp"
    if "current_offset" in filtered.columns:
        sort_options["Huidige offset"] = "current_offset"
    if "effective_reading" in filtered.columns:
        sort_options["Effectieve meterstand"] = "effective_reading"

    if sort_options:
        sort_col_ui, sort_dir_ui = st.columns([2, 1])
        sort_labels = list(sort_options.keys())
        default_sort = st.session_state.get("sort_column_ui", sort_labels[0])
        if default_sort not in sort_options:
            default_sort = sort_labels[0]
        sort_label = sort_col_ui.selectbox(
            "Sorteer tabel op",
            options=sort_labels,
            index=sort_labels.index(default_sort),
            key="sort_column_ui",
        )
        sort_direction = sort_dir_ui.selectbox(
            "Richting",
            options=["Oplopend", "Aflopend"],
            index=0 if st.session_state.get("sort_direction_ui", "Oplopend") == "Oplopend" else 1,
            key="sort_direction_ui",
        )

        primary_sort = sort_options[sort_label]
        fallback_sorts = [col for col in ["location_label", "deviceid", "slavedeviceid"] if col in filtered.columns and col != primary_sort]
        filtered = filtered.sort_values(
            by=[primary_sort] + fallback_sorts,
            ascending=[sort_direction == "Oplopend"] + [True] * len(fallback_sorts),
            na_position="last",
        ).reset_index(drop=True)
    else:
        filtered = filtered.reset_index(drop=True)

    sync_persisted_state()

    # Markeer rijen waar de effectieve meterstand negatief is (offset > raw_reading: datafout).
    _suspect_mask = pd.Series(False, index=filtered.index)
    if "effective_reading" in filtered.columns:
        _eff_num = pd.to_numeric(filtered["effective_reading"], errors="coerce").fillna(0)
        _suspect_mask = _eff_num < 0

    display_cols = []
    if "location_label" in filtered.columns:
        display_cols.append("location_label")
    elif "locationname" in filtered.columns:
        display_cols.append("locationname")
    if "deviceid" in filtered.columns:
        display_cols.append("deviceid")
    if "device_name" in filtered.columns:
        display_cols.append("device_name")
    if "slavedeviceid" in filtered.columns:
        display_cols.append("slavedeviceid")
    if "devicetype_name" in filtered.columns:
        display_cols.append("devicetype_name")
    if "meterdivider" in filtered.columns:
        display_cols.append("meterdivider")
    if "last_reading_timestamp" in filtered.columns:
        display_cols.append("last_reading_timestamp")
    if "offset_edit_status" in filtered.columns:
        display_cols.append("offset_edit_status")
    display_cols += ["raw_reading", "current_offset", "effective_reading"]
    display_cols = [col for col in display_cols if col in filtered.columns]

    _display_source = filtered[display_cols].copy()

    if _suspect_mask.any() and "effective_reading" in _display_source.columns:
        _badge = (
            '<span class="offset-suspect-badge" '
            'title="Effectieve meterstand is negatief: de opgeslagen offset is groter dan de huidige ruwe teller. '
            'Verwijder de offset en stel opnieuw in op de werkelijke meterstand.">&#9888;</span>'
        )
        _display_source["effective_reading"] = _display_source["effective_reading"].astype(object)
        _display_source.loc[_suspect_mask, "effective_reading"] = (
            _display_source.loc[_suspect_mask, "effective_reading"]
            .apply(lambda v: f"{format_table_value(v)}&nbsp;{_badge}")
        )

    display_df = _display_source.rename(columns={
        "location_label": "Location",
        "locationname": "Location",
        "deviceid": "DeviceID",
        "device_name": "Device naam",
        "slavedeviceid": "SlaveDeviceID",
        "devicetype_name": "Meter Type",
        "meterdivider": "Meterdivider",
        "last_reading_timestamp": "Laatste meterstand tijdstip",
        "offset_edit_status": "Aanpassen",
        "effective_reading": "Effectieve meterstand",
        "current_offset": "Huidige offset",
        "": "Ruwe stand",
    })

    render_static_table(display_df, max_height=520)

    debug_snapshot = st.session_state.get("catalog_debug")
    if debug_snapshot:
        with st.expander("Debug: geselecteerde catalog versus ruwe log"):
            st.caption(
                f"Filters: DeviceID={debug_snapshot.get('filters', {}).get('deviceid', '') or '-'} | "
                f"SlaveDeviceID={debug_snapshot.get('filters', {}).get('slavedeviceid', '') or '-'} | "
                f"Rows: log={debug_snapshot.get('counts', {}).get('log_rows', 0)}, "
                f"latest={debug_snapshot.get('counts', {}).get('latest_rows', 0)}, "
                f"catalog={debug_snapshot.get('counts', {}).get('merged_rows', 0)}"
            )
            st.markdown("**Laatste ruwe `pulsecounterlog` rijen (na filter):**")
            render_static_table(pd.DataFrame(debug_snapshot.get("log_tail", [])), max_height=260)
            st.markdown("**Rijen na `drop_duplicates` (één per record_key+channel):**")
            render_static_table(pd.DataFrame(debug_snapshot.get("latest_tail", [])), max_height=260)
            st.markdown("**Uiteindelijke catalog rijen die de UI gebruikt:**")
            render_static_table(pd.DataFrame(debug_snapshot.get("merged_tail", [])), max_height=260)

    with st.expander("Onderhoud: dubbele/verweesde offsets opschonen"):
        st.caption(
            "Scant de volledige pulsecounteroffset-tabel op meerdere offsetrijen voor dezelfde meter "
            "(bijv. een oude device-level offset die is blijven staan naast een nieuwere slavedevice-offset). "
            "Zulke duplicaten kunnen ervoor zorgen dat andere rapportages een verouderde offset gebruiken."
        )
        if st.button("Scan op dubbele offsets", key="scan_duplicate_offsets"):
            try:
                flagged_df, delete_ids = scan_duplicate_offsets(
                    st.session_state["db_name"], st.session_state.get("db_host_override", "auto")
                )
                st.session_state["duplicate_offset_scan"] = {
                    "flagged": flagged_df.to_dict("records"),
                    "delete_ids": delete_ids,
                }
            except Exception as scan_exc:
                st.error(f"Scan mislukt: {scan_exc}")

        scan_result = st.session_state.get("duplicate_offset_scan")
        if scan_result:
            scan_flagged_df = pd.DataFrame(scan_result.get("flagged", []))
            scan_delete_ids = scan_result.get("delete_ids", [])
            if scan_flagged_df.empty:
                st.success("Geen dubbele of verweesde offsets gevonden.")
            else:
                affected_meters = scan_flagged_df["scope_key"].nunique() if "scope_key" in scan_flagged_df.columns else len(scan_flagged_df)
                st.warning(f"{len(scan_delete_ids)} offsetrij(en) gemarkeerd om te verwijderen, verdeeld over {affected_meters} meter(s).")
                cols = [c for c in [
                    "pulsecounteroffsetid", "deviceid", "slavedeviceid", "channel",
                    "offset", "comment", "conflict_type", "recommended_action",
                ] if c in scan_flagged_df.columns]
                render_static_table(scan_flagged_df[cols], max_height=300)
                cleanup_confirm = st.checkbox(
                    "Bevestig verwijderen van gemarkeerde offsetrijen",
                    value=False,
                    key="confirm_cleanup_duplicate_offsets",
                )
                if st.button(
                    "Verwijder gemarkeerde duplicaten",
                    disabled=not scan_delete_ids or not cleanup_confirm,
                    key="delete_duplicate_offsets_btn",
                ):
                    try:
                        delete_offset_rows(st.session_state["db_name"], scan_delete_ids)
                        write_runtime_log(
                            f"Dubbele/verweesde offsets opgeschoond: {len(scan_delete_ids)} rij(en) verwijderd (ids={scan_delete_ids}).",
                            level="WARN",
                        )
                        st.success(f"{len(scan_delete_ids)} offsetrij(en) verwijderd.")
                        st.session_state["duplicate_offset_scan"] = None
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as del_exc:
                        st.error(f"Verwijderen mislukt: {del_exc}")

    with st.expander("Diagnose: offset-conventie per metertype vergelijken (alleen weergave, wijzigt niets)"):
        st.caption(
            "Vergelijkt voor de huidige (gefilterde) selectie twee mogelijke interpretaties van de opgeslagen "
            "`offset`-waarde: A) de conventie die dit script nu gebruikt (raw pulsen, aftrekken en delen door de "
            "meterdivider) en B) de ICY-conventie die voor de Campère-meter is geverifieerd (opgeslagen waarde "
            "vermenigvuldigen met een factor en optellen, zonder extra deling door de divider). Gebruik dit om per "
            "meter/devicetype te bepalen welke conventie klopt, vóórdat de opslaglogica wordt aangepast."
        )
        diag_factor = st.number_input(
            "Te testen offsetfactor (B)", min_value=0.0, value=5.0, step=1.0, format="%g", key="diag_offset_factor"
        )
        diag_cols = [col for col in [
            "location_label", "deviceid", "slavedeviceid", "devicetype_name", "devicetype_code",
            "meterdivider", "raw_reading", "offset_value_raw", "effective_reading",
        ] if col in filtered.columns]
        diag_df = filtered[diag_cols].copy()
        if "offset_value_raw" in diag_df.columns:
            diag_df = diag_df[pd.to_numeric(diag_df["offset_value_raw"], errors="coerce").fillna(0) != 0]
        if diag_df.empty:
            st.info("Geen meters met een actieve offset in de huidige selectie.")
        else:
            diag_df["effective_A_huidige_conventie"] = pd.to_numeric(diag_df.get("effective_reading"), errors="coerce")
            diag_df["effective_B_icy_conventie"] = (
                pd.to_numeric(diag_df["raw_reading"], errors="coerce")
                + diag_factor * pd.to_numeric(diag_df["offset_value_raw"], errors="coerce")
            )
            diag_df["verschil_A_min_B"] = diag_df["effective_A_huidige_conventie"] - diag_df["effective_B_icy_conventie"]
            diag_df = diag_df.rename(columns={
                "location_label": "Location",
                "deviceid": "DeviceID",
                "slavedeviceid": "SlaveDeviceID",
                "devicetype_name": "Meter Type",
                "devicetype_code": "Devicetype code",
                "meterdivider": "Meterdivider",
                "raw_reading": "Raw reading",
                "offset_value_raw": "Opgeslagen offset (raw)",
            })
            render_static_table(diag_df, max_height=400)
            st.caption(
                "Beoordeel per rij welke van de twee kolommen (A of B) overeenkomt met de werkelijke, bekende "
                "meterstand van dat device. Noteer per devicetype welke conventie klopt voordat de formule wordt aangepast."
            )

    unknown_location_count = int((filtered.get("location_label", pd.Series(dtype=str)).astype(str) == "Onbekende locatie").sum()) if not filtered.empty else 0
    if unknown_location_count:
        st.caption(f"{unknown_location_count} record(s) hebben geen locatiekoppeling in de database en zijn gemarkeerd als 'Onbekende locatie'.")

    # =========================
    # MANUAL
    # =========================
    tab1, tab2 = st.tabs(["Handmatig", "Batch"])

    with tab1:

        if filtered.empty:
            st.info("Geen records gevonden voor de huidige selectie.")
        else:
            if st.session_state["current_record_index"] >= len(filtered):
                st.session_state["current_record_index"] = 0

            nav_prev, nav_next, nav_info = st.columns([1, 1, 3])
            if nav_prev.button("Vorige"):
                st.session_state["current_record_index"] = (st.session_state["current_record_index"] - 1) % len(filtered)
                sync_persisted_state()
            if nav_next.button("Volgende"):
                st.session_state["current_record_index"] = (st.session_state["current_record_index"] + 1) % len(filtered)
                sync_persisted_state()

            row = filtered.iloc[st.session_state["current_record_index"]]
            current_location = str(row.get("location_label", "")).strip() or "Onbekende locatie"
            cycle_location = st.session_state.get("selected_location", "Alle locaties")

            nav_info.caption(
                f"Record {st.session_state['current_record_index'] + 1} van {len(filtered)}"
                + (f" • {current_location}" if current_location else "")
            )
            st.info(f"Locatie in cyclus: {cycle_location if cycle_location != 'Alle locaties' else current_location}")
            st.caption(
                f"Huidig record → Locatie: {current_location} | DeviceID: {row.get('deviceid', '-') or '-'} | Device naam: {row.get('device_name', '-') or '-'} | SlaveDeviceID: {row.get('slavedeviceid', '-') or '-'} | Meter Type: {row.get('devicetype_name', '-') or '-'}"
            )
            active_location_scope = st.session_state.get("selected_location", "Alle locaties")
            active_mid_scope = st.session_state.get("mid_filter", "Alle meters")
            st.caption(
                f"Bulkselectie gebruikt de volledige huidige filterset: {active_location_scope} • {active_mid_scope} • {len(filtered)} zichtbare meter(s)."
            )

            with st.expander("Debug huidig record (laatste pulsecounterlog)"):
                try:
                    device_id_dbg = normalize_id_value(row.get("deviceid", ""))
                    slave_id_dbg = normalize_id_value(row.get("slavedeviceid", ""))
                    channel_dbg = normalize_id_value(row.get("channel", ""))

                    log_dbg = log.copy()
                    if not log_dbg.empty:
                        if "deviceid" in log_dbg.columns:
                            log_dbg["deviceid"] = normalize_id_series(log_dbg["deviceid"])
                        if "slavedeviceid" in log_dbg.columns:
                            log_dbg["slavedeviceid"] = normalize_id_series(log_dbg["slavedeviceid"])
                        if "channel" in log_dbg.columns:
                            log_dbg["channel"] = normalize_id_series(log_dbg["channel"])

                    if slave_id_dbg and "slavedeviceid" in log_dbg.columns:
                        log_dbg = log_dbg[log_dbg["slavedeviceid"] == slave_id_dbg]
                    elif device_id_dbg and "deviceid" in log_dbg.columns:
                        log_dbg = log_dbg[log_dbg["deviceid"] == device_id_dbg]

                    if channel_dbg and "channel" in log_dbg.columns:
                        log_dbg = log_dbg[log_dbg["channel"] == channel_dbg]

                    current_meterdivider_dbg = get_normalized_meterdivider(row.get("meterdivider", 1))
                    current_offset_raw_dbg = float(row.get("offset_value_raw", float(row.get("current_offset", 0) or 0) * current_meterdivider_dbg) or 0)
                    offset_factor_dbg = get_offset_factor_override(row.get("deviceid", ""), row.get("slavedeviceid", ""))
                    offset_mode_dbg = get_offset_mode(row)

                    if "value" in log_dbg.columns:
                        log_dbg["value"] = pd.to_numeric(log_dbg["value"], errors="coerce")
                    if "pulsecounterlogid" in log_dbg.columns:
                        log_dbg["pulsecounterlogid"] = pd.to_numeric(log_dbg["pulsecounterlogid"], errors="coerce")
                    if "timestamp" in log_dbg.columns:
                        log_dbg["timestamp"] = pd.to_datetime(log_dbg["timestamp"], errors="coerce")

                    sort_cols = [col for col in ["timestamp", "pulsecounterlogid"] if col in log_dbg.columns]
                    if sort_cols:
                        log_dbg = log_dbg.sort_values(by=sort_cols, ascending=False, na_position="last")

                    preview_dbg = log_dbg.head(8).copy()
                    if not preview_dbg.empty and "value" in preview_dbg.columns:
                        preview_dbg["raw_reading@divider"] = preview_dbg["value"] / current_meterdivider_dbg
                        preview_dbg["effective@current_offset"] = preview_dbg["value"].apply(
                            lambda v: calculate_effective_reading(v, current_offset_raw_dbg, current_meterdivider_dbg, offset_factor_dbg, offset_mode_dbg)
                        )

                    dbg_cols = [
                        col for col in [
                            "pulsecounterlogid",
                            "deviceid",
                            "slavedeviceid",
                            "channel",
                            "value",
                            "timestamp",
                            "raw_reading@divider",
                            "effective@current_offset",
                        ] if col in preview_dbg.columns
                    ]

                    st.caption(
                        f"Recordscope: deviceid={device_id_dbg or '-'} | slavedeviceid={slave_id_dbg or '-'} | channel={channel_dbg or '-'} | "
                        f"meterdivider={current_meterdivider_dbg:g} | offset_raw={current_offset_raw_dbg:g}"
                        + (f" | offset_factor={offset_factor_dbg:g}" if offset_factor_dbg else "")
                    )
                    if dbg_cols:
                        render_static_table(preview_dbg[dbg_cols], max_height=260)
                    else:
                        st.info("Geen pulsecounterlog-regels gevonden voor dit recordscope.")
                except Exception as dbg_exc:
                    st.warning(f"Debugweergave kon niet worden opgebouwd: {dbg_exc}")

            is_locked = bool(row.get("offset_edit_blocked", False)) or is_offset_edit_blocked(row)
            if is_locked:
                st.session_state["manual"] = None
                st.warning(MID_PROTECTED_METER_MESSAGE)

            current_meterdivider = get_normalized_meterdivider(row.get("meterdivider", 1))
            raw_value = float(row.get("raw_value", row.get("raw_reading", 0)) or 0)
            current_offset_raw = float(row.get("offset_value_raw", float(row.get("current_offset", 0) or 0) * current_meterdivider) or 0)
            offset_factor = get_offset_factor_override(row.get("deviceid", ""), row.get("slavedeviceid", ""))
            offset_mode = get_offset_mode(row)
            if offset_factor:
                st.caption(f"⚠️ Voor deze specifieke meter geldt een afwijkende, geverifieerde offsetconventie (factor {offset_factor:g}).")

            divider_toggle_col, divider_input_col = st.columns([1, 1])
            change_divider = divider_toggle_col.checkbox(
                "Meterdivider aanpassen",
                value=False,
                key=f"change_divider_{row.get('deviceid', '')}_{row.get('slavedeviceid', '')}_{row.get('channel', '')}",
                disabled=is_locked,
            )
            new_meterdivider = current_meterdivider
            if change_divider:
                new_meterdivider = divider_input_col.number_input(
                    "Nieuwe meterdivider",
                    min_value=1.0,
                    value=float(current_meterdivider),
                    step=1.0,
                    format="%g",
                    key=f"meterdivider_{row.get('deviceid', '')}_{row.get('slavedeviceid', '')}_{row.get('channel', '')}",
                    disabled=is_locked,
                )

            recalculated_effective = calculate_effective_reading(raw_value, current_offset_raw, new_meterdivider, offset_factor, offset_mode)
            st.caption(
                f"Meterdivider: {current_meterdivider:g}" + (f" → {new_meterdivider:g}" if change_divider else "")
                + f" | Huidige effectieve meterstand bij deze divider: {recalculated_effective:.6g}"
            )

            adjustment_mode_label = st.radio(
                "Wijziging",
                options=["Zet meterstand op", "Tel op bij huidige stand"],
                horizontal=True,
                key=f"adjustment_mode_{row.get('deviceid', '')}_{row.get('slavedeviceid', '')}_{row.get('channel', '')}",
                disabled=is_locked,
            )
            adjustment_mode = "add" if adjustment_mode_label == "Tel op bij huidige stand" else "set"
            desired_input_default = 0.0 if adjustment_mode == "add" else float(recalculated_effective)
            desired_input = st.number_input(
                "Op te tellen stand" if adjustment_mode == "add" else "Nieuwe meterstand",
                value=desired_input_default,
                key=f"desired_{adjustment_mode}_{row.get('deviceid', '')}_{row.get('slavedeviceid', '')}_{row.get('channel', '')}_{str(new_meterdivider).replace('.', '_')}",
                disabled=is_locked,
            )
            desired = calculate_target_meter_reading(desired_input, recalculated_effective, adjustment_mode)
            st.caption("Bij opslaan wordt altijd opnieuw de nieuwste pulsecounterlog gelezen en daarop de offset berekend, zodat de doelstand op dat moment exact wordt gehaald.")
            if adjustment_mode == "add":
                st.caption(f"Doelstand bij opslaan: {desired:.6g}")

            preview_col, push_current_col, push_visible_col, save_col, delete_col = st.columns(5)
            record_payload = {
                "deviceid": row.get("deviceid", ""),
                "slavedeviceid": row.get("slavedeviceid", ""),
                "locationname": row.get("location_label", row.get("locationname", "")),
                "raw_reading": to_plain_value(row["raw_reading"]),
                "raw_value": to_plain_value(raw_value),
                "current_meterdivider": to_plain_value(current_meterdivider),
                "meterdivider": to_plain_value(new_meterdivider),
                "new_meterdivider": to_plain_value(new_meterdivider),
                "current_offset": to_plain_value(row["current_offset"]),
                "effective_reading": to_plain_value(row.get("effective_reading", recalculated_effective)),
                "new_meter_reading": to_plain_value(desired),
                "adjustment_mode": adjustment_mode,
                "adjustment_input": to_plain_value(desired_input),
                "offset_value_raw": to_plain_value(current_offset_raw),
                "new_offset": to_plain_value(calculate_new_offset_raw(desired, raw_value, new_meterdivider, offset_factor, offset_mode)),
                "resulting_effective_reading": to_plain_value(calculate_effective_reading(raw_value, calculate_new_offset_raw(desired, raw_value, new_meterdivider, offset_factor, offset_mode), new_meterdivider, offset_factor, offset_mode)),
                "meter_type_label": row.get("meter_type_label", ""),
                "devicetype_name": row.get("devicetype_name", ""),
                "devicetype_code": row.get("devicetype_code", ""),
                "meter_variable": row.get("meter_variable", ""),
                "channel": row.get("channel", ""),
            }

            if preview_col.button("Preview", disabled=is_locked):
                st.session_state["manual"] = record_payload

            push_confirm = st.checkbox(
                "Bevestig klaarzetten voor batch (nog niet opslaan)",
                value=False,
                key=f"confirm_push_batch_{row.get('deviceid', '')}_{row.get('slavedeviceid', '')}_{row.get('channel', '')}",
                disabled=False,
            )
            if push_current_col.button("Push huidig record", disabled=is_locked or not push_confirm):
                try:
                    staged_row = build_batch_staging_row(record_payload, desired_meter_reading=None, new_meterdivider=new_meterdivider)
                    staged_rows, action = upsert_batch_staging_rows(st.session_state.get("batch_staging", []), staged_row)
                    st.session_state["batch_staging"] = staged_rows
                    write_runtime_log(
                        f"Huidig record toegevoegd aan batchwachtrij ({action}). Nieuwe meterstand moet nog in Batch worden ingevuld; divider={staged_row.get('new_meterdivider', '')}.",
                        level="INFO",
                        record=staged_row,
                    )
                    st.success(f"Huidig record staat klaar in Batch ({len(staged_rows)} regel(s) in wachtrij).")
                except Exception as e:
                    st.error(e)

            if push_visible_col.button(f"Push gefilterde selectie ({len(filtered)})", disabled=filtered.empty or not push_confirm, help="Gebruikt alle meters die nu zichtbaar zijn op basis van locatie-, zoek- en MID-filter."):
                try:
                    staged_rows, added_count, updated_count, blocked_count = build_batch_staging_rows_from_df(
                        filtered,
                        existing_rows=st.session_state.get("batch_staging", []),
                    )
                    st.session_state["batch_staging"] = staged_rows
                    write_runtime_log(
                        f"Zichtbare selectie naar batchwachtrij gezet: toegevoegd={added_count}, bijgewerkt={updated_count}, geblokkeerd={blocked_count}.",
                        level="INFO",
                    )
                    success_message = f"{added_count + updated_count} zichtbare meter(s) staan klaar in Batch."
                    if blocked_count:
                        success_message += f" {blocked_count} MID-meter(s) zijn overgeslagen."
                    st.success(success_message)
                except Exception as e:
                    st.error(e)

            if st.session_state["manual"]:
                st.success("Preview klaar")
                st.json(st.session_state["manual"])

            if save_col.button("Opslaan en volgende", disabled=is_locked):
                if not st.session_state.get("manual"):
                    st.warning("Eerst preview maken")
                else:
                    with st.spinner("Offset opgeslagen. RCV commando verstuurd; wachten op nieuwe pulsecounterwaarde..."):
                        st.session_state["last_save_rounding_warnings"] = save_offset(pd.DataFrame([st.session_state["manual"]]))
                    st.cache_data.clear()
                    st.session_state["manual"] = None
                    st.session_state["current_record_index"] = (st.session_state["current_record_index"] + 1) % len(filtered)
                    sync_persisted_state()
                    st.success("Opgeslagen, volgende record geladen")
                    st.rerun()

            has_current_offset = abs(float(row.get("current_offset", 0) or 0)) > 0
            confirm_delete = delete_col.checkbox(
                "Bevestig verwijderen",
                key=f"confirm_delete_{row.get('deviceid', '')}_{row.get('slavedeviceid', '')}_{row.get('channel', '')}",
                disabled=is_locked or not has_current_offset,
            )
            if delete_col.button("Huidige offset verwijderen", disabled=is_locked or not has_current_offset or not confirm_delete):
                with st.spinner("Offset verwijderd. RCV commando verstuurd; wachten op nieuwe pulsecounterwaarde..."):
                    deleted = delete_offset(pd.DataFrame([record_payload]))
                st.cache_data.clear()
                st.session_state["manual"] = None
                if deleted:
                    st.success("Huidige offset verwijderd")
                else:
                    st.info("Geen opgeslagen offset gevonden om te verwijderen")
                st.rerun()

            # =========================
            # RECOVERY PROCEDURE
            # =========================
            rcv_device_id = str(row.get("deviceid", "")).strip()
            if rcv_device_id:
                with st.expander("Herstel procedure: ververs pulsecounter waarde"):
                    st.caption(
                        "Stuur een 'Request Counter Value' commando naar het apparaat. "
                        "De bridge leest de huidige teller uit en schrijft die naar pulsecounterlog. "
                        "Wacht daarna ~1 minuut en ververs de data voordat je een nieuwe offset instelt."
                    )
                    rcv_confirm = st.checkbox(
                        "Bevestig: verstuur commando naar device " + rcv_device_id,
                        value=False,
                        key=f"rcv_confirm_{rcv_device_id}",
                    )
                    if st.button(
                        "Verstuur Request Counter Value",
                        disabled=not rcv_confirm,
                        key=f"rcv_send_{rcv_device_id}",
                    ):
                        try:
                            used_address = send_counter_request_command(rcv_device_id)
                            st.success(
                                f"Commando verstuurd naar device {rcv_device_id} "
                                f"(address={used_address}). Wacht ~1 minuut en klik '🔄 Data verversen'."
                            )
                        except Exception as rcv_exc:
                            st.error(f"Verzenden mislukt: {rcv_exc}")

    # =========================
    # BATCH
    # =========================
    with tab2:
        st.subheader("Batch import")
        st.write("Upload een Excel-bestand met minimaal een nieuwe meterstand. Als SlavedeviceID is ingevuld, wordt die altijd gebruikt. DeviceID wordt alleen gebruikt voor rechtstreekse meters zonder SlavedeviceID.")

        staged_rows = st.session_state.get("batch_staging", [])
        edited_staged_df = None
        if staged_rows:
            st.markdown("#### Batchwachtrij vanuit selectie")
            st.caption("Deze wachtrij is nog niet opgeslagen in de database. Pas hier de nieuwe meterstand en eventueel de divider aan; pas na de bevestiging onderaan wordt er echt opgeslagen.")
            staged_df = get_batch_staging_editor_df(staged_rows)
            edited_staged_df = st.data_editor(
                staged_df,
                hide_index=True,
                use_container_width=True,
                disabled=["deviceid", "slavedeviceid"],
                num_rows="dynamic",
                column_config={
                    "deviceid": st.column_config.TextColumn("DeviceID"),
                    "slavedeviceid": st.column_config.TextColumn("SlaveDeviceID"),
                    "new_meter_reading": st.column_config.NumberColumn("Nieuwe meterstand", min_value=0.0, step=1.0, format="%g"),
                    "new_meterdivider": st.column_config.NumberColumn("Nieuwe meterdivider", min_value=1.0, step=1.0, format="%g"),
                },
                key="batch_staging_editor",
            )
            st.session_state["batch_staging"] = get_batch_staging_editor_df(edited_staged_df).to_dict("records")

            queue_col1, queue_col2 = st.columns([2, 1])
            use_staged_queue = queue_col1.checkbox(
                f"Gebruik batchwachtrij ({len(st.session_state.get('batch_staging', []))} regel(s))",
                value=True,
                key="use_staged_queue",
            )
            clear_queue_confirm = queue_col2.checkbox(
                "Bevestig legen",
                value=False,
                key="clear_batch_queue_confirm",
            )
            if queue_col2.button("Wachtrij legen", disabled=not clear_queue_confirm):
                st.session_state["batch_staging"] = []
                write_runtime_log("Batchwachtrij handmatig geleegd.", level="INFO")
                st.success("Batchwachtrij geleegd.")
                st.rerun()
        else:
            use_staged_queue = False

        template_df = pd.DataFrame([
            {"slavedeviceid": "50", "deviceid": "25", "new_meter_reading": 1500, "new_meterdivider": 100},
            {"slavedeviceid": "11174", "deviceid": "", "new_meter_reading": 3200, "new_meterdivider": ""},
            {"slavedeviceid": "", "deviceid": "9", "new_meter_reading": 8750, "new_meterdivider": 1000},
        ])
        template_buffer = BytesIO()
        with pd.ExcelWriter(template_buffer, engine="openpyxl") as writer:
            template_df.to_excel(writer, index=False, sheet_name="Template")

        st.download_button(
            "Download template Excel",
            data=template_buffer.getvalue(),
            file_name="pulse_counter_batch_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption("Aanbevolen kolommen: SlavedeviceID, DeviceID, new_meter_reading en optioneel new_meterdivider. Heeft een meter een SlavedeviceID, gebruik dan die waarde. DeviceID alleen is bedoeld voor meters die geen SlavedeviceID hebben.")

        file = st.file_uploader("Excel of CSV upload", type=["xlsx", "csv"])

        source_df = None
        if file:
            if file.name.lower().endswith(".csv"):
                source_df = pd.read_csv(file)
            else:
                source_df = pd.read_excel(file)

        if use_staged_queue and st.session_state.get("batch_staging"):
            source_df = get_batch_staging_editor_df(edited_staged_df if edited_staged_df is not None else st.session_state.get("batch_staging", []))

        if source_df is not None:
            try:
                preview = prepare_batch_preview(source_df, catalog)
                valid_rows = preview[preview["match_status"] == "Klaar om op te slaan"].copy()
                blocked_rows = preview[preview["match_status"].str.contains("Geblokkeerd", na=False)].copy()
                ambiguous_rows = preview[preview["match_status"].str.contains("Meerdere matches", na=False)].copy()
                missing_rows = preview[preview["match_status"] == "Niet gevonden"].copy()
                invalid_rows = preview[preview["match_status"] == "Ongeldige meterstand"].copy()

                st.info(
                    f"Klaar: {len(valid_rows)} | Geblokkeerd: {len(blocked_rows)} | Meerdere matches: {len(ambiguous_rows)} | Niet gevonden: {len(missing_rows)} | Ongeldig: {len(invalid_rows)}"
                )
                st.caption("De tool schrijft ook een lokale log met redenen van skips, blokkades en opslagacties in je Documenten/ICY-Logs map.")
                render_static_table(get_batch_preview_display_df(preview), max_height=420)
                dry_run_summary = pd.DataFrame([
                    {"status": "Klaar om op te slaan", "count": len(valid_rows)},
                    {"status": "Geblokkeerd", "count": len(blocked_rows)},
                    {"status": "Meerdere matches", "count": len(ambiguous_rows)},
                    {"status": "Niet gevonden", "count": len(missing_rows)},
                    {"status": "Ongeldig", "count": len(invalid_rows)},
                ])
                st.download_button(
                    "Download dry-run report Excel",
                    data=dataframe_to_excel_bytes({
                        "Preview": preview,
                        "Zichtbaar": get_batch_preview_display_df(preview),
                        "Samenvatting": dry_run_summary,
                    }),
                    file_name=f"pulse_counter_batch_dry_run_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                with st.expander("Toon laatste batchlog"):
                    st.text_area("Batchlog", value=read_runtime_log_tail(), height=220, disabled=True)

                if not blocked_rows.empty:
                    st.warning("Offsets voor MID gecertificeerde ICY 4850 Campère meters zijn geblokkeerd en worden niet opgeslagen.")
                if not ambiguous_rows.empty:
                    st.warning("Sommige regels zijn nog niet specifiek genoeg. Controleer de invoer of gebruik het juiste SlavedeviceID.")
                if not missing_rows.empty:
                    st.warning("Sommige regels zijn niet gevonden in de gekozen database/host.")
                if not invalid_rows.empty:
                    st.warning("Sommige regels hebben geen geldige nieuwe meterstand.")

                batch_confirm = st.checkbox(
                    f"Ja, ik weet 100% zeker dat ik {len(valid_rows)} wijziging(en) wil opslaan.",
                    value=False,
                    disabled=valid_rows.empty,
                    key=f"batch_confirm_{len(valid_rows)}",
                )
                if not valid_rows.empty:
                    st.warning("Controleer de preview zorgvuldig. Batch opslaan kan in één keer veel offsets wijzigen.")

                if st.button("Batch opslaan", disabled=valid_rows.empty or not batch_confirm):
                    start_batch_log(f"{len(valid_rows)} geldige regel(s)")
                    for _, r in preview.iterrows():
                        status = str(r.get("match_status", "")).strip()
                        detail = str(r.get("status_detail", "")).strip()
                        if status and status != "Klaar om op te slaan":
                            write_runtime_log(f"Batchregel niet opgeslagen: {status}. {detail}", level="WARN", record=r)
                    with st.spinner(f"Batch opgeslagen. RCV commando's verstuurd; wachten op {len(valid_rows)} nieuwe pulsecounterwaarde(n)..."):
                        save_offset_warnings = save_offset(valid_rows)
                    write_runtime_log(f"Batch opgeslagen met {len(valid_rows)} geldige regel(s).", level="INFO")
                    st.session_state["last_save_rounding_warnings"] = save_offset_warnings
                    st.success(f"Batch opgeslagen: {len(valid_rows)} regels")
                    st.cache_data.clear()
                    st.rerun()
            except Exception as e:
                write_runtime_log(f"Batch verwerking mislukt: {e}", level="ERROR")
                st.error(e)


if __name__ == "__main__":
    main()
