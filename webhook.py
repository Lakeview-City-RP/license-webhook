import os
import asyncio
import aiohttp
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Bloxlink API Request ---
async def get_bloxlink_info(discord_id: int, guild_id: int):
    """Fetch Roblox ID + username from Bloxlink API"""
    url = f"https://api.blox.link/v4/public/guilds/{guild_id}/discord-to-roblox/{discord_id}"
    headers = {"Accept": "application/json", "User-Agent": "LicenseWebhook/1.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                rid = data.get("robloxID")
                username = data.get("resolved", {}).get("roblox", {}).get("username")
                return rid, username
            return None, None

# --- Webhook Endpoint ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json or {}
    discord_id = data.get("discord_id")
    guild_id = data.get("guild_id")

    if not discord_id or not guild_id:
        return jsonify({"error": "Missing discord_id or guild_id"}), 400

    # Fetch Bloxlink info
    rid, username = asyncio.run(get_bloxlink_info(int(discord_id), int(guild_id)))
    if not rid:
        return jsonify({"error": "No linked Roblox account"}), 404

    # Log and respond
    print(f"✅ Discord {discord_id} → Roblox {username} ({rid})")

    # Here you could send the data to your bot or image generator
    # e.g., POST to another internal endpoint
    # requests.post("https://my-discord-bot.onrender.com/license", json={"roblox_id": rid, "username": username})

    return jsonify({
        "status": "ok",
        "discord_id": discord_id,
        "roblox_id": rid,
        "roblox_username": username
    }), 200

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
