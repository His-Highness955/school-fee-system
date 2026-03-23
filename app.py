import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import io
import json

# -------------------------------
# 1️⃣ Load Service Account & Spreadsheet
# -------------------------------

# This will automatically use the secrets you've saved in Streamlit Cloud
try:
    # We parse the secret directly. 
    # NOTE: Ensure your secret name in Streamlit matches "google_service_account"
    creds_dict = json.loads(st.secrets["google_service_account"]["json"])
    
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Optional: remove st.success if you want a cleaner UI
except Exception as e:
    st.error(f"❌ Connection Error: Ensure secrets are configured in Streamlit Cloud. {e}")
    st.stop()

# -------------------------------
# 2️⃣ Connect to Google Sheet
# -------------------------------

# Set your Google Sheet URL here
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1DHdvbVUjUhHN4vwXG6jByubgMjfKzWp2Sq3yg-zOAzc/edit"

try:
    SPREADSHEET_URL = SPREADSHEET_URL.strip().split("/edit")[0]
    sheet = client.open_by_url(SPREADSHEET_URL)
    students_sheet = sheet.worksheet("students")
    payments_sheet = sheet.worksheet("payments")
    st.success("✅ Connected to Google Sheets successfully!")
except Exception as e:
    st.error(f"Cannot access the spreadsheet: {e}")
    st.stop()

# -------------------------------
# 3️⃣ Helper Functions
# -------------------------------

def clean_columns(df):
    df.columns = [str(col).strip() if col is not None else "" for col in df.columns]
    return df

def get_students_df():
    df = pd.DataFrame(students_sheet.get_all_records())
    df = clean_columns(df)
    if 'total_fee' in df.columns:
        df['total_fee'] = pd.to_numeric(df['total_fee'], errors='coerce').fillna(0.0)
    return df

def get_payments_df():
    df = pd.DataFrame(payments_sheet.get_all_records())
    df = clean_columns(df)
    if 'amount_paid' in df.columns:
        df['amount_paid'] = pd.to_numeric(df['amount_paid'], errors='coerce').fillna(0.0)
    return df

def add_student(student_id, name, student_class, total_fee, parent_phone_number):
    students_sheet.append_row([student_id, name, student_class, total_fee, parent_phone_number])

def add_payment(student_id, amount_paid, date_paid, time_paid, paid_by, recorded_by, term, session):
    payments_sheet.append_row([None, student_id, amount_paid, date_paid, time_paid, paid_by, recorded_by, term, session])

# -------------------------------
# 4️⃣ Add New Student
# -------------------------------
st.header("Add New Student")
with st.form("student_form"):
    student_id = st.text_input("Student ID")
    name = st.text_input("Student Name")
    student_class = st.text_input("Class")
    total_fee = st.number_input("Total School Fee", min_value=0.0)
    parent_phone_number = st.text_input("Parent Phone Number")
    submit = st.form_submit_button("Add Student")

    if submit:
        students_df = get_students_df()
        if student_id in students_df['student_id'].values:
            st.error("❌ Student ID already exists")
        else:
            add_student(student_id, name, student_class, total_fee, parent_phone_number)
            st.success("✅ Student added successfully")

# -------------------------------
# 5️⃣ Record Payment
# -------------------------------
st.header("Record Payment")
students_df = get_students_df()
if not students_df.empty:
    student_options = {f"{row['student_id']} - {row['name']}": row['student_id'] for _, row in students_df.iterrows()}
    with st.form("payment_form"):
        selected_student = st.selectbox("Select Student", list(student_options.keys()))
        student_id = student_options[selected_student]

        amount_paid = st.number_input("Amount Paid", min_value=0.0)
        date_paid = st.date_input("Date Paid")
        time_paid = st.time_input("Time Paid")
        paid_by = st.text_input("Paid By (Who brought the money)")
        recorded_by = st.text_input("Recorded By (Staff name)")
        term = st.selectbox("Term", ["First Term", "Second Term", "Third Term"])
        session = st.text_input("Session (e.g. 2025/2026)")
        submit_payment = st.form_submit_button("Record Payment")

        if submit_payment:
            add_payment(student_id, amount_paid, str(date_paid), str(time_paid), paid_by, recorded_by, term, session)
            st.success("✅ Payment recorded successfully")
else:
    st.warning("No students available. Add students first.")

# -------------------------------
# 6️⃣ Student Balances & Debtors
# -------------------------------
st.header("Student Balances & Debtors")
students_df = get_students_df()
payments_df = get_payments_df()

if 'term' not in payments_df.columns or 'session' not in payments_df.columns:
    st.error("❌ Payments sheet must have 'term' and 'session' columns")
    st.stop()

terms = ["All Terms"] + payments_df['term'].dropna().unique().tolist()
sessions = ["All Sessions"] + payments_df['session'].dropna().unique().tolist()
selected_term = st.selectbox("Filter by Term", terms)
selected_session = st.selectbox("Filter by Session", sessions)

search_name = st.text_input("Search Student by Name")
filter_debtors = st.checkbox("Filter by Debtors")

if search_name or filter_debtors:
    filtered_students = []
    for _, row in students_df.iterrows():
        student_id = row['student_id']
        name = row['name']
        student_class = row['class']
        total_fee = row.get('total_fee', 0.0)

        student_payments = payments_df[payments_df['student_id'] == student_id]
        if selected_term != "All Terms":
            student_payments = student_payments[student_payments['term'] == selected_term]
        if selected_session != "All Sessions":
            student_payments = student_payments[student_payments['session'] == selected_session]

        total_paid = student_payments['amount_paid'].sum() if not student_payments.empty else 0
        balance = total_fee - total_paid

        if filter_debtors and balance <= 0:
            continue

        filtered_students.append({
            "name": name,
            "class": student_class,
            "total_fee": total_fee,
            "total_paid": total_paid,
            "balance": balance,
            "parent_phone_number": row.get('parent_phone_number', '')
        })

    st.subheader("Filtered Student Balances")
    debtors_list = []

    for f in filtered_students:
        if f['balance'] == 0:
            color = 'green'
            status = "Paid in Full ✅"
        elif f['balance'] < f['total_fee']:
            color = 'orange'
            status = "Partial Payment ⚠️"
            debtors_list.append(f)
        else:
            color = 'red'
            status = "No Payment ❌"
            debtors_list.append(f)

        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f"**{f['name']} ({f['class']})**")
        col2.markdown(f"Total Fee: ₦{f['total_fee']}")
        col3.markdown(f"Paid: ₦{f['total_paid']}")
        col4.markdown(f"Balance: <span style='color:{color};font-weight:bold'>₦{f['balance']}</span>", unsafe_allow_html=True)
        st.markdown(f"Parent Phone: {f['parent_phone_number']}")
        st.markdown(f"Status: **{status}**")
        st.markdown("---")

    st.subheader("Debtors Only")
    if debtors_list:
        for d in debtors_list:
            st.error(f"{d['name']} ({d['class']}) - Balance: ₦{d['balance']} - Parent Phone: {d['parent_phone_number']}")

        if st.button("Export Debtors to CSV"):
            df = pd.DataFrame(debtors_list)
            buffer = io.BytesIO()
            df.to_csv(buffer, index=False)
            st.download_button(
                label="Download Debtors CSV",
                data=buffer,
                file_name="debtors.csv",
                mime="text/csv"
            )
    else:
        st.success("No debtors found ✅")
else:
    st.info("🔎 Type a student name or check 'Filter by Debtors' to see results.")

# -------------------------------
# 7️⃣ Admin: Delete Student Record
# -------------------------------
st.header("🗑️ Admin: Delete Student")
MASTER_CODE = "2026" # Change this to your preferred code

with st.expander("Open Delete Panel"):
    with st.form("delete_student_form"):
        st.write("Deleting a student removes them from the database.")
        students_list = get_students_df()
        
        if not students_list.empty:
            # Map names to IDs for precise deletion
            delete_options = {f"{row['student_id']} - {row['name']}": row['student_id'] for _, row in students_list.iterrows()}
            selected_to_delete = st.selectbox("Select Student to Delete", list(delete_options.keys()))
            
            master_input = st.text_input("Enter Master Code", type="password")
            confirm_check = st.checkbox("I understand this action is permanent")
            
            delete_submit = st.form_submit_button("Permanent Delete")
            
            if delete_submit:
                if master_input == MASTER_CODE and confirm_check:
                    try:
                        # Find student ID in the sheet
                        student_id_to_find = delete_options[selected_to_delete]
                        cell = students_sheet.find(str(student_id_to_find))
                        students_sheet.delete_rows(cell.row)
                        st.success(f"✅ Student {selected_to_delete} deleted successfully.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: Could not locate row. {e}")
                elif master_input != MASTER_CODE:
                    st.error("❌ Incorrect Master Code.")
                else:
                    st.warning("⚠️ Please check the confirmation box.")
        else:
            st.write("No students found to delete.")

# -------------------------------
# 8️⃣ Tutorial
# -------------------------------
st.header("📖 How to Use the School Fee System")
with st.expander("1️⃣ Add New Student"):
    st.write("- Fill Student ID, Name, Class, Total Fee, Parent Phone Number  \n- Click Add Student")
with st.expander("2️⃣ Record Payment"):
    st.write("- Select student, fill amount, date/time, paid by, recorded by, term/session  \n- Click Record Payment")
with st.expander("3️⃣ Search/Filter"):
    st.write("- Search student by name or check 'Filter by Debtors'  \n- Color-coded balances: Green=Full, Orange=Partial, Red=No Payment")
with st.expander("4️⃣ Export Debtors"):
    st.write("- After filtering debtors, click Export Debtors to CSV")
st.success("You are ready to manage school fees ✅")
