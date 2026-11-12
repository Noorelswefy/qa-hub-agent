import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from datetime import datetime

# Page Config
st.set_page_config(page_title="Software Testing Hub - Community Hub", page_icon="🧪", layout="wide")

# ITI-Inspired Theme & Mobile-First CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Header Banner */
.hub-banner {
    background: linear-gradient(135deg, #9B1B20 0%, #6D1216 100%);
    color: #FFFFFF;
    padding: 24px 28px;
    border-radius: 14px;
    margin-bottom: 20px;
    box-shadow: 0 4px 14px rgba(155, 27, 32, 0.18);
}
.hub-banner h1 {
    color: #FFFFFF !important;
    font-size: 1.85rem;
    font-weight: 700;
    margin: 0 0 8px 0;
}
.hub-banner p {
    color: #F3E8E8 !important;
    font-size: 1rem;
    margin: 0;
    line-height: 1.5;
}

/* Resource Cards */
.resource-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-left: 5px solid #9B1B20;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.resource-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 14px rgba(155, 27, 32, 0.12);
}
.badge-course {
    background-color: #9B1B20;
    color: #FFFFFF;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    display: inline-block;
    margin-right: 6px;
    margin-bottom: 4px;
}
.badge-path {
    background-color: #F3F4F6;
    color: #374151;
    border: 1px solid #D1D5DB;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
    display: inline-block;
    margin-right: 6px;
    margin-bottom: 4px;
}
.badge-type {
    background-color: #FEF2F2;
    color: #9B1B20;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
    display: inline-block;
    margin-bottom: 4px;
}
.card-title {
    font-size: 1.08rem;
    font-weight: 600;
    color: #1E2022 !important;
    margin: 8px 0 4px 0;
    display: block;
    text-decoration: none;
    word-break: break-word;
}
.card-title:hover {
    color: #9B1B20 !important;
    text-decoration: underline;
}
.card-meta {
    font-size: 0.78rem;
    color: #6B7280;
}

/* Mobile Responsive Adjustments */
@media (max-width: 768px) {
    .hub-banner {
        padding: 18px 16px;
    }
    .hub-banner h1 {
        font-size: 1.4rem;
    }
    .hub-banner p {
        font-size: 0.9rem;
    }
    .resource-card {
        padding: 14px;
    }
}
</style>
""", unsafe_allow_html=True)

# Google Services Setup
@st.cache_resource
def get_credentials():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets'
    ]
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

def get_drive_service():
    return build('drive', 'v3', credentials=get_credentials())

def get_sheets_service():
    return build('sheets', 'v4', credentials=get_credentials())

MAIN_FOLDER_ID = st.secrets.get("MAIN_FOLDER_ID", "YOUR_DRIVE_FOLDER_ID")
SPREADSHEET_ID = st.secrets.get("SPREADSHEET_ID", "YOUR_GOOGLE_SHEET_ID")

def get_or_create_nested_folders(service, path_parts, root_parent_id):
    current_parent = root_parent_id
    for folder_name in path_parts:
        clean_name = folder_name.strip()
        if not clean_name:
            continue
        safe_name = clean_name.replace("'", "\\'")
        query = f"mimeType='application/vnd.google-apps.folder' and name='{safe_name}' and '{current_parent}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
        if folders:
            current_parent = folders[0]['id']
        else:
            file_metadata = {
                'name': clean_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [current_parent]
            }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            current_parent = folder.get('id')
    return current_parent

def append_to_sheet(row_data):
    service = get_sheets_service()
    body = {'values': [row_data]}
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="Sheet1!A:E",
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

def get_sheet_data():
    try:
        service = get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range="Sheet1!A:E"
        ).execute()
        return result.get('values', [])
    except Exception:
        return []

# --- Header ---
st.markdown("""
<div class="hub-banner">
    <h1>🧪 Software Testing Hub - Community Hub</h1>
    <p>No more digging through messy Drive folders or lost chat links — drop your labs, slides, and useful repos here so everyone finds what they need in seconds.</p>
</div>
""", unsafe_allow_html=True)

# --- Main Tabs ---
tab1, tab2 = st.tabs(["Browse Resources", "Share a Resource"])

with tab1:
    rows = get_sheet_data()
    if len(rows) > 1:
        data = rows[1:]
        
        # Extract main course names (before ' / ' if nested)
        all_main_courses = sorted(list(set([r[0].split(" / ")[0] for r in data if len(r) > 0])))
        
        col_filter, col_search = st.columns([1, 2])
        with col_filter:
            selected_filter = st.selectbox("Filter by Course:", ["All Courses"] + all_main_courses)
        with col_search:
            search_query = st.text_input("Search:", placeholder="Type a file name, lab, or topic...")

        filtered_data = data
        if selected_filter != "All Courses":
            filtered_data = [r for r in filtered_data if len(r) > 0 and r[0].split(" / ")[0] == selected_filter]
        if search_query:
            filtered_data = [
                r for r in filtered_data 
                if (len(r) > 2 and search_query.lower() in r[2].lower()) or (len(r) > 0 and search_query.lower() in r[0].lower())
            ]

        st.caption(f"Showing {len(filtered_data)} resource(s)")

        for r in reversed(filtered_data):
            if len(r) >= 5:
                course_path, stype, title, link, time = r[0], r[1], r[2], r[3], r[4]
                parts = course_path.split(" / ")
                main_course = parts[0]
                sub_path = " › ".join(parts[1:]) if len(parts) > 1 else ""
                
                type_label = "File" if stype == "File" else "Link"
                sub_badge = f'<span class="badge-path">📁 {sub_path}</span>' if sub_path else ""
                
                st.markdown(f"""
                <div class="resource-card">
                    <div>
                        <span class="badge-course">{main_course}</span>
                        {sub_badge}
                        <span class="badge-type">{type_label}</span>
                    </div>
                    <a class="card-title" href="{link}" target="_blank">{title} ↗</a>
                    <div class="card-meta">Added on {time}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Nothing here yet! Head over to 'Share a Resource' and drop the first file or link for the squad.")

with tab2:
    st.subheader("Drop a file or link for the track")
    
    default_courses = ["Software Fundamentals", "Software Testing"]
    data_rows = get_sheet_data()
    existing_courses = list(set([row[0].split(" / ")[0] for row in data_rows[1:] if len(row) > 0])) if len(data_rows) > 1 else []
    all_courses = sorted(list(set(default_courses + existing_courses))) + ["+ Add New Course..."]

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        selected_option = st.selectbox("Course:", all_courses)
        target_course = selected_option
        if selected_option == "+ Add New Course...":
            target_course = st.text_input("New Course Name:", placeholder="e.g., Automation Testing")
    with col_c2:
        subfolder_input = st.text_input(
            "Subfolder / Topic (Optional):", 
            placeholder="e.g., Labs or Lectures/Week 1"
        )

    # Build full folder path list & display string
    folder_parts = [target_course.strip()] if target_course else []
    if subfolder_input.strip():
        folder_parts.extend([p.strip() for p in subfolder_input.split("/") if p.strip()])
    full_course_label = " / ".join(folder_parts)

    source_type = st.radio("What are you sharing?", ["Upload a File", "Share a Link"], horizontal=True)

    if source_type == "Upload a File":
        uploaded_file = st.file_uploader("Choose file", type=["pdf", "zip", "py", "docx", "txt", "ipynb", "rar", "xlsx", "pptx"])
        if st.button("Upload File", type="primary") and uploaded_file and target_course:
            with st.spinner("Uploading to Drive and updating the hub..."):
                try:
                    drive_s = get_drive_service()
                    target_folder_id = get_or_create_nested_folders(drive_s, folder_parts, MAIN_FOLDER_ID)
                    
                    file_metadata = {'name': uploaded_file.name, 'parents': [target_folder_id]}
                    media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), mimetype=uploaded_file.type, resumable=True)
                    file = drive_s.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
                    
                    drive_s.permissions().create(
                        fileId=file.get('id'),
                        body={'type': 'anyone', 'role': 'reader'}
                    ).execute()
                    
                    file_link = file.get('webViewLink')
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    append_to_sheet([full_course_label, "File", uploaded_file.name, file_link, timestamp])
                    st.success(f"Done! **{uploaded_file.name}** is now live under **{full_course_label}**.")
                except Exception as e:
                    st.error(f"Upload failed: {e}")

    else:
        link_title = st.text_input("Title:", placeholder="e.g., ISTQB Foundation Syllabus or Lab 2 Repo")
        link_url = st.text_input("URL:", placeholder="https://...")
        
        if st.button("Save Link", type="primary") and link_url and link_title and target_course:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                append_to_sheet([full_course_label, "Link", link_title, link_url, timestamp])
                st.success(f"Saved! **{link_title}** is now live under **{full_course_label}**.")
            except Exception as e:
                st.error(f"Could not save link: {e}")
