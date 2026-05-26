from __future__ import annotations

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any

from services.models import ResultEnvelope


def _best_effort_snippet(text: str, limit_words: int = 12) -> str:
    words = text.replace("\n", " ").split()
    return " ".join(words[:limit_words]).strip()


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _guess_title_artist(title_hint: str, artist_hint: str, source_name: str) -> tuple[str, str]:
    title = title_hint.strip()
    artist = artist_hint.strip()
    if title and artist:
        return title, artist

    base = source_name.strip()
    if not base:
        return title, artist

    if " - " in base:
        left, right = [part.strip() for part in base.split(" - ", 1)]
        if not artist:
            artist = left
        if not title:
            title = right
    elif not title:
        title = base
    return title, artist


def _lrclib_lookup(title: str, artist: str, duration_seconds: float | None) -> dict[str, Any]:
    if not title:
        return {"validated": False, "matches": [], "provider": "lrclib"}

    params = {"track_name": title}
    if artist:
        params["artist_name"] = artist

    url = f"https://lrclib.net/api/search?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "User-Agent": "AudioAgent/2.0 (lyrics validation)",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))

    duration_hint = float(duration_seconds or 0.0)
    matches = []
    for item in payload[:5]:
        duration = float(item.get("duration") or 0.0)
        matches.append(
            {
                "trackName": item.get("trackName"),
                "artistName": item.get("artistName"),
                "albumName": item.get("albumName"),
                "duration": duration,
                "instrumental": bool(item.get("instrumental")),
                "hasSyncedLyrics": bool(item.get("syncedLyrics")),
                "hasPlainLyrics": bool(item.get("plainLyrics")),
                "duration_delta_seconds": round(abs(duration - duration_hint), 1) if duration_hint else None,
            }
        )

    if duration_hint and matches:
        matches.sort(key=lambda item: item.get("duration_delta_seconds") if item.get("duration_delta_seconds") is not None else 9999)

    return {
        "validated": bool(matches),
        "provider": "lrclib",
        "query": params,
        "matches": matches,
    }


def _genius_api_search(query: str, access_token: str) -> list[dict[str, Any]]:
    if not query.strip() or not access_token.strip():
        return []

    url = f"https://api.genius.com/search?{urlencode({'q': query.strip()})}"
    request = Request(
        url,
        headers={
            "User-Agent": "AudioAgent/2.0 (direct genius api)",
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token.strip()}",
        },
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    sections = (((payload or {}).get("response") or {}).get("sections") or [])
    hits: list[dict[str, Any]] = []
    for section in sections:
        for hit in section.get("hits", [])[:8]:
            result = hit.get("result", {})
            hits.append(
                {
                    "id": result.get("id"),
                    "title": result.get("title"),
                    "artist": (result.get("primary_artist") or {}).get("name"),
                    "url": result.get("url"),
                    "full_title": result.get("full_title"),
                    "api_path": result.get("api_path"),
                }
            )
    return hits


def _pick_best_genius_hit(
    hits: list[dict[str, Any]],
    *,
    title_guess: str,
    artist_guess: str,
) -> dict[str, Any] | None:
    if not hits:
        return None

    normalized_title = _normalize_text(title_guess)
    normalized_artist = _normalize_text(artist_guess)
    scored_hits = []
    for hit in hits:
        title = _normalize_text(str(hit.get("title") or ""))
        artist = _normalize_text(str(hit.get("artist") or ""))
        score = 0
        if normalized_title and normalized_title in title:
            score += 3
        if normalized_artist and normalized_artist in artist:
            score += 3
        if normalized_title and title and title in normalized_title:
            score += 1
        if normalized_artist and artist and artist in normalized_artist:
            score += 1
        scored_hits.append((score, hit))

    scored_hits.sort(key=lambda item: item[0], reverse=True)
    best_score, best_hit = scored_hits[0]
    return best_hit if best_score > 0 else hits[0]


def verify_transcript_exists(
    transcript_text: str,
    *,
    title_hint: str = "",
    artist_hint: str = "",
    source_name: str = "",
    duration_seconds: float | None = None,
    genius_token: str = "",
    genius_client_id: str = "",
    genius_client_secret: str = "",
) -> ResultEnvelope:
    if not transcript_text.strip():
        return ResultEnvelope(
            status="success",
            mode="skipped",
            data={},
            diagnostics=["Sem transcrição textual para validar na internet."],
        )

    title_guess, artist_guess = _guess_title_artist(title_hint, artist_hint, source_name)

    if title_guess:
        try:
            lrclib_result = _lrclib_lookup(title_guess, artist_guess, duration_seconds)
            if lrclib_result.get("validated"):
                return ResultEnvelope(
                    status="success",
                    mode="internet_lookup",
                    data={
                        "validated": True,
                        "provider": "lrclib",
                        "title_hint": title_guess,
                        "artist_hint": artist_guess,
                        "matches": lrclib_result.get("matches", []),
                    },
                    diagnostics=["Letra verificada por metadados via LRCLIB."],
                )
        except Exception as exc:
            if not genius_token.strip():
                return ResultEnvelope(
                    status="success",
                    mode="skipped",
                    data={
                        "validated": False,
                        "provider": "lrclib",
                        "title_hint": title_guess,
                        "artist_hint": artist_guess,
                    },
                    diagnostics=[f"Falha na busca LRCLIB e nenhum token Genius foi informado: {exc}"],
                )

    if not genius_token.strip():
        return ResultEnvelope(
            status="success",
            mode="skipped",
            data={
                "validated": False,
                "provider": "none",
                "title_hint": title_guess,
                "artist_hint": artist_guess,
                "oauth_ready": bool(genius_client_id.strip() and genius_client_secret.strip()),
            },
            diagnostics=["Validação por snippet ignorada: GENIUS_ACCESS_TOKEN não informado."],
        )

    try:
        genius_hits = []
        verification_queries = []
        verification_query = " ".join(part for part in [artist_guess, title_guess] if part).strip()
        if verification_query:
            verification_queries.append(verification_query)
        for snippet_size in (6, 10, 14):
            snippet = _best_effort_snippet(transcript_text, limit_words=snippet_size)
            if snippet and snippet not in verification_queries:
                verification_queries.append(snippet)
        for query in verification_queries:
            genius_hits = _genius_api_search(query, genius_token)
            if genius_hits:
                break
        best_hit = _pick_best_genius_hit(genius_hits, title_guess=title_guess, artist_guess=artist_guess)
        if best_hit:
            return ResultEnvelope(
                status="success",
                mode="internet_lookup",
                data={
                    "validated": True,
                    "provider": "genius_api",
                    "title_hint": title_guess,
                    "artist_hint": artist_guess,
                    "oauth_ready": bool(genius_client_id.strip() and genius_client_secret.strip()),
                    "match": best_hit,
                    "matches": genius_hits[:5],
                },
                diagnostics=["Letra/faixa validada pela API oficial do Genius."],
            )
    except Exception as exc:
        genius_api_error = f"Falha na API oficial do Genius: {exc}"
    else:
        genius_api_error = ""

    try:
        import lyricsgenius
    except ImportError:
        return ResultEnvelope(
            status="success",
            mode="skipped",
            data={},
            diagnostics=[msg for msg in [genius_api_error, "lyricsgenius não está instalado neste ambiente."] if msg],
        )

    try:
        genius = lyricsgenius.Genius(
            genius_token.strip(),
            remove_section_headers=True,
            skip_non_songs=True,
            retries=1,
            timeout=8,
        )

        verification: dict[str, Any] = {
            "title_hint": title_guess,
            "artist_hint": artist_guess,
            "search_strategy": [],
        }

        song = None
        if title_guess.strip():
            verification["search_strategy"].append("search_song")
            song = genius.search_song(title=title_guess.strip(), artist=artist_guess.strip(), get_full_info=False)

        if song is None:
            snippet = _best_effort_snippet(transcript_text)
            verification["search_strategy"].append("search_lyrics")
            search_hits = genius.search_lyrics(snippet)
            hits = ((search_hits or {}).get("sections") or [])
            matched_hits = []
            for section in hits:
                for hit in section.get("hits", [])[:5]:
                    result = hit.get("result", {})
                    matched_hits.append(
                        {
                            "title": result.get("title"),
                            "artist": (result.get("primary_artist") or {}).get("name"),
                            "url": result.get("url"),
                        }
                    )
            return ResultEnvelope(
                status="success",
                mode="internet_lookup",
                data={
                    **verification,
                    "validated": bool(matched_hits),
                    "provider": "genius",
                    "oauth_ready": bool(genius_client_id.strip() and genius_client_secret.strip()),
                    "snippet_used": snippet,
                    "matches": matched_hits,
                },
                diagnostics=[msg for msg in [genius_api_error, "Busca de letra realizada via Genius search_lyrics."] if msg],
            )

        return ResultEnvelope(
            status="success",
            mode="internet_lookup",
            data={
                **verification,
                "validated": True,
                "provider": "genius",
                "oauth_ready": bool(genius_client_id.strip() and genius_client_secret.strip()),
                "match": {
                    "title": getattr(song, "title", title_guess),
                    "artist": getattr(getattr(song, "artist", None), "name", None) or artist_guess,
                    "url": getattr(song, "url", None),
                },
            },
            diagnostics=[msg for msg in [genius_api_error, "Letra verificada via Genius search_song."] if msg],
        )
    except Exception as exc:
        return ResultEnvelope(
            status="success",
            mode="skipped",
            data={},
            diagnostics=[msg for msg in [genius_api_error, f"Falha na validação online da letra: {exc}"] if msg],
        )
