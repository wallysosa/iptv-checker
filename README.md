# 📺 IPTV Stream Checker

Verifica automáticamente el estado de tus canales IPTV y guarda los resultados en `results.json`. Se ejecuta cada 6 horas con GitHub Actions (gratis).

## ✨ Características

- ✅ Detecta canales **activos**, **denegados (403)**, **offline** y **timeout**
- 🕐 Detecta **fecha de expiración** desde headers HTTP (`Expires`, `X-Expires`)
- 🔔 **Notificaciones** por Discord o Slack cuando un canal cae
- 💾 Resultados en `results.json` con historial versionado en git
- ⚡ Verificación paralela (hasta 15 workers simultáneos)
- 🤖 Se ejecuta automáticamente cada 6 horas con GitHub Actions

---

## 🚀 Configuración rápida

### 1. Crear el repositorio en GitHub

```bash
git init iptv-checker
cd iptv-checker
# Copia todos los archivos aquí
git add .
git commit -m "initial commit"
gh repo create iptv-checker --public --push
```

### 2. Agregar los Secrets en GitHub

Ve a tu repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Descripción | Ejemplo |
|--------|-------------|---------|
| `PLAYLIST_URLS` | URLs de tus playlists separadas por coma | `http://servidor:8000/playlist.m3u` |
| `NOTIFY_WEBHOOK` | *(Opcional)* Webhook de Discord o Slack | `https://discord.com/api/webhooks/...` |

### 3. Activar GitHub Actions

Ve a **Actions** en tu repo y haz clic en **"I understand my workflows, go ahead and enable them"**.

Para ejecutarlo manualmente: **Actions → IPTV Stream Checker → Run workflow**

---

## 📄 Formato de results.json

```json
{
  "stats": {
    "total": 50,
    "active": 42,
    "denied": 5,
    "offline": 2,
    "timeout": 1,
    "error": 0,
    "last_check": "2025-01-15T12:00:00Z"
  },
  "channels": [
    {
      "name": "SENALPATSCZ",
      "url": "http://servidor:8000/play/a01f/index.m3u8",
      "group": "Bolivia",
      "tvg_id": "",
      "status": "denied",
      "http_code": 403,
      "response_time_ms": 220,
      "expires_at": null,
      "checked_at": "2025-01-15T12:00:00Z",
      "error": "HTTP 403 - Acceso denegado"
    }
  ]
}
```

### Estados posibles

| Estado | Descripción |
|--------|-------------|
| `active` | Canal funcionando (HTTP 200) |
| `denied` | Acceso denegado (HTTP 403) |
| `not_found` | URL no existe (HTTP 404) |
| `offline` | Servidor no responde |
| `timeout` | Sin respuesta en el tiempo límite |
| `error` | Otro error HTTP |

---

## 🔔 Notificaciones

### Discord

1. En tu servidor de Discord: **Configuración del canal → Integraciones → Webhooks → Nuevo webhook**
2. Copia la URL y agrégala como secret `NOTIFY_WEBHOOK`

### Slack

1. Crea una app en [api.slack.com](https://api.slack.com/apps) con Incoming Webhooks
2. Copia la URL y agrégala como secret `NOTIFY_WEBHOOK`

---

## 🛠️ Ejecución local

```bash
export PLAYLIST_URLS="http://tu-servidor:8000/playlist.m3u"
export CHECK_TIMEOUT=10
export MAX_WORKERS=10
python check_streams.py
```

---

## ⚙️ Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PLAYLIST_URLS` | — | URLs separadas por coma *(requerido)* |
| `CHECK_TIMEOUT` | `10` | Segundos de timeout por canal |
| `MAX_WORKERS` | `10` | Verificaciones en paralelo |
| `NOTIFY_WEBHOOK` | — | URL webhook Discord/Slack *(opcional)* |
