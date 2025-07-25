import streamlit as st
import os
import tempfile
from utils import *
from elabapi_python import ItemsApi
import tempfile

# ─── Session-State initialisieren ────────────────────────────────
def init_session_state():
    defaults = {
        "exp_id": None,
        "api_client": None,
        "item_id": None,
        "positions": [],
        "angles": [],
        "file_name": "",
        "file_path": ""
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ─── Guard: Experiment und Item müssen ausgewählt sein ────────────
if not st.session_state.get("exp_id"):
    st.warning("Bitte zuerst im ersten Tab ein Experiment auswählen.")
    st.stop()
if not st.session_state.get("item_id"):
    st.warning("Bitte zuerst im ersten Tab eine Ressource (Item) auswählen.")
    st.stop()

api_client = st.session_state["api_client"]
item_id     = st.session_state["item_id"]

st.title("🔬 Sample Information")

# --- Sample Metadata ---
step_data = {}
step_data["plate_material"] = st.selectbox(
    "Plate Material", ["Stainless Steel", "Molybdenum", "Tantalum"]
)

# --- Linked Measurement Folder ---
st.subheader("Linked Measurement Folder")

col_path, col_folder = st.columns(2)
with col_path:
    st.session_state.file_path = st.text_input("Path", value=st.session_state.file_path, placeholder="e.g., C:/Users/.../Data/")
with col_folder:
    st.session_state.file_name = st.text_input("Folder Name", value=st.session_state.file_name, placeholder="e.g., TiO2_Sample1")

# --- Optional Comment ---
comment = st.text_area("📝 Optional Comment")

# --- Sample Image Upload ---
sample_img = st.file_uploader(
    "📷 Upload Sample Image", type=["png", "jpg", "jpeg"]
)

st.markdown("---")

# Submit


if st.button("✅ Submit Entry"):
    # 1) Validation

    # ─── A) Sample-Daten in Item schreiben ───────────────────────────
    entry_item = "<h3>Sample Information</h3>"
    entry_item += f"<b>Plate Material:</b> {step_data['plate_material']}<br><hr>"

    if st.session_state.positions:
        entry_item += "<h4>Positions</h4>"
        for idx, ((xx, yy, zz), aa) in enumerate(
                zip(st.session_state.positions, st.session_state.angles), start=1):
            line = f"- Position {idx}: x={xx:.2f}, y={yy:.2f}, z={zz:.2f} mm"
            if aa is not None:
                line += f", α={aa:.1f}°"
            entry_item += line + "<br>"
        entry_item += "<hr>"

    fp = st.session_state.get("file_path","").strip()
    fn = st.session_state.get("file_name","").strip()
    if fp and fn:
        folder = os.path.join(fp, fn)
        os.makedirs(folder, exist_ok=True)
        entry_item += "<h4>Linked Measurement Folder</h4>"
        entry_item += f"{folder}<br><hr>"

    if comment.strip():
        entry_item += "<h4>Comment</h4>" + comment.replace("\n","<br>") + "<hr>"

    # Patch ins Item
    try:
        items_api = ItemsApi(api_client)
        current   = items_api.get_item(item_id)
        new_body  = (current.body or "") + entry_item
        items_api.patch_item(item_id, body={"body": new_body})
        st.success("✅ Sample info erfolgreich ins Item geschrieben.")
    except Exception as e:
        st.error(f"❌ Fehler beim Schreiben ins Item: {e}")
        st.stop()

    # ─── B) Bild nur ins Experiment laden ─────────────────────────────
    if sample_img:
        # Temp-File
        fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(sample_img.name)[1])
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(sample_img.getvalue())

        # Upload ins Experiment
        if upload_image_experiment(api_client, st.session_state["exp_id"], tmp_path):
            insert_image(api_client, st.session_state["exp_id"], sample_img.name)
            st.success("☁️ Bild erfolgreich ins Experiment hochgeladen.")
        else:
            st.info("ℹ️ No folder path or name provided — no local folder created.")
        try:
            os.remove(tmp_path)
        except OSError:
            pass

        # Image Info
        if sample_img:
            entry += "<h4>Sample Image</h4>"
            entry += f"📎 Uploaded file: <b>{sample_img.name}</b><br><hr>"

        # Append entry text to ELN
        if st.session_state.api_client and st.session_state.exp_id:
            append_to_experiment(st.session_state.api_client, st.session_state.exp_id, entry)
            st.success("✅ Sample info successfully added to experiment.")
        else:
            st.error("❌ No experiment selected or API client missing.")

        # Image Upload Block (local save optional)
        if sample_img:
            save_success = False
            if st.session_state.get("file_path") and st.session_state.get("file_name"):
                save_dir = os.path.join(st.session_state["file_path"], st.session_state["file_name"])
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, sample_img.name)
                with open(save_path, "wb") as f:
                    f.write(sample_img.getvalue())
                st.success(f"📷 Image saved locally to: {save_path}")
                save_success = True
            else:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(sample_img.name)[1]) as tmp:
                    tmp.write(sample_img.getvalue())
                    save_path = tmp.name
                st.info("🖼️ No path provided – image uploaded to ELN only (not saved locally)")

            # Upload to ELN
            if upload_image(st.session_state.api_client, st.session_state.exp_id, save_path):
                insert_image(st.session_state.api_client, st.session_state.exp_id, os.path.basename(sample_img.name))
                st.success("☁️ Image uploaded to eLabFTW")
            else:
                st.error("❌ Upload to eLabFTW failed")

            if not save_success:
                os.remove(save_path)

        # Clear session state after submission
        st.session_state.positions.clear()
        st.session_state.angles.clear()
