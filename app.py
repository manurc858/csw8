import io, os, uuid, tempfile, base64
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, flash, session
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pvlib
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required, current_user
from flask import current_app
from functools import wraps

from models import db, User, Project, Chart
from user   import auth_bp, init_oauth
from flask_login import LoginManager, login_required, current_user, logout_user




app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY="shhhhh",
    SQLALCHEMY_DATABASE_URI="sqlite:///mi_app.db",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    GOOGLE_CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID", "RELLENA_CLIENT_ID"),
    GOOGLE_CLIENT_SECRET=os.getenv("GOOGLE_CLIENT_SECRET", "RELLENA_CLIENT_SECRET"),
)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "auth.login_view"

from models import User
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

init_oauth(app)
app.register_blueprint(auth_bp)

def generar_carta_solar(epw_path: str,
                        angle_deg: float,
                        t_min: float = -273.15,
                        shades: list[dict] | None = None) -> io.BytesIO:

    weather_data, meta = pvlib.iotools.read_epw(epw_path)

    latitude = meta['latitude']
    longitude = meta['longitude']
    
    with open(epw_path, 'r') as file:
        first_line = file.readline().strip()
        location = first_line.split(',')[1]
    
    solar_position = pvlib.solarposition.get_solarposition(
        time=weather_data.index,
        latitude=latitude,
        longitude=longitude,
        altitude=meta['altitude']
    )
    
    solar_azimuth = solar_position['azimuth']
    solar_altitude = solar_position['apparent_elevation']
    
    filtered_data = weather_data.between_time("00:00", "23:00")
    azimuth_filtered = solar_azimuth.loc[filtered_data.index]
    altitude_filtered = solar_altitude.loc[filtered_data.index]
    
    temp_all = weather_data["temp_air"]
    altitude_filtered = altitude_filtered.apply(lambda x: max(x, 0))
    mask = altitude_filtered > 0
    mask &= temp_all.loc[altitude_filtered.index] >= t_min
    azimuth_filtered = azimuth_filtered[mask]
    altitude_filtered = altitude_filtered[mask]
    
    azimuth_rad = np.radians(azimuth_filtered)
    
    weather_data_21 = weather_data[weather_data.index.day == 21]
    solar_position_21 = pvlib.solarposition.get_solarposition(
        time=weather_data_21.index,
        latitude=latitude,
        longitude=longitude,
        altitude=meta['altitude']
    )
    solar_azimuth_21 = solar_position_21['azimuth']
    solar_altitude_21 = solar_position_21['apparent_elevation']
    solar_altitude_21 = solar_altitude_21.apply(lambda x: max(x, 0))
    
    azimuth_rad_21 = np.radians(solar_azimuth_21)
    
    fig = plt.figure(figsize=(18, 18), dpi=300)
    ax = fig.add_subplot(111, polar=True)
    
    ax.scatter(azimuth_rad, 90 - altitude_filtered, s=0.6, color='steelblue')
    
    for month in range(1, 13):
        month_indices = (solar_azimuth_21.index.month == month) & (solar_altitude_21 > 0)
        azimuth_month = azimuth_rad_21[month_indices]
        altitude_month = solar_altitude_21[month_indices]
        ax.plot(azimuth_month, 90 - altitude_month, linewidth=0.35, markersize=0.1, color="dimgray")
    
    angle_deg = angle_deg % 360
    theta_ctr = np.radians((angle_deg + 180) % 360)
    theta_s = np.linspace(theta_ctr - np.pi/2, theta_ctr + np.pi/2, 200)
    ax.fill_between(theta_s, 0, 90, color= 'gray', alpha=0.35, zorder=0)
   
    shades = shades or []            # lista vacía si None

    for sh in shades:
        typ   = sh.get("type", "h")
        extra = sh.get("extra", 0.0)
        side  = sh.get("side",  "right") 
        if typ == "v" and extra > 0:
            extra_rad = np.radians(extra)
            theta_ctr = np.radians((angle_deg + 180) % 360)

            if side == "left":
                theta_extra = np.linspace(theta_ctr + np.pi/2, theta_ctr + np.pi/2 + extra_rad, 100)
            else:
                theta_extra = np.linspace(theta_ctr - np.pi/2 - extra_rad, theta_ctr - np.pi/2, 100)

            ax.fill_between(theta_extra, 0, 90, color="red", alpha=0.4, zorder=1)
        if typ == "h" and extra > 0:
            R_ext = 90                      # radio del horizonte
            R_int = extra          # radio que fija P3  (0 < R_int < 90)

            if R_int <= 0:   # ángulo fuera de rango
                pass
            else:
                # ——— 1. Puntos en cartesiano ————————————————
                th_ctr = np.radians(angle_deg % 360)       # lado opuesto
                th1, th2 = th_ctr - np.pi/2, th_ctr + np.pi/2

                P1 = np.array([R_ext*np.cos(th1), R_ext*np.sin(th1)])
                P2 = np.array([R_ext*np.cos(th2), R_ext*np.sin(th2)])
                P3 = np.array([R_int*np.cos(th_ctr), R_int*np.sin(th_ctr)])

                # ——— 2. Centro (xc,yc) y radio Rc de la circunf. P1-P2-P3 ———
                A  = np.linalg.det([[P1[0], P1[1], 1],
                                    [P2[0], P2[1], 1],
                                    [P3[0], P3[1], 1]])
                Dx = -np.linalg.det([[P1[1], P1[0]**2+P1[1]**2, 1],
                                    [P2[1], P2[0]**2+P2[1]**2, 1],
                                    [P3[1], P3[0]**2+P3[1]**2, 1]])
                Dy =  np.linalg.det([[P1[0], P1[0]**2+P1[1]**2, 1],
                                    [P2[0], P2[0]**2+P2[1]**2, 1],
                                    [P3[0], P3[0]**2+P3[1]**2, 1]])
                xc, yc = Dx/(2*A), Dy/(2*A)
                Rc     = np.hypot(P1[0]-xc, P1[1]-yc)

                # ——— 3. Arco de la circunferencia (P1→P2 pasando por P3). Código corregido ———
                phi1 = np.arctan2(P1[1]-yc, P1[0]-xc)
                phi3 = np.arctan2(P3[1]-yc, P3[0]-xc)
                phi2 = np.arctan2(P2[1]-yc, P2[0]-xc)

                # 3.a) Normalizamos cada ángulo al rango [0, 2π)
                phi1_n = phi1 % (2*np.pi)
                phi2_n = phi2 % (2*np.pi)
                phi3_n = phi3 % (2*np.pi)

                # 3.b) Nos aseguramos de tomar el arco “menor” entre phi1_n y phi2_n
                if abs(phi2_n - phi1_n) > np.pi:
                    # Si la distancia en sentido circular es >π, desplazamos el extremo menor +2π
                    if phi1_n < phi2_n:
                        phi1_n += 2*np.pi
                    else:
                        phi2_n += 2*np.pi

                # 3.c) Alinear φ3 al mismo intervalo que φ1→φ2
                if phi3_n < min(phi1_n, phi2_n):
                    phi3_n += 2*np.pi

                # 3.d) Ahora φ1_n < φ2_n y φ3_n queda automáticamente dentro del arco
                phi1, phi2 = phi1_n, phi2_n

                # 3.e) Generamos los 400 puntos del arco φ1→φ2
                phi_arc = np.linspace(phi1, phi2, 400)


                # Coordenadas polares (θ,r) del arco
                x_arc = xc + Rc*np.cos(phi_arc)
                y_arc = yc + Rc*np.sin(phi_arc)
                th_arc = np.arctan2(y_arc, x_arc)
                r_arc = np.hypot(x_arc, y_arc)

                # ——— 4. Cuerda P2→P1 (segmento recto) ———
                t = np.linspace(0, 1, 2)      # basta 2 puntos
                x_ch = P2[0]*(1-t) + P1[0]*t
                y_ch = P2[1]*(1-t) + P1[1]*t
                th_ch = np.arctan2(y_ch, x_ch)
                r_ch  = np.hypot(x_ch, y_ch)

                # ——— 5. Polígono completo (arco → cuerda) en polares ———
                theta_poly = np.concatenate([th_arc, th_ch])
                r_poly     = np.concatenate([r_arc,  r_ch])

                # ——— 6. Sombreado ———
                ax.fill(theta_poly, r_poly, color="red", alpha=0.40, zorder=1)

        
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(np.radians([0, 90, 180, 270]))
    ax.set_xticklabels(["N (0°)", "E (90°)", "S (180°)", "W (270°)"])
    ax.set_yticks(np.arange(0, 91, 10))
    ax.set_yticklabels([f"{90-a}°" for a in np.arange(0, 91, 10)])
    ax.grid(True, ls="--", lw=0.3, color="silver")
    
    plt.suptitle("Carta Solar Estereográfica", fontsize=22, color="steelblue")
    plt.title(location, fontsize=16, color="steelblue", pad=12)
    
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def get_epw_path_for_project(proj_id):
    proj = Project.query.filter_by(id=proj_id, user_id=current_user.id).first()
    if proj and proj.epw_base64:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".epw")
        with open(tmp.name, "wb") as fh:
            fh.write(base64.b64decode(proj.epw_base64))
        return tmp.name
    return None


@app.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        f = request.files.get("epw")
        if not f or not f.filename.lower().endswith(".epw"):
            flash("Selecciona un archivo .epw válido")
            return redirect(url_for("home"))

        project_name = request.form.get("projectName", "Proyecto sin nombre")
        proj_id = request.form.get("projectId") or str(uuid.uuid4())

        # 1) Base64 del EPW
        epw_base64 = base64.b64encode(f.read()).decode("utf-8")

        # 2) Crea el proyecto enlazado al usuario
        new_proj = Project(
            id=proj_id,
            name=project_name,
            epw_base64=epw_base64,
            user_id=current_user.id
        )
        db.session.add(new_proj)
        db.session.commit()

        return redirect(url_for("solar_charts_list", proj_id=proj_id))

    # GET → index
    return render_template("index.html")


@app.route("/api/carta-solar", methods=["GET", "POST"])
@login_required
def carta_solar_api():
    """
    Genera la imagen PNG de la carta solar a partir del EPW
    almacenado en la BD.
    """
    proj_id = request.args.get("project")
    if not proj_id:
        return jsonify(error="Parámetro 'project' obligatorio"), 400

    # 1️⃣  Proyecto + ownership
    proj = Project.query.filter_by(id=proj_id,
                                   user_id=current_user.id).first_or_404()

    if not proj.epw_base64:
        return jsonify(error="El proyecto no tiene EPW cargado"), 400

    # 2️⃣  Crear EPW temporal
    epw_path = get_epw_path_for_project(proj_id)

    # 3️⃣  Parámetros de la carta
    payload = request.get_json(silent=True) or {}
    angle   = float(request.args.get("orient",
                     payload.get("angle", request.form.get("angle", 0))))
    t_min   = float(request.args.get("tmin",
                     payload.get("tmin",  request.form.get("tmin", -273.15))))

    # Shades
    shades = payload.get("shades", [])
    if not shades:
        # compatibilidad con URL ?type=&extra=
        for t, e, s in zip(request.args.getlist("type"),
                           request.args.getlist("extra"),
                           request.args.getlist("side") or ["right"]*999):
            try:
                if t in ("h", "v") and float(e) > 0:
                    shades.append({"type": t, "extra": float(e), "side": s})
            except ValueError:
                pass

    # 4️⃣  Generar PNG
    img = generar_carta_solar(epw_path, angle_deg=angle,
                              t_min=t_min, shades=shades)

    resp = send_file(img, mimetype="image/png")
    resp.headers["X-Request-ID"] = str(uuid.uuid4())
    return resp

@app.route("/api/solar-data", methods=["GET", "POST"])
@login_required
def solar_data():
    proj_id = request.args.get("project")
    if not proj_id:
        return jsonify(error="Parámetro 'project' obligatorio"), 400

    proj = Project.query.filter_by(id=proj_id,
                                   user_id=current_user.id).first_or_404()
    if not proj.epw_base64:
        return jsonify(error="El proyecto no tiene EPW cargado"), 400

    epw_path = get_epw_path_for_project(proj_id)

    # Leer EPW
    df, meta = pvlib.iotools.read_epw(epw_path)
    pos = pvlib.solarposition.get_solarposition(
        time=df.index,
        latitude=meta["latitude"],
        longitude=meta["longitude"],
        altitude=meta["altitude"]
    )

    # Filtro elevación y temperatura
    payload = request.get_json(silent=True) or {}
    t_min = float(request.args.get("tmin", payload.get("tmin", -273.15)))

    mask = (pos["apparent_elevation"] > 0) & (df["temp_air"] >= t_min)

    # Día 21 de cada mes
    df21  = df[df.index.day == 21]
    pos21 = pvlib.solarposition.get_solarposition(
        time=df21.index,
        latitude=meta["latitude"],
        longitude=meta["longitude"],
        altitude=meta["altitude"]
    )
    day21 = []
    for m in range(1, 13):
        sel = (df21.index.month == m) & (pos21["apparent_elevation"] > 0)
        day21.append({
            "azi":  pos21["azimuth"][sel].round(2).tolist(),
            "elev": pos21["apparent_elevation"][sel].round(2).tolist()
        })

    return jsonify({
        "azi":  pos["azimuth"][mask].round(2).tolist(),
        "elev": pos["apparent_elevation"][mask].round(2).tolist(),
        "temp": df["temp_air"][mask].round(1).tolist(),
        "ghi":  df["ghi"][mask].round(1).tolist(),
        "day21": day21
    })

@app.route("/carta_solar")
def carta_solar():
    """Ruta para generar carta solar (compatibilidad con versión anterior)."""
    return carta_solar_api()

@app.route("/projects/<proj_id>/solar-charts", methods=["GET"])
@login_required
def solar_charts_list(proj_id):
    proj = Project.query.filter_by(id=proj_id,
                                   user_id=current_user.id).first_or_404()

    epw_path = get_epw_path_for_project(proj_id)
    if not epw_path:
        flash("No se encontró el archivo EPW para este proyecto")
        return redirect(url_for("home"))

    return render_template(
        "solar_charts.html",
        project_id   = proj.id,
        project_name = proj.name,
        epw_path     = epw_path,
        charts       = proj.charts        # lista SQLAlchemy
    )

@app.route("/projects/<proj_id>/upload_epw", methods=["POST"])
@login_required
def upload_epw_for_project(proj_id):
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".epw"):
        return jsonify(error="EPW inválido"), 400

    epw_b64 = base64.b64encode(file.read()).decode("utf-8")

    proj = Project.query.filter_by(id=proj_id, user_id=current_user.id).first_or_404()
    proj.epw_base64 = epw_b64
    db.session.commit()

    return jsonify(status="ok"), 200


@app.route("/projects/<proj_id>", methods=["DELETE"])
@login_required
def delete_project(proj_id):
    proj = Project.query.filter_by(id=proj_id, user_id=current_user.id).first_or_404()
    db.session.delete(proj)
    db.session.commit()
    return "", 204


@app.route("/projects/<proj_id>/solar-charts", methods=["POST"])
@login_required
def create_solar_chart(proj_id):
    proj = Project.query.filter_by(id=proj_id, user_id=current_user.id).first_or_404()

    chart = Chart(
        id=str(uuid.uuid4()),
        title=f"Carta {len(proj.charts)+1}",
        angle=0.0,
        temp=0.0
    )
    proj.charts.append(chart)
    db.session.commit()

    return jsonify({"id": chart.id}), 201



@app.route("/projects/<proj_id>/solar-charts/<cid>", methods=["PUT"])
@login_required
def update_solar_chart(proj_id, cid):
    data  = request.get_json() or {}
    chart = Chart.query.join(Project).filter(
        Chart.id == cid,
        Project.id == proj_id,
        Project.user_id == current_user.id
    ).first_or_404()

    chart.title       = data.get("title", chart.title)
    chart.description = data.get("description", chart.description)
    db.session.commit()
    return jsonify(status="ok"), 200


@app.route("/projects/<proj_id>/solar-charts/<cid>", methods=["DELETE"])
@login_required
def delete_solar_chart(proj_id, cid):
    chart = Chart.query.join(Project).filter(
        Chart.id == cid,
        Project.id == proj_id,
        Project.user_id == current_user.id
    ).first_or_404()
    db.session.delete(chart)
    db.session.commit()
    return "", 204


@app.route("/projects/<proj_id>/solar-charts/<cid>/edit", methods=["GET"])
@login_required
def solar_chart_edit(proj_id, cid):
    """
    Renderiza la página de edición de una carta solar perteneciente
    al proyecto <proj_id> del usuario conectado.
    """

    # 1️⃣ Traer la carta con JOIN → asegura que pertenece al usuario
    chart = (
        Chart.query
        .join(Project)                            # INNER JOIN project
        .filter(
            Chart.id == cid,
            Project.id == proj_id,
            Project.user_id == current_user.id    # ownership check
        )
        .first_or_404(description="Carta no encontrada")
    )

    # 2️⃣ EPW temporal para Plot / Preview
    epw_path = get_epw_path_for_project(proj_id)
    if not epw_path:
        flash("No se encontró el archivo EPW para este proyecto")
        return redirect(url_for("home"))

    # 3️⃣ Render template
    return render_template(
        "solar_chart_edit.html",
        project_id = proj_id,
        chart      = chart,        # objeto SQLAlchemy (o dict, como prefieras)
        epw_path   = epw_path
    )


@app.route("/projects/<proj_id>/solar-charts/<cid>/save", methods=["POST"])
@login_required
def save_solar_chart(proj_id, cid):
    data = request.get_json() or {}

    # 1️⃣ localiza proyecto y carta (ownership ⇢ user_id)
    chart = (
        Chart.query
        .join(Project)
        .filter(
            Chart.id == cid,
            Project.id == proj_id,
            Project.user_id == current_user.id
        )
        .first()
    )
    if chart is None:
        return jsonify(error="Carta no encontrada"), 404

    # 2️⃣ actualiza campos
    chart.angle       = float(data.get("angle",        chart.angle))
    chart.temp        = float(data.get("temp",         chart.temp))
    chart.shades      =        data.get("shades",      chart.shades)
    chart.title       =        data.get("title",       chart.title)
    chart.description =        data.get("description", chart.description)
    chart.hHeight     = float(data.get("hHeight",      chart.hHeight))
    chart.hLength     = float(data.get("hLength",      chart.hLength))
    chart.chkH        = bool( data.get("chkH",         chart.chkH))
    chart.vLength     = float(data.get("vLength",      chart.vLength))
    chart.vWidth      = float(data.get("vWidth",       chart.vWidth))
    chart.vSide       =        data.get("vSide",       chart.vSide)
    chart.chkV        = bool( data.get("chkV",         chart.chkV))
    if "preview" in data:
        chart.preview = data.get("preview", chart.preview)
        
    chart.shades = data.get ("shades", chart.shades)

    db.session.commit()
    return jsonify(status="ok", message="Carta solar guardada correctamente")

@app.route("/projects/<proj_id>/solar-charts/<cid>/data", methods=["GET"])
@login_required
def get_solar_chart_data(proj_id, cid):
    chart = (
        Chart.query
        .join(Project)
        .filter(
            Chart.id == cid,
            Project.id == proj_id,
            Project.user_id == current_user.id
        )
        .first_or_404(description="Carta no encontrada")
    )

    return jsonify({
        "id":          chart.id,
        "angle":       chart.angle,
        "temp":        chart.temp,
        "shades":      chart.shades,
        "title":       chart.title,
        "description": chart.description,
        "hHeight":     chart.hHeight,
        "hLength":     chart.hLength,
        "chkH":        chart.chkH,
        "vLength":     chart.vLength,
        "vWidth":      chart.vWidth,
        "vSide":       chart.vSide,
        "chkV":        chart.chkV,
        "preview":     chart.preview,
    })

@app.route("/api/projects", methods=["GET"])
@login_required
def api_projects():
    projs = Project.query.filter_by(user_id=current_user.id).all()
    return jsonify([
        {
            "id":   p.id,
            "name": p.name,
            "charts": [
                {"id": c.id, "title": c.title, "description": c.description}
                for c in p.charts
            ],
            "has_epw": bool(p.epw_base64)
        }
        for p in projs
    ])

@app.route("/api/projects/<proj_id>", methods=["GET"])
@login_required
def api_project_detail(proj_id):
    proj = Project.query.filter_by(id=proj_id, user_id=current_user.id).first_or_404()
    return jsonify({
        "id":   proj.id,
        "name": proj.name,
        "charts": [
            {
                "id":    c.id,
                "title": c.title,
                "angle": c.angle,
                "temp":  c.temp,
                "preview": c.preview, 
                "shades":  c.shades
            } for c in proj.charts
        ],
        "has_epw": bool(proj.epw_base64)
    })


@app.route("/api/projects/<proj_id>/charts", methods=["GET"])
@login_required
def api_project_charts(proj_id):
    proj = Project.query.filter_by(id=proj_id, user_id=current_user.id).first_or_404()
    return jsonify([
        {
            "id":          c.id,
            "title":       c.title,
            "description": c.description,
            "angle":       c.angle,
            "temp":        c.temp,
        } for c in proj.charts
    ])


# GET — ¿tiene EPW?
@app.route("/api/projects/<proj_id>/epw", methods=["GET"])
@login_required
def api_project_has_epw(proj_id):
    proj = Project.query.filter_by(id=proj_id, user_id=current_user.id).first_or_404()
    return jsonify(has_epw=bool(proj.epw_base64))

# POST — sobrescribe EPW
@app.route("/api/projects/<proj_id>/epw", methods=["POST"])
@login_required
def api_project_save_epw(proj_id):
    data = request.get_json() or {}
    epw_b64 = data.get("epw_base64")
    if not epw_b64:
        return jsonify(error="epw_base64 faltante"), 400

    proj = Project.query.filter_by(id=proj_id, user_id=current_user.id).first_or_404()
    proj.epw_base64 = epw_b64
    db.session.commit()
    return jsonify(status="ok")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify({'error': 'unauthenticated'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route("/projects", methods=["GET"])
@login_required
def projects_home():
    return render_template("index.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
