"""Planification temporelle avancée pour scénarios HL7.

Algorithme:
1. Extraction timestamps par message (MSH-7 ou EVN-2).
2. Détermination t0 original (plus ancien) et événement admission (A01/A28/A14...)
3. Calcul ancre cible selon mode:
   - now: t0_new = maintenant
   - admission_minus_days: t_admission_new = now - days_offset ; delta = t_admission_new - t_admission_original
   - fixed_start: delta = parse(fixed_start_iso) - t0_original
4. Application delta global sur chaque timestamp.
5. Jitter optionnel ±N minutes sur événements listés (transferts / updates).
6. Correction monotonicité: si timestamp_i < timestamp_{i-1} après jitter → ajuster à +1s.
7. Reconstruction messages HL7 en préservant format (longueur / composants).

Edge cases:
- Messages sans timestamps: ignorés (pas modifiés).
- Plusieurs occurrences identiques: recalcul direct.
- Millisecondes / timezone conservées si présentes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import re

ADMISSION_EVENTS = {"A01", "A28", "A14", "A11"}  # extensible

timestamp_pattern = re.compile(
    r"\b(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])"  # YYYYMMDD
    r"(?:([01]\d|2[0-3])([0-5]\d)([0-5]\d))?"          # HHMMSS optional
    r"(?:\.(\d{1,4}))?"                                # .SSSS
    r"(?:([+-]\d{4}))?"                                 # TZ
    r"\b"
)


@dataclass
class TimeShiftConfig:
    anchor_mode: str = "now"  # now | admission_minus_days | fixed_start
    anchor_days_offset: Optional[int] = None
    fixed_start_iso: Optional[str] = None
    preserve_intervals: bool = True
    jitter_min_minutes: Optional[int] = None
    jitter_max_minutes: Optional[int] = None
    jitter_events: List[str] = None

    def __post_init__(self):
        if self.jitter_events is None:
            self.jitter_events = ["A02", "A03", "A06", "A07", "A08"]


def _extract_event_code(message: str) -> Optional[str]:
    for line in message.split("\n"):
        if line.startswith("MSH|"):
            parts = line.split("|")
            if len(parts) > 8:
                comps = parts[8].split("^")
                if len(comps) > 1:
                    return comps[1]
    return None


def _find_timestamps(message: str) -> List[Tuple[str, datetime, Tuple[int, int]]]:
    results = []
    for m in timestamp_pattern.finditer(message):
        try:
            year = int(m.group(1)); month = int(m.group(2)); day = int(m.group(3))
            hour = int(m.group(4)) if m.group(4) else 0
            minute = int(m.group(5)) if m.group(5) else 0
            second = int(m.group(6)) if m.group(6) else 0
            dt = datetime(year, month, day, hour, minute, second)
            results.append((m.group(0), dt, m.span()))
        except Exception:
            continue
    return results


def _compute_delta(messages: List[str], ts_map: List[List[Tuple[str, datetime, Tuple[int, int]]]], cfg: TimeShiftConfig) -> timedelta:
    # Flatten all timestamps to find oldest
    all_ts = [item[1] for per_msg in ts_map for item in per_msg]
    if not all_ts:
        return timedelta(0)
    oldest = min(all_ts)
    # Admission event timestamp (first timestamp in msg with admission code)
    admission_ts = None
    for msg, per_ts in zip(messages, ts_map):
        ev = _extract_event_code(msg)
        if ev in ADMISSION_EVENTS and per_ts:
            admission_ts = per_ts[0][1]
            break
    now = datetime.utcnow()
    if cfg.anchor_mode == "now":
        return now - oldest
    if cfg.anchor_mode == "admission_minus_days" and admission_ts and cfg.anchor_days_offset:
        target_admission = now - timedelta(days=cfg.anchor_days_offset)
        return target_admission - admission_ts
    if cfg.anchor_mode == "fixed_start" and cfg.fixed_start_iso:
        try:
            fixed = datetime.fromisoformat(cfg.fixed_start_iso)
            return fixed - oldest
        except Exception:
            return now - oldest
    return now - oldest


def _apply_jitter(original_dt: datetime, event_code: Optional[str], cfg: TimeShiftConfig) -> datetime:
    if not event_code or event_code not in cfg.jitter_events:
        return original_dt
    if cfg.jitter_min_minutes is None or cfg.jitter_max_minutes is None:
        return original_dt
    import random
    delta_min = cfg.jitter_min_minutes
    delta_max = cfg.jitter_max_minutes
    if delta_min > delta_max:
        delta_min, delta_max = delta_max, delta_min
    offset = random.randint(delta_min, delta_max)
    # random signe ±
    if random.random() < 0.5:
        offset = -offset
    return original_dt + timedelta(minutes=offset)


def shift_hl7_scenario(messages: List[str], cfg: TimeShiftConfig) -> List[str]:
    """Retourne une nouvelle liste de messages HL7 avec timestamps recalés.

    Les formats sont préservés (longueur originale des timestamps)."""
    ts_map = [_find_timestamps(msg) for msg in messages]
    delta = _compute_delta(messages, ts_map, cfg)
    shifted_messages: List[str] = []

    prev_dt: Optional[datetime] = None
    for idx, (msg, per_ts) in enumerate(zip(messages, ts_map)):
        if not per_ts:
            shifted_messages.append(msg)
            continue
        event_code = _extract_event_code(msg)
        # Build new message by replacing substrings from end to start
        new_msg = msg
        for original_str, original_dt, (start, end) in reversed(per_ts):
            new_dt = original_dt + delta
            if cfg.preserve_intervals:
                # Intervals preserved implicitly by global delta
                pass
            # Apply jitter on eligible events (only first timestamp per message to avoid cascade)
            if original_str == per_ts[0][0]:
                new_dt = _apply_jitter(new_dt, event_code, cfg)
            # Monotonic correction
            if prev_dt and new_dt < prev_dt:
                new_dt = prev_dt + timedelta(seconds=1)
            # Format according to original length
            if len(original_str) == 8:  # YYYYMMDD
                new_str = new_dt.strftime("%Y%m%d")
            elif len(original_str) == 14:  # YYYYMMDDHHMMSS
                new_str = new_dt.strftime("%Y%m%d%H%M%S")
            else:
                base = new_dt.strftime("%Y%m%d%H%M%S")
                # Preserve milliseconds
                if "." in original_str:
                    ms_part = original_str.split(".")[1].split("+")[0].split("-")[0]
                    base += "." + ms_part
                # Preserve timezone
                if "+" in original_str or (original_str.count("-") > 2):
                    tz_part = original_str[-5:] if ("+" in original_str[-5:] or "-" in original_str[-5:]) else ""
                    if tz_part:
                        base += tz_part
                new_str = base
            new_msg = new_msg[:start] + new_str + new_msg[end:]
            prev_dt = new_dt
        shifted_messages.append(new_msg)
    return shifted_messages


__all__ = ["TimeShiftConfig", "shift_hl7_scenario"]
