import os
import io
import json
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from PIL import Image

# Import your helpers from bot.py
from bot import create_license_image, load_licenses

app = Flask(__name__)

LICENSES_DIR = "licenses"
JSON_FILE = "licenses.json"
os.makedirs(LICENSES_DIR, exist_ok=True)


@app.route("/webhook", methods=["POST"])
def webhook():
    """Receives BotGhost data and creates a license image + record."""
    if not request.is_json:
        return jsonify({"error": "Expected JSON body"}), 400

    data = request.get_json()
    roblox_username = data.get("roblox_username", "Unknown")
    roblox_user_id = str(data.get("roblox_user_id", "N/A"))
    product_name = data.get("product_name", "Standard License")
    full_name = data.get("full_name", "N/A")
    dob = data.get("dob", "N/A")
    address = data.get("address", "N/A")
    eye_color = data.get("eye_color", "N/A")
    height = data.get("height", "N/A")

    issued = datetime.utcnow()
    expires = issued + timedelta(days=365 * 4)
    lic_num = f"{roblox_username.upper()}-{uuid.uuid4().hex[:6].upper()}"

    fields = {
        "Full Name": full_name,
        "DOB": dob,
        "Address": address,
        "Eye Color": eye_color,
        "Height": height,
    }

    # Generate image (no avatar for simplicity)
    img_bytes = create_license_image(
        username=roblox_username,
        avatar_bytes=None,
        fields=fields,
        issued=issued,
        expires=expires,
        lic_num=lic_num,
        description=""
    )

    # Save PNG file
    path = f"{LICENSES_DIR}/{lic_num}.png"
    with open(path, "wb") as f:
        f.write(img_bytes)

    # Save record to licenses.json
    record = {
        "roblox_username": roblox_username,
        "roblox_user_id": roblox_user_id,
        "license_number": lic_num,
        "issued": issued.strftime("%Y-%m-%d"),
        "expires": expires.strftime("%Y-%m-%d"),
        "fields": fields,
        "image_path": path,
        "product_name": product_name
    }

    existing = load_licenses()
    existing[roblox_user_id] = record
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

    return jsonify({
        "success": True,
        "license_number": lic_num,
        "roblox_username": roblox_username,
        "image_path": path
    }), 200


@app.route("/health")
def health():
    """Simple check to confirm Flask is alive."""
    return jsonify({"ok": True, "status": "running"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
