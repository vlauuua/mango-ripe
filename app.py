import streamlit as st
from ultralytics import YOLO
import cv2
import numpy as np
from datetime import datetime
from collections import Counter
import sqlite3
import bcrypt

st.set_page_config(page_title="MangoR!pe", page_icon="🥭", layout="wide")

# ================= DB CONNECTION =================
def init_db():
    return sqlite3.connect("mango.db", check_same_thread=False)

conn = init_db()
conn.execute("PRAGMA journal_mode=WAL;")
def create_tables():
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        time TEXT,
        result TEXT,
        image BLOB
    )
    """)

    conn.commit()
    cur.close()

create_tables()

# ================= AUTH =================
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def register_user(username, password):
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hash_password(password))
        )
        conn.commit()
        cur.close()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username=?", (username,))
    data = cur.fetchone()
    cur.close()

    if data and check_password(password, data[0]):
        return True
    return False

if "user" not in st.session_state:
    st.session_state.user = None

# ================= LOGIN PAGE =================
if st.session_state.user is None:
    st.title("🔐 Login/Register MangoR!pe")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            if login_user(username, password):
                st.session_state.user = username
                st.success("Login berhasil")
                st.rerun()
            else:
                st.error("Username atau password salah")

    with tab2:
        new_user = st.text_input("Buat Username")
        new_pass = st.text_input("Buat Password", type="password")

        if st.button("Register"):
            if register_user(new_user, new_pass):
                st.success("Berhasil register, silakan login")
            else:
                st.error("Username sudah ada")

    st.stop()

@st.cache_resource
def load_model():
    return YOLO("best.pt")

model = load_model()

def detect_image(image, conf, imgsz):  
    image_bgr  = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    results    = model.predict(image_bgr, conf=conf, imgsz=imgsz)
    result_img = results[0].plot()
    result_img = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
    labels     = [model.names[int(box.cls[0])] for box in results[0].boxes]
    return result_img, labels

if "history" not in st.session_state:
    st.session_state.history = []

# ================= SIDEBAR =================
st.sidebar.title("📋 Menu")

menu = st.sidebar.radio(
    "Pilih Halaman",
    ["🔍 Deteksi", "📜 Riwayat", "🥭 Deskripsi"],
    label_visibility="visible"
)

st.sidebar.divider()

# ================= MENU: DETEKSI =================
if menu == "🔍 Deteksi":
    st.title("🥭 MangoR!pe")
    st.caption("Deteksi Kematangan Buah Mangga")

    conf  = st.sidebar.slider("Confidence Threshold", 0.1, 1.0, 0.5, 0.05)
    imgsz = st.sidebar.slider("Image Size", 320, 1280, 640, 32)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📁 Upload")
        uploaded_file = st.file_uploader("Upload Gambar", type=["jpg", "png", "jpeg"])
        if uploaded_file is not None:
            file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
            image = cv2.imdecode(file_bytes, 1)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            st.image(image, caption="Input", width=450)
            if st.button("🔍 Deteksi Gambar", key="btn_upload"):
                result_img, labels = detect_image(image, conf, imgsz)
                st.image(result_img, caption="Hasil", width=450)
                if len(labels) == 0:
                    st.warning("❌ Objek tidak terdeteksi")
                    result_text = "Tidak terdeteksi"
                else:
                    count     = Counter(labels)
                    result_text = ", ".join([f"{v} {k}" for k, v in count.items()])
                    st.success(f"Hasil: {result_text}")
                _, img_encoded = cv2.imencode('.jpg', cv2.cvtColor(result_img, cv2.COLOR_RGB2BGR))

                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO history (username, time, result, image) VALUES (?, ?, ?, ?)",
                    (
                        st.session_state.user,
                        datetime.now().strftime("%H:%M:%S"),
                        result_text,
                        img_encoded.tobytes()
                    )
                )
                conn.commit()
                cur.close()
    with col2:
        st.subheader("📷 Camera")
        kamera_aktif = st.toggle("Nyalakan Kamera", value=False)

        if kamera_aktif:
            camera_image = st.camera_input("Ambil Gambar")
            if camera_image is not None:
                file_bytes = np.asarray(bytearray(camera_image.read()), dtype=np.uint8)
                image = cv2.imdecode(file_bytes, 1)
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                st.image(image, caption="Input", width=450)
                if st.button("🔍 Deteksi Kamera"):
                    result_img, labels = detect_image(image, conf, imgsz)
                    st.image(result_img, caption="Hasil", width=450)
                    if len(labels) == 0:
                        st.warning("❌ Objek tidak terdeteksi")
                        result_text = "Tidak terdeteksi"
                    else:
                        count     = Counter(labels)
                        result_text = ", ".join([f"{v} {k}" for k, v in count.items()])
                        st.success(f"Hasil: {result_text}")
                    _, img_encoded = cv2.imencode('.jpg', cv2.cvtColor(result_img, cv2.COLOR_RGB2BGR))

                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO history (username, time, result, image) VALUES (?, ?, ?, ?)",
                        (
                            st.session_state.user,
                            datetime.now().strftime("%H:%M:%S"),
                            result_text,
                            img_encoded.tobytes()
                        )
                    )
                    conn.commit()
                    cur.close()
            
# ================= MENU: RIWAYAT =================
elif menu == "📜 Riwayat":
    st.title("📜 Riwayat Deteksi")

    cur = conn.cursor()
    cur.execute(
        "SELECT time, result, image FROM history WHERE username=? ORDER BY id DESC",
        (st.session_state.user,)
    )
    data = cur.fetchall()
    cur.close()

    if not data:
        st.info("Belum ada riwayat")
    else:
        cols = st.columns(3)
        for i, item in enumerate(data):
            image = cv2.imdecode(np.frombuffer(item[2], np.uint8), 1)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            with cols[i % 3]:
                st.image(image, width=180)
                st.caption(f"🕒 {item[0]}")
                st.write(item[1])

        st.divider()

        if st.button("🗑️ Hapus Semua"):
            cur = conn.cursor()
            cur.execute("DELETE FROM history WHERE username=?", (st.session_state.user,))
            conn.commit()
            cur.close()
            st.success("Riwayat berhasil dihapus")
            st.rerun()

# ================= MENU: DESKRIPSI TINGKAT KEMATANGAN =================
elif menu == "🥭 Deskripsi":
    st.title("🥭 Tingkat Kematangan Mangga")
    st.caption("Panduan visual kematangan buah mangga")
    st.divider()

    kematangan = [
        ("🟢 Sangat Mentah", "#2d6a2d", "Kulit hijau pekat, tekstur sangat keras. Belum bisa dikonsumsi langsung. Biasanya digunakan untuk rujak atau asinan."),
        ("🔵 Mentah",        "#1a4a8a", "Kulit hijau, mulai sedikit lunak di bagian tertentu. Butuh beberapa hari lagi untuk matang sempurna."),
        ("🟡 Mengkal",       "#8a7a10", "Kulit mulai kekuningan, setengah matang. Aroma mulai tercium. 1-2 hari lagi sudah siap dikonsumsi."),
        ("🟠 Matang",        "#8a4a10", "Kulit kuning-oranye, tekstur lunak, aroma harum. Kondisi optimal untuk dikonsumsi langsung."),
        ("🔴 Sangat Matang", "#6a2020", "Kulit kuning penuh atau mulai gelap, sangat lunak. Rasa manis maksimal. Segera dikonsumsi atau diolah."),
    ]

    for nama, warna, deskripsi in kematangan:
        st.markdown(f"""
        <div style="background:{warna}22;border-left:4px solid {warna}aa;
                    border-radius:10px;padding:1rem 1.2rem;margin-bottom:1rem;">
            <div style="font-size:1.1rem;font-weight:700;">{nama}</div>
            <div style="margin-top:0.4rem;color:#black;">{deskripsi}</div>
        </div>""", unsafe_allow_html=True)

st.sidebar.divider()

if st.sidebar.button("🚪 Logout"):
    st.session_state.user = None
    st.rerun()