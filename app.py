"""
app.py
--------------------------------------------------------------------
Home page of the AI Airline Reservation System. Handles login /
registration and links out to the other pages (Streamlit's built-in
multi-page navigation picks up everything under pages/ automatically).
--------------------------------------------------------------------
"""

import streamlit as st

from database.db_connection import test_connection
from utils.helpers import is_valid_email, login, logout, register

st.set_page_config(
    page_title="AI Airline Reservation System",
    page_icon="\u2708\ufe0f",
    layout="wide",
)

if "passenger" not in st.session_state:
    st.session_state["passenger"] = None

st.title("\u2708\ufe0f AI Airline Reservation System")
st.caption("Search and book flights with AI-powered booking risk and occupancy predictions.")

ok, msg = test_connection()
if not ok:
    st.error(
        "Could not connect to MySQL. Check your `.streamlit/secrets.toml` "
        f"(or DB_* environment variables) and make sure the database is running.\n\nDetails: {msg}"
    )
    st.info(
        "Setup reminder:\n"
        "1. `mysql -u root -p -e \"CREATE DATABASE airline_ai_system;\"`\n"
        "2. `mysql -u root -p airline_ai_system < database/schema.sql`\n"
        "3. `python database/seed_data.py`\n"
        "4. Fill in `.streamlit/secrets.toml` with your MySQL credentials."
    )
    st.stop()

passenger = st.session_state["passenger"]

if passenger is None:
    tab_login, tab_register = st.tabs(["Log In", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In")
            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    success, message = login(email, password)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        st.caption("Demo account -> rahul.kumar@example.com / password123")

    with tab_register:
        with st.form("register_form"):
            name = st.text_input("Full Name")
            email_r = st.text_input("Email", key="reg_email")
            phone = st.text_input("Phone")
            col1, col2 = st.columns(2)
            with col1:
                age = st.number_input("Age", min_value=1, max_value=120, value=25)
            with col2:
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            password_r = st.text_input("Password", type="password", key="reg_password")
            password_confirm = st.text_input("Confirm Password", type="password")
            submitted_r = st.form_submit_button("Create Account")

            if submitted_r:
                if not all([name, email_r, phone, password_r]):
                    st.error("Please fill in all fields.")
                elif not is_valid_email(email_r):
                    st.error("Please enter a valid email address.")
                elif password_r != password_confirm:
                    st.error("Passwords do not match.")
                elif len(password_r) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    success, result = register(name, email_r, phone, age, gender, password_r)
                    if success:
                        st.success("Account created! Please log in from the Log In tab.")
                    else:
                        st.error(result)

else:
    st.success(f"Welcome back, **{passenger['name']}**!")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("\U0001F50D Search Flights", use_container_width=True):
            st.switch_page("pages/1_Flight_Search.py")
    with col2:
        if st.button("\U0001F4CB My Bookings", use_container_width=True):
            st.switch_page("pages/3_My_Bookings.py")
    with col3:
        if st.button("\U0001F4CA Admin Dashboard", use_container_width=True):
            st.switch_page("pages/5_Admin_Dashboard.py")

    st.divider()
    if st.button("Log Out"):
        logout()
        st.rerun()

st.divider()
with st.expander("About this system"):
    st.markdown(
        """
        This is an **AI-integrated DBMS project**: every booking and
        cancellation runs as a MySQL transaction, and every transaction
        immediately triggers two machine-learning predictions —

        - **Cancellation / No-Show Risk** (Random Forest classifier)
        - **Flight Occupancy Forecast** (Random Forest regressor)

        Both models are trained offline (see `models/train_*.py`) and
        loaded once at runtime; predictions always use the *current*
        data pulled live from MySQL, and every prediction is written
        back to the `prediction` table.
        """
    )
