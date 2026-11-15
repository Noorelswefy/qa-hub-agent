import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import re
from datetime import datetime

# Page Config
st.set_page_config(page_title="Software Testing Intake 47 Hub - Community Hub", page_icon="🐞", layout="wide")

# ITI-Inspired Theme CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

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
.badge-course {
    background-color: #9B1B20;
    color: #FFFFFF;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    display: inline-block;
    margin-right: 6px;
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
}
.badge-type {
    background-color: #FEF2F2;
    color: #9B1B20;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
    display: inline-block;
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

def batch_append_to_sheet(rows_list):
    if not rows_list:
        return
    service = get_sheets_service()
    body = {'values': rows_list}
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

def extract_drive_id(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    return match_id.group(1) if match_id else None

def scan_drive_folder_recursive(service, folder_id, current_path_parts):
    discovered_files = []
    page_token = None
    while True:
        query = f"'{folder_id}' in parents and trashed=false"
        response = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, createdTime)",
            pageSize=100,
            pageToken=page_token
        ).execute()
        items = response.get('files', [])
        for item in items:
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                discovered_files.extend(
                    scan_drive_folder_recursive(service, item['id'], current_path_parts + [item['name']])
                )
            else:
                course_label = " / ".join(current_path_parts) if current_path_parts else "General / Uncategorized"
                created_raw = item.get('createdTime', '')
                try:
                    dt = datetime.fromisoformat(created_raw.replace('Z', '+00:00'))
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                discovered_files.append({
                    'id': item['id'],
                    'course_path': course_label,
                    'title': item['name'],
                    'link': item.get('webViewLink', ''),
                    'time': formatted_time
                })
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    return discovered_files

def sync_drive_to_sheet():
    drive_s = get_drive_service()
    existing_rows = get_sheet_data()
    
    existing_links = set()
    existing_ids = set()
    for r in existing_rows[1:]:
        if len(r) >= 4:
            link = r[3].strip()
            existing_links.add(link)
            fid = extract_drive_id(link)
            if fid:
                existing_ids.add(fid)

    drive_files = scan_drive_folder_recursive(drive_s, MAIN_FOLDER_ID, [])
    new_rows = []

    for f in drive_files:
        if f['id'] in existing_ids or f['link'] in existing_links:
            continue
        try:
            drive_s.permissions().create(
                fileId=f['id'],
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
        except Exception:
            pass
        new_rows.append([f['course_path'], "File", f['title'], f['link'], f['time']])

    if new_rows:
        batch_append_to_sheet(new_rows)
    return len(new_rows)

# --- Header ---
st.markdown('<div class="hub-banner"><h1>🐞 Software Testing Intake 47 Hub - Community Hub</h1><p>No more digging through messy Drive folders or lost chat links — drop your labs, slides, and useful repos here so everyone finds what they need in seconds.</p></div>', unsafe_allow_html=True)

# --- Main Tabs ---
tab1, tab2 = st.tabs(["Browse Resources", "Share a Resource"])

with tab1:
    rows = get_sheet_data()
    if len(rows) > 1:
        data = rows[1:]
        
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
                course_path, stype, title, link, time = r[0].strip(), r[1].strip(), r[2].strip(), r[3].strip(), r[4].strip()
                parts = course_path.split(" / ")
                main_course = parts[0]
                sub_path = " › ".join(parts[1:]) if len(parts) > 1 else ""
                type_label = "File" if stype == "File" else "Link"
                
                with st.container(border=True):
                    badges = f'<span class="badge-course">{main_course}</span>'
                    if sub_path:
                        badges += f'<span class="badge-path">📁 {sub_path}</span>'
                    badges += f'<span class="badge-type">{type_label}</span>'
                    st.markdown(badges, unsafe_allow_html=True)
                    st.markdown(f"#### [{title} ↗]({link})")
                    st.caption(f"Added on {time}")
    else:
        st.info("Nothing here yet! Head over to 'Share a Resource' or sync existing files from Google Drive below.")

    st.divider()
    with st.expander("🔄 Drive Sync (Import existing files from Google Drive)"):
        st.caption("Uploaded files directly to Google Drive? Click below to scan folders and import missing files into the hub.")
        if st.button("Sync Drive Now"):
            with st.spinner("Scanning Google Drive folders and syncing..."):
                try:
                    added_count = sync_drive_to_sheet()
                    if added_count > 0:
                        st.success(f"Synced {added_count} new file(s) from Google Drive! Refreshing...")
                        st.rerun()
                    else:
                        st.info("Everything on Google Drive is already up to date in the hub.")
                except Exception as e:
                    st.error(f"Sync failed: {e}")

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
            "Subfolder / Topic *:", 
            placeholder="e.g., Labs or Lectures/Week 1"
        )
        if not subfolder_input.strip():
            st.caption("⚠️ Required — enter a folder or topic name to keep things organized.")

    folder_parts = [target_course.strip()] if target_course else []
    if subfolder_input.strip():
        folder_parts.extend([p.strip() for p in subfolder_input.split("/") if p.strip()])
    full_course_label = " / ".join(folder_parts)

    source_type = st.radio("What are you sharing?", ["Upload a File", "Share a Link"], horizontal=True)

    if source_type == "Upload a File":
        uploaded_file = st.file_uploader("Choose file", type=["pdf", "zip", "py", "docx", "txt", "ipynb", "rar", "xlsx", "pptx"])
        if st.button("Upload File", type="primary") and uploaded_file and target_course and subfolder_input.strip():
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
        
        if st.button("Save Link", type="primary") and link_url and link_title and target_course and subfolder_input.strip():
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                append_to_sheet([full_course_label, "Link", link_title, link_url, timestamp])
                st.success(f"Saved! **{link_title}** is now live under **{full_course_label}**.")
            except Exception as e:
                st.error(f"Could not save link: {e}")
