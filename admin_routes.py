"""
Дополнительные API роуты для Веб-Панели Администратора
Добавь эти роуты в конец файла main.py
"""

# ── Admin: Статистика ──────────────────────────────────────────────────────────
@app.get("/api/admin/stats/{clinic_id}")
async def admin_stats(clinic_id: int):
    stats = await get_clinic_stats(clinic_id)
    return stats

# ── Admin: Записи ──────────────────────────────────────────────────────────────
@app.get("/api/admin/appointments/{clinic_id}")
async def admin_appointments(clinic_id: int, date: str = None, doctor_id: int = None):
    if not date:
        from datetime import date as dt
        date = dt.today().strftime("%Y-%m-%d")
    appts = await get_appointments_by_date(clinic_id, date, doctor_id)
    return [dict(a) for a in appts]

@app.post("/api/admin/appointment/{appt_id}/status")
async def admin_update_appt(appt_id: int, request: Request):
    d = await request.json()
    await update_appointment_status(appt_id, d["status"])
    return {"success": True}

# ── Admin: Пациенты ───────────────────────────────────────────────────────────
@app.get("/api/admin/patients/{clinic_id}")
async def admin_patients(clinic_id: int):
    patients = await get_all_patients(clinic_id)
    return [dict(p) for p in patients]

# ── Admin: Лаборатория ────────────────────────────────────────────────────────
@app.get("/api/admin/lab/{clinic_id}")
async def admin_lab(clinic_id: int):
    orders = await get_lab_orders(clinic_id)
    return [dict(o) for o in orders]

@app.post("/api/admin/lab/{order_id}/ready")
async def admin_lab_ready(order_id: int):
    from datetime import date
    await update_lab_order_status(order_id, "ready", date.today().strftime("%Y-%m-%d"))
    return {"success": True}

# ── Admin Panel HTML ───────────────────────────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    with open("static/admin.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())
