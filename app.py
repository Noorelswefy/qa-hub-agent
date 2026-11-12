import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from datetime import datetime

# Page Configuration
st.set_page_config(page_title="Software Engineering Hub", page_icon="🎓", layout="centered")

st.title("🎓 Software Engineering Hub - Community Hub")
st.markdown("مكان موحد لجمع مصادر دفعتنا: محاضرات، Labs، مراجع، ولينكات مفيدة بسهولة تامة.")

# Load Service Account Credentials from Streamlit Secrets
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

def get_or_create_folder(service, folder_name, parent_id):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])
    if folders:
        return folders[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

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

# --- UI ---
tab1, tab2 = st.tabs(["📤 إضافة مصدر جديد", "📚 تصفح مصادر الدفعة"])

with tab1:
    st.subheader("شارك ملف أو رابط مع زملائك")
    
    default_courses = ["Software Fundamentals", "Software Testing"]
    data_rows = get_sheet_data()
    existing_courses = list(set([row[0] for row in data_rows[1:]])) if len(data_rows) > 1 else []
    all_courses = sorted(list(set(default_courses + existing_courses))) + ["+ Add New Course..."]

    selected_option = st.selectbox("اختر المادة الدراسية:", all_courses)
    target_course = selected_option
    if selected_option == "+ Add New Course...":
        target_course = st.text_input("اكتب اسم المادة الجديدة بالإنجليزية:")

    source_type = st.radio("نوع المشاركة:", ["رفع ملف (PDF, Code, Labs, etc.)", "رابط خارجي (GitHub, Website, Doc)"])

    if source_type == "رفع ملف (PDF, Code, Labs, etc.)":
        uploaded_file = st.file_uploader("اختر الملف للرفع", type=["pdf", "zip", "py", "docx", "txt", "ipynb", "rar"])
        if st.button("رفع الملف 🚀") and uploaded_file and target_course:
            with st.spinner("جاري رفع الملف إلى الدرايف..."):
                try:
                    drive_s = get_drive_service()
                    course_folder_id = get_or_create_folder(drive_s, target_course, MAIN_FOLDER_ID)
                    
                    file_metadata = {'name': uploaded_file.name, 'parents': [course_folder_id]}
                    media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), mimetype=uploaded_file.type, resumable=True)
                    file = drive_s.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
                    
                    file_link = file.get('webViewLink')
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    append_to_sheet([target_course, "File", uploaded_file.name, file_link, timestamp])
                    st.success(f"تم رفع الملف وتسجيله بنجاح لمادة **{target_course}**! 🙌")
                except Exception as e:
                    st.error(f"حدث خطأ أثناء الرفع: {e}")

    else:
        link_title = st.text_input("عنوان المصدر (مثلاً: Lab 1 Solution أو Useful Repository):")
        link_url = st.text_input("الرابط (URL):")
        
        if st.button("حفظ الرابط 🔗") and link_url and link_title and target_course:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                append_to_sheet([target_course, "Link", link_title, link_url, timestamp])
                st.success(f"تم حفظ الرابط بنجاح لمادة **{target_course}**! 🚀")
            except Exception as e:
                st.error(f"حدث خطأ أثناء الحفظ: {e}")

with tab2:
    st.subheader("📚 جميع المصادر والمواد المتاحة")
    rows = get_sheet_data()
    
    if len(rows) > 1:
        data = rows[1:]
        selected_filter = st.selectbox("فلترة حسب المادة:", ["الكل"] + list(set([r[0] for r in data])))
        filtered_data = data if selected_filter == "الكل" else [r for r in data if r[0] == selected_filter]
        
        for r in filtered_data:
            course, stype, title, link, time = r[0], r[1], r[2], r[3], r[4]
            with st.container():
                st.markdown(f"**المادة:** `{course}` | **النوع:** `{stype}`")
                st.markdown(f"🔗 [{title}]({link})  \n *تاريخ الإضافة: {time}*")
                st.divider()
    else:
        st.info("لا توجد مصادر مضافة حتى الآن. كن أول من يشارك!")
