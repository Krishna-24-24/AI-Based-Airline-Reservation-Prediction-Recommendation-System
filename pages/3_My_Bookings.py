"""
pages/3_My_Bookings.py
--------------------------------------------------------------------
Shows the logged-in passenger's booking history, their latest stored
cancellation-risk prediction for each active booking, and a link into
the dedicated Cancel Booking page.
--------------------------------------------------------------------
"""

import streamlit as st

from database.db_connection import get_bookings_for_passenger, get_latest_prediction_for_booking
from utils.helpers import format_currency, require_login, risk_badge

st.set_page_config(page_title="My Bookings", page_icon="\U0001F4CB", layout="wide")

passenger = require_login()

st.title("\U0001F4CB My Bookings")

bookings = get_bookings_for_passenger(passenger["passenger_id"])

if not bookings:
    st.info("You have no bookings yet.")
    if st.button("Search Flights"):
        st.switch_page("pages/1_Flight_Search.py")
    st.stop()

status_filter = st.radio("Show", ["All", "Active", "Cancelled", "Completed"], horizontal=True)

for b in bookings:
    if status_filter != "All" and b["booking_status"].upper() != status_filter.upper():
        continue

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1.5])
        with c1:
            st.markdown(f"**{b['booking_ref']}** \u00b7 {b['flight_number']} ({b['airline']})")
            st.caption(f"{b['source_city']} \u2192 {b['destination_city']}")
        with c2:
            st.caption("Travel Date")
            st.write(str(b["travel_date"]))
            st.caption("Seat")
            st.write(f"{b['seat_number']} ({b['seat_class']})")
        with c3:
            st.caption("Fare")
            st.write(format_currency(b["fare"]))
            status_emoji = {"CONFIRMED": "\U0001F7E2", "CANCELLED": "\U0001F534", "COMPLETED": "\u2705"}
            st.write(f"{status_emoji.get(b['booking_status'], '')} {b['booking_status']}")
        with c4:
            if b["booking_status"] == "CONFIRMED":
                pred = get_latest_prediction_for_booking(b["booking_id"])
                if pred and pred["cancellation_risk"]:
                    st.caption("AI Risk")
                    st.write(risk_badge(pred["cancellation_risk"]))
                if st.button("Cancel Booking", key=f"cancel_{b['booking_id']}"):
                    st.session_state["cancel_booking_id"] = b["booking_id"]
                    st.switch_page("pages/4_Cancel_Booking.py")
            elif b["booking_status"] == "CANCELLED":
                st.caption("This booking has been cancelled.")
