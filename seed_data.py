"""seed_data.py — Jeu de données de démonstration complet."""

import os, sys, sqlite3, bcrypt, random
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("❌ Pillow requis"); sys.exit(1)

DATA_DIR  = os.environ.get("DOJO_DATA_DIR",
                            os.path.join(os.path.expanduser("~"), "DojoKaraté"))
DB_PATH   = os.path.join(DATA_DIR, "dojo.db")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
for d in (DATA_DIR, PHOTO_DIR):
    os.makedirs(d, exist_ok=True)

random.seed(42)

MEMBERS = [
    ("Yacine","Benali","2010-03-15","M","0550123456","yacine.b@mail.dz","12 Rue des Oliviers, Tlemcen","O+","5e année","Orange","Kata","LIC-2024-001","2021-09-05","Très assidu"),
    ("Amine","Cherif","2008-07-22","M","0550234567","amine.c@mail.dz","5 Av. Pasteur, Tlemcen","A+","2e AS","Verte","Kumite","LIC-2024-002","2020-09-12",""),
    ("Sara","Mansouri","2012-11-05","F","0550345678","sara.m@mail.dz","8 Rue Ibn Khaldoun","B+","4e année","Jaune","Kata & Kumite","LIC-2024-003","2022-09-01","Talent prometteur"),
    ("Lina","Bouzid","2015-01-18","F","0550456789","lina.b@mail.dz","3 Cité 500 Logts","AB+","CE1","Blanche","Kata","LIC-2024-004","2023-09-10","Débutante"),
    ("Mehdi","Khelifi","2006-09-30","M","0550567890","mehdi.k@mail.dz","22 Rue de la Liberté","O-","Terminale","Bleue","Kumite","LIC-2024-005","2018-09-15","Capitaine cadets"),
    ("Nour","Hamdi","2011-05-12","F","0550678901","nour.h@mail.dz","7 Rue El Andalous","A-","5e année","Orange","Kata","LIC-2024-006","2021-09-01",""),
    ("Rayan","Saidi","2014-02-28","M","0550789012","rayan.s@mail.dz","15 Rue des Frères","B-","CM2","Jaune","Kata & Kumite","LIC-2024-007","2022-09-05",""),
    ("Imane","Belkacem","2009-08-04","F","0550890123","imane.b@mail.dz","4 Rue Ibn Sina","O+","1re AS","Bleue","Kata","LIC-2024-008","2019-09-10","Championne régionale"),
    ("Anis","Tounsi","2013-12-19","M","0550901234","anis.t@mail.dz","9 Cité Djabli","A+","CM1","Orange","Kumite","LIC-2024-009","2022-09-01",""),
    ("Yasmine","Zerrouki","2007-06-25","F","0551012345","yasmine.z@mail.dz","18 Rue Souika","AB-","1re AS","Marron 3e kyu","Kata","LIC-2024-010","2018-09-01",""),
    ("Bilal","Rahmani","2016-04-10","M","0551123456","bilal.r@mail.dz","11 Rue Ahmed Zabana","B+","CP","Blanche","Kata","LIC-2024-011","2023-09-01",""),
    ("Salma","Boudiaf","2010-10-07","F","0551234567","salma.b@mail.dz","6 Rue Larbi Ben M'hidi","O+","5e année","Verte","Kumite","LIC-2024-012","2020-09-10",""),
    ("Karim","Meziane","2005-03-22","M","0551345678","karim.m@mail.dz","2 Rue de l'Indépendance","A+","L2","Marron 1er kyu","Kata & Kumite","LIC-2024-013","2015-09-01","Assistant prof"),
    ("Rania","Haddad","2012-07-14","F","0551456789","rania.h@mail.dz","14 Rue Emir AEK","B-","4e année","Orange","Kata","LIC-2024-014","2021-09-05",""),
    ("Adam","Lounis","2017-09-03","M","0551567890","adam.l@mail.dz","3 Rue des Roses","O-","GS","Blanche","Kata","LIC-2024-015","2024-09-01","Nouveau"),
    ("Meriem","Kaci","2008-11-27","F","0551678901","meriem.k@mail.dz","20 Rue Pasteur","AB+","2e AS","Verte","Kata & Kumite","LIC-2024-016","2019-09-10",""),
    ("Sofiane","Boukhalfa","2004-05-16","M","0551789012","sofiane.b@mail.dz","1 Cité Beni Snous","A+","L3","Noire 1er Dan","Kumite","LIC-2024-017","2013-09-01","Instructeur adjoint"),
    ("Hiba","Merabet","2011-08-21","F","0551890123","hiba.m@mail.dz","5 Rue des Jasmins","B+","5e année","Orange","Kata","LIC-2024-018","2021-09-01",""),
    ("Younes","Brahimi","2009-02-08","M","0551901234","younes.b@mail.dz","17 Rue Ibn Badis","O+","1re AS","Bleue","Kumite","LIC-2024-019","2019-09-10",""),
    ("Assia","Bourenane","2013-06-30","F","0552012345","assia.b@mail.dz","12 Rue El Emir","A-","CM1","Jaune","Kata","LIC-2024-020","2022-09-01",""),
    ("Mourad","Ouali","1985-04-12","M","0552123456","mourad.o@mail.dz","Prof — 4 Rue des Arts","O+","Ingénieur","Noire 4e Dan","Kata & Kumite","LIC-2024-021","2010-09-01","Professeur principal"),
]

COURSES = [
    ("Baby Karaté (4-6 ans)",2,"17:00","18:00","Salle A","Mourad Ouali","Poussins","Kata",15),
    ("Karaté Enfants",0,"18:00","19:00","Salle A","Mourad Ouali","Benjamins","Kata & Kumite",20),
    ("Karaté Ados",1,"19:00","20:30","Salle B","Karim Meziane","Cadets","Kata & Kumite",20),
    ("Karaté Juniors",3,"19:00","20:30","Salle B","Mourad Ouali","Juniors","Kata & Kumite",20),
    ("Karaté Adultes",4,"20:00","21:30","Salle A","Mourad Ouali","Seniors","Kata & Kumite",25),
    ("Kata Compétition",5,"10:00","11:30","Salle B","Imane Belkacem","Espoirs","Kata",15),
    ("Kumite Compétition",5,"11:30","13:00","Salle B","Sofiane Boukhalfa","Seniors","Kumite",15),
]

USERS = [
    ("admin","admin123","admin",None),
    ("prof","prof123","professeur",None),
    ("secretaire","secretaire123","secretaire",None),
    ("yacine","membre123","membre",1),
    ("imane","membre123","membre",8),
]

def hp(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def make_avatar(first, last, member_id):
    palette = ["#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6",
               "#1abc9c","#e67e22","#34495e","#c0392b","#16a085",
               "#8e44ad","#27ae60","#d35400","#2980b9","#c0392b"]
    color = palette[member_id % len(palette)]
    img = Image.new("RGB", (400, 400), color)
    draw = ImageDraw.Draw(img)
    initials = (first[0] + last[0]).upper()
    font = None
    for fp in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/system/fonts/Roboto-Bold.ttf",
               "C:/Windows/Fonts/arialbd.ttf",
               "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(fp):
            try: font = ImageFont.truetype(fp, 170); break
            except Exception: pass
    if font is None: font = ImageFont.load_default()
    try:
        bbox = draw.textbbox((0, 0), initials, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((400-w)/2 - bbox[0], (400-h)/2 - bbox[1]),
                  initials, fill="white", font=font)
    except Exception:
        draw.text((150, 150), initials, fill="white")
    path = os.path.join(PHOTO_DIR, f"member_{member_id}.jpg")
    img.save(path, "JPEG", quality=88)
    return path

def calc_cat(age):
    if age is None: return "Seniors"
    if age <= 5:  return "Poussins"
    if age <= 7:  return "Pupilles"
    if age <= 9:  return "Benjamins"
    if age <= 11: return "Minimes"
    if age <= 14: return "Cadets"
    if age <= 17: return "Juniors"
    if age <= 20: return "Espoirs"
    return "Seniors"

def age_of(bd_iso):
    d = datetime.strptime(bd_iso, "%Y-%m-%d").date()
    t = date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def main(force=False):
    reset = "--reset" in sys.argv or force
    if os.path.exists(DB_PATH) and not reset:
        print(f"⚠️  Base existante : {DB_PATH}")
        print("   Relancez avec --reset pour regénérer.")
        return
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        for p in Path(PHOTO_DIR).glob("member_*.jpg"): p.unlink()
        print("🗑️  Base supprimée.")

    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL,
        member_id INTEGER, created_at TEXT);
    CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL, last_name TEXT NOT NULL, birth_date TEXT,
        gender TEXT, phone TEXT, email TEXT, address TEXT, blood_group TEXT,
        academic_level TEXT, category TEXT, group_name TEXT, license_number TEXT,
        license_expiry TEXT, medical_cert_expiry TEXT, insurance_status TEXT,
        insurance_expiry TEXT, parental_authorization INTEGER DEFAULT 0,
        documents_status TEXT DEFAULT 'Incomplet', grade TEXT, grade_date TEXT,
        discipline TEXT, join_date TEXT, status TEXT DEFAULT 'Actif', notes TEXT,
        photo TEXT, parental_signature TEXT, signature_date TEXT);
    CREATE TABLE IF NOT EXISTS parents(id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT, phone TEXT, email TEXT, address TEXT);
    CREATE TABLE IF NOT EXISTS member_parents(member_id INTEGER, parent_id INTEGER,
        relationship TEXT DEFAULT 'parent', PRIMARY KEY(member_id, parent_id));
    CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, day_of_week INTEGER, start_time TEXT, end_time TEXT,
        room TEXT, teacher TEXT, category TEXT, discipline TEXT,
        capacity INTEGER DEFAULT 20, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER, session_date TEXT, start_time TEXT, end_time TEXT,
        room TEXT, status TEXT DEFAULT 'planned', is_exception INTEGER DEFAULT 0,
        notes TEXT);
    CREATE TABLE IF NOT EXISTS enrollments(id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, course_id INTEGER, date_enrolled TEXT,
        UNIQUE(member_id, course_id));
    CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, course_id INTEGER, attendance_date TEXT,
        status TEXT DEFAULT 'present', note TEXT,
        UNIQUE(member_id, course_id, attendance_date));
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, amount REAL DEFAULT 0, amount_paid REAL DEFAULT 0,
        payment_date TEXT, due_date TEXT, method TEXT, type TEXT, season TEXT,
        status TEXT DEFAULT 'pending', notes TEXT);
    CREATE TABLE IF NOT EXISTS exams(id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, exam_date TEXT, examiner TEXT, grade_targeted TEXT,
        location TEXT, notes TEXT);
    CREATE TABLE IF NOT EXISTS exam_candidates(id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER, member_id INTEGER, grade_targeted TEXT, score REAL,
        result TEXT, observations TEXT, UNIQUE(exam_id, member_id));
    CREATE TABLE IF NOT EXISTS grades_history(id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER, grade TEXT, grade_date TEXT, examiner TEXT,
        result TEXT, exam_id INTEGER, notes TEXT);
    CREATE TABLE IF NOT EXISTS competitions(id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, competition_date TEXT, location TEXT, description TEXT);
    CREATE TABLE IF NOT EXISTS competition_registrations(
        id INTEGER PRIMARY KEY AUTOINCREMENT, competition_id INTEGER,
        member_id INTEGER, category TEXT, discipline TEXT, result TEXT,
        ranking INTEGER, medal TEXT, observations TEXT,
        UNIQUE(competition_id, member_id));
    """)
    conn.commit()
    today = date.today()

    print("👤 Utilisateurs...")
    for u, p, r, mid in USERS:
        try:
            c.execute("INSERT INTO users(username,password,role,member_id,created_at) VALUES(?,?,?,?,?)",
                      (u, hp(p), r, mid, datetime.now().isoformat()))
        except sqlite3.IntegrityError:
            pass
    conn.commit()

    print(f"👥 {len(MEMBERS)} membres...")
    member_ids = []
    for i, (fn, ln, bd, gd, ph, em, ad, blood, acad, gr, disc, lic, jd, notes) in enumerate(MEMBERS, 1):
        age = age_of(bd); cat = calc_cat(age)
        lic_exp = (today + timedelta(days=random.randint(30, 300))).isoformat()
        med_exp = (today + timedelta(days=random.randint(-20, 250))).isoformat()
        ins_exp = (today + timedelta(days=random.randint(60, 365))).isoformat()
        docs = "Complet" if random.random() > 0.2 else "Incomplet"
        c.execute("""INSERT INTO members(
            first_name,last_name,birth_date,gender,phone,email,address,
            blood_group,academic_level,category,grade,grade_date,discipline,
            license_number,license_expiry,medical_cert_expiry,
            insurance_status,insurance_expiry,parental_authorization,
            documents_status,join_date,status,notes,photo)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fn, ln, bd, gd, ph, em, ad, blood, acad, cat, gr,
             jd, disc, lic, lic_exp, med_exp, "oui", ins_exp,
             1 if age < 18 else 0, docs, jd, "Actif", notes, None))
        mid = c.lastrowid; member_ids.append(mid)
        photo = make_avatar(fn, ln, mid)
        c.execute("UPDATE members SET photo=? WHERE id=?", (photo, mid))
    conn.commit()

    print("👨‍👩‍👧 Parents...")
    for i, (fn, ln, bd, *_) in enumerate(MEMBERS[:15]):
        if age_of(bd) >= 18: continue
        mid = member_ids[i]
        c.execute("INSERT INTO parents(first_name,last_name,phone,email) VALUES(?,?,?,?)",
                  (f"Parent de {fn}", ln, f"06600{random.randint(10000,99999)}",
                   f"parent.{ln.lower()}@mail.dz"))
        c.execute("INSERT INTO member_parents(member_id,parent_id) VALUES(?,?)",
                  (mid, c.lastrowid))
    conn.commit()

    print(f"📅 {len(COURSES)} cours...")
    course_ids = []
    for row in COURSES:
        c.execute("""INSERT INTO courses(name,day_of_week,start_time,end_time,
                     room,teacher,category,discipline,capacity,active)
                     VALUES(?,?,?,?,?,?,?,?,?,1)""", row)
        course_ids.append(c.lastrowid)
    conn.commit()

    print("📝 Inscriptions...")
    cat_to_course = {"Poussins":[0],"Pupilles":[0,1],"Benjamins":[1],"Minimes":[1,2],
                     "Cadets":[2],"Juniors":[3],"Espoirs":[3,5,6],"Seniors":[4,5,6]}
    enrollments = []
    for mid in member_ids:
        m = c.execute("SELECT category FROM members WHERE id=?", (mid,)).fetchone()
        for idx in cat_to_course.get(m[0], [1]):
            enrollments.append((mid, course_ids[idx], today.isoformat()))
    for mid in random.sample(member_ids, 10):
        for cid in random.sample(course_ids, 1):
            enrollments.append((mid, cid, today.isoformat()))
    seen = set(); unique_enr = []
    for e in enrollments:
        if (e[0], e[1]) not in seen:
            seen.add((e[0], e[1])); unique_enr.append(e)
    c.executemany("INSERT OR IGNORE INTO enrollments(member_id,course_id,date_enrolled) VALUES(?,?,?)",
                  unique_enr)
    conn.commit()

    print("✅ Présences...")
    statuses = ["present"]*7 + ["absent","justified","late","consultation"]
    att_rows = []
    for weeks_ago in range(8):
        monday = today - timedelta(days=today.weekday() + 7*weeks_ago)
        for cid, row in zip(course_ids, COURSES):
            sd = monday + timedelta(days=row[1])
            if sd > today: continue
            for mid, ecid, _ in unique_enr:
                if ecid != cid: continue
                att_rows.append((mid, cid, sd.isoformat(), random.choice(statuses)))
    c.executemany("INSERT OR IGNORE INTO attendance(member_id,course_id,attendance_date,status) VALUES(?,?,?,?)",
                  att_rows)
    conn.commit()

    print("💰 Paiements...")
    season = f"{today.year}-{today.year+1}"; pay_rows = []
    for mid in member_ids:
        pay_rows.append((mid, 3000.0, 3000.0,
                         (today - timedelta(days=random.randint(180,300))).isoformat(),
                         (today - timedelta(days=200)).isoformat(),
                         "Espèces","Inscription",season,"paid",""))
        r = random.random()
        if r < 0.55:
            pay_rows.append((mid, 12000.0, 12000.0,
                             (today - timedelta(days=random.randint(30,150))).isoformat(),
                             (today - timedelta(days=60)).isoformat(),
                             "Virement","Cotisation",season,"paid",""))
        elif r < 0.75:
            pay_rows.append((mid, 12000.0, 6000.0,
                             (today - timedelta(days=random.randint(10,60))).isoformat(),
                             (today + timedelta(days=30)).isoformat(),
                             "Espèces","Cotisation",season,"partial","1er versement"))
        elif r < 0.9:
            pay_rows.append((mid, 12000.0, 0.0,
                             (today - timedelta(days=random.randint(30,90))).isoformat(),
                             (today - timedelta(days=15)).isoformat(),
                             "—","Cotisation",season,"overdue",""))
        else:
            pay_rows.append((mid, 12000.0, 0.0,
                             today.isoformat(),
                             (today + timedelta(days=45)).isoformat(),
                             "—","Cotisation",season,"pending",""))
        pay_rows.append((mid, 1500.0, 1500.0,
                         (today - timedelta(days=random.randint(60,120))).isoformat(),
                         (today - timedelta(days=90)).isoformat(),
                         "CB","Licence",season,"paid",""))
    c.executemany("""INSERT INTO payments(member_id,amount,amount_paid,payment_date,
                     due_date,method,type,season,status,notes) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  pay_rows)
    conn.commit()

    print("🎓 Examens...")
    past = (today - timedelta(days=60)).isoformat()
    c.execute("""INSERT INTO exams(name,exam_date,examiner,grade_targeted,location,notes)
                 VALUES(?,?,?,?,?,?)""",
              ("Passage de grades — Hiver", past, "Maître Ahmed B. (6e Dan)",
               "Bleue", "Dojo Central, Tlemcen", "Session officielle"))
    ex1 = c.lastrowid
    c.execute("""INSERT INTO exams(name,exam_date,examiner,grade_targeted,location,notes)
                 VALUES(?,?,?,?,?,?)""",
              ("Passage de grades — Été", (today + timedelta(days=45)).isoformat(),
               "Maître Ahmed B. (6e Dan)", "Marron 3e kyu",
               "Dojo Central, Tlemcen", "Session officielle"))
    ex2 = c.lastrowid
    conn.commit()
    for mid in random.sample(member_ids, 8):
        g = c.execute("SELECT grade FROM members WHERE id=?", (mid,)).fetchone()[0]
        if g in ("Orange","Jaune","Verte"):
            score = round(random.uniform(11, 19), 1)
            res = "admis" if score >= 12 else "ajourne"
            c.execute("""INSERT INTO exam_candidates(exam_id,member_id,grade_targeted,
                         score,result,observations) VALUES(?,?,?,?,?,?)""",
                      (ex1, mid, "Bleue", score, res,
                       "Bonne technique" if res == "admis" else "À travailler"))
            if res == "admis":
                c.execute("UPDATE members SET grade=?, grade_date=? WHERE id=?",
                          ("Bleue", past, mid))
                c.execute("""INSERT INTO grades_history(member_id,grade,grade_date,
                             examiner,result,exam_id,notes) VALUES(?,?,?,?,?,?,?)""",
                          (mid, "Bleue", past, "Maître Ahmed B.", "Réussi", ex1, ""))
    for mid in random.sample(member_ids, 5):
        c.execute("INSERT INTO exam_candidates(exam_id,member_id,grade_targeted) VALUES(?,?,?)",
                  (ex2, mid, "Marron 3e kyu"))
    conn.commit()

    print("🏆 Compétitions...")
    c.execute("INSERT INTO competitions(name,competition_date,location,description) VALUES(?,?,?,?)",
              ("Championnat Régional Kata", (today - timedelta(days=90)).isoformat(),
               "Oran", "Championnat régional de la ligue Ouest"))
    cp1 = c.lastrowid
    c.execute("INSERT INTO competitions(name,competition_date,location,description) VALUES(?,?,?,?)",
              ("Coupe d'Algérie Kumite", (today + timedelta(days=30)).isoformat(),
               "Alger", "Compétition nationale — qualificative"))
    cp2 = c.lastrowid
    conn.commit()
    medals = ["or","argent","bronze","none","none"]
    for mid in random.sample(member_ids, 8):
        cat = c.execute("SELECT category FROM members WHERE id=?", (mid,)).fetchone()[0]
        md = random.choice(medals)
        rk = {"or":1,"argent":2,"bronze":3}.get(md, random.randint(4,12))
        c.execute("""INSERT INTO competition_registrations(
            competition_id,member_id,category,discipline,result,ranking,medal)
            VALUES(?,?,?,?,?,?,?)""",
            (cp1, mid, cat, "Kata",
             "1er" if md == "or" else "Finaliste" if md != "none" else "Poules", rk, md))
    for mid in random.sample(member_ids, 6):
        c.execute("""INSERT INTO competition_registrations(
            competition_id,member_id,category,discipline) VALUES(?,?,?,?)""",
            (cp2, mid,
             c.execute("SELECT category FROM members WHERE id=?", (mid,)).fetchone()[0],
             "Kumite"))
    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("✅ Jeu de données généré !")
    print("=" * 60)
    print(f"📂 Base : {DB_PATH}")
    print(f"👥 {len(MEMBERS)} membres | 📅 {len(COURSES)} cours")
    print("\n🔑 Connexion :")
    print("   admin / admin123")
    print("   prof / prof123")
    print("   secretaire / secretaire123")
    print("   yacine / membre123")


if __name__ == "__main__":
    main()
