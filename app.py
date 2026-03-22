import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import base64
import os
import hashlib
import hmac
import io
import requests
import random

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.backends import default_backend

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="🔐 Secure Stego Studio", layout="wide")

# ---------------- STYLE ----------------
st.markdown("""
<style>
.main {background: linear-gradient(135deg, #0f172a, #1e293b); color: white;}
.stButton>button {border-radius: 12px; font-weight: 600;}
</style>
""", unsafe_allow_html=True)

st.title("🔐 Secure Steganography Studio")
st.caption("AES Encryption • HMAC Integrity • Image Steganography")

# ---------------- AES ----------------
def aes_encrypt(message, key):
    key = hashlib.sha256(key.encode()).digest()
    iv = os.urandom(16)

    padder = PKCS7(128).padder()
    padded = padder.update(message.encode()) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode()

def aes_decrypt(enc, key):
    key = hashlib.sha256(key.encode()).digest()
    raw = base64.b64decode(enc)

    iv = raw[:16]
    ciphertext = raw[16:]

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = PKCS7(128).unpadder()
    data = unpadder.update(padded) + unpadder.finalize()

    return data.decode()

# ---------------- HMAC ----------------
def generate_hmac(data, key):
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

# ---------------- RANDOM IMAGE ----------------
def fetch_random_image():
    url = f"https://picsum.photos/400/400?random={random.randint(1,10000)}"
    response = requests.get(url)
    return Image.open(io.BytesIO(response.content)).convert("RGB")

# ---------------- WATERMARK ----------------
def add_watermark(img, text="© Rik Banerjee"):
    watermark_img = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", watermark_img.size, (0,0,0,0))

    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("arial.ttf", int(min(img.size)/15))
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0,0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = img.size[0] - text_width - 10
    y = img.size[1] - text_height - 10

    draw.text((x, y), text, font=font, fill=(255,255,255,120))

    return Image.alpha_composite(watermark_img, overlay).convert("RGB")

# ---------------- ENCODE ----------------
def encode_image(img, payload):
    img = img.convert("RGB")
    encoded = img.copy()

    binary = ''.join(format(ord(c), '08b') for c in payload + "###")
    index = 0

    width, height = img.size

    for row in range(height):
        for col in range(width):
            if index >= len(binary):
                return encoded

            pixel = list(img.getpixel((col, row)))

            for n in range(3):
                if index < len(binary):
                    pixel[n] = pixel[n] & ~1 | int(binary[index])
                    index += 1

            encoded.putpixel((col, row), tuple(pixel))

    return encoded

# ---------------- DECODE ----------------
def decode_image(img):
    img = img.convert("RGB")
    binary = ""

    for pixel in img.getdata():
        for n in range(3):
            binary += str(pixel[n] & 1)

    bytes_data = [binary[i:i+8] for i in range(0, len(binary), 8)]

    decoded = ""
    for byte in bytes_data:
        decoded += chr(int(byte, 2))
        if decoded.endswith("###"):
            return decoded[:-3]

    return None

# ---------------- SIDEBAR ----------------
mode = st.sidebar.radio("⚙️ Mode", ["Encode", "Decode"])

# =========================
# 📤 ENCODE
# =========================
if mode == "Encode":

    st.subheader("📤 Encode Message into Image")

    source_option = st.radio(
        "🖼️ Select Image Source",
        ["Upload Image", "Use Random Image"],
        key="source_radio"
    )

    add_wm = st.checkbox("🪪 Add Watermark (© Rik Banerjee)", value=True)

    col1, col2 = st.columns(2)

    with col1:
        img = None

        if source_option == "Upload Image":
            uploaded_file = st.file_uploader(
                "📁 Upload Image",
                type=["png", "jpg", "jpeg"],
                key="encode_uploader"
            )
            if uploaded_file:
                img = Image.open(uploaded_file)

        else:
            if st.button("🎲 Generate Random Image"):
                st.session_state["random_img"] = fetch_random_image()

            if "random_img" in st.session_state:
                img = st.session_state["random_img"]

        message = st.text_area("💬 Secret Message")

    with col2:
        aes_key = st.text_input("🔑 AES Key", type="password")
        hmac_key = st.text_input("🧾 HMAC Key", type="password")

    if img:
        st.image(img, caption="Original Image", use_container_width=True)

        width, height = img.size
        capacity = width * height * 3 // 8
        st.info(f"📊 Max Capacity: ~{capacity} characters")

    if st.button("🚀 Encode", key="encode_btn"):
        if img and message and aes_key and hmac_key:
            encrypted = aes_encrypt(message, aes_key)
            tag = generate_hmac(encrypted, hmac_key)
            payload = encrypted + "::" + tag

            encoded_img = encode_image(img, payload)

            if add_wm:
                encoded_img = add_watermark(encoded_img)

            st.success("✅ Encoded Successfully!")

            st.image(encoded_img, caption="Encoded Image")

            buf = io.BytesIO()
            encoded_img.save(buf, format="PNG")

            st.download_button(
                "⬇️ Download",
                buf.getvalue(),
                "encoded.png",
                key="download_btn"
            )
        else:
            st.error("⚠️ Fill all fields")

# =========================
# 📥 DECODE
# =========================
if mode == "Decode":

    st.subheader("📥 Decode Message")

    uploaded_file = st.file_uploader(
        "📁 Upload Encoded Image",
        type=["png"],
        key="decode_uploader"
    )

    aes_key = st.text_input("🔑 AES Key", type="password", key="dec_aes")
    hmac_key = st.text_input("🧾 HMAC Key", type="password", key="dec_hmac")

    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, caption="Uploaded Image")

    if st.button("🔍 Decode", key="decode_btn"):
        if uploaded_file and aes_key and hmac_key:
            extracted = decode_image(img)

            if extracted:
                try:
                    enc, recv_tag = extracted.split("::")
                    calc_tag = generate_hmac(enc, hmac_key)

                    if calc_tag != recv_tag:
                        st.error("❌ Tampered Data")
                    else:
                        message = aes_decrypt(enc, aes_key)
                        st.success("✅ Verified & Decrypted")
                        st.code(message)

                except:
                    st.error("❌ Decode Failed")
            else:
                st.error("❌ No Hidden Data Found")

        else:
            st.error("⚠️ Fill all fields")

# ---------------- FOOTER ----------------
st.markdown("---")
st.markdown(
    "<div style='text-align:center;'>© 2026 Rik Banerjee</div>",
    unsafe_allow_html=True
)
