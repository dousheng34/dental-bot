"""
Планировщик автоматических напоминаний пациентам
- За 24 часа до приёма
- За 2 часа до приёма
- День рождения пациента
"""
import asyncio, logging, os
from datetime import datetime, date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import aiosqlite
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
DB = "dental.db"

scheduler = AsyncIOScheduler(timezone="Asia/Almaty")

# ─────────────────────────────────────────────────────────────────────────────
async def send_reminder(bot, patient_id: int, text: str):
    try:
        await bot.send_message(patient_id, text, parse_mode="HTML")
        logger.info(f"✅ Напоминание отправлено пациенту {patient_id}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить пациенту {patient_id}: {e}")

# ─────────────────────────────────────────────────────────────────────────────
async def send_24h_reminders(bot):
    """Напоминания за 24 часа — запускается каждый день в 18:00"""
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT a.id, a.patient_id, a.appt_time, a.reminder_24h,
                   p.full_name as patient_name,
                   d.full_name as doctor_name, d.speciality,
                   s.name as service_name, s.emoji,
                   cl.name as clinic_name, cl.address, cl.phone
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN clinics cl ON a.clinic_id = cl.id
            LEFT JOIN services s ON a.service_id = s.id
            WHERE a.appt_date = ? AND a.status IN ('pending','confirmed')
            AND a.reminder_24h = 0
        """, (tomorrow,))
        appts = await cur.fetchall()

    for a in appts:
        text = (
            f"⏰ <b>Напоминание о записи завтра!</b>\n\n"
            f"🏥 {a['clinic_name']}\n"
            f"📍 {a['address']}\n\n"
            f"📅 Дата: <b>завтра, {tomorrow}</b>\n"
            f"🕐 Время: <b>{a['appt_time']}</b>\n"
            f"👨‍⚕️ Врач: <b>{a['doctor_name']}</b> ({a['speciality']})\n"
            f"🦷 Услуга: {a['emoji'] or ''} {a['service_name'] or 'Консультация'}\n\n"
            f"📞 Вопросы: {a['phone']}\n\n"
            f"❗ Если не сможете прийти — пожалуйста, отмените запись заранее"
        )
        await send_reminder(bot, a["patient_id"], text)
        # Отмечаем что напоминание отправлено
        async with aiosqlite.connect(DB) as db:
            await db.execute("UPDATE appointments SET reminder_24h=1 WHERE id=?", (a["id"],))
            await db.commit()

    if appts:
        logger.info(f"📨 Отправлено 24ч напоминаний: {len(appts)}")

# ─────────────────────────────────────────────────────────────────────────────
async def send_2h_reminders(bot):
    """Напоминания за 2 часа — запускается каждые 30 минут"""
    now = datetime.now()
    target_time = (now + timedelta(hours=2)).strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT a.id, a.patient_id, a.appt_time, a.reminder_2h,
                   p.full_name as patient_name,
                   d.full_name as doctor_name,
                   s.name as service_name, s.emoji,
                   cl.name as clinic_name, cl.address
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN clinics cl ON a.clinic_id = cl.id
            LEFT JOIN services s ON a.service_id = s.id
            WHERE a.appt_date = ? AND a.appt_time = ?
            AND a.status IN ('pending','confirmed')
            AND a.reminder_2h = 0
        """, (today, target_time))
        appts = await cur.fetchall()

    for a in appts:
        text = (
            f"🔔 <b>Через 2 часа у вас приём!</b>\n\n"
            f"🏥 {a['clinic_name']}\n"
            f"📍 {a['address']}\n\n"
            f"🕐 Время: <b>{a['appt_time']}</b>\n"
            f"👨‍⚕️ Врач: <b>{a['doctor_name']}</b>\n"
            f"🦷 {a['emoji'] or ''} {a['service_name'] or 'Консультация'}\n\n"
            f"Ждём вас! 🙌"
        )
        await send_reminder(bot, a["patient_id"], text)
        async with aiosqlite.connect(DB) as db:
            await db.execute("UPDATE appointments SET reminder_2h=1 WHERE id=?", (a["id"],))
            await db.commit()

# ─────────────────────────────────────────────────────────────────────────────
async def send_birthday_greetings(bot):
    """Поздравления с днём рождения — каждый день в 09:00"""
    today_md = date.today().strftime("-%m-%d")
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT id, full_name FROM patients
            WHERE birth_date LIKE ? AND id > 0
        """, (f"%{today_md}",))
        patients = await cur.fetchall()

    for p in patients:
        text = (
            f"🎂 <b>С Днём Рождения, {p['full_name'].split()[0]}!</b>\n\n"
            f"🦷 Вся команда <b>DENT PLUS</b> поздравляет вас!\n\n"
            f"🎁 Специально для вас — <b>скидка 10%</b> на любую услугу в этом месяце\n\n"
            f"Здоровья, счастья и красивой улыбки! 😁"
        )
        await send_reminder(bot, p["id"], text)

    if patients:
        logger.info(f"🎂 Поздравлений отправлено: {len(patients)}")

# ─────────────────────────────────────────────────────────────────────────────
async def send_return_reminders(bot):
    """
    Напоминание вернуться через 6 месяцев после последнего визита
    Запускается каждый день в 10:00
    """
    six_months_ago = (date.today() - timedelta(days=180)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT id, full_name FROM patients
            WHERE last_visit = ? AND id > 0
        """, (six_months_ago,))
        patients = await cur.fetchall()

    for p in patients:
        text = (
            f"🦷 <b>Пора на профилактический осмотр!</b>\n\n"
            f"Привет, {p['full_name'].split()[0]}!\n\n"
            f"Прошло 6 месяцев с вашего последнего визита.\n"
            f"Рекомендуем пройти профилактический осмотр и чистку зубов.\n\n"
            f"📅 <b>Запишитесь прямо сейчас</b> — нажмите /start"
        )
        await send_reminder(bot, p["id"], text)

# ─────────────────────────────────────────────────────────────────────────────
async def notify_lab_ready(bot):
    """Уведомление врачам о готовых лаб. заказах — каждые 2 часа"""
    today = date.today().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT l.*, d.telegram_id, d.full_name as doctor_name,
                   p.full_name as patient_name
            FROM lab_orders l
            JOIN doctors d ON l.doctor_id = d.id
            JOIN patients p ON l.patient_id = p.id
            WHERE l.status = 'ready' AND l.ready_date = ?
        """, (today,))
        orders = await cur.fetchall()

    for o in orders:
        if not o["telegram_id"]:
            continue
        text = (
            f"🔬 <b>Лабораторный заказ готов!</b>\n\n"
            f"👤 Пациент: {o['patient_name']}\n"
            f"📦 Тип: {o['order_type']}\n"
            f"🦷 Зубы: {o['tooth_numbers'] or '—'}\n"
            f"📝 {o['description'] or ''}"
        )
        try:
            await bot.send_message(o["telegram_id"], text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Lab notify error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
def setup_scheduler(bot):
    """Регистрируем все задачи планировщика"""

    # Напоминания за 24ч — каждый день в 18:00
    scheduler.add_job(
        send_24h_reminders, CronTrigger(hour=18, minute=0),
        args=[bot], id="remind_24h", replace_existing=True,
        name="Напоминания за 24ч"
    )

    # Напоминания за 2ч — каждые 30 минут
    scheduler.add_job(
        send_2h_reminders, CronTrigger(minute="0,30"),
        args=[bot], id="remind_2h", replace_existing=True,
        name="Напоминания за 2ч"
    )

    # День рождения — каждый день в 09:00
    scheduler.add_job(
        send_birthday_greetings, CronTrigger(hour=9, minute=0),
        args=[bot], id="birthdays", replace_existing=True,
        name="Поздравления ДР"
    )

    # Напоминание вернуться — каждый день в 10:00
    scheduler.add_job(
        send_return_reminders, CronTrigger(hour=10, minute=0),
        args=[bot], id="return_remind", replace_existing=True,
        name="Вернуться через 6 мес"
    )

    # Уведомление о готовых лаб. заказах — каждые 2 часа
    scheduler.add_job(
        notify_lab_ready, CronTrigger(hour="*/2", minute=0),
        args=[bot], id="lab_ready", replace_existing=True,
        name="Готовые лаб. заказы"
    )

    scheduler.start()
    logger.info("✅ Планировщик запущен. Задач: %d", len(scheduler.get_jobs()))
    for job in scheduler.get_jobs():
        logger.info(f"  ⏰ {job.name} — {job.trigger}")

    return scheduler
