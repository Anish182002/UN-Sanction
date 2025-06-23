import streamlit as st
import xml.etree.ElementTree as ET
import json
import os

st.set_page_config(page_title="UN Sanctions Change Tracker", layout="wide")
st.title("🛡️ UN Sanctions Change Tracker")

# --- Parse XML ---
def parse_consolidated_xml(uploaded_file):
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    individuals_root = root.find("INDIVIDUALS")
    if individuals_root is None:
        return []

    entries = []

    for person in individuals_root.findall("INDIVIDUAL"):
        ref = person.findtext("REFERENCE_NUMBER") or "UNKNOWN_REF"

        # Dynamically collect all *_NAME fields
        name_parts = []
        for child in person:
            tag = child.tag
            if tag.endswith("_NAME") and tag != "ALIAS_NAME":
                value = child.text.strip() if child.text else ""
                name_parts.append(value)

        full_name = " ".join(name_parts).strip()

        # Extract aliases
        aliases = []
        for alias in person.findall("INDIVIDUAL_ALIAS"):
            alias_name = alias.findtext("ALIAS_NAME")
            if alias_name:
                aliases.append(alias_name.strip())

        entries.append({
            "type": "individual",
            "reference_number": ref,
            "name": full_name,
            "aliases": aliases
        })

    return entries

# --- Compare Snapshots ---
def compare_snapshots(old_entries, new_entries):
    old_map = {e['reference_number']: e for e in old_entries}
    new_map = {e['reference_number']: e for e in new_entries}

    added = [new_map[r] for r in new_map if r not in old_map]
    removed = [old_map[r] for r in old_map if r not in new_map]
    modified = [
        {"reference_number": r, "old": old_map[r], "new": new_map[r]}
        for r in new_map if r in old_map and new_map[r] != old_map[r]
    ]

    return added, removed, modified

# --- Snapshot Load/Save ---
def load_previous_snapshot(file_path="consolidated_previous.json"):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return []

def save_current_snapshot(entries, file_path="consolidated_previous.json"):
    with open(file_path, "w") as f:
        json.dump(entries, f, indent=2)

# --- Streamlit UI ---
uploaded_file = st.file_uploader("📤 Upload today's consolidated.xml file", type="xml")

if uploaded_file:
    st.success("✅ File uploaded. Parsing...")
    current_entries = parse_consolidated_xml(uploaded_file)
    st.info(f"📄 {len(current_entries)} entries parsed from today's file.")

    old_entries = load_previous_snapshot()

    if old_entries:
        added, removed, modified = compare_snapshots(old_entries, current_entries)

        col1, col2, col3 = st.columns(3)
        col1.metric("🆕 Added", len(added))
        col2.metric("❌ Removed", len(removed))
        col3.metric("🛠️ Modified", len(modified))

        if added:
            st.subheader("🆕 Added Entries")
            st.json(added)

        if removed:
            st.subheader("❌ Removed Entries")
            st.json(removed)

        if modified:
            st.subheader("🛠️ Modified Entries")
            for m in modified:
                st.write(f"Reference #: {m['reference_number']}")
                st.json({"Old": m["old"], "New": m["new"]})

    else:
        st.warning("⚠️ No previous snapshot found. Saving current snapshot as the baseline.")
        save_current_snapshot(current_entries)

    save_current_snapshot(current_entries)
    st.success("💾 Snapshot updated.")

else:
    st.info("Upload the UN sanctions `consolidated.xml` file to begin.")
