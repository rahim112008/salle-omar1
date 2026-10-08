"""
🥋 Gestion Dojo Karaté — Application complète mono-dojo (local-first)
====================================================================

Fonctionnalités :
  - Authentification sécurisée (bcrypt) + rôles (admin / prof / secrétaire / membre)
  - Licence hors ligne (HMAC signé sur machine_id)
  - Membres : archivage, historique, parents, mineurs, dossier médical
  - Cours + planning hebdo/mensuel + séances exceptionnelles
  - Présences : présent / absent / justifié / retard / consultation + scan QR
  - Paiements : payé / partiel / en retard + reçus PDF + "qui doit payer"
  - Grades & Examens : jury, notes, admis/ajourné + historique
  - Compétitions : catégories, résultats, médailles
  - QR codes sécurisés (HMAC) + cartes membres PDF (individuel + lot)
  - Sauvegarde automatique quotidienne (ZIP) + restauration manuelle
  - Export CSV de toutes les données

Déploiement :
  - PC       : python -m venv venv && pip install -r requirements.txt
                streamlit run main.py
  - Termux   : python main.py --install-termux
                python main.py --run
  - Cloud    : voir options dans l'interface (page Installation)

Configuration licence (à faire par le développeur) :
  1. Générer un secret : python -c "import secrets; print(secrets.token_urlsafe(32))"
  2. Remplacer LICENSE_SECRET ci-dessous
  3. Pour émettre une licence client :
        from main import generate_license
        print(generate_license("Dojo Tlemcen", "MACHINE_ID_DU_CLIENT", "2026-10-08"))
"""

import sys, os, subprocess, platform, shutil, io, json, hmac, hashlib, uuid, zipfile
import sqlite3
import base64
import re
from datetime import datetime, date, timedelta
from pathlib import Path

# ============================================================
# BASH EMBARQUÉ — Installation automatique Termux (Android)
# ============================================================
TERMUX_BASH_SETUP = r"""
set -e
echo "▶ Mise à jour des paquets..."
pkg update -y && pkg upgrade -y

echo "▶ Installation des dépendances système..."
pkg install -y python libjpeg-turbo libpng openssl libxml2 libxslt clang

echo "▶ Autorisation d'accès au stockage..."
termux-setup-storage || true

echo "▶ Mise à jour de pip..."
pip install --upgrade pip wheel setuptools

echo "▶ Installation des paquets Python..."
pip install -r requirements.txt

echo "▶ Création du dossier de stockage local..."
mkdir -p /storage/emulated/0/DojoKaraté/exports
mkdir -p /storage/emulated/0/DojoKaraté/qrcodes
mkdir -p /storage/emulated/0/DojoKaraté/backups

if ! grep -q "DOJO_DATA_DIR" ~/.bashrc 2>/dev/null; then
    echo 'export DOJO_DATA_DIR=/storage/emulated/0/DojoKaraté' >> ~/.bashrc
fi

echo ""
echo "✅ Installation terminée !"
echo "Lancement : python main.py --run"
echo "Puis Chrome : http://localhost:8501"
"""

def is_termux():
    return ("ANDROID_ROOT" in os.environ
            or "ANDROID_DATA" in os.environ
            or os.path.exists("/data/data/com.termux")
            or "com.termux" in os.environ.get("PREFIX", ""))

def is_android_storage_available():
    return os.path.exists("/storage/emulated/0")

def run_termux_setup():
    if not is_termux():
        print("⚠️  Ce script n'est destiné qu'à Termux (Android).")
        print("Sur PC : pip install -r requirements.txt")
        return False
    script_path = os.path.expanduser("~/install_dojo.sh")
    with open(script_path, "w") as f:
        f.write(TERMUX_BASH_SETUP)
    os.chmod(script_path, 0o755)
    try:
        subprocess.run(["bash", script_path], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur : {e}")
        return False

def launch_streamlit():
    subprocess.run(["streamlit", "run", _file_,
                    "--server.address=0.0.0.0", "--server.port=8501"])

# --- CLI avant imports Streamlit ---
if _name_ == "_main_" and len(sys.argv) > 1:
    _arg = sys.argv[1].lower()
    if _arg in ("--install-termux", "--install"):
        sys.exit(0 if run_termux_setup() else 1)
    elif _arg == "--run":
        launch_streamlit()
        sys.exit(0)
    elif _arg in ("-h", "--help"):
        print(_doc_)
        sys.exit(0)
    elif _arg == "--machine-id":
        # Utile pour générer une licence client
        parts = [platform.node(), platform.machine(), str(uuid.getnode())]
        raw = "|".join(parts).encode()
        print(hashlib.sha256(raw).hexdigest()[:16])
        sys.exit(0)

# ============================================================
# IMPORTS DE L'APPLICATION
# ============================================================
import pandas as pd
import streamlit as st
import plotly.express as px
import qrcode
from fpdf import FPDF
import bcrypt

try:
    import cv2, numpy as np
    HAS_CV = True
except Exception:
    HAS_CV = False

# ============================================================
# CONFIGURATION
# ============================================================
LICENSE_SECRET = "REMPLACER_PAR_UN_SECRET_DE_32_CARACTERES_MINIMUM_ALEATOIRES"
# ⚠️ Générez le vôtre : python -c "import secrets; print(secrets.token_urlsafe(32))"

DATA_DIR = os.environ.get("DOJO_DATA_DIR",
                          os.path.join(os.path.expanduser("~"), "DojoKaraté"))
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
QR_DIR     = os.path.join(DATA_DIR, "qrcodes")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
DB_PATH    = os.path.join(DATA_DIR, "dojo.db")
LICENSE_FILE = os.path.join(DATA_DIR, "license.key")

for d in (DATA_DIR, EXPORT_DIR, QR_DIR, BACKUP_DIR):
    os.makedirs(d, exist_ok=True)

APP_TITLE = "🥋 Gestion Dojo Karaté"

GRADES = ["Blanche", "Jaune", "Orange", "Verte", "Bleue",
          "Marron 3e kyu", "Marron 2e kyu", "Marron 1er kyu",
          "Noire 1er Dan", "Noire 2e Dan", "Noire 3e Dan",
          "Noire 4e Dan", "Noire 5e Dan", "Noire 6e Dan"]

CATEGORIES = ["Poussins", "Pupilles", "Benjamins", "Minimes",
              "Cadets", "Juniors", "Espoirs", "Seniors"]

DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

PAYMENT_TYPES = ["Inscription", "Cotisation", "Licence", "Compétition",
                 "Stage", "Boutique", "Autre"]
PAYMENT_METHODS = ["Espèces", "Chèque", "Virement", "CB", "En ligne"]
PAYMENT_STATUS = {
    "paid":    "Payé",
    "pending": "Non payé",
    "partial": "Partiellement payé",
    "overdue": "En retard",
}

ATTENDANCE_STATUS = {
    "present":      "Présent",
    "absent":       "Absent",
    "justified":    "Absence justifiée",
    "late":         "Retard",
    "consultation": "Consultation",
}

ROLES = ["admin", "professeur", "secretaire", "membre"]

st.set_page_config(page_title="Gestion Dojo", page_icon="🥋", layout="wide")


# ============================================================
# LICENCE (HMAC sur machine_id)
# ============================================================
def machine_id() -> str:
    parts = [platform.node(), platform.machine(), str(uuid.getnode())]
    raw = "|".join(parts).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def generate_license(client_name: str, machine: str, expires: str) -> str:
    """À exécuter chez le développeur pour émettre une licence."""
    payload = {
        "client": client_name,
        "machine": machine,
        "expires": expires,   # 'YYYY-MM-DD' ou 'never'
        "issued": date.today().isoformat(),
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    sig = hmac.new(LICENSE_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return json.dumps({"payload": payload, "signature": sig}, indent=2)


def verify_license(path: str = LICENSE_FILE) -> tuple[bool, str]:
    if LICENSE_SECRET.startswith("REMPLACER"):
        return True, "Mode développeur (licence non configurée)."
    if not os.path.exists(path):
        return False, "Licence introuvable."
    try:
        with open(path) as f:
            data = json.load(f)
        payload, sig = data["payload"], data["signature"]
    except Exception:
        return False, "Licence corrompue."
    raw = json.dumps(payload, sort_keys=True).encode()
    expected = hmac.new(LICENSE_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False, "Signature invalide."
    if payload["machine"] != machine_id():
        return False, "Licence liée à un autre appareil."
    if payload["expires"] != "never":
        try:
            if date.fromisoformat(payload["expires"]) < date.today():
                return False, f"Licence expirée le {payload['expires']}."
        except Exception:
            return False, "Date d'expiration invalide."
    return True, f"Licence valide — {payload['client']} (expire : {payload['expires']})"


def license_gate():
    """Écran de blocage si licence absente/invalide."""
    ok, msg = verify_license()
    if ok:
        return True
    st.error(f"🔒 {msg}")
    st.markdown("### Activation requise")
    st.markdown("Envoyez cet identifiant à votre fournisseur pour obtenir votre licence :")
    st.code(machine_id(), language="text")
    st.info("Placez ensuite le fichier license.key reçu dans le dossier "
            f"{DATA_DIR} puis rechargez la page.")
    return False


# ============================================================
# BASE DE DONNÉES (SQLite)
# ============================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hp(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def init_db():
    conn = get_conn(); c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        member_id INTEGER,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS members(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        birth_date TEXT,
        gender TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        blood_group TEXT,
        academic_level TEXT,
        category TEXT,
        group_name TEXT,
        license_number TEXT,
        license_expiry TEXT,
        medical_cert_expiry TEXT,
        insurance_status TEXT,
        insurance_expiry TEXT,
        parental_authorization INTEGER DEFAULT 0,
        documents_status TEXT DEFAULT 'Incomplet',
        grade TEXT,
        grade_date TEXT,
        discipline TEXT,
        join_date TEXT,
        status TEXT DEFAULT 'Actif',
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS parents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT,
        phone TEXT, email TEXT, address TEXT
    );
    CREATE TABLE IF NOT EXISTS member_parents(
        member_id INTEGER, parent_id INTEGER,
        relationship TEXT DEFAULT 'parent',
        PRIMARY KEY(member_id, parent_id)
    );
    CREATE TABLE IF NOT EXISTS courses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        day_of_week INTEGER,
        start_time TEXT, end_time TEXT,
        room TEXT, teacher TEXT,
        category TEXT, discipline TEXT,
        capacity INTEGER DEFAULT 20,
        active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        session_date TEXT,
        start_time TEXT, end_time TEXT,
        room TEXT,
        status TEXT DEFAULT 'planned',
        is_exception INTEGER DEFAULT 0,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS enrollments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, course_id INTEGER,
        date_enrolled TEXT,
        UNIQUE(member_id, course_id)
    );
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, course_id INTEGER,
        attendance_date TEXT,
        status TEXT DEFAULT 'present',
        note TEXT,
        UNIQUE(member_id, course_id, attendance_date)
    );
    CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER,
        amount REAL DEFAULT 0,
        amount_paid REAL DEFAULT 0,
        payment_date TEXT,
        due_date TEXT,
        method TEXT, type TEXT,
        season TEXT,
        status TEXT DEFAULT 'pending',
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS exams(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, exam_date TEXT,
        examiner TEXT, grade_targeted TEXT,
        location TEXT, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS exam_candidates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER, member_id INTEGER,
        grade_targeted TEXT,
        score REAL, result TEXT,
        observations TEXT,
        UNIQUE(exam_id, member_id)
    );
    CREATE TABLE IF NOT EXISTS grades_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, grade TEXT,
        grade_date TEXT, examiner TEXT,
        result TEXT, exam_id INTEGER, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS competitions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, competition_date TEXT,
        location TEXT, description TEXT
    );
    CREATE TABLE IF NOT EXISTS competition_registrations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_id INTEGER, member_id INTEGER,
        category TEXT, discipline TEXT,
        result TEXT, ranking INTEGER, medal TEXT,
        observations TEXT,
        UNIQUE(competition_id, member_id)
    );
    """)
    conn.commit()

    # Création admin par défaut si base vide
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users(username,password,role,created_at) VALUES(?,?,?,?)",
                  ("admin", hp("admin123"), "admin", datetime.now().isoformat()))
        c.execute("INSERT INTO users(username,password,role,created_at) VALUES(?,?,?,?)",
                  ("prof", hp("prof123"), "professeur", datetime.now().isoformat()))
        conn.commit()
    conn.close()


def fetch_all(q, p=()):
    conn = get_conn(); c = conn.cursor(); c.execute(q, p)
    r = [dict(x) for x in c.fetchall()]; conn.close(); return r


def fetch_one(q, p=()):
    conn = get_conn(); c = conn.cursor(); c.execute(q, p)
    row = c.fetchone(); conn.close(); return dict(row) if row else None


def execute(q, p=()):
    conn = get_conn(); c = conn.cursor(); c.execute(q, p); conn.commit()
    lid = c.lastrowid; conn.close(); return lid


def execute_many(q, params_list):
    conn = get_conn(); c = conn.cursor(); c.executemany(q, params_list)
    conn.commit(); conn.close()


# ============================================================
# SAUVEGARDE AUTO
# ============================================================
def auto_backup(keep_days: int = 60) -> str | None:
    try:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(BACKUP_DIR, f"backup_{stamp}.zip")
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(DB_PATH, arcname="dojo.db")
        cutoff = datetime.now() - timedelta(days=keep_days)
        for f in Path(BACKUP_DIR).glob("backup_*.zip"):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
        return dest
    except Exception:
        return None


def should_backup_today() -> bool:
    today = datetime.now().strftime("%Y%m%d")
    return not any(Path(BACKUP_DIR).glob(f"backup_{today}_*.zip"))


# ============================================================
# HELPERS
# ============================================================
def calc_age(bd):
    if not bd: return None
    try:
        d = datetime.strptime(bd, "%Y-%m-%d").date()
    except Exception:
        return None
    t = date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def full_name(m): return f"{m['first_name']} {m['last_name']}"


def auto_category(age):
    if age is None: return "Seniors"
    if age <= 5: return "Poussins"
    if age <= 7: return "Pupilles"
    if age <= 9: return "Benjamins"
    if age <= 11: return "Minimes"
    if age <= 14: return "Cadets"
    if age <= 17: return "Juniors"
    if age <= 20: return "Espoirs"
    return "Seniors"


def slug(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-zA-Z0-9]+", "", s or "")).strip("")


def login(u, p):
    user = fetch_one("SELECT * FROM users WHERE username=?", (u,))
    if user and verify_pw(p, user["password"]):
        return user
    return None


def compute_payment_status(amount, paid, due_date):
    if paid >= amount: return "paid"
    if paid <= 0:
        if due_date and due_date < date.today().isoformat():
            return "overdue"
        return "pending"
    return "partial"


# ============================================================
# QR (HMAC sécurisé)
# ============================================================
def sign_payload(member_id: int) -> str:
    msg = str(member_id).encode()
    return hmac.new(LICENSE_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:16]


def build_qr_payload(member_id: int, license_number: str = "") -> str:
    sig = sign_payload(member_id)
    return f"DOJO|{member_id}|{license_number or ''}|{sig}"


def verify_qr_payload(payload: str):
    try:
        prefix, mid, lic, sig = payload.split("|")
        if prefix != "DOJO": return None
        if not hmac.compare_digest(sig, sign_payload(int(mid))): return None
        return {"member_id": int(mid), "license": lic}
    except Exception:
        return None


def make_qr_code(m) -> tuple[str, str]:
    data = build_qr_payload(m["id"], m.get("license_number") or "")
    img = qrcode.make(data)
    path = os.path.join(QR_DIR, f"qr_{m['id']}_{slug(full_name(m))}.png")
    img.save(path)
    return path, data


def decode_qr_from_bytes(b):
    if not HAS_CV: return None
    arr = np.frombuffer(b, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None: return None
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    return data or None


# ============================================================
# PDF — Fiche membre, Reçu, Carte
# ============================================================
def _t(s): return str(s if s is not None else "").encode("latin-1", "replace").decode("latin-1")


def make_member_pdf(m):
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _t("Fiche membre - Dojo Karaté"), ln=True, align="C"); pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    for k, v in [
        ("Nom complet", full_name(m)), ("Âge", calc_age(m["birth_date"])),
        ("Date naissance", m["birth_date"]), ("Sexe", m["gender"]),
        ("Catégorie", m["category"]), ("Téléphone", m["phone"]),
        ("Email", m["email"]), ("Adresse", m["address"]),
        ("Grade", m["grade"]), ("N° Licence", m["license_number"]),
        ("Exp. licence", m["license_expiry"]),
        ("Exp. cert. médical", m["medical_cert_expiry"]),
        ("Assurance", m["insurance_status"]),
        ("Date inscription", m["join_date"]), ("Statut", m["status"]),
        ("Notes", m["notes"])]:
        pdf.set_font("Helvetica", "B", 11); pdf.cell(60, 8, _t(f"{k} :"))
        pdf.set_font("Helvetica", "", 11); pdf.cell(0, 8, _t(v), ln=True)
    path = os.path.join(EXPORT_DIR, f"fiche_{slug(full_name(m))}.pdf")
    pdf.output(path); return path


def make_receipt_pdf(p, m):
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _t("Reçu de paiement - Dojo Karaté"), ln=True, align="C"); pdf.ln(6)
    pdf.set_font("Helvetica", "", 12)
    reste = (p["amount"] or 0) - (p.get("amount_paid") or 0)
    for k, v in [("Reçu N°", p["id"]), ("Date", p["payment_date"]),
                 ("Membre", full_name(m)), ("Type", p["type"]),
                 ("Montant total", f"{p['amount']:.2f} DA"),
                 ("Montant payé", f"{p.get('amount_paid', 0):.2f} DA"),
                 ("Reste dû", f"{reste:.2f} DA"),
                 ("Méthode", p["method"]),
                 ("Échéance", p["due_date"]), ("Saison", p["season"]),
                 ("Statut", PAYMENT_STATUS.get(p["status"], p["status"])),
                 ("Notes", p["notes"])]:
        pdf.set_font("Helvetica", "B", 12); pdf.cell(60, 10, _t(f"{k} :"))
        pdf.set_font("Helvetica", "", 12); pdf.cell(0, 10, _t(v), ln=True)
    pdf.ln(10); pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 10, _t("Merci de votre confiance. Ossu !"), align="C")
    path = os.path.join(EXPORT_DIR, f"recu_{p['id']}_{slug(full_name(m))}.pdf")
    pdf.output(path); return path


CARD_W, CARD_H = 85, 54  # mm


def _draw_card(pdf, x, y, m, qr_path):
    pdf.set_fill_color(255, 255, 255); pdf.set_draw_color(180, 180, 180)
    pdf.rect(x, y, CARD_W, CARD_H, style="DF")
    pdf.set_fill_color(26, 26, 46)
    pdf.rect(x, y, CARD_W, 10, style="F")
    pdf.set_text_color(255, 255, 255); pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(x + 2, y + 2)
    pdf.cell(0, 6, _t("DOJO KARATÉ"), ln=0)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(x + 2, y + 12)
    pdf.cell(0, 5, _t(f"{m['first_name']} {m['last_name']}"[:26]), ln=1)
    pdf.set_font("Helvetica", "", 😎
    pdf.set_xy(x + 2, y + 19); pdf.cell(0, 4, _t(f"Grade : {m.get('grade') or '—'}"), ln=1)
    pdf.set_xy(x + 2, y + 24); pdf.cell(0, 4, _t(f"Licence : {m.get('license_number') or '—'}"), ln=1)
    pdf.set_font("Helvetica", "I", 6); pdf.set_text_color(120, 120, 120)
    pdf.set_xy(x + 2, y + 29); pdf.cell(0, 4, _t(f"ID : {m['id']:06d}"), ln=1)
    pdf.set_text_color(0, 0, 0)
    if qr_path and os.path.exists(qr_path):
        pdf.image(qr_path, x + CARD_W - 26, y + CARD_H - 26, 24, 24)
    pdf.set_font("Helvetica", "", 6); pdf.set_text_color(120, 120, 120)
    pdf.set_xy(x + 2, y + CARD_H - 6)
    pdf.cell(0, 4, _t(f"Émise le {date.today():%d/%m/%Y}"), ln=1)
    pdf.set_text_color(0, 0, 0)


def generate_member_card_pdf(m) -> str:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    qr_path, _ = make_qr_code(m)
    _draw_card(pdf, 62, 40, m, qr_path)
    path = os.path.join(EXPORT_DIR, f"carte_{slug(full_name(m))}.pdf")
    pdf.output(path); return path


def generate_batch_cards_pdf(members) -> str:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    mx, my, gx, gy = 12, 15, 6, 6
    per_row, per_col = 2, 4
    per_page = per_row * per_col
    for i, m in enumerate(members):
        pos = i % per_page
        if pos == 0 and i > 0:
            pdf.add_page()
        col, row = pos % per_row, pos // per_row
        x = mx + col * (CARD_W + gx)
        y = my + row * (CARD_H + gy)
        qr_path, _ = make_qr_code(m)
        _draw_card(pdf, x, y, m, qr_path)
    path = os.path.join(EXPORT_DIR, f"cartes_lot_{datetime.now():%Y%m%d_%H%M}.pdf")
    pdf.output(path); return path


# ============================================================
# EXPORTS CSV
# ============================================================
def export_members_csv():
    rows = fetch_all("SELECT * FROM members ORDER BY last_name")
    if not rows: return None
    df = pd.DataFrame(rows); df["age"] = df["birth_date"].apply(calc_age)
    path = os.path.join(EXPORT_DIR, "membres.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_payments_csv():
    rows = fetch_all("""SELECT p.*, m.first_name, m.last_name FROM payments p
                        JOIN members m ON m.id=p.member_id ORDER BY p.payment_date DESC""")
    if not rows: return None
    df = pd.DataFrame(rows)
    path = os.path.join(EXPORT_DIR, "paiements.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_attendance_csv():
    rows = fetch_all("""SELECT a.attendance_date, m.first_name, m.last_name,
                               c.name AS cours, a.status
                        FROM attendance a
                        JOIN members m ON m.id=a.member_id
                        LEFT JOIN courses c ON c.id=a.course_id
                        ORDER BY a.attendance_date DESC""")
    if not rows: return None
    df = pd.DataFrame(rows)
    path = os.path.join(EXPORT_DIR, "presences.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def export_all_csv():
    return [p for p in (export_members_csv(), export_payments_csv(),
                         export_attendance_csv()) if p]


# ============================================================
# INITIALISATION
# ============================================================
init_db()

if should_backup_today():
    auto_backup(keep_days=60)


# ============================================================
# SESSION
# ============================================================
if "user" not in st.session_state:
    st.session_state.user = None


def login_page():
    st.markdown(f"<h1 style='text-align:center'>{APP_TITLE}</h1>",
                unsafe_allow_html=True)
    _, c, _ = st.columns([1, 1, 1])
    with c:
        with st.form("login"):
            u = st.text_input("Identifiant")
            p = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter", use_container_width=True):
                user = login(u, p)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Identifiants invalides")
        st.info("Défaut : *admin / admin123* ou *prof / prof123*")
        st.caption(f"📂 Données : {DATA_DIR}")


# ============================================================
# PAGES
# ============================================================
def page_dashboard():
    st.title("📊 Tableau de bord")
    members = fetch_all("SELECT * FROM members")
    active = [m for m in members if m["status"] == "Actif"]
    archived = [m for m in members if m["status"] == "Archivé"]

    tp = fetch_one("SELECT COALESCE(SUM(amount_paid),0) s FROM payments WHERE status='paid'")["s"]
    pend = fetch_one("""SELECT COALESCE(SUM(amount - COALESCE(amount_paid,0)),0) s
                        FROM payments WHERE status!='paid'""")["s"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Membres", len(members))
    c2.metric("Actifs", len(active))
    c3.metric("Archivés", len(archived))
    c4.metric("Encaissé", f"{tp:,.0f} DA")
    c5.metric("En attente", f"{pend:,.0f} DA")

    st.divider()
    if members:
        df = pd.DataFrame(members)
        df["age"] = df["birth_date"].apply(calc_age)
        a, b = st.columns(2)
        cc = df["category"].value_counts().reset_index()
        cc.columns = ["Catégorie", "Nombre"]
        a.plotly_chart(px.pie(cc, names="Catégorie", values="Nombre",
                              title="Par catégorie"), use_container_width=True)
        gc = df["grade"].value_counts().reset_index()
        gc.columns = ["Grade", "Nombre"]
        b.plotly_chart(px.bar(gc, x="Grade", y="Nombre", title="Par grade"),
                       use_container_width=True)

    st.divider()
    st.subheader("⚠️ Alertes administratives")
    today = date.today()
    alerts = []

    for m in active:
        for fld, label in (("license_expiry", "Licence"),
                            ("medical_cert_expiry", "Cert. médical"),
                            ("insurance_expiry", "Assurance")):
            if m.get(fld):
                try:
                    d = datetime.strptime(m[fld], "%Y-%m-%d").date()
                    if d < today:
                        alerts.append(f"🔴 {label} EXPIRÉ — {full_name(m)} ({d})")
                    elif d < today + timedelta(days=30):
                        alerts.append(f"🟠 {label} bientôt expiré — {full_name(m)} ({d})")
                except Exception:
                    pass
        if m.get("documents_status") == "Incomplet":
            alerts.append(f"🟡 Dossier incomplet — {full_name(m)}")

    for p in fetch_all("""SELECT p.*, m.first_name, m.last_name
                          FROM payments p JOIN members m ON m.id=p.member_id
                          WHERE p.status!='paid'"""):
        reste = (p["amount"] or 0) - (p.get("amount_paid") or 0)
        alerts.append(f"💰 Impayé {reste:.0f} DA — {p['first_name']} {p['last_name']}")

    # Détection absences répétées
    for m in active:
        recent = fetch_all("""SELECT status FROM attendance
                              WHERE member_id=?
                              ORDER BY attendance_date DESC LIMIT 4""", (m["id"],))
        if len(recent) >= 4 and all(r["status"] == "absent" for r in recent):
            alerts.append(f"🚨 {full_name(m)} : 4 absences consécutives")

    if alerts:
        for a in alerts[:30]:
            st.warning(a)
        if len(alerts) > 30:
            st.caption(f"... et {len(alerts) - 30} autres.")
    else:
        st.success("Aucune alerte 🎉")


def page_members():
    st.title("👥 Membres")
    t1, t2, t3, t4, t5 = st.tabs(
        ["📋 Liste", "➕ Ajouter", "✏️ Modifier", "🔍 Détails", "🗄️ Archivés"])

    # --- LISTE ---
    with t1:
        rows = fetch_all("SELECT * FROM members WHERE status!='Archivé' ORDER BY last_name, first_name")
        if not rows:
            st.info("Aucun membre.")
        else:
            df = pd.DataFrame(rows)
            df["Nom"] = df["first_name"] + " " + df["last_name"]
            df["Âge"] = df["birth_date"].apply(calc_age)
            f1, f2, f3 = st.columns(3)
            s = f1.text_input("Rechercher")
            cf = f2.selectbox("Catégorie", ["Toutes"] + CATEGORIES)
            sf = f3.selectbox("Statut", ["Tous", "Actif", "Inactif"])
            v = df[["id", "Nom", "Âge", "category", "grade", "status", "phone"]].copy()
            v.columns = ["ID", "Nom", "Âge", "Catégorie", "Grade", "Statut", "Téléphone"]
            if s: v = v[v["Nom"].str.contains(s, case=False, na=False)]
            if cf != "Toutes": v = v[v["Catégorie"] == cf]
            if sf != "Tous": v = v[v["Statut"] == sf]
            st.dataframe(v, use_container_width=True, hide_index=True)
            st.download_button("📥 CSV", v.to_csv(index=False).encode("utf-8-sig"),
                                "membres.csv", "text/csv")

    # --- AJOUTER ---
    with t2:
        with st.form("add_m"):
            c1, c2, c3 = st.columns(3)
            fn = c1.text_input("Prénom *")
            ln = c2.text_input("Nom *")
            gd = c3.selectbox("Sexe", ["M", "F"])
            c4, c5, c6 = st.columns(3)
            bd = c4.date_input("Naissance", value=date(2010, 1, 1))
            blood = c5.selectbox("Groupe sanguin", ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])
            academic = c6.text_input("Niveau académique")
            c7, c8 = st.columns(2)
            ph = c7.text_input("Téléphone")
            em = c8.text_input("Email")
            ad = st.text_input("Adresse")
            c9, c10 = st.columns(2)
            gr = c9.selectbox("Grade", GRADES)
            disc = c10.selectbox("Discipline", ["Kata", "Kumite", "Kata & Kumite"])
            c11, c12, c13 = st.columns(3)
            lic = c11.text_input("N° Licence")
            le = c12.date_input("Exp. licence", value=date.today() + timedelta(days=365))
            me = c13.date_input("Exp. cert. médical", value=date.today() + timedelta(days=365))
            c14, c15 = st.columns(2)
            ins = c14.selectbox("Assurance", ["non", "oui"])
            ins_e = c15.date_input("Exp. assurance", value=date.today() + timedelta(days=365))
            parental = st.checkbox("Autorisation parentale (mineur)")
            nt = st.text_area("Notes")

            if st.form_submit_button("Ajouter", use_container_width=True):
                if not fn or not ln:
                    st.error("Prénom et nom obligatoires.")
                else:
                    age = calc_age(bd.isoformat())
                    cat = auto_category(age)
                    mid = execute("""INSERT INTO members(
                        first_name,last_name,birth_date,gender,phone,email,address,
                        blood_group,academic_level,category,grade,grade_date,
                        discipline,license_number,license_expiry,medical_cert_expiry,
                        insurance_status,insurance_expiry,parental_authorization,
                        documents_status,join_date,status,notes)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (fn, ln, bd.isoformat(), gd, ph, em, ad, blood, academic, cat,
                         gr, date.today().isoformat(), disc, lic, le.isoformat(),
                         me.isoformat(), ins, ins_e.isoformat(), int(parental),
                         "Complet" if (lic and me) else "Incomplet",
                         date.today().isoformat(), "Actif", nt))
                    m = fetch_one("SELECT * FROM members WHERE id=?", (mid,))
                    make_qr_code(m); export_members_csv()
                    st.success(f"Ajouté : {fn} {ln} ({cat}). QR généré.")

    # --- MODIFIER ---
    with t3:
        rows = fetch_all("SELECT * FROM members WHERE status!='Archivé' ORDER BY last_name")
        if not rows:
            st.info("Aucun membre.")
        else:
            opts = {f"{m['id']} — {full_name(m)}": m for m in rows}
            sel = st.selectbox("Membre", list(opts.keys()))
            m = opts[sel]
            with st.form("edit_m"):
                c1, c2 = st.columns(2)
                fn = c1.text_input("Prénom", value=m["first_name"])
                ln = c2.text_input("Nom", value=m["last_name"])
                c3, c4 = st.columns(2)
                gr = c3.selectbox("Grade", GRADES,
                                   index=GRADES.index(m["grade"]) if m["grade"] in GRADES else 0)
                stt = c4.selectbox("Statut", ["Actif", "Inactif", "Archivé"],
                                    index=["Actif", "Inactif", "Archivé"].index(m["status"])
                                    if m["status"] in ["Actif", "Inactif", "Archivé"] else 0)
                c5, c6 = st.columns(2)
                ph = c5.text_input("Téléphone", value=m.get("phone") or "")
                em = c6.text_input("Email", value=m.get("email") or "")
                ad = st.text_input("Adresse", value=m.get("address") or "")
                nt = st.text_area("Notes", value=m.get("notes") or "")
                a, b, c = st.columns(3)
                if a.form_submit_button("💾 Enregistrer", use_container_width=True):
                    execute("""UPDATE members SET first_name=?,last_name=?,grade=?,status=?,
                               phone=?,email=?,address=?,notes=? WHERE id=?""",
                            (fn, ln, gr, stt, ph, em, ad, nt, m["id"]))
                    export_members_csv()
                    st.success("Mis à jour."); st.rerun()
                if b.form_submit_button("🗄️ Archiver", use_container_width=True):
                    execute("UPDATE members SET status='Archivé' WHERE id=?", (m["id"],))
                    st.success("Archivé."); st.rerun()

    # --- DÉTAILS ---
    with t4:
        rows = fetch_all("SELECT * FROM members WHERE status!='Archivé' ORDER BY last_name")
        if not rows:
            st.info("Aucun membre.")
        else:
            opts = {f"{m['id']} — {full_name(m)}": m for m in rows}
            m = opts[st.selectbox("Choisir", list(opts.keys()), key="detail_sel")]
            st.subheader(full_name(m))
            c1, c2, c3 = st.columns(3)
            c1.metric("Âge", calc_age(m["birth_date"]) or "-")
            c2.metric("Grade", m["grade"] or "-")
            c3.metric("Statut", m["status"] or "-")

            col_qr, col_act = st.columns([1, 2])
            qr_path, _ = make_qr_code(m)
            with col_qr:
                st.image(qr_path, caption="QR membre", width=200)
            with col_act:
                pdf_path = make_member_pdf(m)
                with open(pdf_path, "rb") as f:
                    st.download_button("📄 Fiche PDF", f.read(),
                                        os.path.basename(pdf_path), "application/pdf")
                with open(qr_path, "rb") as f:
                    st.download_button("📱 QR", f.read(),
                                        os.path.basename(qr_path), "image/png")

            st.divider()
            sub1, sub2, sub3, sub4 = st.tabs(["💰 Paiements", "🥋 Grades", "✅ Présences", "👨‍👩‍👧 Parents"])
            with sub1:
                ps = fetch_all("SELECT * FROM payments WHERE member_id=? ORDER BY payment_date DESC", (m["id"],))
                if ps:
                    df = pd.DataFrame(ps)[["payment_date", "amount", "amount_paid", "type", "status"]]
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.caption("Aucun paiement.")
            with sub2:
                gh = fetch_all("SELECT * FROM grades_history WHERE member_id=? ORDER BY grade_date DESC", (m["id"],))
                if gh:
                    st.dataframe(pd.DataFrame(gh)[["grade_date", "grade", "examiner", "result"]],
                                 use_container_width=True, hide_index=True)
                else:
                    st.caption("Aucun grade.")
            with sub3:
                at = fetch_all("""SELECT a.attendance_date, c.name AS cours, a.status
                                  FROM attendance a
                                  LEFT JOIN courses c ON c.id=a.course_id
                                  WHERE a.member_id=?
                                  ORDER BY a.attendance_date DESC LIMIT 50""", (m["id"],))
                if at:
                    df = pd.DataFrame(at)
                    present = (df["status"] == "present").sum()
                    st.metric("Taux présence", f"{present}/{len(df)}")
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.caption("Aucune présence.")
            with sub4:
                parents = fetch_all("""SELECT p.*, mp.relationship
                                       FROM parents p
                                       JOIN member_parents mp ON mp.parent_id=p.id
                                       WHERE mp.member_id=?""", (m["id"],))
                if parents:
                    st.dataframe(pd.DataFrame(parents), use_container_width=True, hide_index=True)
                else:
                    st.caption("Aucun parent lié.")
                with st.form("add_parent"):
                    c1, c2 = st.columns(2)
                    pf = c1.text_input("Prénom parent")
                    pl = c2.text_input("Nom parent")
                    c3, c4 = st.columns(2)
                    pp = c3.text_input("Téléphone parent")
                    pe = c4.text_input("Email parent")
                    if st.form_submit_button("Ajouter le parent"):
                        pid = execute("INSERT INTO parents(first_name,last_name,phone,email) VALUES(?,?,?,?)",
                                      (pf, pl, pp, pe))
                        execute("INSERT INTO member_parents(member_id,parent_id) VALUES(?,?)",
                                (m["id"], pid))
                        st.success("Parent ajouté."); st.rerun()

    # --- ARCHIVÉS ---
    with t5:
        arch = fetch_all("SELECT * FROM members WHERE status='Archivé' ORDER BY last_name")
        if not arch:
            st.info("Aucun membre archivé.")
        else:
            df = pd.DataFrame(arch)[["id", "first_name", "last_name", "grade", "join_date"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
            opts = {f"{m['id']} — {full_name(m)}": m for m in arch}
            sel = st.selectbox("Restaurer", list(opts.keys()))
            if st.button("♻️ Restaurer"):
                execute("UPDATE members SET status='Actif' WHERE id=?", (opts[sel]["id"],))
                st.success("Restauré."); st.rerun()


def page_courses():
    st.title("📅 Cours et planning")
    t1, t2, t3 = st.tabs(["📅 Planning", "📋 Liste", "👥 Inscriptions"])

    with t1:
        courses = fetch_all("SELECT * FROM courses WHERE active=1")
        if not courses:
            st.info("Aucun cours.")
        else:
            for day_idx, day in enumerate(DAYS):
                day_courses = [c for c in courses if c.get("day_of_week") == day_idx]
                if not day_courses:
                    continue
                st.subheader(day)
                for c in sorted(day_courses, key=lambda x: x.get("start_time") or ""):
                    with st.expander(f"🕐 {c['start_time']}–{c['end_time']} — {c['name']}"):
                        st.write(f"*Salle :* {c.get('room') or '—'}")
                        st.write(f"*Coach :* {c.get('teacher') or '—'}")
                        enrolled = fetch_one("SELECT COUNT(*) n FROM enrollments WHERE course_id=?", (c["id"],))["n"]
                        st.write(f"*Inscrits :* {enrolled}/{c.get('capacity', '—')}")

    with t2:
        rows = fetch_all("SELECT * FROM courses ORDER BY day_of_week, start_time")
        if rows:
            df = pd.DataFrame(rows)
            df["Jour"] = df["day_of_week"].apply(lambda x: DAYS[x] if isinstance(x, int) and 0 <= x < 7 else "—")
            v = df[["id", "name", "Jour", "start_time", "end_time", "room", "teacher", "category", "capacity", "active"]]
            v.columns = ["ID", "Nom", "Jour", "Début", "Fin", "Salle", "Prof", "Catégorie", "Capacité", "Actif"]
            st.dataframe(v, use_container_width=True, hide_index=True)
            opts = {f"{c['id']} — {c['name']}": c["id"] for c in rows}
            sel = st.selectbox("Supprimer un cours", ["—"] + list(opts.keys()))
            if sel != "—" and st.button("🗑️ Supprimer"):
                cid = opts[sel]
                for q in ("DELETE FROM courses WHERE id=?", "DELETE FROM enrollments WHERE course_id=?",
                          "DELETE FROM attendance WHERE course_id=?"):
                    execute(q, (cid,))
                st.rerun()

        st.divider()
        st.subheader("➕ Créer un cours")
        with st.form("add_c", clear_on_submit=True):
            nm = st.text_input("Nom *")
            c1, c2, c3 = st.columns(3)
            dy = c1.selectbox("Jour", list(enumerate(DAYS)), format_func=lambda x: x[1])
            stt = c2.text_input("Début", "18:00")
            en = c3.text_input("Fin", "19:30")
            c4, c5 = st.columns(2)
            rm = c4.text_input("Salle")
            tc = c5.text_input("Prof")
            c6, c7, c8 = st.columns(3)
            ct = c6.selectbox("Catégorie", CATEGORIES)
            disc = c7.selectbox("Discipline", ["Kata", "Kumite", "Kata & Kumite"])
            cp = c8.number_input("Capacité", 1, 100, 20)
            if st.form_submit_button("Créer", use_container_width=True):
                if not nm:
                    st.error("Nom obligatoire.")
                else:
                    execute("""INSERT INTO courses(name,day_of_week,start_time,end_time,
                               room,teacher,category,discipline,capacity,active)
                               VALUES(?,?,?,?,?,?,?,?,?,1)""",
                            (nm, dy[0], stt, en, rm, tc, ct, disc, cp))
                    st.success("Cours créé."); st.rerun()

    with t3:
        cs = fetch_all("SELECT * FROM courses WHERE active=1")
        ms = fetch_all("SELECT * FROM members WHERE status='Actif' ORDER BY last_name")
        if not cs or not ms:
            st.info("Il faut des cours et des membres actifs.")
        else:
            copt = {f"{c['id']} — {c['name']}": c["id"] for c in cs}
            mopt = {f"{m['id']} — {full_name(m)}": m["id"] for m in ms}
            with st.form("enr"):
                csel = st.selectbox("Cours", list(copt.keys()))
                msel = st.selectbox("Membre", list(mopt.keys()))
                if st.form_submit_button("Inscrire", use_container_width=True):
                    try:
                        execute("INSERT INTO enrollments(member_id,course_id,date_enrolled) VALUES(?,?,?)",
                                (mopt[msel], copt[csel], date.today().isoformat()))
                        st.success("Inscrit.")
                    except Exception:
                        st.warning("Déjà inscrit.")
            st.divider()
            enr = fetch_all("""SELECT e.id, c.name AS cours, m.first_name, m.last_name, e.date_enrolled
                               FROM enrollments e
                               JOIN courses c ON c.id=e.course_id
                               JOIN members m ON m.id=e.member_id
                               ORDER BY c.name, m.last_name""")
            if enr:
                df = pd.DataFrame(enr)
                df["Nom"] = df["first_name"] + " " + df["last_name"]
                st.dataframe(df[["id", "cours", "Nom", "date_enrolled"]],
                             use_container_width=True, hide_index=True)


def page_attendance():
    st.title("✅ Présences")
    t1, t2, t3 = st.tabs(["📝 Pointage", "📷 Scan QR", "📊 Statistiques"])

    with t1:
        cs = fetch_all("SELECT * FROM courses WHERE active=1")
        if not cs:
            st.info("Aucun cours.")
        else:
            copt = {f"{c['id']} — {c['name']}": c for c in cs}
            csel = st.selectbox("Cours", list(copt.keys()))
            course = copt[csel]
            d = st.date_input("Date", value=date.today())
            ms = fetch_all("""SELECT m.* FROM members m
                              JOIN enrollments e ON e.member_id=m.id
                              WHERE e.course_id=? AND m.status='Actif'
                              ORDER BY m.last_name""", (course["id"],))
            if not ms:
                st.info("Aucun membre inscrit.")
            else:
                ex = {a["member_id"]: a["status"] for a in fetch_all(
                    "SELECT member_id, status FROM attendance WHERE course_id=? AND attendance_date=?",
                    (course["id"], d.isoformat()))}
                with st.form("att"):
                    statuses = {}
                    for m in ms:
                        curr = ex.get(m["id"], "present")
                        statuses[m["id"]] = st.selectbox(
                            full_name(m),
                            list(ATTENDANCE_STATUS.keys()),
                            index=list(ATTENDANCE_STATUS.keys()).index(curr),
                            format_func=lambda x: ATTENDANCE_STATUS[x],
                            key=f"att_{m['id']}"
                        )
                    if st.form_submit_button("💾 Enregistrer", use_container_width=True):
                        for mid, stt in statuses.items():
                            execute("""INSERT INTO attendance(member_id,course_id,attendance_date,status)
                                       VALUES(?,?,?,?)
                                       ON CONFLICT(member_id,course_id,attendance_date)
                                       DO UPDATE SET status=excluded.status""",
                                    (mid, course["id"], d.isoformat(), stt))
                        export_attendance_csv()
                        st.success("Présences enregistrées.")

                st.divider()
                st.subheader("🚨 Absences répétées")
                for m in ms:
                    recent = fetch_all("""SELECT status FROM attendance
                                          WHERE member_id=? AND course_id=?
                                          ORDER BY attendance_date DESC LIMIT 4""",
                                        (m["id"], course["id"]))
                    if len(recent) >= 4 and all(r["status"] == "absent" for r in recent):
                        st.error(f"⚠️ {full_name(m)} : 4 absences consécutives !")

    with t2:
        if not HAS_CV:
            st.warning("OpenCV non installé — scan QR indisponible.")
        else:
            cs = fetch_all("SELECT * FROM courses WHERE active=1")
            if not cs:
                st.info("Aucun cours.")
            else:
                copt = {f"{c['id']} — {c['name']}": c["id"] for c in cs}
                csel = st.selectbox("Cours", list(copt.keys()), key="qrc")
                up = st.file_uploader("Photo du QR", type=["png", "jpg", "jpeg"])
                if up:
                    data = decode_qr_from_bytes(up.read())
                    if not data:
                        st.error("QR non lisible.")
                    else:
                        info = verify_qr_payload(data)
                        if not info:
                            st.error("QR invalide ou falsifié.")
                        else:
                            m = fetch_one("SELECT * FROM members WHERE id=?", (info["member_id"],))
                            if not m:
                                st.error("Membre introuvable.")
                            else:
                                st.write(f"*Membre* : {full_name(m)}")
                                execute("""INSERT INTO attendance(member_id,course_id,attendance_date,status)
                                           VALUES(?,?,?,?)
                                           ON CONFLICT(member_id,course_id,attendance_date)
                                           DO UPDATE SET status='present'""",
                                        (m["id"], copt[csel], date.today().isoformat(), "present"))
                                export_attendance_csv()
                                st.success("Présence enregistrée.")

    with t3:
        att = fetch_all("""SELECT a.*, m.first_name, m.last_name FROM attendance a
                           JOIN members m ON m.id=a.member_id""")
        if not att:
            st.info("Aucune présence.")
        else:
            df = pd.DataFrame(att)
            df["Nom"] = df["first_name"] + " " + df["last_name"]
            stats = df.groupby("Nom").agg(
                Total=("id", "count"),
                Présents=("status", lambda s: (s == "present").sum()),
                Absents=("status", lambda s: (s == "absent").sum()),
                Justifiés=("status", lambda s: (s == "justified").sum()),
                Retards=("status", lambda s: (s == "late").sum()),
            ).reset_index()
            stats["Taux"] = (stats["Présents"] / stats["Total"] * 100).round(1).astype(str) + " %"
            st.dataframe(stats, use_container_width=True, hide_index=True)


def page_payments():
    st.title("💰 Paiements")
    t1, t2, t3, t4 = st.tabs(["📋 Liste", "➕ Enregistrer", "⚠️ Impayés", "📊 Synthèse"])

    with t1:
        rows = fetch_all("""SELECT p.*, m.first_name, m.last_name FROM payments p
                            JOIN members m ON m.id=p.member_id
                            ORDER BY p.payment_date DESC""")
        if not rows:
            st.info("Aucun paiement.")
        else:
            df = pd.DataFrame(rows)
            df["Nom"] = df["first_name"] + " " + df["last_name"]
            df["Reste"] = df["amount"] - df["amount_paid"]
            v = df[["id", "Nom", "amount", "amount_paid", "Reste", "payment_date",
                    "due_date", "type", "method", "status"]]
            v.columns = ["ID", "Membre", "Montant", "Payé", "Reste", "Date",
                         "Échéance", "Type", "Méthode", "Statut"]
            st.dataframe(v, use_container_width=True, hide_index=True)
            st.download_button("📥 CSV", v.to_csv(index=False).encode("utf-8-sig"),
                                "paiements.csv", "text/csv")
            st.divider()
            st.subheader("📄 Reçu PDF")
            psel = st.selectbox("Paiement",
                                 [f"{r['id']} — {r['first_name']} {r['last_name']} — {r['amount']} DA"
                                  for r in rows])
            pid = int(psel.split(" — ")[0])
            p = fetch_one("SELECT * FROM payments WHERE id=?", (pid,))
            m = fetch_one("SELECT * FROM members WHERE id=?", (p["member_id"],))
            if st.button("Générer le reçu"):
                path = make_receipt_pdf(p, m)
                with open(path, "rb") as f:
                    st.download_button("⬇️ Télécharger", f.read(),
                                        os.path.basename(path), "application/pdf")

    with t2:
        ms = fetch_all("SELECT * FROM members WHERE status='Actif' ORDER BY last_name")
        if not ms:
            st.info("Aucun membre actif.")
        else:
            mopt = {f"{m['id']} — {full_name(m)}": m["id"] for m in ms}
            with st.form("add_p", clear_on_submit=True):
                msel = st.selectbox("Membre", list(mopt.keys()))
                c1, c2 = st.columns(2)
                am = c1.number_input("Montant (DA)", 0.0, 1_000_000.0, 5000.0, 500.0)
                paid = c2.number_input("Déjà payé (DA)", 0.0, 1_000_000.0, value=am, step=500.0)
                c3, c4 = st.columns(2)
                ty = c3.selectbox("Type", PAYMENT_TYPES)
                mt = c4.selectbox("Méthode", PAYMENT_METHODS)
                c5, c6 = st.columns(2)
                pd_ = c5.date_input("Date paiement", value=date.today())
                dd = c6.date_input("Échéance", value=date.today() + timedelta(days=30))
                se = st.text_input("Saison", value=f"{date.today().year}-{date.today().year+1}")
                nt = st.text_area("Notes")
                if st.form_submit_button("Enregistrer", use_container_width=True):
                    status = compute_payment_status(am, paid, dd.isoformat())
                    execute("""INSERT INTO payments(member_id,amount,amount_paid,payment_date,
                               due_date,method,type,season,status,notes)
                               VALUES(?,?,?,?,?,?,?,?,?,?)""",
                            (mopt[msel], am, paid, pd_.isoformat(), dd.isoformat(),
                             mt, ty, se, status, nt))
                    export_payments_csv()
                    st.success(f"Enregistré — {PAYMENT_STATUS[status]}.")

    with t3:
        due = fetch_all("""SELECT p.*, m.first_name, m.last_name, m.phone
                           FROM payments p JOIN members m ON m.id=p.member_id
                           WHERE p.status!='paid' AND (p.due_date IS NULL OR p.due_date<=?)""",
                        (date.today().isoformat(),))
        if not due:
            st.success("✅ Aucun impayé.")
        else:
            df = pd.DataFrame(due)
            df["Membre"] = df["first_name"] + " " + df["last_name"]
            df["Reste"] = df["amount"] - df["amount_paid"]
            v = df[["Membre", "phone", "type", "Reste", "due_date", "status"]]
            v.columns = ["Membre", "Téléphone", "Type", "Reste dû", "Échéance", "Statut"]
            st.dataframe(v, use_container_width=True, hide_index=True)
            st.metric("Total impayés", f"{df['Reste'].sum():,.0f} DA")

    with t4:
        rows = fetch_all("SELECT type, status, SUM(amount_paid) AS total, COUNT(*) AS n FROM payments GROUP BY type, status")
        if not rows:
            st.info("Aucune donnée.")
        else:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(df, x="type", y="total", color="status",
                                    barmode="group"), use_container_width=True)


def page_grades():
    st.title("🥋 Grades et examens")
    t1, t2, t3 = st.tabs(["📜 Historique", "🎓 Examens", "➕ Passage"])

    with t1:
        rows = fetch_all("""SELECT g.*, m.first_name, m.last_name FROM grades_history g
                            JOIN members m ON m.id=g.member_id ORDER BY g.grade_date DESC""")
        if rows:
            df = pd.DataFrame(rows)
            df["Nom"] = df["first_name"] + " " + df["last_name"]
            st.dataframe(df[["grade_date", "Nom", "grade", "examiner", "result"]],
                         use_container_width=True, hide_index=True)
        else:
            st.info("Aucun passage.")

    with t2:
        st.subheader("➕ Créer un examen")
        with st.form("add_exam", clear_on_submit=True):
            nm = st.text_input("Nom *")
            c1, c2 = st.columns(2)
            d = c1.date_input("Date", value=date.today())
            lo = c2.text_input("Lieu")
            c3, c4 = st.columns(2)
            ex = c3.text_input("Examinateur / Jury")
            gt = c4.selectbox("Grade visé", GRADES)
            nt = st.text_area("Notes")
            if st.form_submit_button("Créer", use_container_width=True):
                if not nm:
                    st.error("Nom obligatoire.")
                else:
                    execute("""INSERT INTO exams(name,exam_date,examiner,grade_targeted,location,notes)
                               VALUES(?,?,?,?,?,?)""", (nm, d.isoformat(), ex, gt, lo, nt))
                    st.success("Examen créé.")

        st.divider()
        st.subheader("📋 Examens et candidats")
        exams = fetch_all("SELECT * FROM exams ORDER BY exam_date DESC")
        for e in exams:
            with st.expander(f"🎓 {e['name']} — {e['exam_date']} ({e.get('location') or '—'})"):
                cands = fetch_all("""SELECT ec.*, m.first_name, m.last_name
                                     FROM exam_candidates ec
                                     JOIN members m ON m.id=ec.member_id
                                     WHERE ec.exam_id=?""", (e["id"],))
                for c in cands:
                    with st.form(f"cand_{c['id']}"):
                        st.write(f"*{c['first_name']} {c['last_name']}* — visé : {c['grade_targeted']}")
                        c1, c2 = st.columns(2)
                        score = c1.number_input("Note /20", 0.0, 20.0, value=float(c.get("score") or 0))
                        res = c2.selectbox("Résultat", ["pending", "admis", "ajourne"],
                                            index=["pending", "admis", "ajourne"].index(c.get("result") or "pending"))
                        obs = st.text_area("Observations", value=c.get("observations") or "")
                        if st.form_submit_button("💾 Enregistrer"):
                            execute("UPDATE exam_candidates SET score=?, result=?, observations=? WHERE id=?",
                                    (score, res, obs, c["id"]))
                            if res == "admis":
                                execute("UPDATE members SET grade=?, grade_date=? WHERE id=?",
                                        (c["grade_targeted"], date.today().isoformat(), c["member_id"]))
                                execute("""INSERT INTO grades_history(member_id,grade,grade_date,
                                           examiner,result,exam_id) VALUES(?,?,?,?,?,?)""",
                                        (c["member_id"], c["grade_targeted"], date.today().isoformat(),
                                         e.get("examiner"), "Réussi", e["id"]))
                            st.success("Enregistré."); st.rerun()

                with st.form(f"add_cand_{e['id']}"):
                    ms = fetch_all("SELECT * FROM members WHERE status='Actif' ORDER BY last_name")
                    mopt = {f"{m['id']} — {full_name(m)}": m for m in ms}
                    msel = st.selectbox("Ajouter un candidat", list(mopt.keys()))
                    m = mopt[msel]
                    gt = st.selectbox("Grade visé",
                                       GRADES,
                                       index=min(GRADES.index(m["grade"]) + 1, len(GRADES) - 1)
                                       if m["grade"] in GRADES else 0,
                                       key=f"gt_{e['id']}")
                    if st.form_submit_button("Ajouter", use_container_width=True):
                        try:
                            execute("""INSERT INTO exam_candidates(exam_id,member_id,grade_targeted)
                                       VALUES(?,?,?)""", (e["id"], m["id"], gt))
                            st.success("Candidat ajouté."); st.rerun()
                        except Exception:
                            st.warning("Déjà candidat.")

    with t3:
        ms = fetch_all("SELECT * FROM members WHERE status='Actif' ORDER BY last_name")
        if not ms:
            st.info("Aucun membre actif.")
        else:
            with st.form("record_grade", clear_on_submit=True):
                mopt = {f"{m['id']} — {full_name(m)}": m for m in ms}
                msel = st.selectbox("Membre", list(mopt.keys()))
                m = mopt[msel]
                gr = st.selectbox("Nouveau grade", GRADES,
                                   index=min(GRADES.index(m["grade"]) + 1, len(GRADES) - 1)
                                   if m["grade"] in GRADES else 0)
                c1, c2 = st.columns(2)
                d = c1.date_input("Date", value=date.today())
                ex = c2.text_input("Examinateur")
                rs = st.selectbox("Résultat", ["Réussi", "Échoué", "En attente"])
                nt = st.text_area("Notes")
                if st.form_submit_button("Enregistrer", use_container_width=True):
                    execute("""INSERT INTO grades_history(member_id,grade,grade_date,
                               examiner,result,notes) VALUES(?,?,?,?,?,?)""",
                            (m["id"], gr, d.isoformat(), ex, rs, nt))
                    if rs == "Réussi":
                        execute("UPDATE members SET grade=?, grade_date=? WHERE id=?",
                                (gr, d.isoformat(), m["id"]))
                        export_members_csv()
                    st.success("Enregistré.")


def page_competitions():
    st.title("🏆 Compétitions")
    t1, t2, t3 = st.tabs(["📋 Liste", "➕ Créer", "👥 Inscriptions"])

    with t1:
        comps = fetch_all("SELECT * FROM competitions ORDER BY competition_date DESC")
        for c in comps:
            with st.expander(f"🏆 {c['name']} — {c.get('competition_date')} ({c.get('location') or '—'})"):
                st.write(c.get("description") or "—")
                regs = fetch_all("""SELECT cr.*, m.first_name, m.last_name
                                    FROM competition_registrations cr
                                    JOIN members m ON m.id=cr.member_id
                                    WHERE cr.competition_id=?""", (c["id"],))
                if regs:
                    df = pd.DataFrame(regs)
                    df["Athlète"] = df["first_name"] + " " + df["last_name"]
                    st.dataframe(df[["Athlète", "category", "discipline",
                                     "result", "ranking", "medal"]],
                                 use_container_width=True, hide_index=True)

    with t2:
        with st.form("add_cp", clear_on_submit=True):
            nm = st.text_input("Nom *")
            c1, c2 = st.columns(2)
            d = c1.date_input("Date", value=date.today())
            lo = c2.text_input("Lieu")
            de = st.text_area("Description")
            if st.form_submit_button("Créer", use_container_width=True):
                if not nm:
                    st.error("Nom obligatoire.")
                else:
                    execute("INSERT INTO competitions(name,competition_date,location,description) VALUES(?,?,?,?)",
                            (nm, d.isoformat(), lo, de))
                    st.success("Créée.")

    with t3:
        cs = fetch_all("SELECT * FROM competitions")
        ms = fetch_all("SELECT * FROM members WHERE status='Actif'")
        if not cs or not ms:
            st.info("Il faut des compétitions et des membres.")
        else:
            copt = {f"{c['id']} — {c['name']}": c["id"] for c in cs}
            mopt = {f"{m['id']} — {full_name(m)}": m["id"] for m in ms}
            with st.form("reg"):
                csel = st.selectbox("Compétition", list(copt.keys()))
                msel = st.selectbox("Athlète", list(mopt.keys()))
                c1, c2 = st.columns(2)
                cat = c1.text_input("Catégorie")
                disc = c2.selectbox("Discipline", ["Kata", "Kumite", "Kata & Kumite"])
                if st.form_submit_button("Inscrire", use_container_width=True):
                    try:
                        execute("""INSERT INTO competition_registrations
                                   (competition_id,member_id,category,discipline)
                                   VALUES(?,?,?,?)""", (copt[csel], mopt[msel], cat, disc))
                        st.success("Inscrit.")
                    except Exception:
                        st.warning("Déjà inscrit.")

            st.divider()
            st.subheader("📝 Saisir les résultats")
            comps = fetch_all("SELECT * FROM competitions")
            for c in comps:
                regs = fetch_all("""SELECT cr.*, m.first_name, m.last_name
                                    FROM competition_registrations cr
                                    JOIN members m ON m.id=cr.member_id
                                    WHERE cr.competition_id=?""", (c["id"],))
                for r in regs:
                    with st.form(f"res_{r['id']}"):
                        st.write(f"*{r['first_name']} {r['last_name']}* — {c['name']}")
                        c1, c2, c3 = st.columns(3)
                        res = c1.text_input("Résultat", value=r.get("result") or "")
                        rk = c2.number_input("Classement", 0, 100, value=int(r.get("ranking") or 0))
                        md = c3.selectbox("Médaille", ["none", "or", "argent", "bronze"],
                                           index=["none", "or", "argent", "bronze"].index(r.get("medal") or "none"))
                        if st.form_submit_button("💾 Enregistrer"):
                            execute("""UPDATE competition_registrations
                                       SET result=?, ranking=?, medal=? WHERE id=?""",
                                    (res, rk, md, r["id"]))
                            st.success("Enregistré."); st.rerun()


def page_qr_cards():
    st.title("📱 QR codes et cartes")
    ms = fetch_all("SELECT * FROM members WHERE status='Actif' ORDER BY last_name")
    if not ms:
        st.info("Aucun membre actif.")
        return

    t1, t2, t3 = st.tabs(["🪪 Carte individuelle", "📚 Cartes en lot", "🔗 QR seuls"])

    with t1:
        opts = {f"{m['id']} — {full_name(m)}": m for m in ms}
        m = opts[st.selectbox("Membre", list(opts.keys()))]
        if st.button("🎨 Générer la carte PDF", type="primary"):
            path = generate_member_card_pdf(m)
            with open(path, "rb") as f:
                st.download_button("⬇️ Télécharger", f.read(),
                                    os.path.basename(path), "application/pdf")

    with t2:
        grades = sorted({m.get("grade") or "—" for m in ms})
        sel = st.multiselect("Filtrer par grade", grades, default=grades)
        filtered = [m for m in ms if (m.get("grade") or "—") in sel]
        st.caption(f"{len(filtered)} carte(s) — 8 par page A4.")
        if st.button("📄 Générer le PDF en lot", type="primary"):
            path = generate_batch_cards_pdf(filtered)
            with open(path, "rb") as f:
                st.download_button("⬇️ Télécharger", f.read(),
                                    os.path.basename(path), "application/pdf")

    with t3:
        cols = st.columns(4)
        for i, m in enumerate(ms):
            path, data = make_qr_code(m)
            with cols[i % 4]:
                st.image(path, caption=full_name(m), width=150)
                with open(path, "rb") as f:
                    st.download_button("⬇️", f.read(),
                                        os.path.basename(path), "image/png",
                                        key=f"dl_{m['id']}")


def page_admin():
    st.title("⚙️ Administration")
    t1, t2, t3, t4 = st.tabs(["👤 Utilisateurs", "💾 Sauvegarde", "📤 Exports", "🗄️ Maintenance"])

    with t1:
        us = fetch_all("SELECT id,username,role,member_id FROM users ORDER BY username")
        st.dataframe(pd.DataFrame(us), use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("➕ Ajouter")
        ms = fetch_all("SELECT * FROM members ORDER BY last_name")
        mopt = {"—": None}
        mopt.update({f"{m['id']} — {full_name(m)}": m["id"] for m in ms})
        with st.form("au", clear_on_submit=True):
            u = st.text_input("Identifiant *")
            p = st.text_input("Mot de passe *", type="password")
            r = st.selectbox("Rôle", ROLES)
            msel = st.selectbox("Lier à un membre", list(mopt.keys()))
            if st.form_submit_button("Créer", use_container_width=True):
                if not u or not p:
                    st.error("Champs obligatoires.")
                else:
                    try:
                        execute("INSERT INTO users(username,password,role,member_id,created_at) VALUES(?,?,?,?,?)",
                                (u, hp(p), r, mopt[msel], datetime.now().isoformat()))
                        st.success("Créé."); st.rerun()
                    except Exception:
                        st.error("Identifiant existant.")
        st.divider()
        st.subheader("🗑️ Supprimer")
        dopts = {f"{x['id']} — {x['username']} ({x['role']})": x["id"]
                 for x in us if x["username"] != "admin"}
        if dopts:
            sel = st.selectbox("Utilisateur", list(dopts.keys()))
            if st.button("Supprimer"):
                execute("DELETE FROM users WHERE id=?", (dopts[sel],)); st.rerun()

    with t2:
        st.subheader("💾 Sauvegarde manuelle")
        if st.button("Sauvegarder maintenant"):
            path = auto_backup(keep_days=60)
            if path:
                st.success(f"Créée : {os.path.basename(path)}")
                with open(path, "rb") as f:
                    st.download_button("⬇️ Télécharger", f.read(),
                                        os.path.basename(path), "application/zip")
        st.divider()
        st.subheader("📂 Sauvegardes existantes")
        files = sorted(Path(BACKUP_DIR).glob("backup_*.zip"), reverse=True)
        if files:
            for f in files[:30]:
                c1, c2 = st.columns([3, 1])
                size_kb = f.stat().st_size / 1024
                c1.write(f"*{f.name}* — {size_kb:.1f} Ko")
                with open(f, "rb") as fh:
                    c2.download_button("⬇️", fh.read(), f.name, key=f"b_{f.name}")
        else:
            st.caption("Aucune sauvegarde.")

        st.divider()
        st.subheader("♻️ Restauration")
        st.info("Pour restaurer : décompressez un ZIP, copiez dojo.db dans "
                f"{DATA_DIR}, puis relancez l'application.")

    with t3:
        st.subheader("📤 Exports CSV")
        if st.button("🔄 Régénérer tous les CSV"):
            paths = export_all_csv()
            st.success(f"{len(paths)} fichier(s) régénéré(s).")
        for label, fn in (("Membres", "membres.csv"),
                           ("Paiements", "paiements.csv"),
                           ("Présences", "presences.csv")):
            p = os.path.join(EXPORT_DIR, fn)
            if os.path.exists(p):
                with open(p, "rb") as f:
                    st.download_button(f"⬇️ {label} ({fn})", f.read(), fn, "text/csv")

    with t4:
        st.subheader("🗄️ Zone technique")
        st.write(f"*Base de données* : {DB_PATH}")
        st.write(f"*Dossier exports* : {EXPORT_DIR}")
        st.write(f"*Dossier QR* : {QR_DIR}")
        st.write(f"*Dossier backups* : {BACKUP_DIR}")
        st.write(f"*Machine ID* : {machine_id()}")
        st.divider()
        if os.path.exists(DB_PATH):
            with open(DB_PATH, "rb") as f:
                st.download_button("⬇️ Télécharger dojo.db", f.read(),
                                    "dojo.db", "application/octet-stream")


def page_my_space():
    st.title("🏠 Mon espace")
    mid = st.session_state.user.get("member_id")
    if not mid:
        st.warning("Aucun profil membre lié à ce compte.")
        return
    m = fetch_one("SELECT * FROM members WHERE id=?", (mid,))
    if not m:
        st.error("Profil introuvable.")
        return
    st.subheader(full_name(m))
    c1, c2, c3 = st.columns(3)
    c1.metric("Âge", calc_age(m["birth_date"]) or "-")
    c2.metric("Grade", m["grade"] or "-")
    c3.metric("Statut", m["status"])
    qr_path, _ = make_qr_code(m)
    st.image(qr_path, width=180, caption="Mon QR")

    st.divider()
    sub1, sub2, sub3 = st.tabs(["💰 Paiements", "🥋 Grades", "✅ Présences"])
    with sub1:
        ps = fetch_all("SELECT * FROM payments WHERE member_id=? ORDER BY payment_date DESC", (mid,))
        if ps:
            st.dataframe(pd.DataFrame(ps)[["payment_date", "amount", "amount_paid", "type", "status"]],
                         use_container_width=True, hide_index=True)
        else:
            st.caption("Aucun.")
    with sub2:
        gh = fetch_all("SELECT * FROM grades_history WHERE member_id=? ORDER BY grade_date DESC", (mid,))
        if gh:
            st.dataframe(pd.DataFrame(gh)[["grade_date", "grade", "result"]],
                         use_container_width=True, hide_index=True)
        else:
            st.caption("Aucun.")
    with sub3:
        at = fetch_all("""SELECT a.attendance_date, c.name AS cours, a.status
                          FROM attendance a
                          LEFT JOIN courses c ON c.id=a.course_id
                          WHERE a.member_id=?
                          ORDER BY a.attendance_date DESC LIMIT 30""", (mid,))
        if at:
            st.dataframe(pd.DataFrame(at), use_container_width=True, hide_index=True)
        else:
            st.caption("Aucune.")


def page_install():
    st.title("🛠️ Installation & Déploiement")
    st.markdown(f"*Dossier de données* : {DATA_DIR}")
    st.info(f*Machine ID** :{machine_id()}`")

    env = "🟢 Termux (Android)" if is_termux() else (
          "🟢 Linux/macOS" if platform.system() in ("Linux", "Darwin") else "🟢 Windows")
    st.write(f"*Environnement* : {env}")

    tab_pc, tab_cloud, tab_termux, tab_bash = st.tabs(
        ["💻 PC", "☁️ Cloud", "📱 Termux", "📜 Script bash"])

    with tab_pc:
        st.code("""mkdir dojo && cd dojo
# Y placer main.py et requirements.txt
python -m venv venv
# Linux/Mac :
source venv/bin/activate
# Windows :
venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run main.py
""", language="bash")

    with tab_cloud:
        st.markdown("""
        1. Repo GitHub public avec main.py et requirements.txt.
        2. https://share.streamlit.io → New app → choisir le repo.
        3. Main file : main.py. Deploy.

        ⚠️ Sur Streamlit Cloud, la base SQLite est *éphémère*.
        Pour un usage réel, hébergez sur un VPS ou en local.
        """)

    with tab_termux:
        st.code("""mkdir -p ~/dojo && cd ~/dojo
# Y placer main.py + requirements.txt
python main.py --install-termux
python main.py --run
""", language="bash")
        if is_termux():
            if st.button("🚀 Lancer l'installation automatique", type="primary"):
                with st.spinner("Installation..."):
                    ok = run_termux_setup()
                st.success("✅ Terminé.") if ok else st.error("❌ Échec.")

    with tab_bash:
        st.code(TERMUX_BASH_SETUP, language="bash")
        st.download_button("⬇️ Télécharger install_dojo.sh",
                            data=TERMUX_BASH_SETUP.encode("utf-8"),
                            file_name="install_dojo.sh",
                            mime="text/x-shellscript")


# ============================================================
# ROUTAGE
# ============================================================
if st.session_state.user is None:
    login_page()
    st.stop()

user = st.session_state.user

# Vérification licence après login (mais avant accès aux données)
if not license_gate():
    st.stop()

st.sidebar.markdown(f"### 👤 {user['username']}")
st.sidebar.caption(f"Rôle : {user['role']}")
st.sidebar.caption(f"📂 {DATA_DIR}")

menu = []
if user["role"] in ("admin", "professeur", "secretaire"):
    menu = ["📊 Tableau de bord", "👥 Membres", "📅 Cours", "✅ Présences",
            "💰 Paiements", "🥋 Grades", "🏆 Compétitions", "📱 QR & Cartes"]
    if user["role"] == "admin":
        menu += ["⚙️ Administration", "🛠️ Installation & Déploiement"]
elif user["role"] == "membre":
    menu = ["🏠 Mon espace"]

page = st.sidebar.radio("Navigation", menu)
if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
    st.session_state.user = None
    st.rerun()

if page == "📊 Tableau de bord": page_dashboard()
elif page == "👥 Membres": page_members()
elif page == "📅 Cours": page_courses()
elif page == "✅ Présences": page_attendance()
elif page == "💰 Paiements": page_payments()
elif page == "🥋 Grades": page_grades()
elif page == "🏆 Compétitions": page_competitions()
elif page == "📱 QR & Cartes": page_qr_cards()
elif page == "⚙️ Administration": page_admin()
elif page == "🛠️ Installation & Déploiement": page_install()
elif page == "🏠 Mon espace": page_my_space()
