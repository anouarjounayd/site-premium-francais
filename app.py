import os
from pathlib import Path
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    abort,
    send_from_directory,
    url_for,
    session,
    redirect,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
PRIVATE_FILES_DIR = BASE_DIR / "private_files"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

DOWNLOAD_TOKEN = os.getenv("DOWNLOAD_TOKEN", "mon_token_secret_123456")

SITE = {
    "name": "Français Complet",
    "slogan": "Tout ce dont tu as besoin pour apprendre le français facilement",
}

PRODUCT = {
    "name": "Pack Complet Français",
    "description": "Un pack PDF clair et pratique avec expressions utiles, traductions et exemples pour progresser rapidement en français.",
    "price": 6.99,
    "currency": "EUR",
    "filename": "pack_complet_francais.pdf",
}


@app.route("/")
def index():
    free_rows = [
        [1, "Bonjour", "مرحبا", "Bonjour, comment allez-vous ?", "hello"],
        [2, "Merci", "شكرا", "Merci pour votre aide.", "thank you"],
        [3, "Au revoir", "إلى اللقاء", "Au revoir et à bientôt.", "goodbye"],
        [4, "S’il vous plaît", "من فضلك", "Un café, s’il vous plaît.", "please"],
        [5, "Excusez-moi", "عذرا", "Excusez-moi, où est la gare ?", "excuse me"],
        [6, "Oui", "نعم", "Oui, je comprends.", "yes"],
        [7, "Non", "لا", "Non, ce n’est pas correct.", "no"],
        [8, "Comment ça va ?", "كيف حالك؟", "Bonjour, comment ça va ?", "how are you?"],
        [9, "Très bien", "بخير جدا", "Je vais très bien aujourd’hui.", "very well"],
        [10, "À bientôt", "أراك قريبا", "Merci et à bientôt.", "see you soon"],
    ]
    return render_template("index.html", free_rows=free_rows, site=SITE, product=PRODUCT)


@app.route("/premium")
def premium():
    preview_rows = [
        [11, "Par exemple", "على سبيل المثال", "Par exemple, tu peux commencer aujourd’hui.", "for example"],
        [12, "En particulier", "خصوصًا", "J’aime les fruits, en particulier les pommes.", "in particular"],
        [13, "À vrai dire", "في الحقيقة", "À vrai dire, je préfère cette méthode.", "to tell the truth"],
        [14, "Tout de suite", "فورا", "Je reviens tout de suite.", "right away"],
        [15, "Au maximum", "كحد أقصى", "Deux heures au maximum.", "at most"],
    ]
    return render_template("premium.html", preview_rows=preview_rows, site=SITE, product=PRODUCT)


@app.route("/success")
def success():
    if not session.get("paid"):
        return redirect(url_for("cancel"))

    download_url = url_for("download_file")
    return render_template("success.html", download_url=download_url, site=SITE, product=PRODUCT)


@app.route("/cancel")
def cancel():
    return render_template("cancel.html", site=SITE, product=PRODUCT)


@app.route("/download")
def download_file():
    if not session.get("paid"):
        abort(403)

    file_path = PRIVATE_FILES_DIR / PRODUCT["filename"]

    if not file_path.exists():
        abort(404)

    return send_from_directory(PRIVATE_FILES_DIR, PRODUCT["filename"], as_attachment=True)


# TEMPORAIRE UNIQUEMENT POUR TEST LOCAL
# Supprime cette route quand tu passeras à PayPal API.
@app.route("/test-unlock")
def test_unlock():
    session["paid"] = True
    return redirect(url_for("success"))


@app.errorhandler(403)
def forbidden(_error):
    return render_template("cancel.html", site=SITE, product=PRODUCT), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("cancel.html", site=SITE, product=PRODUCT), 404


if __name__ == "__main__":
    app.run(debug=True)