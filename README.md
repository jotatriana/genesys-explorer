# Genesys Cloud Explorer

A Flask-based web application for exploring and managing Genesys Cloud PureCloud APIs. Built on the PureCloudPlatformClientV2 Python SDK (v253.0.0).

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-3.1-green)
![SDK](https://img.shields.io/badge/PureCloud%20SDK-253.0.0-orange)
![Theme](https://img.shields.io/badge/Theme-Dark%20Mode-black)

---

## Features

### Dashboard
- Org-wide stats at a glance: users, queues, skills, wrapup codes, groups, locations
- Quick action links to all modules
- Connection info and permission warnings

### User Explorer
- Paginated user listing with search (name, email, department)
- Filter by state (active/inactive/any)
- Real-time presence and routing status badges
- User detail view: profile, skills with proficiency, queue memberships, assigned roles
- Raw JSON inspection toggle

### Queue Manager
- Browse and search all routing queues
- Queue detail view: members, wrapup codes, media settings, skill evaluation method
- Direct links between users and queues

### Analytics Wallboard
- Real-time queue observation data (oWaiting, oInteracting, oOnQueueUsers, oActiveUsers, oOffQueueUsers)
- Auto-refresh toggle (30-second interval)
- Chart.js bar charts for waiting and interacting metrics
- Color-coded alerts for high wait counts

### API Playground
- Browse all 85 APIs and 3,186+ methods from a dropdown
- Filter methods by name, return type, or body model
- Method info panel showing HTTP verb, path, body type, and return type
- Auto-extracted path parameters with input fields
- JSON body editor for POST/PUT/PATCH requests
- Live execution against your connected Genesys Cloud org
- Formatted JSON response viewer
- Request history with status, timing, and verb badges

### Cheat Sheet Viewer
- Rendered SDK cheat sheets with live search and keyword highlighting
- Tabbed view for main cheat sheet and method-to-model extension

---

## Prerequisites

- Python 3.10 or higher
- A Genesys Cloud org with an OAuth Client Credentials grant
- Required OAuth scopes depend on which features you use:
  - `users:readonly` — User Explorer
  - `routing:readonly` — Queues
  - `analytics:readonly` — Analytics Wallboard
  - `authorization:readonly` — Roles/Divisions

---

## Installation

```bash
# Clone or copy the project
cd genesys_explorer

# Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

1. Copy the example environment file:
   ```bash
   copy .env.example .env
   ```

2. Edit `.env` with your credentials:
   ```env
   GENESYS_CLIENT_ID=your-client-id-here
   GENESYS_CLIENT_SECRET=your-client-secret-here
   GENESYS_REGION=us_east_1
   FLASK_SECRET_KEY=change-me-to-a-random-string
   ```

   > **Note:** The `.env` file is optional. You can enter credentials directly on the login page.

### Available Regions

| Region Key | Location |
|-----------|----------|
| `us_east_1` | Americas (US East) |
| `us_east_2` | Americas (US East 2 / FedRAMP) |
| `us_west_2` | Americas (US West) |
| `ca_central_1` | Canada |
| `eu_west_1` | EMEA (Ireland) |
| `eu_west_2` | EMEA (London) |
| `eu_central_1` | EMEA (Frankfurt) |
| `ap_southeast_2` | Asia Pacific (Sydney) |
| `ap_northeast_1` | Asia Pacific (Tokyo) |
| `ap_south_1` | Asia Pacific (Mumbai) |
| `ap_northeast_2` | Asia Pacific (Seoul) |
| `sa_east_1` | South America (Sao Paulo) |
| `me_central_1` | Middle East (UAE) |
| `ap_northeast_3` | Asia Pacific (Osaka) |

---

## Usage

```bash
python main.py
```

Open your browser to **http://localhost:5000**

1. Enter your OAuth Client ID, Client Secret, and select your region
2. Click **Connect** to authenticate
3. Explore the dashboard, users, queues, analytics, and API playground

---

## Project Structure

```
genesys_explorer/
├── main.py                      # Single-file Flask backend (639 lines)
│                                 - GCClient SDK wrapper
│                                 - Auth decorator & session management
│                                 - All routes (16 endpoints)
│                                 - Jinja2 template filters
├── api_method_mappings.json    # Auto-generated index of 3,186 SDK methods
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── static/
│   └── css/
│       └── app.css             # GitHub-dark themed custom styles
└── templates/
    ├── base.html               # Layout: navbar, flash messages, footer
    ├── login.html              # OAuth credentials form
    ├── dashboard.html          # Stats cards, quick actions, connection info
    ├── users.html              # Paginated user table with search
    ├── user_detail.html        # User profile, skills, queues, roles
    ├── queues.html             # Paginated queue browser
    ├── queue_detail.html       # Queue members and wrapup codes
    ├── analytics.html          # Real-time queue wallboard + Chart.js
    ├── playground.html         # API Playground (method picker, executor, history)
    └── cheatsheet.html         # Searchable cheat sheet viewer
```

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Single `main.py`** | Eliminates circular imports, blueprint registration issues, and config scattering |
| **GCClient singleton** | One SDK connection, lazy API instantiation with caching |
| **CDN-only frontend** | Bootstrap 5 + Chart.js + Bootstrap Icons via CDN — no npm/webpack complexity |
| **Every SDK call in try/except** | Graceful degradation when OAuth scopes are missing |
| **Session-based auth** | Token stored in memory, never written to disk |
| **Dark theme by default** | Developer-friendly, reduces eye strain |

---

## API Playground Details

The playground is the flagship feature. It lets you:

1. **Pick any API** from a dropdown of 85 APIs (Users, Routing, Analytics, etc.)
2. **Select a method** from a filterable list showing HTTP verb, method name, and return type
3. **View method metadata**: HTTP verb, REST path, body model, return model
4. **Fill in path parameters** auto-extracted from the URL pattern
5. **Write a JSON body** for POST/PUT/PATCH methods
6. **Execute live** against your connected org
7. **View the response** as formatted JSON with status code and timing
8. **Track history** of all requests with success/error indicators

---

## Security Notes

- Credentials are stored in-memory only (Python process memory)
- No credentials are written to disk, cookies, or logs
- The Flask secret key is used only for flash message sessions
- Tokens expire after ~1 hour and require reconnection
- This application is intended for **local development use only** — do not expose it to the public internet without adding proper security

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: PureCloudPlatformClientV2` | Run `pip install PureCloudPlatformClientV2==253.0.0` |
| `Authentication failed` | Verify Client ID, Secret, and Region. Ensure the OAuth client uses "Client Credentials" grant type |
| Dashboard shows `?` for stats | Your OAuth client is missing the required scopes (e.g., `users:readonly`) |
| API Playground returns 403 | The method requires a scope your OAuth client doesn't have |
| `Connection refused` on port 5000 | Another process is using port 5000. Change with `python main.py` and edit the port in `app.run()` |

---

## Built With

- [Flask](https://flask.palletsprojects.com/) — Python web framework
- [PureCloudPlatformClientV2](https://pypi.org/project/PureCloudPlatformClientV2/) — Genesys Cloud Python SDK
- [Bootstrap 5](https://getbootstrap.com/) — UI framework (dark theme)
- [Chart.js](https://www.chartjs.org/) — Analytics charts
- [Bootstrap Icons](https://icons.getbootstrap.com/) — Icon library
