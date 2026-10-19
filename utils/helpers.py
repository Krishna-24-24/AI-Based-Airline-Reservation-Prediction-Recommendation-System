"""Formatting, badges, and auth helpers."""

import re

import bcrypt
import streamlit as st

from database.db_connection import (
    create_passenger,
    get_admin_by_email,
    get_passenger_by_email,
    insert_audit,
)
from utils.validators import valid_email


def format_currency(amount):
    try:
        return f"\u20b9{float(amount):,.2f}"
    except (TypeError, ValueError):
        return "\u20b90.00"


def risk_badge(level):
    colors = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
    return f"{colors.get(level, '⚪')} {level}"


def occupancy_badge(level):
    colors = {"LOW": "🟦", "MEDIUM": "🟨", "HIGH": "🟥"}
    return f"{colors.get(level, '⚪')} {level}"


def hash_password(plain_password):
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password, password_hash):
    try:
        return bcrypt.checkpw(plain_password.encode(), password_hash.encode())
    except ValueError:
        return False


def is_valid_email(email):
    return valid_email(email)


def current_user():
    return st.session_state.get("user")


def require_login():
    if "passenger" not in st.session_state or st.session_state["passenger"] is None:
        user = st.session_state.get("user")
        if user and user.get("role") == "PASSENGER" and st.session_state.get("passenger"):
            return st.session_state["passenger"]
        st.warning("Please log in from the Home page to continue.")
        st.stop()
    return st.session_state["passenger"]


def require_role(*roles):
    user = st.session_state.get("user")
    if user is None or user.get("role") not in roles:
        st.error("You do not have permission to view this page.")
        st.stop()
    return user


def login(email, password):
    passenger = get_passenger_by_email(email)
    if passenger is not None:
        if passenger.get("account_status") == "INACTIVE":
            return False, "This account is inactive."
        if not verify_password(password, passenger["password_hash"]):
            insert_audit(passenger["passenger_id"], "PASSENGER", "LOGIN", "passenger",
                         passenger["passenger_id"], "failed password")
            return False, "Incorrect password."
        st.session_state["passenger"] = passenger
        st.session_state["admin"] = None
        st.session_state["user"] = {
            "id": passenger["passenger_id"],
            "name": passenger["name"],
            "email": passenger["email"],
            "role": "PASSENGER",
        }
        insert_audit(passenger["passenger_id"], "PASSENGER", "LOGIN", "passenger",
                     passenger["passenger_id"], "success")
        return True, "Logged in successfully."

    admin = get_admin_by_email(email)
    if admin is None:
        return False, "No account found with that email."
    if admin.get("account_status") == "INACTIVE":
        return False, "This account is inactive."
    if not verify_password(password, admin["password_hash"]):
        return False, "Incorrect password."
    st.session_state["passenger"] = None
    st.session_state["admin"] = admin
    st.session_state["user"] = {
        "id": admin["admin_id"],
        "name": admin["name"],
        "email": admin["email"],
        "role": admin["role"],
    }
    insert_audit(admin["admin_id"], admin["role"], "LOGIN", "admin_user", admin["admin_id"], "success")
    return True, f"Logged in as {admin['role']}."


def register(name, email, phone, age, gender, password):
    if get_passenger_by_email(email) is not None:
        return False, "An account with that email already exists."
    password_hash = hash_password(password)
    passenger_id = create_passenger(name, email, phone, age, gender, password_hash)
    return True, passenger_id


def logout():
    st.session_state["passenger"] = None
    st.session_state["admin"] = None
    st.session_state["user"] = None
