import aiosqlite, os

DB = "dental.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS clinics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            kaspi_phone TEXT,
            admin_id INTEGER UNIQUE,
            logo_url TEXT,
            working_hours TEXT DEFAULT '09:00-20:00',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            telegram_id INTEGER UNIQUE,
            full_name TEXT NOT NULL,
            speciality TEXT DEFAULT 'Стоматолог-терапевт',
            photo_url TEXT,
            experience_years INTEGER DEFAULT 0,
            salary_percent INTEGER DEFAULT 40,
            is_active INTEGER DEFAULT 1,
            work_days TEXT DEFAULT '1,2,3,4,5',
            FOREIGN KEY (clinic_id) REFERENCES clinics(id)
        );

        CREATE TABLE IF NOT EXISTS service_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '🦷',
            sort_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            category_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            price_from INTEGER NOT NULL,
            price_to INTEGER,
            duration_min INTEGER DEFAULT 60,
            emoji TEXT DEFAULT '🦷',
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (clinic_id) REFERENCES clinics(id),
            FOREIGN KEY (category_id) REFERENCES service_categories(id)
        );

        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY,
            clinic_id INTEGER,
            full_name TEXT NOT NULL,
            phone TEXT,
            birth_date TEXT,
            gender TEXT DEFAULT 'unknown',
            blood_type TEXT,
            allergies TEXT,
            medical_notes TEXT,
            telegram_username TEXT,
            loyalty_points INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            visits_count INTEGER DEFAULT 0,
            last_visit TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clinic_id) REFERENCES clinics(id)
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            service_id INTEGER,
            appt_date TEXT NOT NULL,
            appt_time TEXT NOT NULL,
            duration_min INTEGER DEFAULT 60,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            complaint TEXT,
            reminder_24h INTEGER DEFAULT 0,
            reminder_2h INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clinic_id) REFERENCES clinics(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        );

        CREATE TABLE IF NOT EXISTS dental_chart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            tooth_number INTEGER NOT NULL,
            status TEXT DEFAULT 'healthy',
            notes TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(patient_id, tooth_number),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_id INTEGER,
            tooth_number INTEGER,
            procedure_name TEXT NOT NULL,
            diagnosis TEXT,
            description TEXT,
            price INTEGER NOT NULL,
            date TEXT DEFAULT CURRENT_DATE,
            FOREIGN KEY (clinic_id) REFERENCES clinics(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            appointment_id INTEGER,
            total_amount INTEGER NOT NULL,
            paid_amount INTEGER DEFAULT 0,
            discount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'unpaid',
            payment_method TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            paid_at TEXT,
            FOREIGN KEY (clinic_id) REFERENCES clinics(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS lab_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            order_type TEXT NOT NULL,
            description TEXT,
            tooth_numbers TEXT,
            status TEXT DEFAULT 'ordered',
            lab_name TEXT,
            ordered_date TEXT DEFAULT CURRENT_DATE,
            ready_date TEXT,
            price INTEGER DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (clinic_id) REFERENCES clinics(id),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clinic_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER,
            appointment_id INTEGER,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        await db.commit()
        await _seed_demo(db)

async def _seed_demo(db):
    cur = await db.execute("SELECT COUNT(*) FROM clinics")
    if (await cur.fetchone())[0] > 0:
        return

    await db.execute("""INSERT INTO clinics (name,address,phone,kaspi_phone,admin_id,working_hours)
        VALUES ('Стоматология DENT PLUS','Алматы, Абая 55','+ 7 727 300 00 01','+77001234567',0,'09:00-20:00')""")

    await db.executemany("INSERT INTO doctors (clinic_id,full_name,speciality,experience_years,salary_percent,work_days) VALUES (?,?,?,?,?,?)",[
        (1,'Иванова Алия Сериковна','Терапевт',12,45,'1,2,3,4,5'),
        (1,'Нурланов Бауыржан','Хирург-имплантолог',18,50,'1,2,3,4,5'),
        (1,'Сейткали Гульнара','Ортодонт',9,40,'2,3,4,5,6'),
        (1,'Ахметов Дамир','Ортопед-протезист',15,45,'1,3,5'),
    ])

    cats = [(1,'Терапия','🦷',1),(1,'Хирургия','🔪',2),(1,'Ортодонтия','🦷',3),(1,'Ортопедия','👑',4),(1,'Гигиена','✨',5),(1,'Имплантация','🔩',6)]
    await db.executemany("INSERT INTO service_categories (clinic_id,name,emoji,sort_order) VALUES (?,?,?,?)", cats)

    services = [
        (1,1,'Лечение кариеса','Пломбирование кариозных полостей',8000,15000,45,'🦷'),
        (1,1,'Лечение пульпита','Эндодонтическое лечение',15000,25000,90,'💊'),
        (1,1,'Лечение периодонтита','Лечение корневых каналов',20000,35000,90,'🔬'),
        (1,1,'Реставрация зуба','Художественная реставрация',12000,20000,60,'✨'),
        (1,2,'Удаление зуба простое','Атравматическое удаление',8000,12000,30,'🔪'),
        (1,2,'Удаление зуба сложное','Хирургическое удаление',15000,25000,60,'⚕️'),
        (1,2,'Удаление нерва','Депульпирование',10000,15000,60,'💉'),
        (1,3,'Брекет-система металл','Полное ортодонтическое лечение',150000,250000,90,'🦷'),
        (1,3,'Элайнеры','Прозрачное выравнивание',200000,400000,60,'😁'),
        (1,3,'Ретейнер','Закрепляющий аппарат',20000,35000,30,'🔧'),
        (1,4,'Коронка металлокерамика','Несъёмное протезирование',35000,50000,60,'👑'),
        (1,4,'Коронка цирконий','Безметалловая керамика',60000,90000,60,'💎'),
        (1,4,'Виниры','Фарфоровые накладки',45000,70000,45,'⭐'),
        (1,4,'Съёмный протез','Полное/частичное протезирование',80000,150000,60,'🦷'),
        (1,5,'Профессиональная чистка','Ультразвук + Air Flow',12000,18000,60,'✨'),
        (1,5,'Отбеливание ZOOM','Фотоотбеливание',45000,60000,90,'😁'),
        (1,5,'Фторирование','Укрепление эмали',5000,8000,30,'💪'),
        (1,6,'Имплант Nobel','Установка импланта Nobel Biocare',180000,220000,120,'🔩'),
        (1,6,'Имплант Straumann','Швейцарский имплант',200000,280000,120,'🏆'),
        (1,6,'Наращивание кости','Костная пластика',120000,200000,90,'🦴'),
    ]
    await db.executemany("INSERT INTO services (clinic_id,category_id,name,description,price_from,price_to,duration_min,emoji) VALUES (?,?,?,?,?,?,?,?)", services)
    await db.commit()
    print("✅ Dental demo data seeded")

# ───── CLINICS ────────────────────────────────────────────────────────────────
async def get_clinic_by_admin(admin_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM clinics WHERE admin_id=?", (admin_id,))
        return await c.fetchone()

async def get_clinic(clinic_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM clinics WHERE id=?", (clinic_id,))
        return await c.fetchone()

# ───── DOCTORS ────────────────────────────────────────────────────────────────
async def get_doctors(clinic_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM doctors WHERE clinic_id=? AND is_active=1", (clinic_id,))
        return await c.fetchall()

async def get_doctor(doctor_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,))
        return await c.fetchone()

async def get_doctor_by_tg(tg_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM doctors WHERE telegram_id=?", (tg_id,))
        return await c.fetchone()

# ───── SERVICES ───────────────────────────────────────────────────────────────
async def get_service_categories(clinic_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM service_categories WHERE clinic_id=? ORDER BY sort_order", (clinic_id,))
        return await c.fetchall()

async def get_services(clinic_id, category_id=None):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        if category_id:
            c = await db.execute("SELECT * FROM services WHERE clinic_id=? AND category_id=? AND is_active=1", (clinic_id, category_id))
        else:
            c = await db.execute("SELECT * FROM services WHERE clinic_id=? AND is_active=1 ORDER BY category_id, name", (clinic_id,))
        return await c.fetchall()

async def get_service(service_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM services WHERE id=?", (service_id,))
        return await c.fetchone()

# ───── PATIENTS ───────────────────────────────────────────────────────────────
async def get_or_create_patient(tg_id, full_name, clinic_id=1, phone=None, username=None):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM patients WHERE id=?", (tg_id,))
        p = await c.fetchone()
        if not p:
            await db.execute(
                "INSERT INTO patients (id,clinic_id,full_name,phone,telegram_username) VALUES (?,?,?,?,?)",
                (tg_id, clinic_id, full_name, phone, username)
            )
            await db.commit()
            c = await db.execute("SELECT * FROM patients WHERE id=?", (tg_id,))
            p = await c.fetchone()
        return p

async def get_patient(patient_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM patients WHERE id=?", (patient_id,))
        return await c.fetchone()

async def search_patients(clinic_id, query):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute(
            "SELECT * FROM patients WHERE clinic_id=? AND (full_name LIKE ? OR phone LIKE ?) LIMIT 10",
            (clinic_id, f"%{query}%", f"%{query}%")
        )
        return await c.fetchall()

async def get_all_patients(clinic_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM patients WHERE clinic_id=? ORDER BY full_name", (clinic_id,))
        return await c.fetchall()

# ───── APPOINTMENTS ───────────────────────────────────────────────────────────
async def get_free_slots(doctor_id, date_str):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute(
            "SELECT appt_time, duration_min FROM appointments WHERE doctor_id=? AND appt_date=? AND status NOT IN ('cancelled','no_show')",
            (doctor_id, date_str)
        )
        booked = await c.fetchall()

    busy_slots = set()
    for b in booked:
        h, m = map(int, b["appt_time"].split(":"))
        total_m = h * 60 + m
        for i in range(0, b["duration_min"], 30):
            slot_m = total_m + i
            busy_slots.add(f"{slot_m//60:02d}:{slot_m%60:02d}")

    all_slots = []
    for h in range(9, 20):
        for m in [0, 30]:
            t = f"{h:02d}:{m:02d}"
            all_slots.append({"time": t, "available": t not in busy_slots})
    return all_slots

async def create_appointment(data: dict):
    async with aiosqlite.connect(DB) as db:
        c = await db.execute("""
            INSERT INTO appointments (clinic_id,patient_id,doctor_id,service_id,appt_date,appt_time,duration_min,complaint)
            VALUES (:clinic_id,:patient_id,:doctor_id,:service_id,:appt_date,:appt_time,:duration_min,:complaint)
        """, data)
        await db.commit()
        return c.lastrowid

async def get_appointments_by_date(clinic_id, date_str, doctor_id=None):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        if doctor_id:
            c = await db.execute("""
                SELECT a.*,p.full_name as patient_name,p.phone,d.full_name as doctor_name,s.name as service_name,s.emoji,s.price_from
                FROM appointments a
                JOIN patients p ON a.patient_id=p.id
                JOIN doctors d ON a.doctor_id=d.id
                LEFT JOIN services s ON a.service_id=s.id
                WHERE a.clinic_id=? AND a.appt_date=? AND a.doctor_id=?
                ORDER BY a.appt_time
            """, (clinic_id, date_str, doctor_id))
        else:
            c = await db.execute("""
                SELECT a.*,p.full_name as patient_name,p.phone,d.full_name as doctor_name,s.name as service_name,s.emoji,s.price_from
                FROM appointments a
                JOIN patients p ON a.patient_id=p.id
                JOIN doctors d ON a.doctor_id=d.id
                LEFT JOIN services s ON a.service_id=s.id
                WHERE a.clinic_id=? AND a.appt_date=?
                ORDER BY a.appt_time, d.full_name
            """, (clinic_id, date_str))
        return await c.fetchall()

async def get_patient_appointments(patient_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT a.*,d.full_name as doctor_name,d.speciality,s.name as service_name,s.emoji,s.price_from
            FROM appointments a
            JOIN doctors d ON a.doctor_id=d.id
            LEFT JOIN services s ON a.service_id=s.id
            WHERE a.patient_id=?
            ORDER BY a.appt_date DESC, a.appt_time DESC
            LIMIT 30
        """, (patient_id,))
        return await c.fetchall()

async def update_appointment_status(appt_id, status):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE appointments SET status=? WHERE id=?", (status, appt_id))
        await db.commit()

# ───── DENTAL CHART ───────────────────────────────────────────────────────────
async def get_dental_chart(patient_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM dental_chart WHERE patient_id=?", (patient_id,))
        rows = await c.fetchall()
        chart = {r["tooth_number"]: dict(r) for r in rows}
        return chart

async def update_tooth(patient_id, tooth_number, status, notes=""):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            INSERT INTO dental_chart (patient_id,tooth_number,status,notes,updated_at)
            VALUES (?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(patient_id,tooth_number) DO UPDATE
            SET status=excluded.status, notes=excluded.notes, updated_at=excluded.updated_at
        """, (patient_id, tooth_number, status, notes))
        await db.commit()

# ───── TREATMENTS ─────────────────────────────────────────────────────────────
async def get_patient_treatments(patient_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT t.*,d.full_name as doctor_name
            FROM treatments t
            JOIN doctors d ON t.doctor_id=d.id
            WHERE t.patient_id=?
            ORDER BY t.date DESC LIMIT 50
        """, (patient_id,))
        return await c.fetchall()

async def add_treatment(data: dict):
    async with aiosqlite.connect(DB) as db:
        c = await db.execute("""
            INSERT INTO treatments (clinic_id,patient_id,doctor_id,appointment_id,tooth_number,procedure_name,diagnosis,description,price,date)
            VALUES (:clinic_id,:patient_id,:doctor_id,:appointment_id,:tooth_number,:procedure_name,:diagnosis,:description,:price,:date)
        """, data)
        # Обновить расходы пациента
        await db.execute("UPDATE patients SET total_spent=total_spent+?, last_visit=? WHERE id=?",
                         (data["price"], data["date"], data["patient_id"]))
        await db.commit()
        return c.lastrowid

# ───── INVOICES / ФИНАНСЫ ─────────────────────────────────────────────────────
async def create_invoice(clinic_id, patient_id, appointment_id, total):
    async with aiosqlite.connect(DB) as db:
        c = await db.execute(
            "INSERT INTO invoices (clinic_id,patient_id,appointment_id,total_amount) VALUES (?,?,?,?)",
            (clinic_id, patient_id, appointment_id, total)
        )
        await db.commit()
        return c.lastrowid

async def get_patient_invoices(patient_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM invoices WHERE patient_id=? ORDER BY created_at DESC", (patient_id,))
        return await c.fetchall()

async def get_clinic_stats(clinic_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT COUNT(*) as total FROM appointments WHERE clinic_id=?", (clinic_id,))
        total_appts = (await c.fetchone())["total"]
        c = await db.execute("SELECT COUNT(*) as today FROM appointments WHERE clinic_id=? AND appt_date=date('now') AND status!='cancelled'", (clinic_id,))
        today_appts = (await c.fetchone())["today"]
        c = await db.execute("SELECT COUNT(*) as cnt FROM patients WHERE clinic_id=?", (clinic_id,))
        total_patients = (await c.fetchone())["cnt"]
        c = await db.execute("SELECT COALESCE(SUM(total_amount),0) as rev FROM invoices WHERE clinic_id=? AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now')", (clinic_id,))
        month_rev = (await c.fetchone())["rev"]
        c = await db.execute("SELECT COALESCE(SUM(total_amount-paid_amount),0) as debt FROM invoices WHERE clinic_id=? AND status='unpaid'", (clinic_id,))
        total_debt = (await c.fetchone())["debt"]
        c = await db.execute("SELECT COALESCE(SUM(total_amount),0) as today_rev FROM invoices WHERE clinic_id=? AND date(created_at)=date('now')", (clinic_id,))
        today_rev = (await c.fetchone())["today_rev"]
        return {"total_appts": total_appts, "today_appts": today_appts,
                "total_patients": total_patients, "month_rev": month_rev,
                "total_debt": total_debt, "today_rev": today_rev}

async def get_doctor_stats(doctor_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT COUNT(*) as today FROM appointments WHERE doctor_id=? AND appt_date=date('now') AND status!='cancelled'", (doctor_id,))
        today = (await c.fetchone())["today"]
        c = await db.execute("SELECT COALESCE(SUM(price),0) as month_earn FROM treatments WHERE doctor_id=? AND strftime('%Y-%m',date)=strftime('%Y-%m','now')", (doctor_id,))
        month_earn = (await c.fetchone())["month_earn"]
        return {"today": today, "month_earn": month_earn}

# ───── LAB ORDERS ─────────────────────────────────────────────────────────────
async def create_lab_order(data: dict):
    async with aiosqlite.connect(DB) as db:
        c = await db.execute("""
            INSERT INTO lab_orders (clinic_id,patient_id,doctor_id,order_type,description,tooth_numbers,lab_name,price)
            VALUES (:clinic_id,:patient_id,:doctor_id,:order_type,:description,:tooth_numbers,:lab_name,:price)
        """, data)
        await db.commit()
        return c.lastrowid

async def get_lab_orders(clinic_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("""
            SELECT l.*,p.full_name as patient_name,d.full_name as doctor_name
            FROM lab_orders l
            JOIN patients p ON l.patient_id=p.id
            JOIN doctors d ON l.doctor_id=d.id
            WHERE l.clinic_id=? AND l.status IN ('ordered','in_progress')
            ORDER BY l.ordered_date DESC
        """, (clinic_id,))
        return await c.fetchall()

async def update_lab_order_status(order_id, status, ready_date=None):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE lab_orders SET status=?,ready_date=? WHERE id=?", (status, ready_date, order_id))
        await db.commit()

# ───── REVIEWS ────────────────────────────────────────────────────────────────
async def add_review(clinic_id, patient_id, doctor_id, appt_id, rating, comment):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            INSERT INTO reviews (clinic_id,patient_id,doctor_id,appointment_id,rating,comment)
            VALUES (?,?,?,?,?,?)
        """, (clinic_id, patient_id, doctor_id, appt_id, rating, comment))
        await db.commit()

async def get_doctor_rating(doctor_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT AVG(rating) as avg, COUNT(*) as cnt FROM reviews WHERE doctor_id=?", (doctor_id,))
        r = await c.fetchone()
        return {"avg": round(r["avg"] or 0, 1), "count": r["cnt"]}

async def register_business(admin_id: int, name: str, address: str, phone: str):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "INSERT INTO clinics (name,address,phone,admin_id) VALUES (?,?,?,?)",
            (name, address, phone, admin_id)
        )
        await db.commit()
        return cur.lastrowid
