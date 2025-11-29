"""
LetsCycleToRecycle - E-Waste Tracking System
Flask Web Application (Phase 2 - Oracle + QR Services)

Architecture:
- Customer Portal: Public device tracking via QR codes
- Employee Portal: Authenticated intake and management

Data Layer:
- All Oracle + QR logic is handled in:
    - db.py        → get_connection()
    - services.py  → get_device_by_mac(), register_device_with_order()

This file only defines:
    - Flask app
    - Routes
    - Session-based employee auth
"""

import os
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_from_directory,
)

# Service layer: all DB + QR logic lives here
from services import get_device_by_mac, register_device_with_order, QR_FOLDER, BASE_TRACK_URL

# ======================================================================
#                         FLASK APP INITIALIZATION
# ======================================================================

app = Flask(__name__)

# Security: Load secret key from environment variable in production
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "dev-secret-key-change-in-production",
)

# ======================================================================
#                        EMPLOYEE AUTH (PROTOTYPE)
# ======================================================================

# For now we still use an in-memory employee store.
# Later, you can move this to Oracle EMPLOYEE table.
EMPLOYEE_USERS = {
    "tech01": {
        "password": "Pass123!",  # TODO: Hash passwords using bcrypt/argon2
        "full_name": "Lab Technician 01",
        "role": "Tech",
    },
    "admin01": {
        "password": "Admin123!",
        "full_name": "Recycling Center Admin",
        "role": "Admin",
    },
}

# ======================================================================
#                  CUSTOMER-FACING ROUTES (PUBLIC)
# ======================================================================


@app.route("/", methods=["GET", "POST"])
def track_device():
    """
    Homepage: Manual device tracking interface (MAC address search)

    Phase 2 behavior:
        - Read device data from Oracle via services.get_device_by_mac()
        - If not found, show a friendly error message.
    """
    device_id = ""
    device = None
    error = None

    if request.method == "POST":
        # Extract and sanitize user input
        device_id = request.form.get("device_id", "").strip()

        if device_id:
            # Oracle lookup handled in services.py
            device = get_device_by_mac(device_id)

        if device is None:
            error = (
                "Device ID not found. Please verify your MAC address "
                "or contact the recycling center."
            )

    # In Phase 2 we don't show demo sample IDs.
    sample_ids = []

    return render_template(
        "track.html",
        device_id=device_id,
        device=device,
        error=error,
        sample_ids=sample_ids,
    )


@app.route("/track/<device_id>", methods=["GET"])
def track_device_direct(device_id):
    """
    QR Code Landing Page: Direct device lookup by MAC address

    URL example (inside QR):
        http://YOUR_PUBLIC_URL/track/9a:4b:7c:12:ff:09

    Behavior:
        - Uses services.get_device_by_mac(device_id)
        - No authentication required (public tracking)
    """
    error = None
    device = None

    if device_id:
        device = get_device_by_mac(device_id)

    if device is None:
        error = "Device ID not found. Please contact the recycling center."

    sample_ids = []  # kept for template compatibility

    return render_template(
        "track.html",
        device_id=device_id,
        device=device,
        error=error,
        sample_ids=sample_ids,
    )


# ======================================================================
#                 EMPLOYEE PORTAL ROUTES (AUTHENTICATED)
# ======================================================================


@app.route("/employee/login", methods=["GET", "POST"])
def employee_login():
    """
    Employee Authentication Endpoint (prototype)

    Future upgrade:
        - Hash passwords
        - Store users in Oracle EMPLOYEE table
    """
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = EMPLOYEE_USERS.get(username)

        if user and user["password"] == password:
            # Create authenticated session
            session["employee_username"] = username
            session["employee_role"] = user.get("role", "Tech")
            return redirect(url_for("employee_dashboard"))
        else:
            error = "Invalid credentials. Please try again."

    return render_template("employee_login.html", error=error)


@app.route("/employee/logout")
def employee_logout():
    """
    Session Termination Endpoint
    """
    session.clear()
    return redirect(url_for("employee_login"))


@app.route("/employee/dashboard")
def employee_dashboard():
    """
    Employee Dashboard (Protected Route)
    """
    username = session.get("employee_username")
    if not username:
        return redirect(url_for("employee_login"))

    user = EMPLOYEE_USERS.get(username, {})
    full_name = user.get("full_name", username)
    role = user.get("role", "Employee")

    return render_template(
        "employee_dashboard.html",
        full_name=full_name,
        role=role,
    )


@app.route("/employee/intake", methods=["GET", "POST"])
def employee_intake():
    """
    Device Intake Form (Protected Route)

    On POST:
        - Call services.register_device_with_order()
          which:
            * Inserts CUSTOMER / RECYCLINGORDER / DEVICE / ORDLINE into Oracle
            * Generates QR code PNG and saves it to qr_codes/
        - Redirects to /employee/qr/<device_id> for a clean QR page.
    """
    if "employee_username" not in session:
        return redirect(url_for("employee_login"))

    # GET → just render the blank form
    if request.method == "GET":
        return render_template("employee_intake.html", message=None, result=None)

    # POST → handle form submission
    try:
        employee_username = session.get("employee_username")
        result = register_device_with_order(request.form, employee_username)

     
        # Build a fully qualified URL to the tracking page (no hard-coded localhost)
        track_url = f"{BASE_TRACK_URL}{result['mac_addr']}"

        # Store in session so the QR page can read it
        session["last_mac"] = result["mac_addr"]
        session["last_track_url"] = track_url

        # Redirect to clean QR page
        return redirect(url_for("employee_qr_page", device_id=result["device_id"]))

    except Exception as e:
        # Log error for debugging; show generic message to user
        print("Error during device intake:", e)
        message = {
            "type": "error",
            "text": (
                "There was a problem saving this device. "
                "Please try again or contact the system administrator."
            ),
        }
        return render_template("employee_intake.html", message=message, result=None)


@app.route("/employee/qr/<int:device_id>")
def employee_qr_page(device_id):
    """
    After successful intake, show the QR code clean page.
    """
    mac_addr = session.get("last_mac")
    track_url = session.get("last_track_url")

    if not mac_addr or not track_url:
        return "No QR data found. Please record intake again."

    qr_filename = f"{device_id}.png"

    return render_template(
        "employee_qr.html",
        device_id=device_id,
        mac_addr=mac_addr,
        qr_filename=qr_filename,
        track_url=track_url,
    )


# ======================================================================
#                  STATIC SERVE FOR QR CODE IMAGES
# ======================================================================


@app.route("/qr_codes/<path:filename>")
def serve_qr_code(filename):
    """
    Serve QR code PNGs from the local qr_codes folder.

    This keeps QR generation logic in services.py,
    while Flask takes care of actually serving the image.
    """
    qr_folder = os.path.join(app.root_path, "qr_codes")
    return send_from_directory(qr_folder, filename)


# ======================================================================
#                         APPLICATION ENTRY POINT
# ======================================================================

if __name__ == "__main__":
    """
    Flask Development Server

    On Render, you typically use gunicorn instead of this.
    """
    app.run(debug=True, host="0.0.0.0", port=5000)
