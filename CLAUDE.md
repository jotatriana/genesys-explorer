# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your Genesys Cloud OAuth client credentials

# Start the development server
python main.py
# Runs at http://localhost:5000 with debug mode enabled
```

No build step, test suite, or linting configuration exists — this is an intentionally minimal local development tool.

## Environment Variables

| Variable | Purpose |
|---|---|
| `GENESYS_CLIENT_ID` | OAuth 2.0 client ID |
| `GENESYS_CLIENT_SECRET` | OAuth 2.0 client secret |
| `GENESYS_REGION` | Region key (e.g. `us_east_1`); see `REGIONS` dict in `main.py` for all 13 options |
| `FLASK_SECRET_KEY` | Flask session signing key |

## Architecture

**Single-file Flask app** — all backend logic lives in `main.py` (639 lines). This is intentional to avoid blueprint complexity.

### GCClient (main.py:57–123)
A singleton (`gc`) that wraps `PureCloudPlatformClientV2`. Key behaviors:
- `connect()` authenticates via OAuth client credentials and stores the token in memory (never on disk).
- `get_api(name)` lazily instantiates and caches SDK API class instances (e.g. `UsersApi`, `RoutingApi`).
- `is_token_valid` checks expiry; stale tokens require re-login.

All 16 Flask routes call `gc.get_api(...)` to interact with Genesys Cloud. Routes check `gc.is_authenticated` and redirect to `/login` if not connected.

### API Playground
`api_method_mappings.json` (22K lines) is a pre-generated index of 85 API namespaces and ~3,186 SDK methods. It is loaded once at startup into the `API_MAPPINGS` global. The `/api/playground/execute` route uses `getattr()` to dynamically invoke any SDK method by name, passing path params and an optional JSON body.

### Frontend
Server-rendered Jinja2 templates using Bootstrap 5 + Chart.js (all via CDN — no build step). Custom styles in `static/css/app.css` implement a GitHub dark theme. All JavaScript is embedded in the templates, not in `static/js/`.

### Key Template Filters
- `to_json_filter` — serializes SDK response models to formatted JSON
- `presence_badge_filter` / `presence_text_filter` — map Genesys presence states to Bootstrap badge colors

## Key Files

| File | Purpose |
|---|---|
| `main.py` | Entire backend: GCClient class, all routes, template filters |
| `api_method_mappings.json` | Pre-generated SDK method index for the API Playground |
| `templates/playground.html` | Interactive API executor (most complex template) |
| `templates/analytics.html` | Real-time queue wallboard with 30s auto-refresh |
| `static/css/app.css` | Dark theme styles |
