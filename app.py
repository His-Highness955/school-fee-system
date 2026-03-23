import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import io
import json

# -------------------------------
# 1️⃣ Load Service Account & Spreadsheet
# -------------------------------
try:
    creds_dict = json.loads(st.secrets["google_service_account"]["json"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"❌ Connection Error: Ensure secrets are configured in Streamlit Cloud. {e}")
    st.stop()

# -------------------------------
# 2️⃣ Connect to Google Sheet
# -------------------------------
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1DHdvbVUjUhHN4vwXG6jByubgMjfKzWp2Sq3yg-zOAzc/edit"

try:
    url_clean = SPREADSHEET_URL.strip().split("/edit")[0]
    sheet = client.open_by_url(url_clean)
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

def add_student(name, student_class, total_fee, parent_phone_number):
    # Column A is now Name
    students_sheet.append_row([name, student_class, total_fee, parent_phone_number])

def add_payment(name, amount_paid, date_paid, time_paid, paid_by, recorded_by, term, session):
    # Column B in payments is now Name
    payments_sheet.append_row([None, name, amount_paid, date_paid, time_paid, paid_by, recorded_by, term, session])

# -------------------------------
# 4️⃣ Add New Student
# -------------------------------
st.header("Add New Student")
with st.form("student_form"):
    name = st.text_input("Student Full Name")
    student_class = st.text_input("Class")
    total_fee = st.number_input("Total School Fee", min_value=0.0)
    parent_phone_number = st.text_input("Parent Phone Number")
    submit = st.form_submit_button("Add Student")

    if submit:
        students_df = get_students_df()
        if not name:
            st.error("Please enter a name.")
        elif name in students_df['name'].values:
            st.error("❌ A student with this name already exists.")
        else:
            add_student(name, student_class, total_fee, parent_phone_number)
            st.success(f"✅ {name} added successfully")

# -------------------------------
# 5️⃣ Record Payment
# -------------------------------
st.header("Record Payment")
students_df = get_students_df()
if not students_df.empty:
    student_names = students_df['name'].tolist()
    with st.form("payment_form"):
        selected_name = st.selectbox("Select Student", student_names)
        amount_paid = st.number_input("Amount Paid", min_value=0.0)
        date_paid = st.date_input("Date Paid")
        time_paid = st.time_input("Time Paid")
        paid_by = st.text_input("Paid By")
        recorded_by = st.text_input("Recorded By (Staff)")
        term = st.selectbox("Term", ["First Term", "Second Term", "Third Term"])
        session = st.text_input("Session (e.g. 2025/2026)")
        submit_payment = st.form_submit_button("Record Payment")

        if submit_payment:
            add_payment(selected_name, amount_paid, str(date_paid), str(time_paid), paid_by, recorded_by, term, session)
            st.success(f"✅ Payment recorded for {selected_name}")
else:
    st.warning("No students available. Add students first.")

# -------------------------------
# 6️⃣ Student Balances & Debtors
# -------------------------------
st.header("Student Balances & Debtors")
payments_df = get_payments_df()

# Filtering Controls
col_a, col_b = st.columns(2)
with col_a:
    terms = ["All Terms"] + (payments_df['term'].dropna().unique().tolist() if not payments_df.empty else [])
    selected_term = st.selectbox("Filter by Term", terms)
with col_b:
    sessions = ["All Sessions"] + (payments_df['session'].dropna().unique().tolist() if not payments_df.empty else [])
    selected_session = st.selectbox("Filter by Session", sessions)

search_name = st.text_input("Search Student by Name")
filter_debtors = st.checkbox("Show Debtors Only")

if search_name or filter_debtors:
    filtered_students = []
    
    for _, row in students_df.iterrows():
        name = str(row['name'])
        student_class = row['class']
        total_fee = row.get('total_fee', 0.0)

        if search_name and search_name.lower() not in name.lower():
            continue

        # Match payments by Name
        student_payments = payments_df[payments_df['name'].astype(str) == name]
        
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

    if filtered_students:
        st.subheader(f"Results ({len(filtered_students)})")
        for f in filtered_students:
            color = 'green' if f['balance'] <= 0 else ('orange' if f['balance'] < f['total_fee'] else 'red')
            
            with st.container():
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"**{f['name']}**")
                c2.markdown(f"Total: ₦{f['total_fee']}")
                c3.markdown(f"Paid: ₦{f['total_paid']}")
                c4.markdown(f"Balance: <span style='color:{color};font-weight:bold'>₦{f['balance']}</span>", unsafe_allow_html=True)
                st.text(f"Class: {f['class']} | Parent: {f['parent_phone_number']}")
                st.divider()
    else:
        st.info("No matching records found.")

# -------------------------------
# 7️⃣ Admin: Delete Student Record
# -------------------------------
st.header("🗑️ Admin: Delete Student")
MASTER_CODE = "2026" 

with st.expander("Open Delete Panel"):
    students_list = get_students_df()
    if not students_list.empty:
        with st.form("delete_student_form"):
            target_name = st.selectbox("Select Student to Delete", students_list['name'].tolist())
            master_input = st.text_input("Enter Master Code", type="password")
            confirm_check = st.checkbox("Confirm permanent deletion")
            delete_submit = st.form_submit_button("Execute Delete")
            
            if delete_submit:
                if master_input == MASTER_CODE and confirm_check:
                    try:
                        # Find by Name in Column 1
                        cell = students_sheet.find(target_name, in_column=1)
                        if cell:
                            students_sheet.delete_rows(cell.row)
                            st.success(f"✅ Deleted: {target_name}")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Invalid code or confirmation missing.")

# -------------------------------
# 8️⃣ Tutorial
# -------------------------------
st.header("📖 Quick Guide")
st.info("1. **Add Student**: Use the student's full name. \n2. **Record Payment**: Select the name from the dropdown. \n3. **Search**: Type a name to see their specific balance.")
