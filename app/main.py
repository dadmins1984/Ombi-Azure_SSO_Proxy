import os
import requests
import json
import jwt
import uuid
import time
from flask import Flask, request, redirect, session, jsonify, url_for, render_template_string
from urllib.parse import urlencode
from base64 import urlsafe_b64encode
import sqlite3

app = Flask(__name__)
app.secret_key = os.urandom(24)

#Configuration
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
AUTHORIZATION_URL = os.getenv("AUTHORIZATION_URL")
TOKEN_URL = os.getenv("TOKEN_URL")
API_KEY = os.getenv("API_KEY")
OMBI_LOGIN_URL = os.getenv("OMBI_LOGIN_URL")
OMBI_DOCKER_IP = os.getenv("OMBI_DOCKER_IP")
OMBI_PORT = os.getenv("OMBI_PORT")
BASE_DOMAIN = os.getenv("BASE_DOMAIN")

db_path = "users.db"

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def generate_code_verifier():
    return urlsafe_b64encode(os.urandom(40)).decode('utf-8').rstrip('=')

def generate_code_challenge(verifier):
    from hashlib import sha256
    hashed = sha256(verifier.encode('utf-8')).digest()
    return urlsafe_b64encode(hashed).decode('utf-8').rstrip('=')

@app.route("/")
def home():
    if session.get("id_token"):
        return redirect(url_for("verify_user"))

    code_verifier = generate_code_verifier()
    session["code_verifier"] = code_verifier
    code_challenge = generate_code_challenge(code_verifier)

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "response_mode": "query",
        "scope": "openid profile email",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{AUTHORIZATION_URL}?{urlencode(params)}"
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Authorization code not provided.", 400

    code_verifier = session.get("code_verifier")
    if not code_verifier:
        return "Code verifier not found in session.", 400

    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Failed to fetch access token"}), 500

    tokens = token_response.json()
    session["id_token"] = tokens.get("id_token")

    return redirect(url_for("verify_user"))

@app.route("/verify_user")
def verify_user():

    id_token = session.get("id_token")
    if not id_token:
        return redirect(url_for("home"))

    decoded_token = jwt.decode(id_token, options={"verify_signature": False})
    email = decoded_token.get("email")
    username = decoded_token.get("name") or decoded_token.get("display_name") or decoded_token.get("given_name")
    if not email or not username:
        return "Email or Username not found in ID token.", 400

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT username, password FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        password = str(uuid.uuid4())

        ombi_url = f"http://{OMBI_DOCKER_IP}:{OMBI_PORT}/api/v1/Identity/"

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'ApiKey': API_KEY,
        }

        user_data = {
            "alias": username,
            "claims": [
                {"value": "AutoApproveMovie", "enabled": True},
                {"value": "Admin", "enabled": False},
                {"value": "AutoApproveTv", "enabled": True},
                {"value": "AutoApproveMusic", "enabled": False},
                {"value": "RequestMusic", "enabled": False},
                {"value": "PowerUser", "enabled": False},
                {"value": "RequestMovie", "enabled": True},
                {"value": "RequestTv", "enabled": True},
                {"value": "Disabled", "enabled": False},
                {"value": "ReceivesNewsletter", "enabled": False},
                {"value": "ManageOwnRequests", "enabled": True},
                {"value": "EditCustomPage", "enabled": True}
            ],
            "emailAddress": email,
            "id": "",
            "password": password,
            "userName": username,
            "userType": 1,
            "hasLoggedIn": False,
            "lastLoggedIn": None,
            "episodeRequestLimit": 0,
            "movieRequestLimit": 0,
            "userAccessToken": "",
            "musicRequestLimit": 0,
            "episodeRequestQuota": None,
            "movieRequestQuota": None,
            "language": None,
            "userAlias": "",
            "streamingCountry": "US",
            "userQualityProfiles": {
                "radarrQualityProfile": 0,
                "radarrRootPath": 0,
                "radarr4KQualityProfile": 0,
                "radarr4KRootPath": 0,
                "sonarrQualityProfile": 0,
                "sonarrQualityProfileAnime": 0,
                "sonarrRootPath": 0,
                "sonarrRootPathAnime": 0
            },
            "musicRequestQuota": None
        }

        try:
            response = requests.post(ombi_url, headers=headers, data=json.dumps(user_data))
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                           (username, email, password))
            conn.commit()
            time.sleep(1)
            return redirect(url_for("verify_user"))

        except Exception as e:
            return jsonify({"error": "Ombi Error: Failed to register user"}), 500

    username, password = user
    if isinstance(password, bytes):
        password = password.decode('utf-8')

    login_url = f"http://{OMBI_DOCKER_IP}:{OMBI_PORT}/api/v1/token/"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'ApiKey': API_KEY,
    }

    login_data = {
        "username": username,
        "password": password,
        "rememberMe": True,
        "usePlexOAuth": False,
        "plexTvPin": {"id": 0, "code": ""}
    }

    try:
        response = requests.post(login_url, headers=headers, data=json.dumps(login_data))
        response.raise_for_status()

        if response.status_code == 200:
            token_data = response.json()
            if "access_token" in token_data:
                token = token_data["access_token"]

                js_code = f"""
                document.cookie = "id_token={token}; path=/; domain={BASE_DOMAIN}; max-age=3600; Secure; SameSite=None;";
                window.location.href = "{OMBI_LOGIN_URL}";
                """

                return render_template_string(f"""
                <html>
                    <head><title>Token Storage</title></head>
                    <body>
                        <script>
                            {js_code}
                        </script>
                    </body>
                </html>
                """)

            else:
                return "Access token not found in response.", 400
        else:
            return "Login failed. Please try again.", 400
    except requests.exceptions.RequestException:
        return "Error during login. Please try again.", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
