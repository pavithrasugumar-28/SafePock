import os
import json
import io
import socket
from pathlib import Path
from bson import ObjectId
from flask import Flask, jsonify, request, render_template, send_from_directory, send_file
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import qrcode
# --- NEW IMPORT ---
from werkzeug.middleware.proxy_fix import ProxyFix


def get_lan_ip():
    """Finds the local network IP address of the machine."""
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        if s:
            s.close()
    return IP


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None, template_folder="templates")
    CORS(app)

    # --- NEW MIDDLEWARE CONFIGURATION ---
    # This line tells Flask to trust the headers sent by a proxy like ngrok.
    # This is the key to making request.host and request.scheme work correctly.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db_name = os.getenv("MONGO_DB", "medapp")

    use_file_db = False
    users_collection = None
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        db = client[mongo_db_name]
        users_collection = db["users"]
    except ServerSelectionTimeoutError:
        use_file_db = True

    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    users_json_path = data_dir / "users.json"
    if use_file_db and not users_json_path.exists():
        users_json_path.write_text("[]", encoding="utf-8")

    def file_db_read_all():
        try:
            return json.loads(users_json_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def file_db_write_all(items):
        users_json_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def serialize_user(doc):
        return {
            "id": str(doc.get("_id")) if doc.get("_id") is not None else str(doc.get("id")),
            "fullName": doc.get("fullName", ""),
            "dob": doc.get("dob", ""),
            "bloodGroup": doc.get("bloodGroup", ""),
            "emergencyContact": doc.get("emergencyContact", {"name": "N/A", "phone": "N/A", "relationship": "N/A"}),
            "medicalInfo": doc.get(
                "medicalInfo",
                {
                    "allergies": "None",
                    "chronicConditions": "None",
                    "medications": "None",
                    "implants": "None",
                    "organDonor": False,
                },
            ),
            "doctor": doc.get("doctor", {"name": "N/A", "phone": "N/A"}),
            "auth": doc.get("auth", {}),
        }

    @app.route("/")
    def index():
        root_index = os.path.join(os.getcwd(), "index.html")
        if os.path.exists(root_index):
            return send_from_directory(os.getcwd(), "index.html")
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/login/admin")
    def login_admin():
        data = request.get_json(force=True)
        if data.get("username") == "med" and data.get("password") == "health":
            return jsonify({"role": "admin"})
        return jsonify({"error": "invalid credentials"}), 401

    @app.post("/api/login/patient")
    def login_patient():
        data = request.get_json(force=True)
        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            return jsonify({"error": "missing credentials"}), 400
        candidate = None
        if use_file_db:
            for u in file_db_read_all():
                a = (u.get("auth") or {})
                if a.get("username") == username and a.get("password") == password:
                    candidate = u
                    break
        else:
            candidate = users_collection.find_one({"auth.username": username, "auth.password": password})
        if not candidate:
            return jsonify({"error": "invalid credentials"}), 401
        return jsonify(serialize_user(candidate))

    @app.get("/api/users")
    def list_users():
        if use_file_db:
            result = [serialize_user(u) for u in file_db_read_all()[::-1]]
            return jsonify(result)
        result = [serialize_user(u) for u in users_collection.find().sort("_id", -1)]
        return jsonify(result)

    @app.get("/api/users/<user_id>")
    def get_user(user_id: str):
        if use_file_db:
            items = file_db_read_all()
            doc = next((u for u in items if str(u.get("id")) == user_id), None)
            if not doc:
                return jsonify({"error": "not found"}), 404
            return jsonify(serialize_user(doc))
        try:
            doc = users_collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return jsonify({"error": "invalid id"}), 400
        if not doc:
            return jsonify({"error": "not found"}), 404
        return jsonify(serialize_user(doc))

    @app.post("/api/users")
    def create_user():
        data = request.get_json(force=True)
        for key in ["fullName", "dob", "bloodGroup"]:
            if not data.get(key):
                return jsonify({"error": f"{key} is required"}), 400
        if use_file_db:
            items = file_db_read_all()
            new_id = str(max([int(u.get("id", 0)) for u in items] + [0]) + 1)
            ins = {
                "id": new_id,
                "fullName": data["fullName"],
                "dob": data["dob"],
                "bloodGroup": data["bloodGroup"],
                "emergencyContact": data.get("emergencyContact", {}),
                "medicalInfo": data.get("medicalInfo", {}),
                "doctor": data.get("doctor", {}),
                "auth": data.get("auth", {}),
            }
            items.append(ins)
            file_db_write_all(items)
            return jsonify(serialize_user(ins)), 201
        ins = {
            "fullName": data["fullName"],
            "dob": data["dob"],
            "bloodGroup": data["bloodGroup"],
            "emergencyContact": data.get("emergencyContact", {}),
            "medicalInfo": data.get("medicalInfo", {}),
            "doctor": data.get("doctor", {}),
            "auth": data.get("auth", {}),
        }
        res = users_collection.insert_one(ins)
        created = users_collection.find_one({"_id": res.inserted_id})
        return jsonify(serialize_user(created)), 201

    @app.put("/api/users/<user_id>")
    def update_user(user_id: str):
        data = request.get_json(force=True)
        update = {
            k: v
            for k, v in {
                "fullName": data.get("fullName"),
                "dob": data.get("dob"),
                "bloodGroup": data.get("bloodGroup"),
                "emergencyContact": data.get("emergencyContact"),
                "medicalInfo": data.get("medicalInfo"),
                "doctor": data.get("doctor"),
                "auth": data.get("auth"),
            }.items()
            if v is not None
        }
        if not update:
            return jsonify({"error": "no fields to update"}), 400
        if use_file_db:
            items = file_db_read_all()
            idx = next((i for i, u in enumerate(items) if str(u.get("id")) == user_id), None)
            if idx is None:
                return jsonify({"error": "not found"}), 404
            items[idx].update(update)
            file_db_write_all(items)
            return jsonify(serialize_user(items[idx]))
        try:
            oid = ObjectId(user_id)
        except Exception:
            return jsonify({"error": "invalid id"}), 400
        res = users_collection.update_one({"_id": oid}, {"$set": update})
        if res.matched_count == 0:
            return jsonify({"error": "not found"}), 404
        doc = users_collection.find_one({"_id": oid})
        return jsonify(serialize_user(doc))

    @app.delete("/api/users/<user_id>")
    def delete_user(user_id: str):
        if use_file_db:
            items = file_db_read_all()
            new_items = [u for u in items if str(u.get("id")) != user_id]
            if len(new_items) == len(items):
                return jsonify({"error": "not found"}), 404
            file_db_write_all(new_items)
            return jsonify({"deleted": True})
        try:
            oid = ObjectId(user_id)
        except Exception:
            return jsonify({"error": "invalid id"}), 400
        res = users_collection.delete_one({"_id": oid})
        if res.deleted_count == 0:
            return jsonify({"error": "not found"}), 404
        return jsonify({"deleted": True})

    @app.get("/api/users/<user_id>/qr")
    def user_qr(user_id: str):
        """Return a PNG QR code that points to a clean, mobile-friendly profile page."""
        user = None
        if use_file_db:
            user = next((u for u in file_db_read_all() if str(u.get("id")) == user_id), None)
        else:
            try:
                user = users_collection.find_one({"_id": ObjectId(user_id)})
            except Exception:
                return jsonify({"error": "invalid id"}), 400
        
        if not user:
            return jsonify({"error": "not found"}), 404

        base_url = os.getenv("BASE_URL")
        if not base_url:
            host = request.host.split(':')[0]
            port = os.getenv("PORT", 5000)
            if host in ("localhost", "127.0.0.1"):
                lan_ip = get_lan_ip()
                base_url = f"http://{lan_ip}:{port}"
            else:
                base_url = f"{request.scheme}://{request.host}"
        
        profile_url = f"{base_url.rstrip('/')}/p/{user_id}"
        
        print(f"--- Generating QR Code with URL: {profile_url} ---")

        qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=6, border=2)
        qr.add_data(profile_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        
        return send_file(buf, mimetype="image/png", download_name=f"user_{user_id}.png")

    @app.get('/p/<user_id>')
    def public_profile(user_id: str):
        """Mobile-friendly, readable profile view for QR scans."""
        user = None
        if use_file_db:
            user = next((u for u in file_db_read_all() if str(u.get("id")) == user_id), None)
        else:
            try:
                user = users_collection.find_one({"_id": ObjectId(user_id)})
            except Exception:
                return "Invalid ID", 400
        if not user:
            return "Not found", 404

        ec = (user.get('emergencyContact') or {})
        mi = (user.get('medicalInfo') or {})
        doc = (user.get('doctor') or {})

        html = f"""
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{user.get('fullName','Profile')}</title>
<style>
  :root {{
    --c1:#0aa6a6; --c2:#078c8c; --txt:#0f172a; --mut:#475569; --b:#d6e6ea; --bg:#f5fbfc;
  }}
  body {{ margin:0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: var(--bg); color: var(--txt); }}
  .wrap {{ max-width:720px; margin:0 auto; padding:20px; }}
  .card {{ background:#fff; border:1px solid var(--b); border-radius:16px; box-shadow:0 10px 25px rgba(7,140,140,.12); padding:20px; }}
  h1 {{ font-size: clamp(22px,5vw,30px); margin:0 0 10px; color: var(--c2); }}
  .tag {{ display:inline-block; padding:6px 12px; border-radius:999px; background:linear-gradient(180deg,var(--c1),var(--c2)); color:#fff; font-weight:700; font-size:14px; }}
  .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap:14px; margin-top:16px; }}
  @media (max-width:560px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .group h2 {{ font-size:18px; margin:16px 0 8px; color: var(--c2); border-bottom:1px solid var(--b); padding-bottom:6px; }}
  .row {{ display:flex; gap:8px; margin:6px 0; align-items:baseline; }}
  .lbl {{ min-width:140px; font-weight:700; color: var(--mut); }}
  .val {{ color:#111827; font-size:17px; }}
  .pill {{ display:inline-block; padding:4px 10px; border:1px solid var(--b); border-radius:999px; margin:2px 6px 2px 0; background:#f8feff; }}
  .footer {{ text-align:center; color: var(--mut); margin-top:16px; font-size:14px; }}
</style></head>
<body><div class="wrap"> 
  <div class="card">
    <h1>{user.get('fullName','')}</h1>
    <span class="tag">Blood Group: {user.get('bloodGroup','')}</span>
    <div class="grid">
      <div class="group">
        <h2>Personal</h2>
        <div class="row"><div class="lbl">Date of Birth</div><div class="val">{user.get('dob','')}</div></div>
        <div class="row"><div class="lbl">Organ Donor</div><div class="val">{"Yes" if mi.get('organDonor') else "No"}</div></div>
      </div>
      <div class="group">
        <h2>Emergency Contact</h2>
        <div class="row"><div class="lbl">Name</div><div class="val">{ec.get('name','')}</div></div>
        <div class="row"><div class="lbl">Phone</div><div class="val">{ec.get('phone','')}</div></div>
        <div class="row"><div class="lbl">Relationship</div><div class="val">{ec.get('relationship','')}</div></div>
      </div>
    </div>

    <div class="group">
      <h2>Medical</h2>
      <div class="row"><div class="lbl">Allergies</div><div class="val">{mi.get('allergies','None')}</div></div>
      <div class="row"><div class="lbl">Chronic Conditions</div><div class="val">{mi.get('chronicConditions','None')}</div></div>
      <div class="row"><div class="lbl">Medications</div><div class="val">{mi.get('medications','None')}</div></div>
      <div class="row"><div class="lbl">Implants</div><div class="val">{mi.get('implants','None')}</div></div>
    </div>

    <div class="group">
      <h2>Primary Doctor</h2>
      <div class="row"><div class="lbl">Name</div><div class="val">{doc.get('name','')}</div></div>
      <div class="row"><div class="lbl">Phone</div><div class="val">{doc.get('phone','')}</div></div>
    </div>

    <div class="footer">Generated from your Health Profile • {request.host}</div>
  </div>
</div></body></html>
        """
        return html

    return app


if __name__ == "__main__":
    app = create_app()
    lan_ip = get_lan_ip()
    port = int(os.getenv("PORT", 5000))
    print("---")
    print("Your app is running and accessible at:")
    print(f"  Local:   http://localhost:{port}")
    print(f"  Network: http://{lan_ip}:{port}")
    print("---")
    app.run(host="0.0.0.0", port=port, debug=True)