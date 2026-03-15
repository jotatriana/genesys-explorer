"""
Genesys Cloud Explorer — Flask Web Application
A visual tool for exploring and managing Genesys Cloud PureCloud APIs.

Run:  python main.py
Then:  http://localhost:5001
"""

import json
import os
import time
import traceback
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)

load_dotenv()

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

# Load the pre-generated API method→model mappings
MAPPINGS_PATH = os.path.join(os.path.dirname(__file__), "api_method_mappings.json")
with open(MAPPINGS_PATH, encoding="utf-8") as f:
    API_MAPPINGS = json.load(f)

# Available Genesys Cloud regions
REGIONS = {
    "us_east_1":      "Americas (US East) — mypurecloud.com",
    "us_east_2":      "Americas (US East 2) — use2.us-gov-pure.cloud",
    "us_west_2":      "Americas (US West) — usw2.pure.cloud",
    "ca_central_1":   "Canada — cac1.pure.cloud",
    "eu_west_1":      "EMEA (Ireland) — mypurecloud.ie",
    "eu_west_2":      "EMEA (London) — euw2.pure.cloud",
    "eu_central_1":   "EMEA (Frankfurt) — mypurecloud.de",
    "ap_southeast_2": "Asia Pacific (Sydney) — mypurecloud.com.au",
    "ap_northeast_1": "Asia Pacific (Tokyo) — mypurecloud.jp",
    "ap_south_1":     "Asia Pacific (Mumbai) — aps1.pure.cloud",
    "ap_northeast_2": "Asia Pacific (Seoul) — apne2.pure.cloud",
    "sa_east_1":      "South America (São Paulo) — sae1.pure.cloud",
    "me_central_1":   "Middle East (UAE) — mec1.pure.cloud",
    "ap_northeast_3": "Asia Pacific (Osaka) — apne3.pure.cloud",
}


# ---------------------------------------------------------------------------
# SDK Client Singleton (stored in app context, not session)
# ---------------------------------------------------------------------------
class GCClient:
    """Thin wrapper around PureCloudPlatformClientV2 to manage auth state."""

    def __init__(self):
        self.api_client = None
        self.authenticated = False
        self.region = None
        self.token_expiry = None
        self._api_cache = {}

    def connect(self, client_id, client_secret, region):
        import PureCloudPlatformClientV2

        self.api_client = PureCloudPlatformClientV2.api_client.ApiClient()

        # Set region host
        region_host = getattr(
            PureCloudPlatformClientV2.PureCloudRegionHosts, region, None
        )
        if region_host:
            self.api_client.configuration.host = region_host.get_api_host()

        # Authenticate
        self.api_client.get_client_credentials_token(client_id, client_secret)
        self.authenticated = True
        self.region = region
        self.token_expiry = time.time() + 3600  # tokens last ~1hr
        self._api_cache.clear()
        return True

    def get_api(self, api_name):
        """Lazily instantiate and cache API class instances.
        api_name example: 'UsersApi', 'RoutingApi', etc.
        """
        if api_name not in self._api_cache:
            import PureCloudPlatformClientV2
            api_cls = getattr(PureCloudPlatformClientV2.apis, api_name, None)
            if api_cls is None:
                # Try the module-level import
                mod = __import__(
                    f"PureCloudPlatformClientV2.apis.{self._to_snake(api_name)}",
                    fromlist=[api_name]
                )
                api_cls = getattr(mod, api_name)
            self._api_cache[api_name] = api_cls(self.api_client)
        return self._api_cache[api_name]

    def disconnect(self):
        self.api_client = None
        self.authenticated = False
        self.region = None
        self.token_expiry = None
        self._api_cache.clear()

    @property
    def is_token_valid(self):
        if not self.authenticated or not self.token_expiry:
            return False
        return time.time() < self.token_expiry

    @staticmethod
    def _to_snake(name):
        """Convert CamelCase to snake_case: 'UsersApi' -> 'users_api'"""
        import re
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# Global client instance
gc = GCClient()


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not gc.authenticated:
            flash("Please connect to Genesys Cloud first.", "warning")
            return redirect(url_for("login"))
        if not gc.is_token_valid:
            flash("Session expired. Please reconnect.", "warning")
            gc.disconnect()
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {
        "authenticated": gc.authenticated,
        "region": gc.region,
        "now": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if gc.authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        client_id = request.form.get("client_id", "").strip()
        client_secret = request.form.get("client_secret", "").strip()
        region = request.form.get("region", "us_east_1")

        if not client_id or not client_secret:
            flash("Client ID and Secret are required.", "danger")
            return render_template("login.html", regions=REGIONS)

        try:
            gc.connect(client_id, client_secret, region)
            session["region"] = region
            flash("Connected to Genesys Cloud!", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            flash(f"Authentication failed: {e}", "danger")
            return render_template("login.html", regions=REGIONS)

    return render_template("login.html", regions=REGIONS)


@app.route("/logout")
def logout():
    gc.disconnect()
    session.clear()
    flash("Disconnected.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes — Dashboard
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@require_auth
def dashboard():
    stats = {}
    errors = []

    # Gather quick stats — each one is independent, so we catch errors individually
    try:
        users_api = gc.get_api("UsersApi")
        result = users_api.get_users(page_size=1, page_number=1)
        stats["total_users"] = result.total
    except Exception as e:
        errors.append(f"Users: {e}")
        stats["total_users"] = "?"

    try:
        routing_api = gc.get_api("RoutingApi")
        result = routing_api.get_routing_queues(page_size=1, page_number=1)
        stats["total_queues"] = result.total
    except Exception as e:
        errors.append(f"Queues: {e}")
        stats["total_queues"] = "?"

    try:
        routing_api = gc.get_api("RoutingApi")
        result = routing_api.get_routing_skills(page_size=1, page_number=1)
        stats["total_skills"] = result.total
    except Exception as e:
        errors.append(f"Skills: {e}")
        stats["total_skills"] = "?"

    try:
        routing_api = gc.get_api("RoutingApi")
        result = routing_api.get_routing_wrapupcodes(page_size=1, page_number=1)
        stats["total_wrapupcodes"] = result.total
    except Exception as e:
        errors.append(f"Wrapup Codes: {e}")
        stats["total_wrapupcodes"] = "?"

    try:
        groups_api = gc.get_api("GroupsApi")
        result = groups_api.get_groups(page_size=1, page_number=1)
        stats["total_groups"] = result.total
    except Exception as e:
        errors.append(f"Groups: {e}")
        stats["total_groups"] = "?"

    try:
        loc_api = gc.get_api("LocationsApi")
        result = loc_api.get_locations(page_size=1, page_number=1)
        stats["total_locations"] = result.total
    except Exception as e:
        errors.append(f"Locations: {e}")
        stats["total_locations"] = "?"

    return render_template("dashboard.html", stats=stats, errors=errors)


# ---------------------------------------------------------------------------
# Routes — Users
# ---------------------------------------------------------------------------
@app.route("/users")
@require_auth
def users_list():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 25, type=int)
    search_q = request.args.get("q", "").strip()
    state_filter = request.args.get("state", "active")

    try:
        users_api = gc.get_api("UsersApi")

        if search_q:
            # Use search endpoint
            import PureCloudPlatformClientV2
            body = PureCloudPlatformClientV2.UserSearchRequest()
            body.page_size = page_size
            body.page_number = page
            body.query = [{
                "value": search_q,
                "fields": ["name", "email", "department"],
                "type": "CONTAINS"
            }]
            body.sort_order = "ASC"
            body.sort_by = "name"
            result = users_api.post_users_search(body)
            users = result.results or []
            total = result.total or 0
            page_count = max(1, -(-total // page_size))  # ceil div
        else:
            result = users_api.get_users(
                page_size=page_size,
                page_number=page,
                state=state_filter,
                expand=["presence", "routingStatus"]
            )
            users = result.entities or []
            total = result.total or 0
            page_count = result.page_count or 1

    except Exception as e:
        flash(f"Error loading users: {e}", "danger")
        users, total, page_count = [], 0, 1

    return render_template(
        "users.html",
        users=users, total=total, page=page,
        page_size=page_size, page_count=page_count,
        search_q=search_q, state_filter=state_filter
    )


@app.route("/users/<user_id>")
@require_auth
def user_detail(user_id):
    try:
        users_api = gc.get_api("UsersApi")
        user = users_api.get_user(
            user_id,
            expand=["presence", "routingStatus", "skills", "languages",
                     "locations", "groups", "employerInfo"]
        )
        queues = users_api.get_user_queues(user_id, page_size=100)
        roles = users_api.get_user_roles(user_id)
    except Exception as e:
        flash(f"Error loading user: {e}", "danger")
        return redirect(url_for("users_list"))

    return render_template(
        "user_detail.html",
        user=user,
        queues=queues.entities if queues and queues.entities else [],
        roles=roles
    )


# ---------------------------------------------------------------------------
# Routes — Queues
# ---------------------------------------------------------------------------
@app.route("/queues")
@require_auth
def queues_list():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 25, type=int)
    search_q = request.args.get("q", "").strip()

    try:
        routing_api = gc.get_api("RoutingApi")
        if search_q:
            result = routing_api.get_routing_queues(
                page_size=page_size, page_number=page, name=f"*{search_q}*"
            )
        else:
            result = routing_api.get_routing_queues(
                page_size=page_size, page_number=page
            )
        queues = result.entities or []
        total = result.total or 0
        page_count = result.page_count or 1
    except Exception as e:
        flash(f"Error loading queues: {e}", "danger")
        queues, total, page_count = [], 0, 1

    return render_template(
        "queues.html",
        queues=queues, total=total, page=page,
        page_size=page_size, page_count=page_count, search_q=search_q
    )


@app.route("/queues/<queue_id>")
@require_auth
def queue_detail(queue_id):
    try:
        routing_api = gc.get_api("RoutingApi")
        queue = routing_api.get_routing_queue(queue_id)
        members = routing_api.get_routing_queue_members(queue_id, page_size=100)
        wrapup_codes = routing_api.get_routing_queue_wrapupcodes(queue_id, page_size=100)
    except Exception as e:
        flash(f"Error loading queue: {e}", "danger")
        return redirect(url_for("queues_list"))

    return render_template(
        "queue_detail.html",
        queue=queue,
        members=members.entities if members and members.entities else [],
        wrapup_codes=wrapup_codes.entities if wrapup_codes and wrapup_codes.entities else []
    )


# ---------------------------------------------------------------------------
# Routes — Analytics (Queue Observations — real-time wallboard)
# ---------------------------------------------------------------------------
@app.route("/analytics")
@require_auth
def analytics():
    return render_template("analytics.html")


@app.route("/api/analytics/queues", methods=["POST"])
@require_auth
def api_analytics_queues():
    """AJAX endpoint: fetch real-time queue observation data."""
    try:
        import PureCloudPlatformClientV2

        routing_api = gc.get_api("RoutingApi")
        all_queues = routing_api.get_routing_queues(page_size=100, page_number=1)
        queue_ids = [q.id for q in (all_queues.entities or [])]

        if not queue_ids:
            return jsonify({"queues": [], "observations": []})

        # Build observation query
        analytics_api = gc.get_api("AnalyticsApi")
        body = PureCloudPlatformClientV2.QueueObservationQuery()
        body.filter = {
            "type": "or",
            "predicates": [
                {"dimension": "queueId", "value": qid} for qid in queue_ids[:20]
            ]
        }
        body.metrics = [
            "oActiveUsers", "oWaiting", "oInteracting",
            "oOnQueueUsers", "oOffQueueUsers"
        ]
        result = analytics_api.post_analytics_queues_observations_query(body)

        # Build a queue_id -> name map
        q_map = {q.id: q.name for q in (all_queues.entities or [])}

        observations = []
        for r in (result.results or []):
            queue_id = None
            for g in (r.group or []):
                if hasattr(g, "value"):
                    queue_id = g.value
                    break
            if not queue_id:
                continue

            metrics = {}
            for d in (r.data or []):
                metric_name = d.metric if hasattr(d, "metric") else "unknown"
                stats = d.stats if hasattr(d, "stats") else None
                if stats:
                    metrics[metric_name] = {
                        "count": getattr(stats, "count", 0),
                        "current": getattr(stats, "current", 0),
                    }

            observations.append({
                "queue_id": queue_id,
                "queue_name": q_map.get(queue_id, queue_id),
                "metrics": metrics,
            })

        return jsonify({"observations": observations})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Routes — API Playground
# ---------------------------------------------------------------------------
@app.route("/playground")
@require_auth
def playground():
    return render_template("playground.html", api_mappings=API_MAPPINGS)


@app.route("/api/playground/apis")
@require_auth
def playground_apis():
    """Return list of API names for the dropdown."""
    apis = []
    for api_name, methods in sorted(API_MAPPINGS.items()):
        apis.append({
            "name": api_name,
            "method_count": len(methods),
            "class_name": api_name.replace(" ", "") + "Api"
        })
    return jsonify(apis)


@app.route("/api/playground/methods/<api_name>")
@require_auth
def playground_methods(api_name):
    """Return methods for a given API."""
    methods = API_MAPPINGS.get(api_name, [])
    return jsonify(methods)


@app.route("/api/playground/execute", methods=["POST"])
@require_auth
def playground_execute():
    """Execute an arbitrary SDK method and return the result."""
    data = request.get_json()
    api_class = data.get("api_class", "")
    method_name = data.get("method", "")
    params = data.get("params", {})
    body_json = data.get("body")

    start_time = time.time()

    try:
        api_instance = gc.get_api(api_class)
        method_fn = getattr(api_instance, method_name, None)
        if method_fn is None:
            return jsonify({"error": f"Method '{method_name}' not found on {api_class}"}), 400

        # Build kwargs
        kwargs = {}
        for k, v in params.items():
            if v != "" and v is not None:
                kwargs[k] = v

        # If there's a body, try to pass it as the `body` parameter
        if body_json:
            if isinstance(body_json, str):
                body_json = json.loads(body_json)
            kwargs["body"] = body_json

        # Execute
        result = method_fn(**kwargs)

        elapsed = round((time.time() - start_time) * 1000, 1)

        # Serialize result
        if result is None:
            response_data = None
        elif hasattr(result, "to_dict"):
            response_data = result.to_dict()
        elif isinstance(result, (dict, list, str, int, float, bool)):
            response_data = result
        else:
            response_data = str(result)

        return jsonify({
            "success": True,
            "elapsed_ms": elapsed,
            "result": response_data
        })

    except Exception as e:
        elapsed = round((time.time() - start_time) * 1000, 1)
        error_body = None
        if hasattr(e, "body"):
            try:
                error_body = json.loads(e.body)
            except (json.JSONDecodeError, TypeError):
                error_body = str(e.body) if e.body else None

        return jsonify({
            "success": False,
            "elapsed_ms": elapsed,
            "error": str(e),
            "status": getattr(e, "status", None),
            "error_body": error_body,
            "traceback": traceback.format_exc()
        }), 400


# ---------------------------------------------------------------------------
# Routes — Cheat Sheet Viewer
# ---------------------------------------------------------------------------
@app.route("/cheatsheet")
@require_auth
def cheatsheet():
    # Load cheat sheet files if they exist
    base_dir = os.path.dirname(os.path.dirname(__file__))
    sheets = {}

    for name, filename in [
        ("main", "PureCloudPlatformClientV2_CheatSheet.md"),
        ("extension", "PureCloudPlatformClientV2_CheatSheet_Extension.md"),
    ]:
        path = os.path.join(base_dir, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                sheets[name] = f.read()
        else:
            sheets[name] = f"# File not found: {filename}"

    return render_template("cheatsheet.html", sheets=sheets)


# ---------------------------------------------------------------------------
# Jinja Filters
# ---------------------------------------------------------------------------
@app.template_filter("to_json")
def to_json_filter(obj):
    """Convert a SDK model object to a JSON string for templates."""
    if obj is None:
        return "null"
    if hasattr(obj, "to_dict"):
        return json.dumps(obj.to_dict(), indent=2, default=str)
    return json.dumps(obj, indent=2, default=str)


@app.template_filter("presence_badge")
def presence_badge_filter(user):
    """Return a Bootstrap badge class for a user's presence."""
    try:
        sp = user.presence.presence_definition.system_presence
    except (AttributeError, TypeError):
        return "secondary"

    mapping = {
        "Available": "success",
        "On Queue": "success",
        "Busy": "danger",
        "Away": "warning",
        "Break": "info",
        "Meal": "info",
        "Meeting": "primary",
        "Training": "primary",
        "Offline": "dark",
        "Idle": "secondary",
    }
    return mapping.get(sp, "secondary")


@app.template_filter("presence_text")
def presence_text_filter(user):
    """Return the system presence text for a user."""
    try:
        return user.presence.presence_definition.system_presence
    except (AttributeError, TypeError):
        return "Unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
