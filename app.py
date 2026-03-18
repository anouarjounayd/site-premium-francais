import os
import uuid
from pathlib import Path
from functools import wraps

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PRIVATE_FILES_DIR = BASE_DIR / "private_files"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox").strip().lower()

PAYPAL_API_BASE = (
    "https://api-m.paypal.com"
    if PAYPAL_MODE == "live"
    else "https://api-m.sandbox.paypal.com"
)

PRODUCT = {
    "name": "Pack Excel Français Premium",
    "description": "Expressions, exemples et traductions FR / AR / EN",
    "price": "9.99",
    "currency": "EUR",
    "filename": "pack_francais_premium.xlsx",
}


def paypal_ready() -> bool:
    return bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)


def get_paypal_access_token() -> str:
    response = requests.post(
        f"{PAYPAL_API_BASE}/v1/oauth2/token",
        headers={"Accept": "application/json", "Accept-Language": "fr_FR"},
        data={"grant_type": "client_credentials"},
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["access_token"]


def paypal_headers(token: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def login_required_for_download(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("paid"):
            abort(403)
        return f(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_globals():
    return {
        "product": PRODUCT,
        "paypal_client_id": PAYPAL_CLIENT_ID,
        "paypal_ready": paypal_ready(),
    }


@app.route("/")
def index():
    free_rows = [
        [1, "Quelque part", "في مكان ما", "J’ai laissé mes clés quelque part.", "somewhere"],
        [2, "En quelque sorte", "نوعًا ما", "Il est en quelque sorte responsable.", "somehow"],
        [3, "À peu près", "تقريبًا", "Il y avait à peu près 50 personnes.", "approximately"],
        [4, "Tout à coup", "فجأة", "Tout à coup la lumière s’est éteinte.", "suddenly"],
        [5, "Par hasard", "بالصدفة", "Je l’ai rencontré par hasard.", "by chance"],
    ]
    return render_template("index.html", free_rows=free_rows)


@app.route("/premium")
def premium():
    preview_rows = [
        ["11", "Au maximum", "كحد أقصى", "Deux heures au maximum.", "at most"],
        ["12", "Par exemple", "على سبيل المثال", "Par exemple, tu peux commencer aujourd’hui.", "for example"],
        ["13", "En particulier", "خصوصًا", "J’aime les fruits, en particulier les pommes.", "in particular"],
        ["14", "À condition que", "بشرط أن", "Je viens à condition que tu sois là.", "provided that"],
    ]
    return render_template("premium.html", preview_rows=preview_rows)


@app.route("/success")
def success():
    if not session.get("paid"):
        return render_template("cancel.html", message="Aucun paiement validé pour cette session."), 403
    return render_template("success.html", download_url=url_for("download_file"))


@app.route("/cancel")
def cancel():
    return render_template("cancel.html", message="Le paiement a été annulé ou interrompu.")


@app.route("/download")
@login_required_for_download
def download_file():
    file_path = PRIVATE_FILES_DIR / PRODUCT["filename"]
    if not file_path.exists():
        abort(404)
    return send_from_directory(PRIVATE_FILES_DIR, PRODUCT["filename"], as_attachment=True)


@app.post("/api/paypal/create-order")
def create_paypal_order():
    if not paypal_ready():
        return jsonify({"error": "PayPal n'est pas configuré."}), 500

    token = get_paypal_access_token()
    request_id = str(uuid.uuid4())
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "pack-francais-premium",
                "description": PRODUCT["description"],
                "amount": {
                    "currency_code": PRODUCT["currency"],
                    "value": PRODUCT["price"],
                },
            }
        ],
        "application_context": {
            "brand_name": "Pack Français Premium",
            "landing_page": "LOGIN",
            "user_action": "PAY_NOW",
            "return_url": f"{BASE_URL}/success",
            "cancel_url": f"{BASE_URL}/cancel",
        },
    }

    response = requests.post(
        f"{PAYPAL_API_BASE}/v2/checkout/orders",
        headers={**paypal_headers(token), "PayPal-Request-Id": request_id},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    session["paypal_order_id"] = data["id"]
    session["paid"] = False
    return jsonify({"id": data["id"]})


@app.post("/api/paypal/capture-order")
def capture_paypal_order():
    if not paypal_ready():
        return jsonify({"error": "PayPal n'est pas configuré."}), 500

    body = request.get_json(silent=True) or {}
    order_id = body.get("orderID")

    if not order_id:
        return jsonify({"error": "orderID manquant."}), 400

    token = get_paypal_access_token()
    response = requests.post(
        f"{PAYPAL_API_BASE}/v2/checkout/orders/{order_id}/capture",
        headers=paypal_headers(token),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    status = data.get("status")
    captures = (
        data.get("purchase_units", [{}])[0]
        .get("payments", {})
        .get("captures", [])
    )
    capture_status = captures[0].get("status") if captures else None

    if status == "COMPLETED" or capture_status == "COMPLETED":
        session["paid"] = True
        session["paypal_order_id"] = order_id
        return jsonify({"status": "COMPLETED", "redirect_url": url_for("success")})

    session["paid"] = False
    return jsonify({"status": status or capture_status or "UNKNOWN"}), 400


@app.errorhandler(403)
def forbidden(_error):
    return render_template("cancel.html", message="Accès refusé."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("cancel.html", message="Fichier introuvable."), 404


@app.errorhandler(requests.RequestException)
def paypal_error(error):
    return render_template("cancel.html", message=f"Erreur PayPal : {error}"), 500


if __name__ == "__main__":
    app.run(debug=True)
