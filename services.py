# services.py
import os
import qrcode

from db import get_connection

"""
Service layer for LetsCycleToRecycle.

Responsibilities:
- Read from Oracle (SELECT)
- Write to Oracle (INSERT via sequences)
- Generate QR codes
- Return simple Python dictionaries to app.py
"""

# ---------------------------------------------------------------------
# QR CODE CONFIG
# ---------------------------------------------------------------------

BASE_DIR = os.path.dirname(__file__)
QR_FOLDER = os.path.join(BASE_DIR, "qr_codes")
os.makedirs(QR_FOLDER, exist_ok=True)

# Base URL encoded inside the QR code.
# LOCAL  : http://localhost:5000/track/
# NGROK  : https://<application-id>.ngrok.io/track/
# RENDER : https://<our-app>.onrender.com/track/
BASE_TRACK_URL = os.getenv("BASE_TRACK_URL", "http://localhost:5000/track/")


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def _split_customer_name(full_name: str):
    """
    'James Smith' -> ('James', 'Smith')
    'DIPINA'      -> ('DIPINA', '')
    '' or None    -> ('', '')
    """
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _parse_weight(value: str, default: float = 1.0) -> float:
    """
    Safely parse weight from string → float.
    If invalid, return default instead of crashing.
    """
    try:
        value = (value or "").strip()
        if not value:
            return default
        return float(value)
    except ValueError:
        return default


def _generate_qr_for_mac(mac_addr: str, device_id: str) -> str:
    """
    Create a QR code PNG for the given MAC address.

    Returns:
        qr_filename (e.g., '12345.png')
    """
    track_url = BASE_TRACK_URL + mac_addr  # e.g. http://host/track/9a:4b...
    img = qrcode.make(track_url)

    qr_filename = f"{device_id}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)
    img.save(qr_path)

    return qr_filename


# ---------------------------------------------------------------------
# READ OPERATION: CUSTOMER TRACKING
# ---------------------------------------------------------------------

def get_device_by_mac(mac_addr: str):
    """
    Look up a device by MAC address (IotMacAddr) in Oracle.

    Returns:
        dict shaped like the template expects, or
        None if not found or on error.
    """
    mac_addr = (mac_addr or "").strip()
    if not mac_addr:
        return None

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                d.DeviceType,
                d.Make,
                d.Model,
                d.SerialNo,
                d.HazardClass,
                d.WeightKg,
                d.Status,
                r.DropOffSite,
                TO_CHAR(r.OrdDate, 'YYYY-MM-DD') AS OrdDate,
                c.CustFirstName,
                c.CustLastName
            FROM Device d
            JOIN OrdLine        ol ON ol.DeviceID = d.DeviceID
            JOIN RecyclingOrder  r ON r.OrdNo     = ol.OrdNo
            JOIN Customer        c ON c.CustNo    = r.CustNo
            WHERE d.IotMacAddr = :mac
        """, {"mac": mac_addr})

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return None

        return {
            "type":          row[0],
            "make":          row[1],
            "model":         row[2],
            "serial_no":     row[3],
            "hazard_class":  row[4],
            "weight_kg":     row[5],
            "status":        row[6],
            "dropoff_site":  row[7],
            "received_date": row[8],
            "customer_name": f"{row[9]} {row[10]}",
            "timeline": [
                ("Received", "Device received at LetsCycleToRecycle center"),
                ("Under Recycle Check", "Technician inspecting components"),
                ("In Laboratory", "Hazardous materials being processed"),
                ("Recycled", "Metals recovered and logged"),
            ],
        }

    except Exception as e:
        print("Error in get_device_by_mac:", e)
        return None


# ---------------------------------------------------------------------
# WRITE OPERATION: EMPLOYEE INTAKE
# ---------------------------------------------------------------------

def register_device_with_order(form_data, employee_username: str):
    """
    Core transaction for Phase 2:

    - Find EmpNo for logged-in employee
    - Insert or reuse Customer (by email) via seq_customer
    - Insert RecyclingOrder via seq_order
    - Insert Device via seq_device (with QR code + MAC)
    - Insert OrdLine (1 line per device)

    Returns:
        dict with { device_id, qr_filename, mac_addr }
    """

    # ------------ Extract & normalize form fields ------------ #
    mac_addr       = form_data.get("mac_address", "").strip()
    device_type    = form_data.get("device_type", "").strip()
    make           = form_data.get("make", "").strip()
    model          = form_data.get("model", "").strip()
    serial_no      = form_data.get("serial_no", "").strip()
    customer_name  = form_data.get("customer_name", "").strip()
    customer_email = form_data.get("customer_email", "").strip()
    dropoff_site   = form_data.get("dropoff_site", "Main Facility").strip()
    status         = form_data.get("status", "Received").strip()
    notes          = form_data.get("notes", "").strip()
    hazard_class   = form_data.get("hazard_class", "Medium").strip()
    weight_kg      = _parse_weight(form_data.get("weight_kg", "1.0"), default=1.0)

    cust_first, cust_last = _split_customer_name(customer_name)
    if not cust_first:
        cust_first = "Unknown"
    if not cust_last:
        cust_last = "Customer"

    conn = get_connection()
    cur = conn.cursor()

    try:
        # --------------------------------------------------
        # 0) Look up EmpNo from Employee (username = EmpEmail)
        # --------------------------------------------------
        cur.execute("""
            SELECT EmpNo
            FROM Employee
            WHERE EmpEmail = :email
        """, {"email": employee_username})

        row = cur.fetchone()
        if not row:
            raise Exception(f"No Employee found for username {employee_username!r}")
        emp_no = row[0]   # NUMBER(10)

        # --------------------------------------------------
        # 1) Customer: reuse by email or create via seq_customer
        # --------------------------------------------------
        existing_cust_no = None
        if customer_email:
            cur.execute("""
                SELECT CustNo
                FROM Customer
                WHERE CustEmail = :email
            """, {"email": customer_email})
            row = cur.fetchone()
            if row:
                existing_cust_no = row[0]

        if existing_cust_no is not None:
            cust_no_to_use = existing_cust_no
        else:
            cur.execute("SELECT seq_customer.NEXTVAL FROM dual")
            cust_no_to_use = cur.fetchone()[0]  # NUMBER(10)

            cur.execute("""
                INSERT INTO Customer (
                    CustNo, CustFirstName, CustLastName, CustEmail
                )
                VALUES (
                    :cust_no, :first_name, :last_name, :email
                )
            """, {
                "cust_no":    cust_no_to_use,
                "first_name": cust_first,
                "last_name":  cust_last,
                "email":      customer_email
            })

        # --------------------------------------------------
        # 2) Order: OrdNo from seq_order
        # --------------------------------------------------
        cur.execute("SELECT seq_order.NEXTVAL FROM dual")
        ord_no = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO RecyclingOrder (
                OrdNo, OrdDate, CustNo, EmpNo, DropOffSite
            )
            VALUES (
                :ord_no, SYSDATE, :cust_no, :emp_no, :dropoff_site
            )
        """, {
            "ord_no":       ord_no,
            "cust_no":      cust_no_to_use,
            "emp_no":       emp_no,
            "dropoff_site": dropoff_site
        })

        # --------------------------------------------------
        # 3) Device: DeviceID from seq_device + QR code
        # --------------------------------------------------
        cur.execute("SELECT seq_device.NEXTVAL FROM dual")
        device_id = cur.fetchone()[0]   # NUMBER(10)

        qr_filename = _generate_qr_for_mac(mac_addr, str(device_id))

        cur.execute("""
            INSERT INTO Device (
                DeviceID, DeviceType, Make, Model, SerialNo,
                QRCode, IotMacAddr, HazardClass, WeightKg,
                Status, OrigCustNo
            )
            VALUES (
                :device_id, :device_type, :make, :model, :serial_no,
                :qr_code, :mac_addr, :hazard_class, :weight_kg,
                :status, :cust_no
            )
        """, {
            "device_id":     device_id,
            "device_type":   device_type,
            "make":          make,
            "model":         model,
            "serial_no":     serial_no,
            "qr_code":       qr_filename,
            "mac_addr":      mac_addr,
            "hazard_class":  hazard_class,
            "weight_kg":     weight_kg,
            "status":        status,
            "cust_no":       cust_no_to_use
        })

        # --------------------------------------------------
        # 4) Order line: one line per device
        # --------------------------------------------------
        cur.execute("""
            INSERT INTO OrdLine (
                OrdNo, LineNo, DeviceID, ActionCode, Qty, Notes
            )
            VALUES (
                :ord_no, :line_no, :device_id, :action_code, :qty, :notes
            )
        """, {
            "ord_no":      ord_no,
            "line_no":     1,
            "device_id":   device_id,
            "action_code": "Recycle",
            "qty":         1,
            "notes":       notes
        })

        conn.commit()

        return {
            "device_id":   device_id,
            "qr_filename": qr_filename,
            "mac_addr":    mac_addr
        }

    except Exception as e:
        conn.rollback()
        print("Error in register_device_with_order:", e)
        raise

    finally:
        cur.close()
        conn.close()
