from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
import uuid

# SMB imports
import smbprotocol
from smbprotocol.connection import Connection
from smbprotocol.session import Session
from smbprotocol.tree import TreeConnect
from smbprotocol.open import Open, CreateDisposition
from smbprotocol.exceptions import SMBException
from smbprotocol.open import ImpersonationLevel
from smbprotocol.file_info import FileInformationClass

# Logueos
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import threading
import time


# =========================================================
# SMB CONNECTION
# =========================================================
def smb_connect(server, share, username, password):

    # Crear conexión TCP al servidor SMB
    conn = Connection(uuid.uuid4(), server, 445)
    conn.connect()

    # Crear sesión SMB (esta versión NO soporta ClientConfig)
    session = Session(connection=conn, username=username, password=password)
    session.connect()

    # Validación anti-guest
    if session.session_id == 0:
        raise Exception(
            "ERROR SMB: Sesión autenticada como GUEST. Credenciales o dominio incorrectos."
        )

    # Montar el recurso compartido
    tree = TreeConnect(session, rf"\\{server}\{share}")
    tree.connect()

    return conn, session, tree


# =========================================================
# FLASK APP SETUP
# =========================================================

app = Flask(__name__)
app.secret_key = "your-secret-key-change-this-in-production"

USERS_FILE = "users.json"
BATCHES_FILE = "batches.json"
SMB_PATH = "//orexplorefs04.local/pond/incoming/Orexplore/"

# =========================================================
# LOGGING PROFESIONAL
# =========================================================

LOG_DIR = "/var/log/operator_page"

# Crear carpeta si no existe
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "smb_monitor.log")

# Handler de rotación semanal
handler = TimedRotatingFileHandler(
    LOG_FILE,
    when="W0",  # Rotar los lunes
    interval=1,
    backupCount=4,  # Mantener 4 semanas
    encoding="utf-8",
)

# Formato profesional
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

handler.setFormatter(formatter)

# Crear logger para el monitor
monitor_logger = logging.getLogger("SMB_MONITOR")
monitor_logger.setLevel(logging.INFO)
monitor_logger.addHandler(handler)


# =========================================================
# INITIAL DATA FILES
# =========================================================


def init_data_files():
    if not os.path.exists(USERS_FILE):
        users = {
            "Felipe.Campos": {
                "password": generate_password_hash("WeScanRocks"),
                "created_at": datetime.now().isoformat(),
            }
        }
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)

    if not os.path.exists(BATCHES_FILE):
        with open(BATCHES_FILE, "w") as f:
            json.dump([], f)


init_data_files()


# =========================================================
# DATA LOAD/SAVE UTILITIES
# =========================================================


def load_users():
    with open(USERS_FILE, "r") as f:
        return json.load(f)


def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)


def load_batches():
    """Carga y renumera en orden ASCENDENTE siempre."""
    with open(BATCHES_FILE, "r") as f:
        batches = json.load(f)

    # Renumerar ASCENDENTE
    for i, b in enumerate(batches, start=1):
        b["batch_number"] = i

    return batches


def save_batches(batches):
    with open(BATCHES_FILE, "w") as f:
        json.dump(batches, f, indent=4)


# =========================================================
# GENERAL UTILITIES
# =========================================================


def is_logged():
    return "username" in session


def paginate(data, page, per_page):
    start = (page - 1) * per_page
    return data[start : start + per_page]


# =========================================================
# FILE CHECK
# =========================================================


def check_file_values(hole_id, from_val, to_val, machine):
    try:
        file_path = os.path.join(SMB_PATH, f"{hole_id}.txr")
        return True
    except:
        return False


def get_preview_image(hole_id, to_val):
    try:
        return f"smb://172.16.11.107/pond/incoming/Orexplore/{hole_id}/batch-{to_val}/sample-1/rec-low-res-thumb-x.jpg"
    except:
        return None


# =========================================================
# METERS
# =========================================================


def calculate_metros_escaneados():
    batches = load_batches()
    total = 0
    for batch in batches:
        if batch.get("status") == "pending":  # Esperando comparacion
            try:
                total += float(batch.get("to", 0)) - float(batch.get("from", 0))
            except:
                pass
    return round(total, 2)


# =========================================================
# ROUTES
# =========================================================


@app.route("/")
def root():
    return redirect(url_for("index_route"))


@app.route("/index/")
def index_route():
    if not is_logged():
        return redirect(url_for("login"))
    return render_template("index.html", username=session["username"])


# ------------------- LOGIN -------------------


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json
        username = data.get("username")
        password = data.get("password")

        users = load_users()

        if username in users and check_password_hash(
            users[username]["password"], password
        ):
            session["username"] = username
            return jsonify({"success": True})

        return jsonify(
            {"success": False, "message": "Usuario o contraseña incorrectos"}
        )

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


# ------------------- CREATE USER -------------------


@app.route("/create_user", methods=["GET", "POST"])
def create_user():
    if not is_logged():
        return redirect(url_for("login"))

    if request.method == "POST":
        data = request.json
        username = data.get("username")
        password = data.get("password")

        users = load_users()

        if username in users:
            return jsonify({"success": False, "message": "El usuario ya existe"})

        users[username] = {
            "password": generate_password_hash(password),
            "created_at": datetime.now().isoformat(),
        }

        save_users(users)
        return jsonify({"success": True})

    return render_template("create_user.html")


# ------------------- BATCHES -------------------
# ============================================================
# API: LISTAR Y CREAR BATCHES
# ============================================================


@app.route("/api/batches", methods=["GET", "POST"])
def batches_api():
    if "username" not in session:
        return jsonify({"error": "No autorizado"}), 401

    if request.method == "GET":
        page = int(request.args.get("page", 1))
        per_page = 20

        batches = load_batches()

        # 🔥 MÁS NUEVOS ARRIBA (sin reverse)
        batches = sorted(batches, key=lambda b: b["created_at"], reverse=True)

        start = (page - 1) * per_page
        end = start + per_page

        return jsonify(
            {
                "batches": batches[start:end],
                "total_pages": (len(batches) + per_page - 1) // per_page,
                "current_page": page,
            }
        )

    if request.method == "POST":
        data = request.json
        batches = load_batches()

        new_batch = {
            "batch_number": len(batches) + 1,
            "hole_id": data.get("hole_id"),
            "from": data.get("from"),
            "to": data.get("to"),
            "machine": data.get("machine"),
            "comentarios": data.get("comentarios", ""),
            "status": "correct",
            "created_at": datetime.now().isoformat(),
        }

        batches.append(new_batch)
        save_batches(batches)

        return jsonify({"success": True})


# ------------------- DELETE -------------------
@app.route("/api/batches/<int:batch_number>", methods=["DELETE"])
def delete_batch(batch_number):
    if "username" not in session:
        return jsonify({"error": "No autorizado"}), 401

    batches = load_batches()
    new_list = [b for b in batches if b["batch_number"] != batch_number]

    if len(new_list) == len(batches):
        return jsonify({"error": "Batch no encontrado"}), 404

    # Renumerar
    for i, b in enumerate(new_list, start=1):
        b["batch_number"] = i

    save_batches(new_list)
    return jsonify({"success": True})


# ------------------- EDITAR BATCH FROM STATUS CHECKER-------------------
@app.route("/api/batches/<int:batch_number>", methods=["PUT"])
def update_batch(batch_number):
    if "username" not in session:
        return jsonify({"error": "No autorizado"}), 401

    data = request.json
    batches = load_batches()

    batch = next((b for b in batches if b["batch_number"] == batch_number), None)

    if not batch:
        return jsonify({"error": "Batch no encontrado"}), 404

    # Actualizar campos editables
    batch["hole_id"] = data.get("hole_id", batch["hole_id"])
    batch["from"] = data.get("from", batch["from"])
    batch["to"] = data.get("to", batch["to"])
    batch["machine"] = data.get("machine", batch["machine"])
    batch["comentarios"] = data.get("comentarios", batch.get("comentarios", ""))

    save_batches(batches)

    return jsonify({"success": True})


# ------------------- PREVIEW -------------------


@app.route("/api/preview/<int:batch_number>")
def preview_image(batch_number):
    if not is_logged():
        return jsonify({"error": "No autorizado"}), 401

    batches = load_batches()

    batch = next((b for b in batches if b["batch_number"] == batch_number), None)

    if not batch:
        return jsonify({"error": "Batch no encontrado"}), 404

    return jsonify({"image_path": get_preview_image(batch["hole_id"], batch["to"])})


# ------------------- STATUS CHECKER -------------------


@app.route("/status_checker")
def status_checker():
    if not is_logged():
        return redirect(url_for("login"))
    return render_template("status_checker.html", username=session["username"])


# ============================================================
# FUNCION: ACTUALIZAR EL ESTADO DE BATCHES (STATUS CHECKER)
# INSERTAR AQUI
# ============================================================
def actualizar_estado_batches():
    batches = load_batches()
    smb_data = leer_orexplore_smb()

    for batch in batches:
        # valores por defecto (lo que verá la tabla)
        batch["status"] = "pending"
        batch["from"] = batch.get("from", "")

        match = next(
            (
                smb
                for smb in smb_data
                if smb.get("M_hole_id") == batch.get("hole_id")
                and str(smb.get("M_to")) == str(batch.get("to"))
            ),
            None,
        )

        # SMB no encontró nada → pending (tabla queda igual)
        if not match:
            continue

        # SMB encontró carpeta/hole
        batch["status"] = "in_progress"

        # SMB encontró depth.txt
        if match.get("M_from"):
            batch["from"] = match.get("M_from")
            batch["status"] = "correct"

    save_batches(batches)


# ============================================================
# API: STATUS CHECKER DATA
# ============================================================


@app.route("/api/status_checker_data")
def status_checker_data():
    if not is_logged():
        return jsonify({"error": "No autorizado"}), 401

    page = int(request.args.get("page", 1))
    per_page = 30

    batches = load_batches()
    smb_data = leer_orexplore_smb()

    def norm_str(v):
        return str(v).strip() if v is not None else ""

    def norm_num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    for batch in batches:
        match = next(
            (
                smb
                for smb in smb_data
                if norm_str(smb.get("M_hole_id")) == norm_str(batch.get("hole_id"))
                and norm_num(smb.get("M_from")) == norm_num(batch.get("from"))
                and norm_num(smb.get("M_to")) == norm_num(batch.get("to"))
            ),
            None,
        )

        # Estructura SIEMPRE presente (frontend depende de esto)
        batch["machine_values"] = {
            "hole_id": match.get("M_hole_id") if match else "-",
            "from": match.get("M_from") if match else "-",
            "to": match.get("M_to") if match else "-",
            "machine": "OREXPLORE" if match else "-",
        }

        if not match:
            batch["status"] = "pending"
        else:
            batch["status"] = "correct"

    # Paginación
    total_pages = (len(batches) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page

    return jsonify(
        {
            "batches": batches[start:end],
            "total_pages": total_pages,
            "current_page": page,
        }
    )


# =========================================================
# SMB READER
# =========================================================
from smbprotocol.open import (
    Open,
    CreateDisposition,
    CreateOptions,
    FileAttributes,
    ShareAccess,
    FilePipePrinterAccessMask,
    ImpersonationLevel,
)
from smbprotocol.file_info import FileInformationClass
from smbprotocol.exceptions import SMBException


def smb_path(*parts):
    return "\\".join(p.strip("\\/") for p in parts if p)


def leer_orexplore_smb():
    """
    Lectura SEGURA de SMB Orexplore.
    Nunca rompe el backend.
    """

    SERVER = "172.16.11.107"
    SHARE = "pond"
    BASE_PATH = "incoming/Orexplore"

    USERNAME = "orexplore"
    PASSWORD = "en6Eith0aphi"

    resultados = []

    try:
        if not USERNAME or not PASSWORD:
            monitor_logger.warning("SMB credentials no definidas")
            return []

        conn, session, tree = smb_connect(
            server=SERVER, share=SHARE, username=USERNAME, password=PASSWORD
        )

        try:
            base_dir = Open(
                tree,
                BASE_PATH,
                desired_access=0x00000001,
                share_access=0x00000007,
                create_disposition=CreateDisposition.FILE_OPEN,
                create_options=0x00000001,
                impersonation_level=ImpersonationLevel.Impersonation,
            )
            base_dir.create()

            holes = base_dir.query_directory(
                "*", FileInformationClass.FILE_DIRECTORY_INFORMATION
            )

            for hole in holes:
                hole_name = hole["file_name"]
                if hole_name in (".", ".."):
                    continue

                hole_path = f"{BASE_PATH}/{hole_name}"

                try:
                    hole_dir = Open(
                        tree,
                        hole_path,
                        desired_access=0x00000001,
                        share_access=0x00000007,
                        create_disposition=CreateDisposition.FILE_OPEN,
                        create_options=0x00000001,
                        impersonation_level=ImpersonationLevel.Impersonation,
                    )
                    hole_dir.create()
                except SMBException:
                    continue

                batches = hole_dir.query_directory(
                    "batch-*", FileInformationClass.FILE_DIRECTORY_INFORMATION
                )

                for batch in batches:
                    batch_name = batch["file_name"]

                    try:
                        m_to = round(float(batch_name.replace("batch-", "")), 2)
                    except ValueError:
                        continue

                    depth_path = f"{hole_path}/{batch_name}/depth.txt"

                    try:
                        depth_file = Open(
                            tree,
                            depth_path,
                            desired_access=0x00000001,
                            share_access=0x00000007,
                            create_disposition=CreateDisposition.FILE_OPEN,
                            impersonation_level=ImpersonationLevel.Impersonation,
                        )
                        depth_file.create()

                        raw = depth_file.read(0, 2048).decode("utf-8", errors="ignore")
                        lines = [l.strip() for l in raw.splitlines() if l.strip()]
                        if not lines:
                            depth_file.close()
                            continue

                        m_from = round(float(lines[0]), 2)

                        resultados.append(
                            {
                                "M_hole_id": hole_name.strip(),
                                "M_from": m_from,
                                "M_to": m_to,
                                "M_machine": "OREXPLORE",
                            }
                        )

                        depth_file.close()

                    except (SMBException, ValueError):
                        continue

                hole_dir.close()

            base_dir.close()

        finally:
            conn.disconnect()

    except Exception as e:
        monitor_logger.error(f"SMB crítico: {e}")
        return []

    return resultados


# =========================================================
# METERS PAGE
# =========================================================


@app.route("/metros")
def metros():
    if not is_logged():
        return redirect(url_for("login"))
    return render_template("metros.html", username=session["username"])


@app.route("/api/metros_data")
def metros_data():
    if not is_logged():
        return jsonify({"error": "No autorizado"}), 401

    batches = load_batches()
    now = datetime.now()

    daily_data = []
    for hour in range(24):
        metros = 0
        for batch in batches:
            if batch.get("status") == "correct":
                batch_time = datetime.fromisoformat(batch["created_at"])
                if batch_time.date() == now.date() and batch_time.hour <= hour:
                    try:
                        metros += float(batch["to"]) - float(batch["from"])
                    except:
                        pass

        daily_data.append({"hour": hour, "metros": round(metros, 2)})

    monthly_data = []
    for day in range(30):
        date_point = now - timedelta(days=29 - day)
        metros = 0

        for batch in batches:
            if batch.get("status") == "correct":
                batch_time = datetime.fromisoformat(batch["created_at"])
                if batch_time.date() == date_point.date():
                    try:
                        metros += float(batch["to"]) - float(batch["from"])
                    except:
                        pass

        monthly_data.append(
            {"day": date_point.strftime("%d/%m"), "metros": round(metros, 2)}
        )

    return jsonify({"daily": daily_data, "monthly": monthly_data})


@app.route("/api/metros_total")
def metros_total():
    if not is_logged():
        return jsonify({"error": "No autorizado"}), 401

    total = calculate_metros_escaneados()
    return jsonify({"total": total})


# =========================================================
# MONITOR AUTOMÁTICO SMB
# =========================================================


def start_smb_monitor_interval():
    """Monitor automático que revisa SMB cada 5 minutos."""
    while True:
        try:
            monitor_logger.info("Iniciando monitoreo SMB...")
            actualizar_estado_batches()
            monitor_logger.info("Monitoreo SMB completado correctamente.")
        except Exception as e:
            monitor_logger.error(f"Error durante monitoreo SMB: {e}")

        time.sleep(300)  # 5 minutos


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":
    # Iniciar hilo del monitoreo SMB automático
    monitor_thread = threading.Thread(target=start_smb_monitor_interval, daemon=True)
    monitor_thread.start()

    app.run(host="172.16.11.104", port=5001, debug=True)
