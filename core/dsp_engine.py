"""
dsp_engine.py
─────────────
Motor de Processamento Digital de Sinais para AudioAgent.
Executa análise acústica e mantém o núcleo matemático do v1.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

# ── Krumhansl-Schmuckler key profiles ──────────────────────────────────────
MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)
CHROMATIC = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

CAMELOT: dict[tuple[str, str], str] = {
    ("C", "major"): "8B", ("C#", "major"): "3B", ("D", "major"): "10B",
    ("D#", "major"): "5B", ("E", "major"): "12B", ("F", "major"): "7B",
    ("F#", "major"): "2B", ("G", "major"): "9B", ("G#", "major"): "4B",
    ("A", "major"): "11B", ("A#", "major"): "6B", ("B", "major"): "1B",
    ("A", "minor"): "8A", ("A#", "minor"): "3A", ("B", "minor"): "10A",
    ("C", "minor"): "5A", ("C#", "minor"): "12A", ("D", "minor"): "7A",
    ("D#", "minor"): "2A", ("E", "minor"): "9A", ("F", "minor"): "4A",
    ("F#", "minor"): "11A", ("G", "minor"): "6A", ("G#", "minor"): "1A",
}

SECTION_LABELS = [
    "Intro", "Verse 1", "Build 1", "Drop 1",
    "Break", "Verse 2", "Build 2", "Drop 2 / Outro",
]


def detect_key(y: np.ndarray, sr: int) -> tuple[str, str, str]:
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    chroma_norm = chroma_mean / (chroma_mean.sum() + 1e-8)

    best_score: float = -np.inf
    best_key: tuple[str, str] = ("C", "major")

    for i, note in enumerate(CHROMATIC):
        shifted = np.roll(chroma_norm, -i)
        maj_corr = float(np.corrcoef(shifted, MAJOR_PROFILE)[0, 1])
        min_corr = float(np.corrcoef(shifted, MINOR_PROFILE)[0, 1])
        if maj_corr > best_score:
            best_score, best_key = maj_corr, (note, "major")
        if min_corr > best_score:
            best_score, best_key = min_corr, (note, "minor")

    note, mode = best_key
    return note, mode, CAMELOT.get(best_key, "N/A")


def analyze_spectral_bands(y: np.ndarray, sr: int) -> dict:
    d_matrix = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)

    def band_db(f_lo: float, f_hi: float) -> float:
        mask = (freqs >= f_lo) & (freqs < f_hi)
        if not mask.any():
            return -80.0
        rms = np.sqrt(np.mean(d_matrix[mask] ** 2))
        return round(float(20.0 * np.log10(rms + 1e-10)), 1)

    return {
        "low_energy_db": band_db(20, 250),
        "mid_energy_db": band_db(250, 4000),
        "high_energy_db": band_db(4000, 20000),
    }


def detect_sections(y: np.ndarray, sr: int, n: int = 8) -> list[dict]:
    hop = 512
    y_harm, y_perc = librosa.effects.hpss(y)

    rms_full = librosa.feature.rms(y=y, hop_length=hop)[0]
    rms_harm = librosa.feature.rms(y=y_harm, hop_length=hop)[0]
    rms_perc = librosa.feature.rms(y=y_perc, hop_length=hop)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]

    duration = len(y) / sr
    seg_dur = duration / n
    max_rms = rms_full.max() + 1e-8
    fps = sr / hop

    sections: list[dict] = []
    for i in range(n):
        t0 = i * seg_dur
        t1 = min((i + 1) * seg_dur, duration)
        f0, f1 = int(t0 * fps), int(t1 * fps)

        def seg_mean(arr: np.ndarray) -> float:
            chunk = arr[f0:f1]
            return float(np.mean(chunk)) if len(chunk) > 0 else 0.0

        energy = seg_mean(rms_full) / max_rms
        m_harm = seg_mean(rms_harm)
        m_perc = seg_mean(rms_perc)
        m_cent = seg_mean(centroid)

        if m_perc > m_harm * 1.4:
            dominant = "drums"
        elif m_cent < 550 and m_harm >= m_perc:
            dominant = "bass"
        elif m_harm > m_perc and m_cent > 1100:
            dominant = "vocals"
        else:
            dominant = "other"

        label = SECTION_LABELS[i] if i < len(SECTION_LABELS) else f"Seção {i + 1}"
        sections.append(
            {
                "section_label": label,
                "timestamp_start": f"{int(t0 // 60):02d}:{int(t0 % 60):02d}",
                "timestamp_end": f"{int(t1 // 60):02d}:{int(t1 % 60):02d}",
                "relative_energy_score": round(energy, 3),
                "dominant_stem": dominant,
            }
        )

    return sections


def analyze_audio(audio_path: str, n_sections: int = 8) -> dict:
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    duration = float(len(y) / sr)

    tempo_raw, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo_raw)[0])

    key_note, key_mode, camelot = detect_key(y, sr)
    freq_dist = analyze_spectral_bands(y, sr)
    sections = detect_sections(y, sr, n=n_sections)

    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)[0]))
    spec_flat = float(np.mean(librosa.feature.spectral_flatness(y=y)[0]))
    spec_bw = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]))

    hop = 512
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    times = librosa.times_like(rms, sr=sr, hop_length=hop)
    step = max(1, len(rms) // 500)

    return {
        "metadata": {
            "source_name": Path(audio_path).name,
            "source_path": str(Path(audio_path).resolve()),
            "duration_seconds": round(duration, 2),
            "sample_rate": int(sr),
            "section_count": int(n_sections),
        },
        "acoustic_metrics": {
            "bpm_measured": round(bpm, 1),
            "key_note": key_note,
            "key_mode": key_mode,
            "camelot_key": camelot,
            "spectral_bandwidth_hz": round(spec_bw, 1),
            "zero_crossing_rate": round(zcr, 5),
            "spectral_flatness": round(spec_flat, 5),
            "frequency_distribution": freq_dist,
        },
        "timeline_sections": sections,
        "_energy_curve": {
            "times": times[::step].tolist(),
            "rms_values": rms[::step].tolist(),
        },
    }

