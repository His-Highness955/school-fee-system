import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import io
import json
from datetime import datetime
import pytz

# -------------------------------
# 1️⃣ Setup & Network Time
# -------------------------------
try:
    local_tz = pytz.timezone('Africa/Lagos') 
    now = datetime.now(local_tz)
except:
    now = datetime.now()

SCHOOL_CLASSES = [
    "Kg 1", "Kg 1b", "Kg 2", "Nur 1", "Nur 2", 
    "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", 
    "Jss 1", "Jss 2", "Jss 3", "Ss 1", "Ss 2", "Ss 3"
]

# -------------------------------
# 2️⃣ Connection Logic
# -------------------------------
try:
    creds_dict = json.loads(st.secrets["google_service_account"]["json"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1DHdvbVUjUhHN4vwXG6jByubgMjfKzWp2Sq3yg-zOAzc/edit"
    url_clean = SPREADSHEET_URL.strip().split("/edit")[0]
    sheet = client.open_by_url(url_clean)
    students_sheet = sheet.worksheet("students")
    payments_sheet = sheet.worksheet("payments")
except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.stop()

# -------------------------------
# 3️⃣ Helper Functions (Crucial for fixing KeyError)
# -------------------------------
def fetch_data(worksheet):
    data = worksheet.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    # This strips spaces and makes all column names lowercase for consistency
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

# -------------------------------
# 4️⃣ UI - Collapsible Sections
# -------------------------------
st.title("🏫 School Fee Management System")
st.write(f"📅 **Network Date:** {now.strftime('%d %B %Y')} | 🕒 **Time:** {now.strftime('%H:%M:%S')}")

# Refresh data
students_df = fetch_data(students_sheet)
payments_df = fetch_data(payments_sheet)

# --- SECTION: ADD STUDENT ---
with st.expander("➕ Add New Student"):
    with st.form("student_form", clear_on_submit=True):
        name = st.text_input("Student Full Name")
        student_class = st.selectbox("Select Class", SCHOOL_CLASSES)
        total_fee = st.number_input("Total School Fee (₦)", min_value=0.0)
        parent_phone = st.text_input("Parent Phone Number")
        submit_student = st.form_submit_button("Save Student")

        if submit_student and name:
            # Note: Headers in Sheet should be: name, class, total_fee, parent_phone
            students_sheet.append_row([name, student_class, total_fee, parent_phone])
            st.success(f"✅ {name} added!")
            st.rerun()

# --- SECTION: RECORD PAYMENT ---
with st.expander("💰 Record New Payment"):
    if not students_df.empty:
        with st.form("payment_form", clear_on_submit=True):
            # Using 'name' (lowercase) because of our fetch_data function
            student_names = sorted(students_df['name'].tolist())
            selected_name = st.selectbox("Select Student", student_names)
            
            amount_paid = st.number_input("Amount Paid (₦)", min_value=0.0)
            date_paid = st.date_input("Date Paid", value=now.date())
            time_paid = st.time_input("Time Paid", value=now.time())
            
            paid_by = st.text_input("Paid By")
            recorded_by = st.text_input("Recorded By (Staff)")
            term = st.selectbox("Term", ["First Term", "Second Term", "Third Term"])
            session = st.text_input("Session (e.g., 2025/2026)")
            submit_pay = st.form_submit_button("Confirm Payment")

            if submit_pay:
                # Headers: id (null), name, amount_paid, date, time, payer, staff, term, session
                payments_sheet.append_row([
                    None, selected_name, amount_paid, 
                    str(date_paid), str(time_paid), 
                    paid_by, recorded_by, term, session
                ])
                st.success("✅ Payment recorded!")
                st.rerun()

# --- SECTION: BALANCES & SEARCH ---
with st.expander("🔍 View Balances & Debtors", expanded=True):
    if not students_df.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            # Check if columns exist before filtering
            terms = ["All Terms"]
            if 'term' in payments_df.columns:
                terms += sorted(payments_df['term'].unique().tolist())
            term_filter = st.selectbox("Filter Term", terms)
        with c2:
            sessions = ["All Sessions"]
            if 'session' in payments_df.columns:
                sessions += sorted(payments_df['session'].unique().tolist())
            session_filter = st.selectbox("Filter Session", sessions)
        with c3:
            class_filter = st.selectbox("Filter Class", ["All Classes"] + SCHOOL_CLASSES)
        
        search_q = st.text_input("Search Student Name")
        only_debtors = st.checkbox("Show Only Debtors")

        results = []
        for _, s in students_df.iterrows():
            if search_q and search_q.lower() not in s['name'].lower():
                continue
            if class_filter != "All Classes" and s['class'] != class_filter:
                continue
            
            # Match payments
            s_pays = pd.DataFrame()
            if not payments_df.empty and 'name' in payments_df.columns:
                s_pays = payments_df[payments_df['name'] == s['name']]
            
            if not s_pays.empty:
                if term_filter != "All Terms" and 'term' in s_pays.columns:
                    s_pays = s_pays[s_pays['term'] == term_filter]
                if session_filter != "All Sessions" and 'session' in s_pays.columns:
                    s_pays = s_pays[s_pays['session'] == session_filter]

            total_pd = s_pays['amount_paid'].sum() if not s_pays.empty else 0
            # Use .get() to avoid errors if total_fee is missing
            fee = s.get('total_fee', 0)
            bal = fee - total_pd
            
            if only_debtors and bal <= 0:
                continue
                
            results.append({
                "Name": s['name'], 
                "Class": s.get('class', 'N/A'), 
                "Total Fee": fee, 
                "Paid": total_pd, 
                "Balance": bal
            })

        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True)
        else:
            st.info("No matching records.")

# --- SECTION: ADMIN DELETE ---
with st.expander("🗑️ Admin: Remove Student"):
    MASTER_CODE = "2026"
    if not students_df.empty:
        admin_name = st.selectbox("Student to Remove", sorted(students_df['name'].tolist()), key="del_select")
        pass_code = st.text_input("Master Code", type="password", key="del_pass")
        if st.button("Delete Permanently"):
            if pass_code == MASTER_CODE:
                # Search in column 1 (Name)
                cell = students_sheet.find(admin_name, in_column=1)
                if cell:
                    students_sheet.delete_rows(cell.row)
                    st.success("Deleted.")
                    st.rerun()
            else:
                st.error("Incorrect code.")
                
# -------------------------------
# 8️⃣ Tutorial
# -------------------------------
st.header("📖 Quick Guide")
st.info("1. **Add Student**: Use the student's full name. \n2. **Record Payment**: Select the name from the dropdown. \n3. **Search**: Type a name to see their specific balance.")
