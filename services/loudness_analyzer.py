from __future__ import annotations

from typing import Any
from pathlib import Path
import hashlib
import json

import numpy as np
import soundfile as sf

from services.config import LOUDNESS_CACHE_DIR, ensure_runtime_dirs, optional_dependency_available
from services.models import ResultEnvelope


def _dbfs(value: float) -> float:
    return round(float(20.0 * np.log10(max(value, 1e-12))), 2)


def _to_mono(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return data.astype(np.float64)
    return np.mean(data.astype(np.float64), axis=1)


def _correlation(data: np.ndarray) -> float | None:
    if data.ndim < 2 or data.shape[1] < 2:
        return None
    left = data[:, 0].astype(np.float64)
    right = data[:, 1].astype(np.float64)
    if np.std(left) < 1e-12 or np.std(right) < 1e-12:
        return None
    return round(float(np.corrcoef(left, right)[0, 1]), 3)


def _crest_factor_db(mono: np.ndarray) -> float:
    peak = float(np.max(np.abs(mono)))
    rms = float(np.sqrt(np.mean(np.square(mono))) + 1e-12)
    return round(float(20.0 * np.log10(max(peak, 1e-12) / rms)), 2)


def _cache_key(audio_path: str) -> str:
    path = Path(audio_path)
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    fingerprint = f"{hasher.hexdigest()}|pyloudnorm:{optional_dependency_available('pyloudnorm')}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]


def _legacy_cache_key(audio_path: str) -> str:
    path = Path(audio_path)
    stat = path.stat()
    fingerprint = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|pyloudnorm:{optional_dependency_available('pyloudnorm')}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]


def _rms_window_loudness(mono: np.ndarray, sr: int, window_seconds: float = 3.0) -> list[float]:
    window = max(1, int(sr * window_seconds))
    if len(mono) < window:
        rms = float(np.sqrt(np.mean(np.square(mono))) + 1e-12)
        return [_dbfs(rms)]
    values = []
    hop = max(1, window // 2)
    for start in range(0, len(mono) - window + 1, hop):
        chunk = mono[start : start + window]
        rms = float(np.sqrt(np.mean(np.square(chunk))) + 1e-12)
        values.append(_dbfs(rms))
    return values


def analyze_loudness(audio_path: str) -> ResultEnvelope:
    ensure_runtime_dirs()
    cache_key = _cache_key(audio_path)
    cache_path = LOUDNESS_CACHE_DIR / f"{cache_key}.json"
    legacy_cache_path = LOUDNESS_CACHE_DIR / f"{_legacy_cache_key(audio_path)}.json"
    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return ResultEnvelope(
            status="success",
            mode=payload.get("method", "cached"),
            data=payload,
            diagnostics=["Loudness reaproveitado do cache local."],
            metadata={"cache_hit": True, "cache_path": str(cache_path)},
        )
    if legacy_cache_path.exists():
        payload = json.loads(legacy_cache_path.read_text(encoding="utf-8"))
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return ResultEnvelope(
            status="success",
            mode=payload.get("method", "cached"),
            data=payload,
            diagnostics=["Loudness reaproveitado e migrado para o cache por conteúdo."],
            metadata={"cache_hit": True, "cache_path": str(cache_path)},
        )

    try:
        data, sr = sf.read(audio_path, always_2d=False)
        if data.size == 0:
            raise ValueError("Arquivo de audio vazio.")

        mono = _to_mono(data)
        peak = float(np.max(np.abs(data)))
        rms = float(np.sqrt(np.mean(np.square(mono))) + 1e-12)
        window_values = _rms_window_loudness(mono, sr)
        lra_proxy = round(float(np.percentile(window_values, 95) - np.percentile(window_values, 10)), 2)

        data_out: dict[str, Any] = {
            "sample_peak_dbfs": _dbfs(peak),
            "rms_loudness_dbfs": _dbfs(rms),
            "loudness_range_proxy_lu": lra_proxy,
            "crest_factor_db": _crest_factor_db(mono),
            "stereo_correlation": _correlation(data),
            "method": "rms_proxy",
            "confidence": "medium",
        }
        diagnostics = [
            "Loudness calculado por RMS/peak local; LUFS real requer pyloudnorm instalado."
        ]

        if optional_dependency_available("pyloudnorm"):
            import pyloudnorm as pyln

            meter = pyln.Meter(sr)
            lufs = float(meter.integrated_loudness(data.astype(np.float64)))
            data_out["integrated_lufs"] = round(lufs, 2)
            data_out["method"] = "pyloudnorm_integrated_lufs"
            data_out["confidence"] = "high"
            diagnostics = [
                "LUFS integrado calculado com pyloudnorm; LRA segue proxy por janelas RMS nesta versão."
            ]

        cache_path.write_text(json.dumps(data_out, ensure_ascii=False), encoding="utf-8")
        return ResultEnvelope(
            status="success",
            mode=data_out["method"],
            data=data_out,
            diagnostics=diagnostics,
            metadata={"cache_hit": False, "cache_path": str(cache_path)},
        )
    except Exception as exc:
        return ResultEnvelope(
            status="success",
            mode="skipped",
            data={},
            diagnostics=[f"Loudness indisponivel nesta rodada: {exc}"],
        )
