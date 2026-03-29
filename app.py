import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import json
import io
from datetime import datetime
import pytz  # Handles Internet/Network Timezones

# -------------------------------
# 1️⃣ Sync Internet Time Function
# -------------------------------
def get_internet_time():
    # This ensures the time is correct regardless of where the server is hosted
    nigeria_tz = pytz.timezone('Africa/Lagos')
    return datetime.now(nigeria_tz)

# Initial fetch for display
internet_now = get_internet_time()
current_date_str = internet_now.strftime("%Y-%m-%d")
current_time_str = internet_now.strftime("%H:%M:%S")

# -------------------------------
# 2️⃣ Connection Logic
# -------------------------------
try:
    # Load credentials from Streamlit Secrets
    creds_dict = json.loads(st.secrets["google_service_account"]["json"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Open Spreadsheet
    # Ensure this URL matches your actual Google Sheet
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1DHdvbVUjUhHN4vwXG6jByubgMjfKzWp2Sq3yg-zOAzc/edit"
    url_clean = SPREADSHEET_URL.strip().split("/edit")[0]
    sheet = client.open_by_url(url_clean)
    students_sheet = sheet.worksheet("students")
    payments_sheet = sheet.worksheet("payments")
except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.stop()

# Helper to clean headers and fetch data
def fetch_data(worksheet):
    data = worksheet.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    # Clean headers: lowercase and remove hidden spaces
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

# -------------------------------
# 3️⃣ Main UI & Global Refresh
# -------------------------------
st.title("🏫 School Fee Management System")
st.info(f"🌐 **Internet Time (Lagos):** {current_date_str} | {current_time_str}")

# Refresh Data from Sheets
students_df = fetch_data(students_sheet)
payments_df = fetch_data(payments_sheet)

# Global Class List
class_options = [
    "Kg 1", "Kg 1b", "Kg 2", "Nur 1", "Nur 2", 
    "Pry 1", "Pry 2", "Pry 3", "Pry 4", "Pry 5", 
    "Jss 1", "Jss 2", "Jss 3", "Ss 1", "Ss 2", "Ss 3"
]

# --- SECTION: ADD STUDENT ---
with st.expander("➕ Add New Student", expanded=False):
    with st.form("student_form", clear_on_submit=True):
        name_in = st.text_input("Student Full Name")
        class_in = st.selectbox("Select Class", class_options)
        fee_in = st.number_input("Total School Fee (₦)", min_value=0.0)
        phone_in = st.text_input("Parent Phone Number")
        
        submit_student = st.form_submit_button("Save Student")

        if submit_student and name_in:
            # Expected Student Sheet Headers: name, class, total_fee, parent_phone
            students_sheet.append_row([name_in, class_in, fee_in, phone_in])
            st.success(f"✅ {name_in} added successfully!")
            st.rerun()

# --- SECTION: RECORD PAYMENT ---
with st.expander("💰 Record New Payment", expanded=False):
    if not students_df.empty:
        with st.form("payment_form", clear_on_submit=True):
            student_names = sorted(students_df['name'].tolist())
            selected_student = st.selectbox("Select Student", student_names)
            
            amount = st.number_input("Amount Paid (₦)", min_value=0.0)
            
            # Recalculate Internet Time specifically for this form rendering
            live_now = get_internet_time()
            date_val = st.date_input("Date Paid", value=live_now.date())
            time_val = st.time_input("Time Paid", value=live_now.time())
            
            payer = st.text_input("Paid By (Payer Name)")
            staff = st.text_input("Recorded By (Staff Name)")
            term_val = st.selectbox("Term", ["First Term", "Second Term", "Third Term"])
            session_val = st.text_input("Session (e.g., 2025/2026)")
            
            submit_pay = st.form_submit_button("Confirm Payment")

            if submit_pay:
                # Capture the EXACT internet time at the precise second of submission
                exact_time = get_internet_time().strftime("%H:%M:%S")
                
                # ORDER: name, amount_paid, date_paid, time_paid, paid_by, recorded_by, term, session
                payments_sheet.append_row([
                    selected_student, 
                    amount, 
                    str(date_val), 
                    exact_time, 
                    payer, 
                    staff, 
                    term_val, 
                    session_val
                ])
                st.success(f"✅ Payment for {selected_student} recorded at {exact_time}!")
                st.rerun()
    else:
        st.warning("Please add students first.")

# --- SECTION: VIEW BALANCES ---
with st.expander("🔍 View Balances & Debtors", expanded=True):
    if not students_df.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            t_filter = st.selectbox("Filter Term", ["All Terms"] + (sorted(payments_df['term'].unique().tolist()) if 'term' in payments_df.columns else []))
        with col2:
            s_filter = st.selectbox("Filter Session", ["All Sessions"] + (sorted(payments_df['session'].unique().tolist()) if 'session' in payments_df.columns else []))
        with col3:
            c_filter = st.selectbox("Filter Class", ["All Classes"] + class_options)
        
        search_name = st.text_input("Search Student Name")
        debtors_only = st.checkbox("Show Only Debtors")

        report_data = []
        for _, s in students_df.iterrows():
            if search_name and search_name.lower() not in s['name'].lower():
                continue
            if c_filter != "All Classes" and s['class'] != c_filter:
                continue
            
            # Match Payments
            s_pays = payments_df[payments_df['name'] == s['name']] if not payments_df.empty else pd.DataFrame()
            
            if not s_pays.empty:
                if t_filter != "All Terms":
                    s_pays = s_pays[s_pays['term'] == t_filter]
                if s_filter != "All Sessions":
                    s_pays = s_pays[s_pays['session'] == s_filter]

            total_paid = pd.to_numeric(s_pays['amount_paid'], errors='coerce').sum() if not s_pays.empty else 0
            total_fee = pd.to_numeric(s.get('total_fee', 0), errors='coerce')
            balance = total_fee - total_paid
            
            if debtors_only and balance <= 0:
                continue
                
            report_data.append({
                "Name": s['name'], 
                "Class": s.get('class', 'N/A'), 
                "Total Fee": total_fee, 
                "Paid": total_paid, 
                "Balance": balance
            })

        if report_data:
            df_report = pd.DataFrame(report_data)
            st.dataframe(df_report, use_container_width=True)
            
            # CSV Download
            csv_buf = io.BytesIO()
            df_report.to_csv(csv_buf, index=False)
            st.download_button("📥 Download Report", data=csv_buf.getvalue(), file_name="student_balances.csv", mime="text/csv")
        else:
            st.info("No matching records found.")

# --- SECTION: ADMIN DELETE ---
with st.expander("🗑️ Admin: Remove Student", expanded=False):
    MASTER_CODE = "2026"
    if not students_df.empty:
        to_delete = st.selectbox("Student to Remove", sorted(students_df['name'].tolist()), key="admin_del")
        m_code = st.text_input("Master Code", type="password")
        if st.button("Delete Permanently"):
            if m_code == MASTER_CODE:
                # Find by name in the first column
                cell = students_sheet.find(to_delete, in_column=1)
                if cell:
                    students_sheet.delete_rows(cell.row)
                    st.success(f"Deleted {to_delete}.")
                    st.rerun()
            else:
                st.error("Invalid Master Code.")

# --- SECTION: TUTORIAL ---
st.header("📖 Quick Guide")
st.info("1. **Add Student**: Select a class from the dropdown and save. \n2. **Record Payment**: Time is pulled live from the internet upon submission. \n3. **View Balances**: Use filters to narrow down specific classes or debtors.")
