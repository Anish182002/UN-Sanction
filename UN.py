import streamlit as st
import xml.etree.ElementTree as ET
import json
import requests
import base64

# --- Streamlit Page Setup ---
st.set_page_config(page_title="UN Sanctions Tracker", layout="wide")
st.title("🛡️ UN Sanctions Change Tracker (GitHub Integrated)")

# --- Load Secrets ---
GITHUB_USERNAME = st.secrets["GITHUB_USERNAME"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
GITHUB_BRANCH = st.secrets["GITHUB_BRANCH"]
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
SNAPSHOT_FILE_PATH = st.secrets["SNAPSHOT_FILE_PATH"]

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# --- GitHub API Helpers ---

def get_snapshot_from_github():
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{SNAPSHOT_FILE_PATH}?ref={GITHUB_BRANCH}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        content = base64.b64decode(response.json()["content"]).decode()
        return json.loads(content), response.json()["sha"]
    return None, None

def upload_snapshot_to_github(snapshot_json, sha=None):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{SNAPSHOT_FILE_PATH}"
    content_encoded = base64.b64encode(json.dumps(snapshot_json, indent=2).encode()).decode()

    data = {
        "message": "Update snapshot",
        "content": content_encoded,
        "branch": GITHUB_BRANCH
    }

    if sha:
        data["sha"] = sha  # Include only if file exists

    response = requests.put(url, headers=HEADERS, data=json.dumps(data))

    if response.status_code in [200, 201]:
        return True
    else:
        st.error(f"❌ GitHub upload failed. Status Code: {response.status_code}")
        try:
            error_json = response.json()
            message = error_json.get("message", "Unknown error")
            errors = error_json.get("errors", [])
            st.code(f"Message: {message}")
            if errors:
                st.code(f"Details: {json.dumps(errors, indent=2)}")
        except:
            st.code(f"Raw Response: {response.text}")
        return False

# --- XML Parser ---

def parse_consolidated_xml(uploaded_file):
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    individuals_root = root.find("INDIVIDUALS")
    if individuals_root is None:
        return []

    entries = []
    for person in individuals_root.findall("INDIVIDUAL"):
        ref = person.findtext("REFERENCE_NUMBER") or "UNKNOWN_REF"

        # Collect *_NAME tags dynamically
        name_parts = []
        for child in person:
            if child.tag.endswith("_NAME") and child.tag != "ALIAS_NAME":
                value = child.text.strip() if child.text else ""
                name_parts.append(value)
        full_name = " ".join(name_parts).strip()

        # Collect aliases
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

# --- Comparison Logic ---

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

# --- Streamlit UI ---

uploaded_file = st.file_uploader("📤 Upload today's consolidated.xml file", type="xml")

if uploaded_file:
    st.success("✅ File uploaded. Parsing...")
    current_entries = parse_consolidated_xml(uploaded_file)
    st.info(f"📄 {len(current_entries)} entries parsed from today's file.")

    old_entries, old_sha = get_snapshot_from_github()

    if old_entries is not None:
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
        st.warning("⚠️ No previous snapshot found. Saving this as the baseline.")

    success = upload_snapshot_to_github(current_entries, sha=old_sha)
    if success:
        st.success("📤 Snapshot successfully updated to GitHub.")
    else:
        st.warning("⚠️ Snapshot NOT saved to GitHub. See debug info above.")
else:
    st.info("Upload the UN sanctions `consolidated.xml` file to begin.")
