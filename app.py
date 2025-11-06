import streamlit as st
from docx import Document
from PIL import Image
import pillow_heif # enable HEIC support
import exifread
import pytesseract
import openai
import os
import io
from dotenv import load_dotenv
import base64

try:
    import pillow_heif
    pillow_heif.register_heif_opener()  # <— required for PIL to understand HEIC
except ImportError:
    st.warning("⚠️ HEIC support unavailable. Convert iPhone photos to JPEG.")

# Load secrets
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ---- App Layout ----
st.set_page_config(page_title="TrailTeller", layout="wide")
st.title("🌍 TrailTeller — Your AI Travel Journal")
st.write("Upload your travel photos or word documents and let AI craft your story.")

uploaded_files = st.file_uploader(
    "Upload one or more files",
    type=["docx", "jpg", "jpeg", "png", "HEIC"],
    accept_multiple_files=True
)

trip_data = []

def extract_docx_text(file_bytes):
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def caption_image_with_gpt(file_bytes: bytes) -> str:
    """Ask GPT-4o to describe what it sees in the uploaded image."""
    b64 = base64.b64encode(file_bytes).decode("utf-8")

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this travel photo accurately in one short, vivid sentence."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                        },
                    ],
                }
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Image captioning failed: {e}]"

def extract_exif_data(file_bytes):
    tags = exifread.process_file(io.BytesIO(file_bytes))
    gps = {tag: str(tags[tag]) for tag in tags if tag.startswith("GPS")}
    return gps

def convert_heic_to_jpeg(file_bytes):
    heif_file = pillow_heif.read_heif(io.BytesIO(file_bytes))
    image = Image.frombytes(
        heif_file.mode, heif_file.size, heif_file.data, "raw"
    )
    buf = BytesIO()
    image.save(buf, format="JPEG")
    return buf.getvalue()

if uploaded_files:
    for file in uploaded_files:
        file_bytes = file.read()
        name = file.name.lower()

        if name.endswith(".heic"):
            file_bytes = convert_heic_to_jpeg(file_bytes)

        if file.name.endswith(".docx"):
            text = extract_docx_text(file_bytes)
            trip_data.append({"type": "text", "content": text})
            
        elif file.name.lower().endswith((".jpg", ".jpeg", ".png", "heic")):
            gps = extract_exif_data(file_bytes)
            caption = caption_image_with_gpt(file_bytes)
            # image_text = extract_image_text(file_bytes)
            trip_data.append({"type": "photo", "caption": caption, "gps": gps})
        else:
            st.warning(f"Unsupported file: {file.name}")

    if st.button("🧠 Generate Travel Journal"):
        with st.spinner("Crafting your travel journal..."):
            prompt = f"""
            You are an expert travel writer. Based on the following travel data:
            {trip_data}
            Write a beautiful, chronological travel journal that summarizes the experiences.
            Include emotional tone, sensory details, and natural transitions.
            """
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )
            story = response.choices[0].message.content.strip()
            st.success("✨ Travel journal created!")
            st.markdown(story)
