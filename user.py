# user.py  ─── Blueprint de autenticación
import uuid
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from models import db, User

auth_bp = Blueprint("auth", __name__, template_folder="templates")

# ── OAuth ──────────────────────────────────────────────────────────────────────
oauth = OAuth()
def init_oauth(app):
    """Llama a esto en create_app(app) después de cargar configuración."""
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        access_token_url="https://oauth2.googleapis.com/token",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        api_base_url="https://www.googleapis.com/oauth2/v3/",
        client_kwargs={"scope": "openid email profile"},
    )

# ── Vistas públicas ───────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET"])
def login_view():
    """Página HTML con formulario + botón Google."""
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login_view"))

# ── API REST: usuario/contraseña propia ────────────────────────────────────────
@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    remember = data.get("remember", False)

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Credenciales inválidas"}), 401

    login_user(user, remember=remember)
    return jsonify({"message": "ok"})

@auth_bp.route("/api/signup", methods=["POST"])
def api_signup():
    """Alta con email/contraseña (opcional, si solo quieres Google omítelo)."""
    data = request.get_json(force=True)
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Usuario ya existe"}), 409

    new_user = User(
        id=str(uuid.uuid4()),
        email=email,
        name=email.split("@")[0],
        password_hash=generate_password_hash(password),
    )
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user, remember=True)
    return jsonify({"message": "registrado"})

# ── API: quién soy ────────────────────────────────────────────────────────────
@auth_bp.route("/api/me", methods=["GET"])
@login_required
def api_me():
    """Devuelve el e-mail del usuario autenticado."""
    return jsonify({"email": current_user.email})

# ── API: logout ──────────────────────────────────────────────────────────────
@auth_bp.route("/api/logout", methods=["POST"])
@login_required
def api_logout():
    """Vacía la sesión (Flask-Login) y responde 204."""
    logout_user()
    return "", 204

# ── OAuth 2.0 con Google ───────────────────────────────────────────────────────
@auth_bp.route("/login/google")
def login_google():
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route("/login/google/callback")
def google_callback():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.parse_id_token(token)
    email = user_info["email"].lower()
    name = user_info.get("name")
    google_id = user_info["sub"]

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            google_id=google_id,
            password_hash=None,   
        )
        db.session.add(user)
        db.session.commit()

    login_user(user, remember=True)  
    return redirect(url_for("home")) 
