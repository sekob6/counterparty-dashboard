import streamlit as st
import pandas as pd
import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from supabase import create_client, Client
import io
import uuid
import mimetypes
import os
from datetime import datetime
from pathlib import Path

st.set_page_config(
    page_title="Стоп-лист контрагентов",
    page_icon="🚫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
#  СЕКРЕТЫ (Supabase)
#  Приоритет: переменные окружения -> st.secrets (для локалки)
# =========================================================
DB_URL    = os.environ.get("SUPABASE_DB_URL")
SUPA_URL  = os.environ.get("SUPABASE_URL")
SUPA_KEY  = os.environ.get("SUPABASE_KEY")
BUCKET    = os.environ.get("SUPABASE_BUCKET", "attachments")

if not all([DB_URL, SUPA_URL, SUPA_KEY]):
    try:
        DB_URL   = st.secrets["supabase"]["db_url"]
        SUPA_URL = st.secrets["supabase"]["url"]
        SUPA_KEY = st.secrets["supabase"]["key"]
        BUCKET   = st.secrets["supabase"].get("bucket", "attachments")
    except Exception:
        st.error(
            "⚠️ Не настроены секреты Supabase.\n\n"
            "Для облака задайте переменные окружения: SUPABASE_DB_URL, SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET.\n"
            "Для локального запуска — создайте файл `.streamlit/secrets.toml`."
        )
        st.stop()

# =========================================================
#  КАСТОМНАЯ ТЕМА
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp { font-family: 'Inter', -apple-system, sans-serif; }

.stApp {
    background: radial-gradient(ellipse at top left, #1a1f3a 0%, #0f1220 45%, #07080f 100%);
    color: #e6e9f0;
}

[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }

[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 999999 !important;
}
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="collapsedControl"] svg {
    fill: #a4b1ff !important;
    color: #a4b1ff !important;
}
[data-testid="stSidebarCollapsedControl"]:hover svg,
[data-testid="collapsedControl"]:hover svg {
    fill: #ffffff !important;
    color: #ffffff !important;
}

.main .block-container {
    padding-top: 0.4rem;
    padding-bottom: 4rem;
    padding-left: 0.4rem;
    padding-right: 0.4rem;
    max-width: 100%;
}
.main .block-container > div:first-child { margin-top: 0; }

h1, h2, h3, h4 { color: #f5f7ff !important; font-weight: 700 !important; letter-spacing: -0.02em; }
h1 { font-size: 1.7rem !important; }
h2 { font-size: 1.35rem !important; }
h3 { font-size: 1.1rem !important; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #141829 0%, #0d101c 100%);
    border-right: 1px solid rgba(120, 130, 200, 0.12);
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0.9rem; }
[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: 0.55rem 0.85rem;
    margin: 3px 0;
    border-radius: 10px;
    transition: all 0.18s;
    cursor: pointer;
    border-left: 3px solid transparent;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: rgba(120, 130, 220, 0.1);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
    background: linear-gradient(90deg, rgba(107,124,255,0.22), rgba(107,124,255,0.02));
    border-left: 3px solid #6b7cff;
}

.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
    background: linear-gradient(135deg, #4f5bd5 0%, #6b7cff 100%);
    color: #ffffff !important;
    border: none;
    border-radius: 10px;
    padding: 0.5rem 1.15rem;
    font-weight: 600;
    transition: all 0.2s;
    box-shadow: 0 4px 14px rgba(79, 91, 213, 0.28);
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 22px rgba(107, 124, 255, 0.5);
    background: linear-gradient(135deg, #5a66dd 0%, #7a8bff 100%);
    color: #ffffff !important;
}
.stButton > button:active { transform: translateY(0); }

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput input,
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    background: rgba(255,255,255,0.045) !important;
    border: 1px solid rgba(120,130,200,0.2) !important;
    color: #e6e9f0 !important;
    border-radius: 10px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #6b7cff !important;
    box-shadow: 0 0 0 3px rgba(107,124,255,0.18) !important;
}

[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(120,130,200,0.15);
}

[data-testid="stForm"] {
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(120,130,200,0.14);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
}

[data-testid="stExpander"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(120,130,200,0.15) !important;
    border-radius: 12px !important;
    overflow: hidden;
}
[data-testid="stExpander"] summary:hover { color: #a4b1ff; }

[data-testid="stAlert"] { border-radius: 12px; border-left-width: 4px; }
hr { border-color: rgba(120,130,200,0.12); }

[data-testid="stFileUploaderDropzone"] {
    background: rgba(107,124,255,0.05) !important;
    border: 2px dashed rgba(107,124,255,0.35) !important;
    border-radius: 12px !important;
    transition: all 0.2s;
}
[data-testid="stFileUploaderDropzone"]:hover {
    background: rgba(107,124,255,0.1) !important;
    border-color: rgba(107,124,255,0.6) !important;
}

.hero-card {
    background: linear-gradient(135deg, rgba(107,124,255,0.16), rgba(180,100,255,0.07));
    border: 1px solid rgba(120,130,220,0.22);
    border-radius: 16px;
    padding: 2.2rem 2rem;
    margin: 0 0 1.2rem 0;
    backdrop-filter: blur(12px);
    position: relative;
    overflow: hidden;
    width: 100%;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 20px;
    min-height: 120px;
}
.hero-card::before {
    content: "";
    position: absolute;
    top: -80%; right: -5%;
    width: 420px; height: 420px;
    background: radial-gradient(circle, rgba(107,124,255,0.28) 0%, transparent 70%);
    pointer-events: none;
}
.hero-icon {
    width: 54px; height: 54px;
    flex: 0 0 54px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 14px;
    background: linear-gradient(135deg, #4f5bd5 0%, #7a5bff 100%);
    box-shadow: 0 6px 20px rgba(107,124,255,0.45);
    position: relative;
    z-index: 1;
}
.hero-icon svg { width: 26px; height: 26px; }
.hero-text { position: relative; z-index: 1; min-width: 0; }
.hero-title {
    font-size: 1.35rem;
    font-weight: 800;
    background: linear-gradient(90deg, #c3cdff 0%, #e2cdff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1.2;
}
.hero-sub { color: #a4b1d8; margin: 0; font-size: 1rem; font-weight: 500; }

.status-pill {
    display: inline-block; padding: 3px 12px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600;
}
.status-active  { background: rgba(60,220,130,0.14); color: #4ade80; border: 1px solid rgba(60,220,130,0.35); }
.status-removed { background: rgba(250,200,60,0.12); color: #fbbf24; border: 1px solid rgba(250,200,60,0.3); }

.card-info {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(120,130,200,0.15);
    border-radius: 14px;
    padding: 1rem 1.3rem;
    margin-bottom: 1rem;
}
.card-info-row { margin: 6px 0; }
.card-info-label { color: #8891b5; font-size: 0.82rem; }
.card-info-value { color: #e6e9f0; font-weight: 500; }

.side-user-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(120,130,200,0.18);
    border-radius: 12px;
    padding: 0.7rem 0.9rem;
    margin-bottom: 0.7rem;
}
</style>
""", unsafe_allow_html=True)

PAGE_SIZE = 50

# =========================================================
#  ПОДКЛЮЧЕНИЯ
# =========================================================
def get_conn():
    """Свежее соединение с PostgreSQL."""
    return psycopg2.connect(DB_URL, connect_timeout=15)

def get_dict_cursor(conn):
    return conn.cursor(cursor_factory=RealDictCursor)

@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    """Клиент Supabase Storage (кэшируется на всё время работы приложения)."""
    return create_client(SUPA_URL, SUPA_KEY)

# =========================================================
#  ПРОВЕРКА АДМИНА
#  Таблицы уже созданы вручную через SQL Editor Supabase,
#  поэтому здесь только проверяем наличие стартового admin.
# =========================================================
def ensure_admin():
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        cnt = c.fetchone()[0]
        if cnt == 0:
            pw = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            c.execute(
                "INSERT INTO users (username, password_hash, role, full_name, created_at) "
                "VALUES (%s, %s, 'admin', %s, %s)",
                ("admin", pw, "Администратор", datetime.now())
            )
            conn.commit()
        c.close()
        conn.close()
    except Exception as e:
        st.warning(f"Не удалось проверить наличие администратора: {e}")

ensure_admin()

# =========================================================
#  ЛОГИКА БД
# =========================================================
def log_action(username, action, entity="", entity_id="", details=""):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO audit_log (username, action, entity, entity_id, details, ts) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (username, action, entity, entity_id, details, datetime.now())
        )
        conn.commit(); c.close(); conn.close()
    except Exception as e:
        print(f"log_action failed: {e}")

def verify_user(username, password):
    conn = get_conn()
    c = get_dict_cursor(conn)
    c.execute("SELECT * FROM users WHERE username = %s", (username,))
    row = c.fetchone()
    c.close(); conn.close()
    if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return dict(row)
    return None

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def role_label(r):
    return {"admin": "администратор", "editor": "редактор", "viewer": "пользователь",
            "user": "пользователь"}.get(r, r)

# =========================================================
#  ФАЙЛЫ — Supabase Storage
# =========================================================
def human_size(n):
    if n is None: return "—"
    n = float(n)
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ТБ"

def is_image(mime, filename):
    if mime and mime.startswith("image/"): return True
    return Path(filename).suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

def is_pdf(mime, filename):
    if mime == "application/pdf": return True
    return Path(filename).suffix.lower() == ".pdf"

def save_attachments(company_id, files, username):
    if not files: return 0
    supa = get_supabase()
    conn = get_conn(); c = conn.cursor()
    saved = 0
    for f in files:
        ext = Path(f.name).suffix
        stored = f"{company_id}/{uuid.uuid4().hex}{ext}"
        data = f.getvalue()
        try:
            supa.storage.from_(BUCKET).upload(
                stored, data,
                file_options={"content-type": f.type or "application/octet-stream"}
            )
        except Exception as e:
            st.error(f"Не удалось загрузить файл {f.name}: {e}")
            continue
        mime = f.type or mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        c.execute(
            "INSERT INTO attachments "
            "(company_id, filename, stored_name, size, mime, uploaded_by, uploaded_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (company_id, f.name, stored, len(data), mime, username, datetime.now())
        )
        saved += 1
    conn.commit(); c.close(); conn.close()
    return saved

def get_attachments(company_id):
    conn = get_conn()
    c = get_dict_cursor(conn)
    c.execute(
        "SELECT * FROM attachments WHERE company_id = %s ORDER BY id DESC",
        (company_id,)
    )
    rows = c.fetchall()
    c.close(); conn.close()
    return [dict(r) for r in rows]

def delete_attachment(att_id, username):
    conn = get_conn()
    c = get_dict_cursor(conn)
    c.execute("SELECT * FROM attachments WHERE id = %s", (att_id,))
    row = c.fetchone()
    if not row:
        c.close(); conn.close(); return False
    try:
        get_supabase().storage.from_(BUCKET).remove([row["stored_name"]])
    except Exception as e:
        print(f"Storage remove failed: {e}")
    c.execute("DELETE FROM attachments WHERE id = %s", (att_id,))
    conn.commit(); c.close(); conn.close()
    log_action(username, "DELETE_ATTACHMENT", "attachment", str(att_id), row["filename"])
    return True

def delete_all_attachments(company_id):
    atts = get_attachments(company_id)
    if not atts:
        return
    paths = [a["stored_name"] for a in atts]
    try:
        get_supabase().storage.from_(BUCKET).remove(paths)
    except Exception as e:
        print(f"Storage bulk remove failed: {e}")

def signed_url(stored_name, expires=3600):
    try:
        res = get_supabase().storage.from_(BUCKET).create_signed_url(stored_name, expires)
        return res.get("signedURL") or res.get("signedUrl") or res.get("signed_url")
    except Exception as e:
        print(f"Signed URL failed: {e}")
        return None

def render_attachments(cid, username, can_delete=False, prefix="view"):
    atts = get_attachments(cid)
    if not atts:
        st.caption("Нет прикреплённых файлов")
        return 0
    for att in atts:
        title = f"📄  {att['filename']}  ·  {human_size(att['size'])}"
        with st.expander(title):
            st.caption(f"Загружено: {att['uploaded_by']} · {att['uploaded_at']}")
            url = signed_url(att["stored_name"])
            if not url:
                st.warning("Не удалось получить ссылку на файл")
                continue
            if is_image(att["mime"], att["filename"]):
                st.image(url, use_container_width=True)
            elif is_pdf(att["mime"], att["filename"]):
                st.markdown(
                    f'<iframe src="{url}" width="100%" height="600px" '
                    f'style="border:1px solid rgba(120,130,200,0.2);border-radius:8px;"></iframe>',
                    unsafe_allow_html=True)
            try:
                data = get_supabase().storage.from_(BUCKET).download(att["stored_name"])
                st.download_button("⬇️ Скачать", data,
                                   file_name=att["filename"],
                                   key=f"{prefix}_dl_{att['id']}")
            except Exception as e:
                st.caption(f"Скачивание недоступно: {e}")
            if can_delete:
                if st.button("🗑 Удалить файл", key=f"{prefix}_del_{att['id']}"):
                    delete_attachment(att["id"], username)
                    st.session_state.flash = f"Файл {att['filename']} удалён"
                    st.rerun()
    return len(atts)

# =========================================================
#  СЕССИЯ
# =========================================================
if "user" not in st.session_state:
    st.session_state.user = None

# =========================================================
#  ВХОД
# =========================================================
def login_page():
    st.markdown("""
    <div class="hero-card" style="max-width: 500px; margin: 3rem auto 1.5rem; min-height: auto;">
        <div class="hero-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <line x1="4" y1="4" x2="20" y2="20"/>
            </svg>
        </div>
        <div class="hero-text">
            <p class="hero-title">Стоп-лист контрагентов</p>
            <p class="hero-sub">Вход в систему · введите ваши учётные данные</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login"):
            u = st.text_input("👤 Логин", placeholder="Введите логин")
            p = st.text_input("🔒 Пароль", type="password", placeholder="Введите пароль")
            ok = st.form_submit_button("→  Войти", use_container_width=True)
        if ok:
            try:
                usr = verify_user(u, p)
            except Exception as e:
                st.error(f"Ошибка подключения к базе: {e}")
                usr = None
            if usr:
                prev_login = usr.get("last_login_at")
                now = datetime.now()
                cnt = 0
                try:
                    conn = get_conn()
                    c = conn.cursor()
                    if prev_login:
                        c.execute(
                            """SELECT COUNT(*) FROM audit_log
                               WHERE ts > %s AND username != %s
                                 AND action IN ('ADD_COMPANY','EDIT_COMPANY','DELETE_COMPANY',
                                                'REMOVE_COMPANY','RESTORE_COMPANY','IMPORT')""",
                            (prev_login, usr["username"]))
                        cnt = c.fetchone()[0]
                    c.execute("UPDATE users SET last_login_at=%s WHERE id=%s", (now, usr["id"]))
                    conn.commit(); c.close(); conn.close()
                except Exception as e:
                    print(f"Login bookkeeping failed: {e}")

                st.session_state.user = usr
                st.session_state.notify_count = cnt
                log_action(u, "LOGIN", "user", str(usr["id"]))
                st.rerun()
            else:
                st.error("Неверный логин или пароль")

if not st.session_state.user:
    login_page(); st.stop()

user = st.session_state.user
role = user["role"]
is_admin = role == "admin"
is_editor = role in ("admin", "editor")

CATEGORIES = ["Мошенничество", "Суд/претензии", "Налоговые риски",
              "Банкротство", "Отказ в сотрудничестве", "Прочее"]

pages = ["🔍 Проверить ИНН", "📋 Список", "🔑 Сменить пароль"]
if is_editor:
    pages += ["➕ Добавить", "✏️ Редактировать", "🚫 Снять / Вернуть",
              "📎 Файлы", "📥 Импорт", "📜 История компании"]
if is_admin:
    pages += ["🗑 Удалить", "👥 Пользователи", "📜 Журнал"]

# ---------- САЙДБАР ----------
with st.sidebar:
    role_icon = "🛡️" if is_admin else ("✏️" if is_editor else "👤")
    st.markdown(
        f"""<div class="side-user-card">
            <div style="color:#e6e9f0;font-weight:600;font-size:0.9rem;">{role_icon} {user.get('full_name') or user['username']}</div>
            <div style="color:#7b85a8;font-size:0.75rem;margin-top:2px;">{role_label(role)}</div>
        </div>""",
        unsafe_allow_html=True)

    if st.button("🚪 Выйти", use_container_width=True):
        log_action(user["username"], "LOGOUT", "user", str(user["id"]))
        st.session_state.user = None; st.rerun()

    st.markdown("<hr style='margin: 0.9rem 0;'>", unsafe_allow_html=True)
    page = st.radio("Раздел", pages, label_visibility="collapsed")

# ---------- ЗАГОЛОВОК ----------
st.markdown("""
<div class="hero-card">
    <div class="hero-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            <line x1="4" y1="4" x2="20" y2="20"/>
        </svg>
    </div>
    <div class="hero-text">
        <p class="hero-sub">Единая база не рекомендованных контрагентов</p>
    </div>
</div>
""", unsafe_allow_html=True)

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

if "notify_count" in st.session_state:
    cnt = st.session_state.pop("notify_count")
    if is_admin and cnt > 0:
        st.info(f"📣 С вашего последнего входа в стоп-листе произошло изменений: **{cnt}**. "
                f"Подробности — в разделе «📜 Журнал».")

# =========================================================
#  РАЗДЕЛЫ
# =========================================================

if page == "🔍 Проверить ИНН":
    st.subheader("🔍 Проверка контрагента по ИНН")
    c1, c2 = st.columns([3, 1])
    with c1:
        inn = st.text_input("Введите ИНН", max_chars=12, placeholder="Например, 7707083893").strip()
    with c2:
        st.write(""); st.write("")
        check = st.button("Проверить", type="primary", use_container_width=True)

    if check and inn:
        conn = get_conn()
        c = get_dict_cursor(conn)
        c.execute("SELECT * FROM companies WHERE inn = %s", (inn,))
        row = c.fetchone()
        c.close(); conn.close()
        log_action(user["username"], "CHECK_INN", "check", inn, "найден" if row else "не найден")
        if row and row["status"] == "active":
            st.markdown(f"""
            <div class="card-info" style="border-left: 4px solid #ef4444; background: rgba(239,68,68,0.06);">
                <div style="font-size:1.15rem;font-weight:700;color:#f5f7ff;">❌ {inn} — НАЙДЕН в стоп-листе</div>
                <div style="margin-top:4px;"><span class="status-pill status-active">🟢 активен</span></div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="card-info">
                <div class="card-info-row"><span class="card-info-label">Название</span><br><span class="card-info-value">{row['name'] or '—'}</span></div>
                <div class="card-info-row"><span class="card-info-label">Категория</span><br><span class="card-info-value">{row['category'] or '—'}</span></div>
                <div class="card-info-row"><span class="card-info-label">Причина включения</span><br><span class="card-info-value">{row['reason'] or '—'}</span></div>
                <div class="card-info-row"><span class="card-info-label">Комментарий</span><br><span class="card-info-value">{row['comment'] or '—'}</span></div>
                <div class="card-info-row"><span class="card-info-label">Добавлен</span><br><span class="card-info-value">{row['added_by']} · {row['added_at']}</span></div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"**📎 Прикреплённые файлы: {len(get_attachments(row['id']))}**")
            render_attachments(row["id"], user["username"], can_delete=False, prefix="inn_active")

        elif row and row["status"] == "removed":
            st.markdown(f"""
            <div class="card-info" style="border-left: 4px solid #fbbf24; background: rgba(251,191,36,0.06);">
                <div style="font-size:1.15rem;font-weight:700;color:#f5f7ff;">⚠️ {inn} — был в стоп-листе, СНЯТ</div>
                <div style="margin-top:4px;"><span class="status-pill status-removed">🟡 снят</span></div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="card-info">
                <div class="card-info-row"><span class="card-info-label">Название</span><br><span class="card-info-value">{row['name'] or '—'}</span></div>
                <div class="card-info-row"><span class="card-info-label">Категория</span><br><span class="card-info-value">{row['category'] or '—'}</span></div>
                <div class="card-info-row"><span class="card-info-label">Причина включения</span><br><span class="card-info-value">{row['reason'] or '—'}</span></div>
                <div class="card-info-row"><span class="card-info-label">Добавлен</span><br><span class="card-info-value">{row['added_by']} · {row['added_at']}</span></div>
                <div class="card-info-row"><span class="card-info-label">Снят</span><br><span class="card-info-value">{row['removed_by'] or '—'} · {row['removed_at'] or '—'}</span></div>
                <div class="card-info-row"><span class="card-info-label">Причина снятия</span><br><span class="card-info-value">{row['removed_reason'] or '—'}</span></div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"**📎 Прикреплённые файлы: {len(get_attachments(row['id']))}**")
            render_attachments(row["id"], user["username"], can_delete=False, prefix="inn_removed")

        else:
            st.markdown(f"""
            <div class="card-info" style="border-left: 4px solid #4ade80; background: rgba(74,222,128,0.06);">
                <div style="font-size:1.15rem;font-weight:700;color:#f5f7ff;">✅ ИНН {inn} не найден в стоп-листе</div>
                <div style="color:#8f97b8;margin-top:4px;font-size:0.9rem;">Контрагент не числится в списке нерекомендованных</div>
            </div>
            """, unsafe_allow_html=True)

elif page == "📋 Список":
    st.subheader("📋 Список нерекомендованных контрагентов")
    conn = get_conn()
    df = pd.read_sql_query(
        """SELECT c.id, c.inn, c.name, c.category, c.reason, c.comment,
                  c.added_by, c.added_at, c.status, c.removed_at, c.removed_by, c.removed_reason,
                  (SELECT COUNT(*) FROM attachments a WHERE a.company_id = c.id) AS files_count
           FROM companies c ORDER BY c.added_at DESC""", conn)
    conn.close()
    if df.empty:
        st.info("Список пуст")
    else:
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            q = st.text_input("🔎 Поиск", placeholder="ИНН / название / категория")
        with c2:
            cats = sorted(df["category"].dropna().unique().tolist())
            cat_filter = st.multiselect("Категории", cats)
        with c3:
            status_filter = st.selectbox("Статус", ["Все", "Активные", "Снятые"])

        v = df.copy()
        if q:
            v = v[v.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
        if cat_filter:
            v = v[v["category"].isin(cat_filter)]
        if status_filter == "Активные":
            v = v[v["status"] == "active"]
        elif status_filter == "Снятые":
            v = v[v["status"] == "removed"]

        if "list_page" not in st.session_state:
            st.session_state.list_page = 1
        total = len(v)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if st.session_state.list_page > total_pages:
            st.session_state.list_page = total_pages

        pc1, pc2, pc3 = st.columns([1, 1, 4])
        with pc1:
            if st.button("◀ Назад", disabled=(st.session_state.list_page <= 1)):
                st.session_state.list_page -= 1
                st.rerun()
        with pc2:
            if st.button("Вперёд ▶", disabled=(st.session_state.list_page >= total_pages)):
                st.session_state.list_page += 1
                st.rerun()
        with pc3:
            st.caption(f"📄 Страница {st.session_state.list_page} из {total_pages} · всего {total} записей")

        start = (st.session_state.list_page - 1) * PAGE_SIZE
        page_df = v.iloc[start:start + PAGE_SIZE].copy()

        page_df["status"] = page_df["status"].apply(
            lambda s: "🟢 активен" if s == "active" else "🟡 снят")
        show_df = page_df.drop(columns=["id"]).rename(columns={
            "inn": "ИНН", "name": "Название", "category": "Категория",
            "reason": "Причина", "comment": "Комментарий",
            "added_by": "Добавил", "added_at": "Дата добавления",
            "status": "Статус", "removed_at": "Снят",
            "removed_by": "Кто снял", "removed_reason": "Причина снятия",
            "files_count": "📎 Файлов",
        })
        st.dataframe(show_df, use_container_width=True, hide_index=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            v.drop(columns=["id"]).to_excel(w, index=False, sheet_name="Стоп-лист")
        st.download_button("📥 Скачать в Excel (все отфильтрованные)",
                           buf.getvalue(), file_name="stop-list.xlsx")

elif page == "🔑 Сменить пароль":
    st.subheader("🔑 Смена пароля")
    st.caption(f"Вы вошли как **{user['username']}**")
    with st.form("change_pw", clear_on_submit=True):
        old = st.text_input("Текущий пароль", type="password")
        new1 = st.text_input("Новый пароль", type="password")
        new2 = st.text_input("Повторите новый пароль", type="password")
        ok = st.form_submit_button("Сменить пароль", type="primary")
    if ok:
        if not old or not new1 or not new2:
            st.error("Заполните все поля")
        elif new1 != new2:
            st.error("Новые пароли не совпадают")
        elif len(new1) < 6:
            st.error("Пароль должен быть не короче 6 символов")
        elif not verify_user(user["username"], old):
            st.error("Текущий пароль неверен")
        else:
            conn = get_conn(); c = conn.cursor()
            c.execute("UPDATE users SET password_hash = %s WHERE id = %s",
                      (hash_pw(new1), user["id"]))
            conn.commit(); c.close(); conn.close()
            log_action(user["username"], "CHANGE_PASSWORD", "user", str(user["id"]))
            st.session_state.flash = "Пароль успешно изменён"
            st.rerun()

elif page == "➕ Добавить" and is_editor:
    st.subheader("➕ Добавить компанию в стоп-лист")
    with st.form("add_company", clear_on_submit=True):
        inn = st.text_input("ИНН *", max_chars=12)
        name = st.text_input("Название компании")
        category = st.selectbox("Категория", CATEGORIES)
        reason = st.text_area("Причина включения")
        comment = st.text_area("Комментарий")
        st.markdown("**📎 Прикрепить файлы** — PDF, фото, документы (можно несколько)")
        files = st.file_uploader("Выберите файлы", accept_multiple_files=True,
                                 key="add_files", label_visibility="collapsed")
        ok = st.form_submit_button("➕ Добавить", type="primary")
    if ok:
        inn = inn.strip()
        if not inn:
            st.error("Укажите ИНН")
        else:
            conn = get_conn()
            c = conn.cursor()
            try:
                c.execute(
                    """INSERT INTO companies
                       (inn, name, category, reason, comment, added_by, added_at, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                       RETURNING id""",
                    (inn, name, category, reason, comment, user["username"], datetime.now()))
                cid = c.fetchone()[0]
                conn.commit()
                log_action(user["username"], "ADD_COMPANY", "company", str(cid), f"ИНН {inn} · {name}")
                saved = save_attachments(cid, files, user["username"])
                if saved:
                    log_action(user["username"], "UPLOAD_ATTACHMENT", "company",
                               str(cid), f"файлов: {saved}")
                st.session_state.flash = f"Компания с ИНН {inn} добавлена" + (
                    f" · файлов: {saved}" if saved else "")
                st.rerun()
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                st.warning("Компания с таким ИНН уже есть в списке. "
                           "Если она снята — используйте «🚫 Снять / Вернуть», "
                           "а файлы можно добавить в разделе «📎 Файлы».")
            finally:
                c.close(); conn.close()

elif page == "✏️ Редактировать" and is_editor:
    st.subheader("✏️ Редактировать компанию")
    conn = get_conn()
    df_edit = pd.read_sql_query(
        "SELECT id, inn, name, category, reason, comment FROM companies ORDER BY inn", conn)
    conn.close()
    if df_edit.empty:
        st.info("Список пуст — нечего редактировать")
    else:
        options = [f"{r.id} | {r.inn} — {r.name or 'без названия'}" for r in df_edit.itertuples()]
        choice = st.selectbox("Выберите компанию", options, key="edit_choice")
        cid = int(choice.split(" | ")[0])
        row = df_edit[df_edit["id"] == cid].iloc[0]
        cur_cat = row["category"] if row["category"] in CATEGORIES else "Прочее"

        with st.form("edit_company"):
            new_inn = st.text_input("ИНН *", value=row["inn"] or "", max_chars=12)
            new_name = st.text_input("Название компании", value=row["name"] or "")
            new_cat = st.selectbox("Категория", CATEGORIES, index=CATEGORIES.index(cur_cat))
            new_reason = st.text_area("Причина включения", value=row["reason"] or "")
            new_comment = st.text_area("Комментарий", value=row["comment"] or "")
            save = st.form_submit_button("💾 Сохранить изменения", type="primary")

        if save:
            new_inn = new_inn.strip()
            if not new_inn:
                st.error("ИНН не может быть пустым")
            else:
                conn = get_conn(); c = conn.cursor()
                try:
                    c.execute(
                        "UPDATE companies SET inn=%s, name=%s, category=%s, reason=%s, comment=%s WHERE id=%s",
                        (new_inn, new_name, new_cat, new_reason, new_comment, cid))
                    conn.commit()
                    changes = []
                    if (row["inn"] or "") != new_inn:
                        changes.append(f"ИНН: {row['inn']} → {new_inn}")
                    if (row["name"] or "") != (new_name or ""):
                        changes.append(f"Название: {row['name'] or '—'} → {new_name or '—'}")
                    if (row["category"] or "") != new_cat:
                        changes.append(f"Категория: {row['category'] or '—'} → {new_cat}")
                    if (row["reason"] or "") != (new_reason or ""):
                        changes.append("Изменена причина")
                    if (row["comment"] or "") != (new_comment or ""):
                        changes.append("Изменён комментарий")
                    log_action(user["username"], "EDIT_COMPANY", "company", str(cid),
                               "; ".join(changes) or "без существенных изменений")
                    st.session_state.flash = f"Изменения для ИНН {new_inn} сохранены"
                    st.rerun()
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    st.error("Компания с таким ИНН уже существует в списке")
                finally:
                    c.close(); conn.close()

elif page == "🚫 Снять / Вернуть" and is_editor:
    st.subheader("🚫 Снять компанию со стоп-листа или вернуть обратно")
    conn = get_conn()
    df_all = pd.read_sql_query(
        "SELECT id, inn, name, status, removed_at, removed_by, removed_reason FROM companies ORDER BY inn", conn)
    conn.close()
    if df_all.empty:
        st.info("Список пуст")
    else:
        df_all["label"] = df_all.apply(
            lambda r: f"{r['id']} | {r['inn']} — {r['name'] or 'без названия'} "
                      f"[{'активен' if r['status']=='active' else 'снят'}]", axis=1)
        choice = st.selectbox("Выберите компанию", df_all["label"].tolist(), key="toggle_choice")
        cid = int(choice.split(" | ")[0])
        row = df_all[df_all["id"] == cid].iloc[0]

        if row["status"] == "active":
            st.markdown('<span class="status-pill status-active">🟢 активен</span>', unsafe_allow_html=True)
            st.write("")
            reason = st.text_area("Причина снятия со стоп-листа *")
            if st.button("🚫 Снять со стоп-листа", type="primary"):
                if not reason.strip():
                    st.error("Укажите причину снятия")
                else:
                    conn = get_conn(); c = conn.cursor()
                    c.execute(
                        """UPDATE companies SET status='removed', removed_at=%s, removed_by=%s, removed_reason=%s
                           WHERE id=%s""",
                        (datetime.now(), user["username"], reason.strip(), cid))
                    conn.commit(); c.close(); conn.close()
                    log_action(user["username"], "REMOVE_COMPANY", "company", str(cid), reason.strip())
                    st.session_state.flash = f"Компания {row['inn']} снята со стоп-листа"
                    st.rerun()
        else:
            st.markdown('<span class="status-pill status-removed">🟡 снят</span>', unsafe_allow_html=True)
            st.write("")
            st.write(f"**Снят:** {row['removed_by'] or '—'} · {row['removed_at'] or '—'}")
            st.write(f"**Причина снятия:** {row['removed_reason'] or '—'}")
            if st.button("♻️ Вернуть в стоп-лист", type="primary"):
                conn = get_conn(); c = conn.cursor()
                c.execute(
                    """UPDATE companies SET status='active',
                       removed_at=NULL, removed_by=NULL, removed_reason=NULL
                       WHERE id=%s""", (cid,))
                conn.commit(); c.close(); conn.close()
                log_action(user["username"], "RESTORE_COMPANY", "company", str(cid))
                st.session_state.flash = f"Компания {row['inn']} возвращена в стоп-лист"
                st.rerun()

elif page == "📎 Файлы" and is_editor:
    st.subheader("📎 Прикреплённые файлы")
    conn = get_conn()
    df_c = pd.read_sql_query("SELECT id, inn, name FROM companies ORDER BY inn", conn)
    conn.close()
    if df_c.empty:
        st.info("Список пуст — сначала добавьте компанию")
    else:
        labels = [f"{r.id} | {r.inn} — {r.name or 'без названия'}" for r in df_c.itertuples()]
        choice = st.selectbox("Выберите компанию", labels, key="files_choice")
        cid = int(choice.split(" | ")[0])

        st.markdown("**📤 Загрузить новые файлы**")
        up_files = st.file_uploader("Выберите файлы", accept_multiple_files=True,
                                    key="files_upload", label_visibility="collapsed")
        if up_files and st.button("Загрузить", type="primary"):
            saved = save_attachments(cid, up_files, user["username"])
            log_action(user["username"], "UPLOAD_ATTACHMENT", "company",
                       str(cid), f"файлов: {saved}")
            st.session_state.flash = f"Загружено файлов: {saved}"
            st.rerun()

        st.divider()
        st.markdown("**📁 Текущие файлы**")
        render_attachments(cid, user["username"], can_delete=True, prefix="files")

elif page == "📥 Импорт" and is_editor:
    st.subheader("📥 Массовый импорт из Excel/CSV")
    st.caption("Колонки: inn, name, category, reason, comment")
    up = st.file_uploader("Загрузите файл", type=["xlsx", "csv"])
    if up and st.button("Импортировать", type="primary"):
        imp = pd.read_csv(up, dtype=str) if up.name.endswith(".csv") else pd.read_excel(up, dtype=str)
        imp.columns = [c.lower().strip() for c in imp.columns]
        if "inn" not in imp.columns:
            st.error("Нужна колонка inn")
        else:
            conn = get_conn(); c = conn.cursor()
            added = 0
            for _, row in imp.iterrows():
                inn = str(row.get("inn") or "").strip()
                if not inn or inn == "nan":
                    continue
                try:
                    c.execute(
                        """INSERT INTO companies
                           (inn, name, category, reason, comment, added_by, added_at, status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')""",
                        (inn, row.get("name"), row.get("category"), row.get("reason"),
                         row.get("comment"), user["username"], datetime.now()))
                    added += 1
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
            conn.commit(); c.close(); conn.close()
            log_action(user["username"], "IMPORT", "company", "", f"добавлено {added}")
            st.session_state.flash = f"Импортировано: {added}"
            st.rerun()

elif page == "📜 История компании" and is_editor:
    st.subheader("📜 История изменений по компании")
    conn = get_conn()
    df_c = pd.read_sql_query("SELECT id, inn, name FROM companies ORDER BY inn", conn)
    if df_c.empty:
        st.info("Список пуст")
        conn.close()
    else:
        labels = [f"{r.id} | {r.inn} — {r.name or 'без названия'}" for r in df_c.itertuples()]
        choice = st.selectbox("Выберите компанию", labels, key="hist_choice")
        cid = int(choice.split(" | ")[0])
        hist = pd.read_sql_query(
            """SELECT ts AS "Дата", username AS "Пользователь",
                      action AS "Действие", details AS "Детали"
               FROM audit_log
               WHERE (entity='company' AND entity_id=%s)
                  OR (entity='attachment' AND entity_id IN
                       (SELECT id::text FROM attachments WHERE company_id=%s))
               ORDER BY id DESC""",
            conn, params=(str(cid), cid))
        conn.close()
        if hist.empty:
            st.info("По этой компании пока нет записей в истории")
        else:
            st.dataframe(hist, use_container_width=True, hide_index=True)

elif page == "🗑 Удалить" and is_admin:
    st.subheader("🗑 Удалить компанию из базы (безвозвратно)")
    st.caption("⚠️ Если компания просто больше не в стоп-листе — используйте "
               "раздел «🚫 Снять / Вернуть», чтобы сохранить историю. "
               "Вместе с компанией удалятся и все её файлы.")
    conn = get_conn()
    df = pd.read_sql_query(
        """SELECT c.id, c.inn, c.name,
                  (SELECT COUNT(*) FROM attachments a WHERE a.company_id=c.id) AS cnt
           FROM companies c ORDER BY c.inn""", conn)
    conn.close()
    if df.empty:
        st.info("Список пуст")
    else:
        options = [f"{r.id} | {r.inn} — {r.name or ''} ({r.cnt} файлов)"
                   for r in df.itertuples()]
        choice = st.selectbox("Выберите компанию", options, key="del_choice")
        if st.button("🗑 Удалить навсегда", type="primary"):
            cid = int(choice.split(" | ")[0])
            delete_all_attachments(cid)
            conn = get_conn(); c = conn.cursor()
            c.execute("DELETE FROM companies WHERE id = %s", (cid,))
            conn.commit(); c.close(); conn.close()
            log_action(user["username"], "DELETE_COMPANY", "company", str(cid), choice)
            st.session_state.flash = f"Удалено навсегда: {choice}"
            st.rerun()

elif page == "👥 Пользователи" and is_admin:
    st.subheader("👥 Пользователи")
    conn = get_conn()
    users_df = pd.read_sql_query(
        "SELECT id, username, full_name, role, created_at FROM users ORDER BY id", conn)
    conn.close()
    disp = users_df.copy()
    disp["role"] = disp["role"].apply(role_label)
    disp = disp.rename(columns={"id": "ID", "username": "Логин", "full_name": "ФИО",
                                "role": "Роль", "created_at": "Создан"})
    st.dataframe(disp, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**➕ Добавить пользователя**")
    with st.form("add_user", clear_on_submit=True):
        nu = st.text_input("Логин")
        nf = st.text_input("ФИО")
        npw = st.text_input("Пароль", type="password")
        nr = st.selectbox("Роль", ["viewer", "editor", "admin"], format_func=role_label)
        ok = st.form_submit_button("Создать", type="primary")
    if ok:
        if not nu or not npw:
            st.error("Логин и пароль обязательны")
        elif len(npw) < 6:
            st.error("Пароль должен быть не короче 6 символов")
        else:
            conn = get_conn(); c = conn.cursor()
            try:
                c.execute(
                    """INSERT INTO users (username, password_hash, role, full_name, created_at)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (nu, hash_pw(npw), nr, nf, datetime.now()))
                conn.commit()
                log_action(user["username"], "ADD_USER", "user", nu, nr)
                st.session_state.flash = f"Пользователь {nu} создан"
                st.rerun()
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                st.warning("Такой логин уже существует")
            finally:
                c.close(); conn.close()

    st.divider()
    st.markdown("**🔑 Сбросить пароль пользователя**")
    all_users = users_df["username"].tolist()
    c1, c2 = st.columns([2, 1])
    with c1:
        rst_user = st.selectbox("Пользователь", all_users, key="rst_user")
        rst_pw = st.text_input("Новый пароль", type="password", key="rst_pw")
    with c2:
        st.write(""); st.write("")
        if st.button("Сбросить пароль", use_container_width=True):
            if not rst_pw or len(rst_pw) < 6:
                st.error("Пароль должен быть не короче 6 символов")
            else:
                conn = get_conn(); c = conn.cursor()
                c.execute("UPDATE users SET password_hash = %s WHERE username = %s",
                          (hash_pw(rst_pw), rst_user))
                conn.commit(); c.close(); conn.close()
                log_action(user["username"], "RESET_PASSWORD", "user", rst_user)
                st.success(f"Пароль пользователя **{rst_user}** изменён")

    st.divider()
    st.markdown("**🗑 Удалить пользователя**")
    del_user = st.selectbox("Выберите", all_users, key="del_user_select")
    if st.button("Удалить пользователя"):
        if del_user == user["username"]:
            st.error("Нельзя удалить самого себя")
        else:
            conn = get_conn(); c = conn.cursor()
            c.execute("DELETE FROM users WHERE username = %s", (del_user,))
            conn.commit(); c.close(); conn.close()
            log_action(user["username"], "DELETE_USER", "user", del_user)
            st.session_state.flash = f"Удалён пользователь: {del_user}"
            st.rerun()

elif page == "📜 Журнал" and is_admin:
    st.subheader("📜 Журнал действий")
    conn = get_conn()
    log_df = pd.read_sql_query(
        """SELECT ts AS "Дата", username AS "Пользователь", action AS "Действие",
                  entity AS "Объект", entity_id AS "ID", details AS "Детали"
           FROM audit_log ORDER BY id DESC LIMIT 5000""", conn)
    conn.close()
    c1, c2 = st.columns(2)
    with c1:
        fu = st.multiselect("Пользователь", sorted(log_df["Пользователь"].dropna().unique().tolist()))
    with c2:
        fa = st.multiselect("Действие", sorted(log_df["Действие"].dropna().unique().tolist()))
    v = log_df.copy()
    if fu: v = v[v["Пользователь"].isin(fu)]
    if fa: v = v[v["Действие"].isin(fa)]
    st.caption(f"Показано: {len(v)} записей (не более 5000 последних)")
    st.dataframe(v, use_container_width=True, hide_index=True)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        v.to_excel(w, index=False, sheet_name="Журнал")
    st.download_button(
        "📥 Скачать отфильтрованный журнал в Excel",
        buf.getvalue(),
        file_name=f"audit-log-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx",
    )