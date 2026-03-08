import asyncio, logging, os, aiosqlite
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from database import *

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_app():
    with open("static/miniapp/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# ── Услуги ────────────────────────────────────────────────────────────────────
@app.get("/api/categories/{clinic_id}")
async def api_categories(clinic_id: int):
    cats = await get_service_categories(clinic_id)
    return [dict(c) for c in cats]

@app.get("/api/services/{clinic_id}")
async def api_services(clinic_id: int, category_id: int = None):
    svcs = await get_services(clinic_id, category_id)
    return [dict(s) for s in svcs]

# ── Врачи ─────────────────────────────────────────────────────────────────────
@app.get("/api/doctors/{clinic_id}")
async def api_doctors(clinic_id: int):
    docs = await get_doctors(clinic_id)
    result = []
    for d in docs:
        r = await get_doctor_rating(d["id"])
        row = dict(d); row["rating"] = r["avg"]; row["reviews"] = r["count"]
        result.append(row)
    return result

# ── Свободные слоты ───────────────────────────────────────────────────────────
@app.get("/api/slots/{doctor_id}/{date_str}")
async def api_slots(doctor_id: int, date_str: str):
    return await get_free_slots(doctor_id, date_str)

# ── Запись ────────────────────────────────────────────────────────────────────
@app.post("/api/appointment")
async def api_book(request: Request):
    data = await request.json()
    required = ["clinic_id","patient_id","doctor_id","appt_date","appt_time"]
    for f in required:
        if f not in data:
            return JSONResponse({"error": f"Missing {f}"}, status_code=400)

    # Проверка слота
    slots = await get_free_slots(data["doctor_id"], data["appt_date"])
    slot = next((s for s in slots if s["time"] == data["appt_time"]), None)
    if not slot or not slot["available"]:
        return JSONResponse({"error": "Слот занят, выберите другое время"}, status_code=409)

    # Создать/обновить пациента
    await get_or_create_patient(
        data["patient_id"], data.get("patient_name","Пациент"),
        clinic_id=data["clinic_id"],
        phone=data.get("phone"), username=data.get("username")
    )

    appt_id = await create_appointment({
        "clinic_id":   data["clinic_id"],
        "patient_id":  data["patient_id"],
        "doctor_id":   data["doctor_id"],
        "service_id":  data.get("service_id"),
        "appt_date":   data["appt_date"],
        "appt_time":   data["appt_time"],
        "duration_min":data.get("duration_min", 60),
        "complaint":   data.get("complaint",""),
    })

    # Уведомить бота
    try:
        from bot import notify_new_booking, notify_patient, bot as tg_bot
        async with aiosqlite.connect(DB) as db:
            db.row_factory = aiosqlite.Row
            c = await db.execute("""
                SELECT a.*,p.full_name as patient_name,p.phone,
                       d.full_name as doctor_name,d.telegram_id as doc_tg,
                       cl.admin_id,s.name as service_name
                FROM appointments a
                JOIN patients p ON a.patient_id=p.id
                JOIN doctors d ON a.doctor_id=d.id
                JOIN clinics cl ON a.clinic_id=cl.id
                LEFT JOIN services s ON a.service_id=s.id
                WHERE a.id=?
            """, (appt_id,))
            row = await c.fetchone()
        if row:
            info = dict(row); info["appt_id"] = appt_id
            asyncio.create_task(notify_new_booking(row["admin_id"], row["doc_tg"], info))
            asyncio.create_task(notify_patient(data["patient_id"],
                f"✅ <b>Запись подтверждена!</b>\n\n"
                f"🦷 <b>DENT PLUS</b>\n"
                f"👨‍⚕️ Врач: {row['doctor_name']}\n"
                f"🦷 Услуга: {row['service_name'] or 'Консультация'}\n"
                f"📅 Дата: <b>{data['appt_date']}</b>\n"
                f"🕐 Время: <b>{data['appt_time']}</b>\n\n"
                f"⏰ Напомним за 2 часа до приёма!"
            ))
    except Exception as e:
        logging.warning(f"Notify skipped: {e}")

    return {"success": True, "appointment_id": appt_id}

# ── Записи пациента ───────────────────────────────────────────────────────────
@app.get("/api/patient/appointments/{patient_id}")
async def api_patient_appts(patient_id: int):
    appts = await get_patient_appointments(patient_id)
    return [dict(a) for a in appts]

# ── Зубная карта ─────────────────────────────────────────────────────────────
@app.get("/api/patient/chart/{patient_id}")
async def api_dental_chart(patient_id: int):
    chart = await get_dental_chart(patient_id)
    return chart

@app.post("/api/patient/chart")
async def api_update_tooth(request: Request):
    d = await request.json()
    await update_tooth(d["patient_id"], d["tooth_number"], d["status"], d.get("notes",""))
    return {"success": True}

# ── История лечения ───────────────────────────────────────────────────────────
@app.get("/api/patient/treatments/{patient_id}")
async def api_treatments(patient_id: int):
    treats = await get_patient_treatments(patient_id)
    return [dict(t) for t in treats]

# ── Отзыв ─────────────────────────────────────────────────────────────────────
@app.post("/api/review")
async def api_review(request: Request):
    d = await request.json()
    await add_review(d["clinic_id"], d["patient_id"], d.get("doctor_id"),
                     d.get("appointment_id"), d["rating"], d.get("comment",""))
    return {"success": True}

# ── Данные клиники ─────────────────────────────────────────────────────────────
@app.get("/api/clinic/{clinic_id}")
async def api_clinic(clinic_id: int):
    c = await get_clinic(clinic_id)
    return dict(c) if c else {}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

# ─── ADMIN WEB PANEL ─────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    with open("static/admin.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/api/admin/stats/{clinic_id}")
async def admin_stats(clinic_id: int):
    return await get_clinic_stats(clinic_id)

@app.get("/api/admin/appointments/{clinic_id}")
async def admin_appointments(clinic_id: int, date: str = None, doctor_id: int = None):
    from datetime import date as dt
    if not date: date = dt.today().strftime("%Y-%m-%d")
    appts = await get_appointments_by_date(clinic_id, date, doctor_id)
    return [dict(a) for a in appts]

@app.post("/api/admin/appointment/{appt_id}/status")
async def admin_update_appt(appt_id: int, request: Request):
    d = await request.json()
    await update_appointment_status(appt_id, d["status"])
    return {"success": True}

@app.get("/api/admin/patients/{clinic_id}")
async def admin_patients_list(clinic_id: int):
    patients = await get_all_patients(clinic_id)
    return [dict(p) for p in patients]

@app.get("/api/admin/lab/{clinic_id}")
async def admin_lab_list(clinic_id: int):
    orders = await get_lab_orders(clinic_id)
    return [dict(o) for o in orders]

@app.post("/api/admin/lab/{order_id}/ready")
async def admin_lab_ready(order_id: int):
    from datetime import date
    await update_lab_order_status(order_id, "ready", date.today().strftime("%Y-%m-%d"))
    return {"success": True}
