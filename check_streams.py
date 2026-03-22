#!/usr/bin/env python3
"""
IPTV Stream Checker
Verifica estado y expiración de canales en playlists M3U
"""

import re
import json
import time
import datetime
import urllib.request
import urllib.error
import urllib.parse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Configuración ────────────────────────────────────────────────────────────
PLAYLIST_URLS = os.environ.get("PLAYLIST_URLS", "").split(",")
TIMEOUT = int(os.environ.get("CHECK_TIMEOUT", "10"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "10"))
OUTPUT_FILE = "results.json"
NOTIFY_WEBHOOK = os.environ.get("NOTIFY_WEBHOOK", "")  # Discord/Slack webhook
# ──────────────────────────────────────────────────────────────────────────────


def fetch_playlist(url: str) -> str | None:
    """Descarga el contenido de una playlist M3U."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "IPTV-Checker/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[ERROR] No se pudo descargar la playlist {url}: {e}")
        return None


def parse_m3u(content: str, source_url: str = "") -> list[dict]:
    """Parsea una playlist M3U y extrae canales."""
    channels = []
    lines = content.strip().splitlines()
    current_info = {}

    # Nombre corto de la fuente (host:port)
    try:
        parsed = urllib.parse.urlparse(source_url)
        source_label = parsed.netloc or source_url
    except Exception:
        source_label = source_url

    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF"):
            name_match = re.search(r',(.+)$', line)
            tvg_id = re.search(r'tvg-id="([^"]*)"', line)
            group = re.search(r'group-title="([^"]*)"', line)
            current_info = {
                "name": name_match.group(1).strip() if name_match else "Unknown",
                "tvg_id": tvg_id.group(1) if tvg_id else "",
                "group": group.group(1) if group else "",
                "source": source_label,
            }
        elif line and not line.startswith("#") and current_info:
            current_info["url"] = line
            channels.append(current_info.copy())
            current_info = {}

    return channels


def check_stream(channel: dict) -> dict:
    """Verifica el estado de un stream individual."""
    url = channel.get("url", "")
    result = {
        "name": channel.get("name", "Unknown"),
        "url": url,
        "group": channel.get("group", ""),
        "tvg_id": channel.get("tvg_id", ""),
        "source": channel.get("source", ""),
        "status": "unknown",
        "http_code": None,
        "response_time_ms": None,
        "expires_at": None,
        "checked_at": datetime.datetime.utcnow().isoformat() + "Z",
        "error": None,
    }

    if not url:
        result["status"] = "error"
        result["error"] = "URL vacía"
        return result

    try:
        start = time.time()
        req = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": "IPTV-Checker/1.0"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            elapsed = int((time.time() - start) * 1000)
            result["http_code"] = resp.status
            result["response_time_ms"] = elapsed

            # Intentar detectar expiración desde headers
            headers = dict(resp.headers)
            expires = (
                headers.get("Expires")
                or headers.get("expires")
                or headers.get("X-Expires")
                or headers.get("x-expires")
            )
            if expires:
                result["expires_at"] = expires

            if resp.status == 200:
                result["status"] = "active"
            elif resp.status == 403:
                result["status"] = "denied"
                result["error"] = "HTTP 403 - Acceso denegado"
            elif resp.status == 404:
                result["status"] = "not_found"
                result["error"] = "HTTP 404 - No encontrado"
            else:
                result["status"] = "error"
                result["error"] = f"HTTP {resp.status}"

    except urllib.error.HTTPError as e:
        result["http_code"] = e.code
        result["status"] = "denied" if e.code == 403 else "error"
        result["error"] = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        result["status"] = "offline"
        result["error"] = str(e.reason)
    except TimeoutError:
        result["status"] = "timeout"
        result["error"] = f"Timeout después de {TIMEOUT}s"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def send_notification(webhook_url: str, fallen: list[dict]) -> None:
    """Envía notificación a Discord o Slack con canales caídos."""
    if not webhook_url or not fallen:
        return

    lines = [f"🔴 *{c['name']}* — {c['error']}" for c in fallen[:20]]
    message = f"⚠️ *IPTV Checker* — {len(fallen)} canal(es) sin acceso\n" + "\n".join(lines)

    # Detectar si es Discord o Slack
    if "discord" in webhook_url:
        payload = json.dumps({"content": message}).encode()
    else:
        payload = json.dumps({"text": message}).encode()

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        print("[OK] Notificación enviada")
    except Exception as e:
        print(f"[WARN] No se pudo enviar notificación: {e}")


def main():
    if not any(PLAYLIST_URLS):
        print("[ERROR] Define PLAYLIST_URLS como variable de entorno.")
        sys.exit(1)

    all_channels = []
    for url in PLAYLIST_URLS:
        url = url.strip()
        if not url:
            continue
        print(f"📥 Descargando playlist: {url}")
        content = fetch_playlist(url)
        if content:
            channels = parse_m3u(content, url)
            print(f"   → {len(channels)} canales encontrados")
            all_channels.extend(channels)

    if not all_channels:
        print("[ERROR] No se encontraron canales.")
        sys.exit(1)

    print(f"\n🔍 Verificando {len(all_channels)} canales con {MAX_WORKERS} workers...\n")
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_stream, ch): ch for ch in all_channels}
        for i, future in enumerate(as_completed(futures), 1):
            res = future.result()
            icon = {"active": "✅", "denied": "🔐", "offline": "❌", "timeout": "⏱️"}.get(
                res["status"], "⚠️"
            )
            print(f"[{i:>4}/{len(all_channels)}] {icon} {res['name'][:40]:<40} {res['status']}")
            results.append(res)

    # Ordenar por nombre
    results.sort(key=lambda x: x["name"].lower())

    # Estadísticas
    stats = {
        "total": len(results),
        "active": sum(1 for r in results if r["status"] == "active"),
        "denied": sum(1 for r in results if r["status"] == "denied"),
        "offline": sum(1 for r in results if r["status"] == "offline"),
        "timeout": sum(1 for r in results if r["status"] == "timeout"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "last_check": datetime.datetime.utcnow().isoformat() + "Z",
    }

    output = {"stats": stats, "channels": results}

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n📊 Resultados:")
    print(f"   ✅ Activos  : {stats['active']}")
    print(f"   🔐 Denegados: {stats['denied']}")
    print(f"   ❌ Offline  : {stats['offline']}")
    print(f"   ⏱️  Timeout  : {stats['timeout']}")
    print(f"\n💾 Guardado en {OUTPUT_FILE}")

    # Notificar canales caídos
    fallen = [r for r in results if r["status"] in ("denied", "offline", "error")]
    if NOTIFY_WEBHOOK and fallen:
        send_notification(NOTIFY_WEBHOOK, fallen)

    # Salir con error si hay canales caídos (útil para CI)
    if stats["active"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
