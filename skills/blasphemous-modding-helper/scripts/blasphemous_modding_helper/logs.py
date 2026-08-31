"""Bounded log reading and startup evidence diagnostics.

The module owns log-specific behavior so lifecycle entry points only provide
session state and resolved source paths. It never copies or persists log
contents; callers receive bounded output and bounded evidence metadata.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple


DEFAULT_LOG_LINES = 200
STARTUP_POLL_INTERVAL_SECONDS = 0.25
MAX_EVIDENCE_HITS = 20
MAX_EVIDENCE_TEXT = 240
LOG_OUTPUT_ENCODING = "utf-8"
LOG_OUTPUT_ERRORS = "replace"


@dataclass(frozen=True)
class LogEvidenceSource:
    label: str
    path: Optional[Path]
    exists: bool
    current: bool
    total_lines: int
    output_lines: Tuple[str, ...]
    evidence_lines: Tuple[str, ...]
    warning: Optional[str]


@dataclass(frozen=True)
class EvidenceHit:
    source: str
    line_number: int
    reason: str
    text: str
    kind: str = "positive"
    path: Optional[Path] = None
    mod_id: Optional[str] = None
    mod_name: Optional[str] = None


@dataclass(frozen=True)
class EvidenceReport:
    state: str
    ready: bool
    mod_loaded: bool
    timed_out: bool
    sources: Tuple[LogEvidenceSource, ...]
    warnings: Tuple[str, ...]
    hits: Tuple[EvidenceHit, ...] = ()


def _expand_path(value: str, base: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    path = Path(expanded)
    if not path.is_absolute():
        path = base / path
    return path.resolve(strict=False)


def resolve_unity_log_path(
    configured_directory: Optional[str],
    *,
    preference_path: Path,
    log_filenames: Sequence[str],
    explicit_directory: Optional[str] = None,
    cwd: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve a configured Unity log path and return recovery guidance."""

    filenames = tuple(str(filename) for filename in log_filenames if str(filename))
    if not filenames:
        raise ValueError("At least one Unity log filename is required.")

    configured = explicit_directory or configured_directory
    if not configured:
        return None, (
            "Unity log directory is not configured. Ask the user for the Unity "
            "log directory, then add 'unity_log_dir: PATH' to the active "
            f"preferences.md: {preference_path}"
        )

    directory = _expand_path(configured, cwd or Path.cwd())
    if directory.exists() and not directory.is_dir():
        return None, (
            f"Configured unity_log_dir is not a directory: {directory}. Ask the "
            "user for the directory containing the Unity log and update "
            f"{preference_path}."
        )

    for filename in filenames:
        candidate = directory / filename
        if candidate.is_file():
            if not os.access(candidate, os.R_OK):
                return candidate, (
                    f"Configured Unity log is not readable: {candidate}. Ask the "
                    "user for an accessible log directory and update "
                    f"{preference_path}."
                )
            return candidate, None

    expected = ", ".join(str(directory / filename) for filename in filenames)
    if not directory.exists():
        reason = f"Configured Unity log directory does not exist: {directory}."
    else:
        reason = f"Unity log was not found under configured directory: {directory}."
    return directory / filenames[0], (
        f"{reason} Expected {expected}. Ask the user for the correct directory, "
        "then add or update 'unity_log_dir: PATH' in the active "
        f"preferences.md: {preference_path}."
    )


def log_signature(path: Path) -> Optional[Dict[str, object]]:
    """Return file metadata and content digest without persisting log data."""

    try:
        if not path.is_file():
            return None
        stat_result = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return {
        "exists": True,
        "mtime_ns": int(stat_result.st_mtime_ns),
        "size": int(stat_result.st_size),
        "sha256": digest.hexdigest(),
    }


def capture_log_baselines(paths: Sequence[Path]) -> Dict[str, Dict[str, object]]:
    """Capture only signatures needed to distinguish pre-launch logs."""

    baselines: Dict[str, Dict[str, object]] = {}
    for index, path in enumerate(paths):
        key = "bepinex" if index == 0 else "unity" if index == 1 else f"log_{index}"
        normalized = path.resolve(strict=False)
        signature = log_signature(normalized)
        baselines[key] = signature or {
            "exists": False,
            "mtime_ns": None,
            "size": None,
        }
    return baselines


def log_is_current(
    path: Path,
    process_state: Mapping[str, object],
    baseline_key: str,
) -> bool:
    """Return whether a log changed after the tracked session began."""

    signature = log_signature(path)
    if signature is None:
        return False

    baseline_value = process_state.get("log_baseline")
    baseline: Optional[Dict[str, object]] = None
    if isinstance(baseline_value, dict):
        raw_baseline = baseline_value.get(baseline_key)
        if raw_baseline is None:
            raw_baseline = baseline_value.get(str(path.resolve(strict=False)))
        if isinstance(raw_baseline, dict):
            baseline = raw_baseline
    if baseline is not None:
        if not bool(baseline.get("exists")):
            return True
        baseline_digest = baseline.get("sha256")
        current_digest = signature.get("sha256")
        if isinstance(baseline_digest, str) and isinstance(current_digest, str):
            return baseline_digest != current_digest
        return any(
            signature.get(key) != baseline.get(key)
            for key in ("mtime_ns", "size")
        )

    started_at = process_state.get("started_at_epoch_ns")
    try:
        return int(signature["mtime_ns"]) >= int(started_at)
    except (KeyError, TypeError, ValueError):
        return False


def read_log_source(
    label: str,
    path: Optional[Path],
    process_state: Mapping[str, object],
    full: bool,
    configured_warning: Optional[str] = None,
    baseline_key: str = "log",
) -> LogEvidenceSource:
    """Read one source, retaining complete lines only in the transient report."""

    if path is None:
        return LogEvidenceSource(
            label,
            None,
            False,
            False,
            0,
            (),
            (),
            configured_warning or f"{label} log path is not configured.",
        )

    normalized = path.resolve(strict=False)
    if not normalized.is_file():
        return LogEvidenceSource(
            label,
            normalized,
            False,
            False,
            0,
            (),
            (),
            configured_warning or f"{label} log was not found: {normalized}",
        )

    try:
        lines = normalized.read_text(
            encoding=LOG_OUTPUT_ENCODING,
            errors=LOG_OUTPUT_ERRORS,
        ).splitlines()
    except OSError as error:
        return LogEvidenceSource(
            label,
            normalized,
            False,
            False,
            0,
            (),
            (),
            f"Could not read {label} log {normalized}: {error}",
        )

    current = log_is_current(normalized, process_state, baseline_key)
    warning = configured_warning
    if not current:
        warning = (
            warning
            or f"{label} log is not current for session {process_state.get('session_id', 'unknown')}; "
            "startup evidence from it is ignored."
        )
    selected_lines = tuple(lines if full else lines[-DEFAULT_LOG_LINES:])
    return LogEvidenceSource(
        label,
        normalized,
        True,
        current,
        len(lines),
        selected_lines,
        tuple(lines),
        warning,
    )


def chainloader_ready(lines: Sequence[str]) -> bool:
    """Recognize BepInEx chainloader completion records."""

    readiness_words = (
        "initialized",
        "initialised",
        "ready",
        "completed",
        "finished",
        "loaded",
        "startup complete",
        "start-up complete",
    )
    for line in lines:
        lowered = line.casefold()
        if "chainloader" in lowered and any(
            word in lowered for word in readiness_words
        ):
            return True
    return False


_BEPINEX_LOAD_RECORD = re.compile(
    r"^\s*\[(?P<level>[^:\]]+):\s*(?P<source>BepInEx)\s*\]\s+"
    r"(?:Loading|Loaded)\s+\[(?P<identity>[^\]\r\n]+)\]",
    re.IGNORECASE,
)
_MODDING_API_REGISTRATION_RECORD = re.compile(
    r"^\s*\[(?P<level>[^:\]]+):\s*"
    r"(?P<source>ModdingAPI|Mod\s+Loader)\s*\]\s+"
    r"(?:Registered|Registering)\s+Mod\s*(?::|=)?\s*"
    r"(?:['\"](?P<quoted_identity>[^'\"]+)['\"]|"
    r"(?P<identity>[A-Za-z0-9][A-Za-z0-9_.-]*))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _StructuredLoadRecord:
    source: str
    record_kind: str
    identity: str
    mod_id: Optional[str] = None
    mod_name: Optional[str] = None


_VERSION_SUFFIX = re.compile(
    r"^(?P<identity>.+?)\s+"
    r"(?P<version>\d+(?:\.\d+){1,4}(?:[-+][0-9A-Za-z.-]+)?)\s*$"
)


def _strip_record_version(value: str) -> str:
    normalized = value.strip()
    match = _VERSION_SUFFIX.match(normalized)
    if match is None:
        return normalized
    return match.group("identity").strip()


def _is_positive_record_level(level: str) -> bool:
    return level.strip().casefold() not in {
        "error",
        "warning",
        "warn",
        "fatal",
    }


def _normalize_log_source(source: str) -> str:
    return " ".join(source.split())


def parse_structured_load_record(line: str) -> Optional[_StructuredLoadRecord]:
    """Parse recognized ModdingAPI, Mod Loader, and BepInEx load records."""

    registration = _MODDING_API_REGISTRATION_RECORD.match(line)
    if registration and _is_positive_record_level(registration.group("level")):
        raw_identity = (
            registration.group("quoted_identity")
            or registration.group("identity")
            or ""
        )
        identity = _strip_record_version(raw_identity)
        if identity:
            return _StructuredLoadRecord(
                _normalize_log_source(registration.group("source")),
                "registration",
                identity,
                mod_id=identity,
            )

    loading = _BEPINEX_LOAD_RECORD.match(line)
    if loading and _is_positive_record_level(loading.group("level")):
        display_name = _strip_record_version(loading.group("identity"))
        if display_name:
            return _StructuredLoadRecord(
                _normalize_log_source(loading.group("source")),
                "bepinex",
                display_name,
                mod_name=display_name,
            )
    return None


_STRUCTURED_ERROR_RECORD = re.compile(
    r"^\s*\[(?P<level>[^:\]]+):\s*(?P<source>[^\]]+)\]\s*",
    re.IGNORECASE,
)


def _alias_matches_record(record: str, aliases: Sequence[str]) -> bool:
    normalized_record = record.strip().casefold()
    return any(
        normalized_record == alias.casefold()
        or normalized_record.startswith(alias.casefold() + " ")
        for alias in aliases
    )


def _line_mentions_alias(line: str, aliases: Sequence[str]) -> bool:
    return any(
        re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(alias)}(?![A-Za-z0-9_])",
            line,
            re.IGNORECASE,
        )
        for alias in aliases
    )


def target_mod_evidence(
    lines: Sequence[str],
    aliases: Sequence[str],
    source: str = "BepInEx",
    source_path: Optional[Path] = None,
) -> Tuple[EvidenceHit, ...]:
    """Match only framework records whose identity exactly matches an alias."""

    normalized_aliases = tuple(alias.strip() for alias in aliases if alias.strip())
    hits = []
    for line_number, line in enumerate(lines, start=1):
        record = parse_structured_load_record(line)
        if record is None or not _alias_matches_record(
            record.identity, normalized_aliases
        ):
            continue
        reason = (
            f"{record.source} registration"
            if record.record_kind == "registration"
            else "BepInEx loading record"
        )
        hits.append(
            EvidenceHit(
                source,
                line_number,
                reason,
                line[:MAX_EVIDENCE_TEXT],
                path=source_path,
                mod_id=record.mod_id,
                mod_name=record.mod_name,
            )
        )
    return tuple(hits[:MAX_EVIDENCE_HITS])


def bepinex_context_evidence(
    lines: Sequence[str],
    target_hits: Sequence[EvidenceHit],
    source: str = "BepInEx",
    source_path: Optional[Path] = None,
) -> Tuple[EvidenceHit, ...]:
    """Retain recognized non-target BepInEx records as bounded context."""

    target_bepinex_lines = {
        hit.line_number
        for hit in target_hits
        if hit.reason == "BepInEx loading record"
    }
    hits = []
    for line_number, line in enumerate(lines, start=1):
        if line_number in target_bepinex_lines:
            continue
        record = parse_structured_load_record(line)
        if record is None or record.record_kind != "bepinex":
            continue
        hits.append(
            EvidenceHit(
                source,
                line_number,
                "BepInEx loading record",
                line[:MAX_EVIDENCE_TEXT],
                kind="context",
                path=source_path,
                mod_name=record.mod_name,
            )
        )
    return tuple(hits[:MAX_EVIDENCE_HITS])


def target_error_evidence(
    lines: Sequence[str],
    aliases: Sequence[str],
    source: str = "BepInEx",
    source_path: Optional[Path] = None,
) -> Tuple[EvidenceHit, ...]:
    """Retain structured target errors without treating them as load records."""

    hits = []
    for line_number, line in enumerate(lines, start=1):
        record = _STRUCTURED_ERROR_RECORD.match(line)
        if (
            record
            and record.group("level").strip().casefold()
            in {"error", "exception", "fatal"}
            and _line_mentions_alias(line[record.end() :], aliases)
        ):
            hits.append(
                EvidenceHit(
                    source,
                    line_number,
                    "target error",
                    line[:MAX_EVIDENCE_TEXT],
                    "error",
                    path=source_path,
                )
            )
    return tuple(hits[:MAX_EVIDENCE_HITS])


def select_evidence_hits(
    positive_hits: Sequence[EvidenceHit],
    error_hits: Sequence[EvidenceHit],
    context_hits: Sequence[EvidenceHit] = (),
) -> Tuple[EvidenceHit, ...]:
    """Keep bounded evidence while retaining positive and error context."""

    ordered_hits = sorted(
        [*positive_hits, *error_hits, *context_hits],
        key=lambda hit: hit.line_number,
    )
    required_hits = []
    if positive_hits:
        required_hits.append(positive_hits[0])
    if error_hits:
        required_hits.append(error_hits[0])

    selected = []
    for hit in [*required_hits, *ordered_hits]:
        if hit in selected:
            continue
        selected.append(hit)
        if len(selected) == MAX_EVIDENCE_HITS:
            break
    return tuple(sorted(selected, key=lambda hit: hit.line_number))


def target_mod_loaded(lines: Sequence[str], target_name: str) -> bool:
    """Compatibility helper for callers that provide one package alias."""

    return bool(target_mod_evidence(lines, (target_name,)))


def collect_log_evidence(
    bepinex_path: Path,
    unity_path: Optional[Path],
    process_state: Mapping[str, object],
    target_name: str,
    runtime_aliases: Sequence[str] = (),
    *,
    full: bool = False,
    unity_warning: Optional[str] = None,
) -> EvidenceReport:
    """Read current logs once and classify bounded startup evidence."""

    aliases_value = (runtime_aliases,) if isinstance(runtime_aliases, str) else runtime_aliases
    aliases = tuple(
        str(alias).strip()
        for alias in aliases_value
        if str(alias).strip()
    )
    if not aliases:
        aliases = (str(target_name).strip(),) if str(target_name).strip() else ()

    sources = (
        read_log_source(
            "BepInEx",
            bepinex_path,
            process_state,
            full,
            baseline_key="bepinex",
        ),
        read_log_source(
            "Unity",
            unity_path,
            process_state,
            full,
            configured_warning=unity_warning,
            baseline_key="unity",
        ),
    )
    warnings = tuple(
        source.warning for source in sources if source.warning is not None
    )
    bepinex_source = sources[0]
    current_lines = (
        bepinex_source.evidence_lines
        if bepinex_source.exists and bepinex_source.current
        else ()
    )
    ready = bool(current_lines) and chainloader_ready(current_lines)
    positive_hits = target_mod_evidence(
        current_lines,
        aliases,
        source_path=bepinex_source.path,
    )
    error_hits = target_error_evidence(
        current_lines,
        aliases,
        source_path=bepinex_source.path,
    )
    context_hits = bepinex_context_evidence(
        current_lines,
        positive_hits,
        source_path=bepinex_source.path,
    )
    hits = select_evidence_hits(positive_hits, error_hits, context_hits)
    first_positive_line = (
        min(hit.line_number for hit in positive_hits)
        if positive_hits
        else None
    )
    first_error_line = (
        min(hit.line_number for hit in error_hits) if error_hits else None
    )
    mod_loaded = ready and first_positive_line is not None and (
        first_error_line is None or first_positive_line < first_error_line
    )
    state = "mod_loaded" if mod_loaded else "ready" if ready else "launched"
    return EvidenceReport(
        state,
        ready,
        mod_loaded,
        False,
        sources,
        warnings,
        hits,
    )


def wait_for_startup_evidence(
    collect: Callable[[], EvidenceReport],
    timeout: float,
    *,
    update: Optional[Callable[[EvidenceReport], None]] = None,
    clock: Optional[Callable[[], float]] = None,
    sleeper: Optional[Callable[[float], None]] = None,
    poll_interval: float = STARTUP_POLL_INTERVAL_SECONDS,
) -> EvidenceReport:
    """Poll a collector and preserve the final timeout-boundary diagnosis."""

    clock_function = clock or time.monotonic
    sleep_function = sleeper or time.sleep
    deadline = clock_function() + timeout
    while True:
        report = collect()
        if report.mod_loaded:
            if update is not None:
                update(report)
            return report
        if clock_function() >= deadline:
            # Re-read once at the boundary. The game can append its registration
            # line between the poll and the timeout check.
            final_report = collect()
            if final_report.mod_loaded:
                if update is not None:
                    update(final_report)
                return final_report
            timed_out = EvidenceReport(
                "timeout",
                final_report.ready,
                final_report.mod_loaded,
                True,
                final_report.sources,
                final_report.warnings,
                final_report.hits,
            )
            if update is not None:
                update(timed_out)
            return timed_out
        sleep_function(
            min(
                poll_interval,
                max(0.0, deadline - clock_function()),
            )
        )


__all__ = [
    "DEFAULT_LOG_LINES",
    "STARTUP_POLL_INTERVAL_SECONDS",
    "MAX_EVIDENCE_HITS",
    "MAX_EVIDENCE_TEXT",
    "LOG_OUTPUT_ENCODING",
    "LOG_OUTPUT_ERRORS",
    "LogEvidenceSource",
    "EvidenceHit",
    "EvidenceReport",
    "resolve_unity_log_path",
    "log_signature",
    "capture_log_baselines",
    "log_is_current",
    "read_log_source",
    "chainloader_ready",
    "parse_structured_load_record",
    "target_mod_evidence",
    "bepinex_context_evidence",
    "target_error_evidence",
    "select_evidence_hits",
    "target_mod_loaded",
    "collect_log_evidence",
    "wait_for_startup_evidence",
]
