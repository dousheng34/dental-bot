import asyncio, logging, os
from aiogram import Bot, Dispatcher, F
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup,
                            InlineKeyboardButton, WebAppInfo)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from datetime import date, timedelta
from database import *

load_dotenv()
BOT_TOKEN  = os.getenv("BOT_TOKEN","TEST")
ADMIN_ID   = int(os.getenv("ADMIN_ID","0"))
WEBAPP_URL = os.getenv("WEBAPP_URL","https://example.com")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

ST = {"pending":"🟡","confirmed":"✅","cancelled":"❌","done":"💚","no_show":"👻"}

# ══════════════════ FSM ══════════════════════════════════════════════════════
class RegBusiness(StatesGroup):
    name=State(); address=State(); phone=State()

class AddTreatment(StatesGroup):
    select_patient=State(); select_tooth=State()
    procedure=State(); diagnosis=State(); price=State(); confirm=State()

class AddLabOrder(StatesGroup):
    select_patient=State(); order_type=State()
    tooth_nums=State(); lab_name=State(); price=State()

class AddPatient(StatesGroup):
    full_name=State(); phone=State(); birth=State(); allergies=State()

# ══════════════════ /start ═══════════════════════════════════════════════════
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    uid = msg.from_user.id
    doctor = await get_doctor_by_tg(uid)
    if doctor:
        await show_doctor_menu(msg, doctor); return
    clinic = await get_clinic_by_admin(uid)
    if clinic or uid == ADMIN_ID:
        await show_admin_menu(msg, clinic); return
    patient = await get_or_create_patient(
        uid, msg.from_user.full_name, phone=None,
        username=msg.from_user.username or "")
    await show_patient_menu(msg, patient)

# ══════════════════ PATIENT ══════════════════════════════════════════════════
async def show_patient_menu(msg: Message, patient):
    name = patient["full_name"] if patient else msg.from_user.first_name
    uid  = msg.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Записаться к врачу",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?uid={uid}&name={name}&page=booking"))],
        [InlineKeyboardButton(text="🦷 Моя зубная карта",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?uid={uid}&name={name}&page=chart"))],
        [InlineKeyboardButton(text="📋 Мои записи",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?uid={uid}&name={name}&page=history"))],
        [InlineKeyboardButton(text="💰 Мои счета",      callback_data="my_invoices")],
        [InlineKeyboardButton(text="📞 Контакты клиники",callback_data="contacts")],
    ])
    await msg.answer(
        f"👋 Добро пожаловать, <b>{name}</b>!\n\n"
        f"🦷 <b>Стоматология DENT PLUS</b>\n"
        f"📍 Алматы, ул. Абая 55\n"
        f"⏰ Режим работы: 09:00–20:00\n\n"
        f"Чем могу помочь?",
        reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data=="my_invoices")
async def cb_invoices(cb: CallbackQuery):
    invs = await get_patient_invoices(cb.from_user.id)
    if not invs:
        await cb.message.edit_text("💰 Счетов нет.\n\n/start — назад")
        return
    text = "💰 <b>Ваши счета:</b>\n\n"
    for i in invs[:5]:
        s = "✅ Оплачен" if i["status"]=="paid" else f"⚠️ Долг: {i['total_amount']-i['paid_amount']:,} тг"
        text += f"📄 #{i['id']} от {i['created_at'][:10]}\n   {i['total_amount']:,} тг — {s}\n\n"
    await cb.message.edit_text(text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад",callback_data="back_patient")]]))

@dp.callback_query(F.data=="contacts")
async def cb_contacts(cb: CallbackQuery):
    await cb.message.answer(
        "📞 <b>Контакты клиники:</b>\n\n"
        "🏥 DENT PLUS\n📍 Алматы, ул. Абая 55\n"
        "📞 <code>+7 727 300 00 01</code>\n"
        "💬 WhatsApp: <code>+7 700 123 45 67</code>\n"
        "⏰ Пн–Сб: 09:00–20:00",
        parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data=="back_patient")
async def cb_back_patient(cb: CallbackQuery):
    p = await get_patient(cb.from_user.id)
    await cb.message.delete()
    await show_patient_menu(cb.message, p)
    await cb.answer()

# ══════════════════ DOCTOR ═══════════════════════════════════════════════════
async def show_doctor_menu(msg: Message, doctor):
    stats  = await get_doctor_stats(doctor["id"])
    rating = await get_doctor_rating(doctor["id"])
    stars  = "⭐" * int(rating["avg"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Расписание сегодня",  callback_data=f"doc_today_{doctor['id']}")],
        [InlineKeyboardButton(text="📅 Расписание завтра",   callback_data=f"doc_tmr_{doctor['id']}")],
        [InlineKeyboardButton(text="🔍 Найти пациента",      callback_data=f"doc_search_{doctor['id']}")],
        [InlineKeyboardButton(text="➕ Добавить лечение",    callback_data=f"doc_add_treat_{doctor['id']}")],
        [InlineKeyboardButton(text="🔬 Заказ в лабораторию", callback_data=f"doc_add_lab_{doctor['id']}")],
        [InlineKeyboardButton(text="📊 Моя статистика",      callback_data=f"doc_stats_{doctor['id']}")],
    ])
    salary = int(stats["month_earn"] * doctor["salary_percent"] / 100)
    await msg.answer(
        f"👨‍⚕️ Добрый день, <b>д-р {doctor['full_name']}</b>!\n"
        f"🏥 {doctor['speciality']} · Опыт: {doctor['experience_years']} лет\n"
        f"{stars} {rating['avg']} ({rating['count']} отз.)\n\n"
        f"📅 Сегодня: <b>{stats['today']}</b> пациентов\n"
        f"💰 Заработок за месяц: <b>{stats['month_earn']:,} тг</b>\n"
        f"💵 К выплате ({doctor['salary_percent']}%): <b>{salary:,} тг</b>",
        reply_markup=kb, parse_mode="HTML")

@dp.message(Command("doctor"))
async def cmd_doctor(msg: Message):
    d = await get_doctor_by_tg(msg.from_user.id)
    if d: await show_doctor_menu(msg, d)
    else: await msg.answer("⛔ Вы не зарегистрированы как врач.")

# ─ Расписание ─────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("doc_today_"))
async def cb_doc_today(cb: CallbackQuery):
    did = int(cb.data.split("_")[-1])
    doc = await get_doctor(did)
    today = date.today().strftime("%Y-%m-%d")
    appts = await get_appointments_by_date(doc["clinic_id"], today, did)
    await _send_schedule(cb.message, appts, f"📅 Расписание на сегодня ({today})")
    await cb.answer()

@dp.callback_query(F.data.startswith("doc_tmr_"))
async def cb_doc_tmr(cb: CallbackQuery):
    did = int(cb.data.split("_")[-1])
    doc = await get_doctor(did)
    tmr = (date.today()+timedelta(1)).strftime("%Y-%m-%d")
    appts = await get_appointments_by_date(doc["clinic_id"], tmr, did)
    await _send_schedule(cb.message, appts, f"📅 Расписание на завтра ({tmr})")
    await cb.answer()

async def _send_schedule(msg, appts, title):
    if not appts:
        await msg.answer(f"{title}\n\n🎉 Нет записей — свободный день!", parse_mode="HTML")
        return
    text = f"{title}:\n\n"
    for a in appts:
        em = ST.get(a["status"],"⚪")
        text += (f"{em} <b>{a['appt_time']}</b> — {a['emoji'] or '🦷'} {a['service_name'] or 'Консультация'}\n"
                 f"   👤 {a['patient_name']} · 📞 {a['phone'] or '—'}\n"
                 f"   💰 от {a['price_from'] or 0:,} тг\n\n")
    await msg.answer(text[:4000], parse_mode="HTML")

# ─ Статистика врача ───────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("doc_stats_"))
async def cb_doc_stats(cb: CallbackQuery):
    did = int(cb.data.split("_")[-1])
    doc = await get_doctor(did)
    stats  = await get_doctor_stats(did)
    rating = await get_doctor_rating(did)
    salary = int(stats["month_earn"] * doc["salary_percent"] / 100)
    await cb.message.answer(
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"📅 Сегодня: <b>{stats['today']}</b> пациентов\n"
        f"💰 Выручка (месяц): <b>{stats['month_earn']:,} тг</b>\n"
        f"💵 К выплате ({doc['salary_percent']}%): <b>{salary:,} тг</b>\n"
        f"⭐ Рейтинг: <b>{rating['avg']}</b> ({rating['count']} отзывов)",
        parse_mode="HTML")
    await cb.answer()

# ─── FSM: Добавить лечение ────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("doc_add_treat_"))
async def cb_add_treat(cb: CallbackQuery, state: FSMContext):
    did = int(cb.data.split("_")[-1])
    await state.update_data(doctor_id=did)
    await cb.message.answer(
        "➕ <b>Добавление лечения</b>\n\n"
        "Введите ФИО или телефон пациента:",
        parse_mode="HTML")
    await state.set_state(AddTreatment.select_patient)
    await cb.answer()

@dp.message(AddTreatment.select_patient)
async def fsm_treat_patient(msg: Message, state: FSMContext):
    data = await state.get_data()
    doc  = await get_doctor(data["doctor_id"])
    patients = await search_patients(doc["clinic_id"], msg.text)
    if not patients:
        await msg.answer("❌ Пациент не найден. Попробуйте ещё раз или введите точнее:")
        return
    if len(patients) == 1:
        await state.update_data(patient_id=patients[0]["id"],
                                patient_name=patients[0]["full_name"])
        await msg.answer(
            f"✅ Пациент: <b>{patients[0]['full_name']}</b>\n\n"
            f"🦷 Введите номер зуба (1-48) или 0 если без привязки к зубу:",
            parse_mode="HTML")
        await state.set_state(AddTreatment.select_tooth)
    else:
        buttons = [[InlineKeyboardButton(
            text=f"👤 {p['full_name']} · {p['phone'] or '—'}",
            callback_data=f"sel_patient_{p['id']}")] for p in patients[:5]]
        await msg.answer("Выберите пациента:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("sel_patient_"))
async def cb_sel_patient(cb: CallbackQuery, state: FSMContext):
    pid = int(cb.data.split("_")[-1])
    p   = await get_patient(pid)
    await state.update_data(patient_id=pid, patient_name=p["full_name"])
    await cb.message.answer(
        f"✅ Пациент: <b>{p['full_name']}</b>\n\n"
        f"🦷 Введите номер зуба (1-48) или 0 без привязки:",
        parse_mode="HTML")
    await state.set_state(AddTreatment.select_tooth)
    await cb.answer()

@dp.message(AddTreatment.select_tooth)
async def fsm_treat_tooth(msg: Message, state: FSMContext):
    try: tooth = int(msg.text)
    except: await msg.answer("❌ Введите число (0–48):"); return
    await state.update_data(tooth_number=tooth if tooth > 0 else None)
    await msg.answer("📝 Введите название процедуры:\n(например: Лечение кариеса, Пломба, Удаление нерва)")
    await state.set_state(AddTreatment.procedure)

@dp.message(AddTreatment.procedure)
async def fsm_treat_proc(msg: Message, state: FSMContext):
    await state.update_data(procedure_name=msg.text)
    await msg.answer("🔍 Введите диагноз (или прочерк -):")
    await state.set_state(AddTreatment.diagnosis)

@dp.message(AddTreatment.diagnosis)
async def fsm_treat_diag(msg: Message, state: FSMContext):
    await state.update_data(diagnosis=msg.text if msg.text != "-" else "")
    await msg.answer("💰 Введите стоимость лечения (только цифры, в тенге):")
    await state.set_state(AddTreatment.price)

@dp.message(AddTreatment.price)
async def fsm_treat_price(msg: Message, state: FSMContext):
    try: price = int(msg.text.replace(" ","").replace(",",""))
    except: await msg.answer("❌ Введите сумму цифрами, например: 15000"); return
    await state.update_data(price=price)
    data = await state.get_data()
    tooth_txt = f"🦷 Зуб #{data['tooth_number']}" if data.get("tooth_number") else "—"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить", callback_data="treat_save")],
        [InlineKeyboardButton(text="❌ Отмена",   callback_data="treat_cancel")],
    ])
    await msg.answer(
        f"📋 <b>Подтвердите запись:</b>\n\n"
        f"👤 Пациент: <b>{data['patient_name']}</b>\n"
        f"{tooth_txt}\n"
        f"🩺 Процедура: <b>{data['procedure_name']}</b>\n"
        f"🔍 Диагноз: {data.get('diagnosis') or '—'}\n"
        f"💰 Стоимость: <b>{price:,} тг</b>",
        reply_markup=kb, parse_mode="HTML")
    await state.set_state(AddTreatment.confirm)

@dp.callback_query(F.data=="treat_save", AddTreatment.confirm)
async def fsm_treat_save(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    doc  = await get_doctor(data["doctor_id"])
    await add_treatment({
        "clinic_id":      doc["clinic_id"],
        "patient_id":     data["patient_id"],
        "doctor_id":      data["doctor_id"],
        "appointment_id": None,
        "tooth_number":   data.get("tooth_number"),
        "procedure_name": data["procedure_name"],
        "diagnosis":      data.get("diagnosis",""),
        "description":    "",
        "price":          data["price"],
        "date":           date.today().strftime("%Y-%m-%d"),
    })
    # Обновить статус зуба если указан
    if data.get("tooth_number"):
        await update_tooth(data["patient_id"], data["tooth_number"], "treated",
                           data.get("procedure_name",""))
    await state.clear()
    await cb.message.edit_text(
        f"✅ <b>Лечение сохранено!</b>\n\n"
        f"👤 {data['patient_name']}\n"
        f"🩺 {data['procedure_name']}\n"
        f"💰 {data['price']:,} тг\n\n"
        f"Пациенту начислено +100 баллов лояльности 🏆",
        parse_mode="HTML")
    await cb.answer("✅ Сохранено!")

@dp.callback_query(F.data=="treat_cancel")
async def fsm_treat_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Отменено.")
    await cb.answer()

# ─── FSM: Лабораторный заказ ──────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("doc_add_lab_"))
async def cb_add_lab(cb: CallbackQuery, state: FSMContext):
    did = int(cb.data.split("_")[-1])
    await state.update_data(doctor_id=did)
    await cb.message.answer(
        "🔬 <b>Заказ в лабораторию</b>\n\n"
        "Введите ФИО пациента для поиска:",
        parse_mode="HTML")
    await state.set_state(AddLabOrder.select_patient)
    await cb.answer()

@dp.message(AddLabOrder.select_patient)
async def fsm_lab_patient(msg: Message, state: FSMContext):
    data = await state.get_data()
    doc  = await get_doctor(data["doctor_id"])
    patients = await search_patients(doc["clinic_id"], msg.text)
    if not patients:
        await msg.answer("❌ Не найден. Попробуйте ещё:"); return
    p = patients[0]
    await state.update_data(patient_id=p["id"], patient_name=p["full_name"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Коронка металлокерамика", callback_data="lab_type_Коронка металлокерамика")],
        [InlineKeyboardButton(text="💎 Коронка цирконий",        callback_data="lab_type_Коронка цирконий")],
        [InlineKeyboardButton(text="⭐ Винир",                    callback_data="lab_type_Винир")],
        [InlineKeyboardButton(text="🦷 Съёмный протез",          callback_data="lab_type_Съёмный протез")],
        [InlineKeyboardButton(text="🔧 Капа / ретейнер",         callback_data="lab_type_Капа/ретейнер")],
        [InlineKeyboardButton(text="✏️ Другое",                  callback_data="lab_type_Другое")],
    ])
    await msg.answer(
        f"✅ Пациент: <b>{p['full_name']}</b>\n\n"
        f"Выберите тип лабораторной работы:",
        reply_markup=kb, parse_mode="HTML")
    await state.set_state(AddLabOrder.order_type)

@dp.callback_query(F.data.startswith("lab_type_"), AddLabOrder.order_type)
async def fsm_lab_type(cb: CallbackQuery, state: FSMContext):
    order_type = cb.data.replace("lab_type_","")
    await state.update_data(order_type=order_type)
    await cb.message.answer(
        f"📦 Тип: <b>{order_type}</b>\n\n"
        f"🦷 Введите номера зубов через запятую (например: 26,27):",
        parse_mode="HTML")
    await state.set_state(AddLabOrder.tooth_nums)
    await cb.answer()

@dp.message(AddLabOrder.tooth_nums)
async def fsm_lab_teeth(msg: Message, state: FSMContext):
    await state.update_data(tooth_numbers=msg.text)
    await msg.answer("🏭 Введите название лаборатории (или -):")
    await state.set_state(AddLabOrder.lab_name)

@dp.message(AddLabOrder.lab_name)
async def fsm_lab_name(msg: Message, state: FSMContext):
    await state.update_data(lab_name=msg.text if msg.text!="-" else "")
    await msg.answer("💰 Введите стоимость заказа (только цифры):")
    await state.set_state(AddLabOrder.price)

@dp.message(AddLabOrder.price)
async def fsm_lab_price(msg: Message, state: FSMContext):
    try: price = int(msg.text.replace(" ",""))
    except: await msg.answer("❌ Только цифры!"); return
    data = await state.get_data()
    doc  = await get_doctor(data["doctor_id"])
    await create_lab_order({
        "clinic_id":    doc["clinic_id"],
        "patient_id":   data["patient_id"],
        "doctor_id":    data["doctor_id"],
        "order_type":   data["order_type"],
        "description":  data["order_type"],
        "tooth_numbers":data.get("tooth_numbers",""),
        "lab_name":     data.get("lab_name",""),
        "price":        price,
    })
    await state.clear()
    await msg.answer(
        f"✅ <b>Лабораторный заказ создан!</b>\n\n"
        f"👤 Пациент: {data['patient_name']}\n"
        f"📦 Тип: {data['order_type']}\n"
        f"🦷 Зубы: {data.get('tooth_numbers','—')}\n"
        f"🏭 Лаборатория: {data.get('lab_name') or '—'}\n"
        f"💰 Стоимость: {price:,} тг\n\n"
        f"Вы получите уведомление когда заказ будет готов 🔔",
        parse_mode="HTML")

# ─── Поиск пациента ───────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("doc_search_"))
async def cb_doc_search(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("🔍 Введите ФИО или номер телефона пациента:")
    await state.update_data(doctor_id=int(cb.data.split("_")[-1]), action="search")
    await state.set_state(AddTreatment.select_patient)
    await cb.answer()

# ══════════════════ ADMIN ════════════════════════════════════════════════════
async def show_admin_menu(msg: Message, clinic):
    if not clinic:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏥 Зарегистрировать клинику", callback_data="reg_clinic")]])
        await msg.answer(
            "👑 <b>Супер-Админ</b>\n\nКлиника не зарегистрирована.",
            reply_markup=kb, parse_mode="HTML"); return
    stats = await get_clinic_stats(clinic["id"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 Записи сегодня ({stats['today_appts']})", callback_data=f"adm_today_{clinic['id']}")],
        [InlineKeyboardButton(text="📋 Все предстоящие",    callback_data=f"adm_upcoming_{clinic['id']}")],
        [InlineKeyboardButton(text="🔬 Лаборатория",        callback_data=f"adm_lab_{clinic['id']}")],
        [InlineKeyboardButton(text="👥 Пациенты",           callback_data=f"adm_patients_{clinic['id']}")],
        [InlineKeyboardButton(text="💰 Финансы",            callback_data=f"adm_finance_{clinic['id']}")],
        [InlineKeyboardButton(text="📊 Статистика",         callback_data=f"adm_stats_{clinic['id']}")],
        [InlineKeyboardButton(text="🌐 Веб-панель",         callback_data=f"adm_weblink_{clinic['id']}")],
        [InlineKeyboardButton(text="🔗 Ссылка для записи",  callback_data=f"adm_link_{clinic['id']}")],
    ])
    await msg.answer(
        f"🏥 <b>{clinic['name']}</b>\n📍 {clinic['address']}\n\n"
        f"📅 Сегодня: <b>{stats['today_appts']}</b> записей\n"
        f"💰 Сегодня: <b>{stats['today_rev']:,} тг</b>\n"
        f"💰 Месяц: <b>{stats['month_rev']:,} тг</b>\n"
        f"⚠️ Долги: <b>{stats['total_debt']:,} тг</b>\n"
        f"👥 Пациентов: <b>{stats['total_patients']}</b>",
        reply_markup=kb, parse_mode="HTML")

@dp.message(Command("admin"))
async def cmd_admin(msg: Message):
    c = await get_clinic_by_admin(msg.from_user.id)
    await show_admin_menu(msg, c)

# ─ Записи сегодня ─────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_today_"))
async def cb_adm_today(cb: CallbackQuery):
    cid   = int(cb.data.split("_")[-1])
    today = date.today().strftime("%Y-%m-%d")
    appts = await get_appointments_by_date(cid, today)
    if not appts:
        await cb.message.answer("📅 Записей на сегодня нет."); await cb.answer(); return
    text = f"📅 <b>Записи на {today}:</b>\n\n"
    buttons = []
    for a in appts:
        em = ST.get(a["status"],"⚪")
        text += (f"{em} <b>{a['appt_time']}</b> | 👨‍⚕️ {a['doctor_name']}\n"
                 f"   {a['emoji'] or '🦷'} {a['service_name'] or 'Консультация'}\n"
                 f"   👤 {a['patient_name']} · 📞 {a['phone'] or '—'}\n\n")
        if a["status"] == "pending":
            buttons.append([
                InlineKeyboardButton(text=f"✅ #{a['id']}",  callback_data=f"ac_{a['id']}_confirmed"),
                InlineKeyboardButton(text=f"❌ #{a['id']}",  callback_data=f"ac_{a['id']}_cancelled"),
                InlineKeyboardButton(text=f"✔ #{a['id']}",  callback_data=f"ac_{a['id']}_done"),
            ])
    await cb.message.answer(text[:4000],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("ac_"))
async def cb_appt_action(cb: CallbackQuery):
    parts  = cb.data.split("_")
    aid    = int(parts[1])
    status = parts[2]
    await update_appointment_status(aid, status)
    labels = {"confirmed":"✅ Подтверждено","cancelled":"❌ Отменено","done":"💚 Выполнено"}
    await cb.answer(labels.get(status,"Обновлено"))

# ─ Все предстоящие ────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_upcoming_"))
async def cb_adm_upcoming(cb: CallbackQuery):
    cid   = int(cb.data.split("_")[-1])
    today = date.today().strftime("%Y-%m-%d")
    tmr   = (date.today()+timedelta(1)).strftime("%Y-%m-%d")
    appts = await get_appointments_by_date(cid, tmr)
    if not appts:
        await cb.message.answer("📋 Завтра записей нет."); await cb.answer(); return
    text = f"📋 <b>Записи на завтра ({tmr}):</b>\n\n"
    for a in appts:
        em = ST.get(a["status"],"⚪")
        text += (f"{em} <b>{a['appt_time']}</b> — {a['service_name'] or 'Консультация'}\n"
                 f"   👤 {a['patient_name']} | 👨‍⚕️ {a['doctor_name']}\n\n")
    await cb.message.answer(text[:4000], parse_mode="HTML")
    await cb.answer()

# ─ Лаборатория ────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_lab_"))
async def cb_adm_lab(cb: CallbackQuery):
    cid    = int(cb.data.split("_")[-1])
    orders = await get_lab_orders(cid)
    if not orders:
        await cb.message.answer("🔬 Нет активных лаб. заказов."); await cb.answer(); return
    text = "🔬 <b>Лабораторные заказы:</b>\n\n"
    buttons = []
    smap = {"ordered":"📤","in_progress":"⚙️","ready":"✅"}
    for o in orders:
        text += (f"{smap.get(o['status'],'?')} #{o['id']} — {o['order_type']}\n"
                 f"   👤 {o['patient_name']} | 👨‍⚕️ {o['doctor_name']}\n"
                 f"   🦷 Зубы: {o['tooth_numbers'] or '—'} | 💰 {o['price']:,} тг\n\n")
        if o["status"] != "ready":
            buttons.append([InlineKeyboardButton(
                text=f"✅ Готово #{o['id']}", callback_data=f"lab_rdy_{o['id']}")])
    await cb.message.answer(text[:4000],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("lab_rdy_"))
async def cb_lab_ready(cb: CallbackQuery):
    oid = int(cb.data.split("_")[-1])
    await update_lab_order_status(oid, "ready", date.today().strftime("%Y-%m-%d"))
    await cb.answer("✅ Помечено как готово!")

# ─ Пациенты ───────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_patients_"))
async def cb_adm_patients(cb: CallbackQuery):
    cid = int(cb.data.split("_")[-1])
    ps  = await get_all_patients(cid)
    text = f"👥 <b>Пациентов всего: {len(ps)}</b>\n\n"
    for p in ps[:10]:
        text += f"👤 {p['full_name']} · 📞 {p['phone'] or '—'} · Визитов: {p['visits_count'] or 0}\n"
    if len(ps) > 10: text += f"\n... и ещё {len(ps)-10} пациентов"
    await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()

# ─ Финансы ────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_finance_"))
async def cb_adm_finance(cb: CallbackQuery):
    cid   = int(cb.data.split("_")[-1])
    stats = await get_clinic_stats(cid)
    await cb.message.answer(
        f"💰 <b>Финансовый отчёт:</b>\n\n"
        f"📅 Сегодня: <b>{stats['today_rev']:,} тг</b>\n"
        f"📅 За месяц: <b>{stats['month_rev']:,} тг</b>\n"
        f"⚠️ Долги: <b>{stats['total_debt']:,} тг</b>\n\n"
        f"🌐 Подробно: /admin → Веб-панель",
        parse_mode="HTML")
    await cb.answer()

# ─ Статистика ─────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_stats_"))
async def cb_adm_stats(cb: CallbackQuery):
    cid   = int(cb.data.split("_")[-1])
    stats = await get_clinic_stats(cid)
    await cb.message.answer(
        f"📊 <b>Статистика клиники:</b>\n\n"
        f"👥 Пациентов: <b>{stats['total_patients']}</b>\n"
        f"📅 Всего записей: <b>{stats['total_appts']}</b>\n"
        f"📅 Сегодня: <b>{stats['today_appts']}</b>\n"
        f"💰 Месяц: <b>{stats['month_rev']:,} тг</b>\n"
        f"💰 Сегодня: <b>{stats['today_rev']:,} тг</b>\n"
        f"⚠️ Долги: <b>{stats['total_debt']:,} тг</b>",
        parse_mode="HTML")
    await cb.answer()

# ─ Ссылки ─────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("adm_link_"))
async def cb_adm_link(cb: CallbackQuery):
    info = await bot.get_me()
    link = f"https://t.me/{info.username}"
    await cb.message.answer(
        f"🔗 <b>Ссылка для записи пациентов:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"📌 Разместите на:\n"
        f"• Instagram / 2GIS / Сайт\n"
        f"• WhatsApp визитка\n"
        f"• QR-код на стойке регистрации",
        parse_mode="HTML")
    await cb.answer()

@dp.callback_query(F.data.startswith("adm_weblink_"))
async def cb_adm_weblink(cb: CallbackQuery):
    webapp = os.getenv("WEBAPP_URL","https://example.com")
    await cb.message.answer(
        f"🌐 <b>Веб-панель администратора:</b>\n\n"
        f"<code>{webapp}/admin</code>\n\n"
        f"Откройте в браузере на компьютере для удобного управления клиникой 💻",
        parse_mode="HTML")
    await cb.answer()

# ─ Регистрация клиники FSM ────────────────────────────────────────────────────
@dp.callback_query(F.data=="reg_clinic")
async def cb_reg_clinic(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("🏥 Введите название клиники:")
    await state.set_state(RegBusiness.name)
    await cb.answer()

@dp.message(RegBusiness.name)
async def fsm_reg_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await msg.answer("📍 Введите адрес клиники:")
    await state.set_state(RegBusiness.address)

@dp.message(RegBusiness.address)
async def fsm_reg_addr(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text)
    await msg.answer("📞 Введите номер телефона клиники:")
    await state.set_state(RegBusiness.phone)

@dp.message(RegBusiness.phone)
async def fsm_reg_phone(msg: Message, state: FSMContext):
    data = await state.get_data()
    from database import register_business
    await register_business(msg.from_user.id, data["name"], data["address"], msg.text)
    await state.clear()
    await msg.answer(
        f"✅ <b>Клиника зарегистрирована!</b>\n\n"
        f"🏥 {data['name']}\n📍 {data['address']}\n📞 {msg.text}\n\n"
        f"Напишите /admin для управления",
        parse_mode="HTML")

# ══════════════════ УВЕДОМЛЕНИЯ ══════════════════════════════════════════════
async def notify_new_booking(admin_id: int, doc_tg_id: int, info: dict):
    text = (f"🔔 <b>НОВАЯ ЗАПИСЬ!</b>\n\n"
            f"👤 {info['patient_name']}\n"
            f"📞 {info.get('phone','—')}\n"
            f"👨‍⚕️ {info['doctor_name']}\n"
            f"🦷 {info.get('service_name','Консультация')}\n"
            f"📅 {info['appt_date']} · 🕐 {info['appt_time']}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"ac_{info['appt_id']}_confirmed"),
        InlineKeyboardButton(text="❌ Отменить",    callback_data=f"ac_{info['appt_id']}_cancelled"),
    ]])
    for tid in set(filter(None,[admin_id, doc_tg_id])):
        try: await bot.send_message(tid, text, reply_markup=kb, parse_mode="HTML")
        except: pass

async def notify_patient(patient_id: int, text: str):
    try: await bot.send_message(patient_id, text, parse_mode="HTML")
    except: pass

# ══════════════════ ЗАПУСК ═══════════════════════════════════════════════════
async def start_polling():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(start_polling())
