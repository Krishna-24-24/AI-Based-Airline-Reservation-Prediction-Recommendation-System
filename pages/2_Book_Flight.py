"""
pages/2_Book_Flight.py
--------------------------------------------------------------------
Shows flight + fare details, an interactive seat map pulled live from
MySQL, and confirms the booking as a database transaction. Immediately
after a successful booking, runs BOTH AI models against the freshly
updated database state and displays the results (per spec section 16).
--------------------------------------------------------------------
"""

from datetime import datetime

import streamlit as st

from database.db_connection import (BookingError, book_flight, get_flight_by_id,
                                     get_seats_for_flight)
from ml.cancellation_prediction import predict_cancellation_risk
from ml.occupancy_prediction import predict_flight_occupancy
from utils.helpers import format_currency, occupancy_badge, require_login, risk_badge

st.set_page_config(page_title="Book Flight", page_icon="\U0001F4B3", layout="wide")

passenger = require_login()

st.title("\U0001F4B3 Book Flight")

flight_id = st.session_state.get("selected_flight_id")
if flight_id is None:
    st.warning("No flight selected. Please search and select a flight first.")
    if st.button("Go to Flight Search"):
        st.switch_page("pages/1_Flight_Search.py")
    st.stop()

flight = get_flight_by_id(flight_id)
if flight is None:
    st.error("The selected flight no longer exists.")
    st.stop()

travel_date = st.session_state.get("selected_travel_date") or flight["departure_time"].strftime("%Y-%m-%d")

# ---------------------------------------------------------------------
# Flight summary
# ---------------------------------------------------------------------
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader(f"{flight['flight_number']} — {flight['airline']}")
        st.caption(f"{flight['source_city']} \u2192 {flight['destination_city']}")
    with c2:
        st.metric("Departure", flight["departure_time"].strftime("%d %b, %H:%M"))
        st.metric("Arrival", flight["arrival_time"].strftime("%d %b, %H:%M"))
    with c3:
        st.metric("Base Fare", format_currency(flight["base_fare"]))
        st.metric("Seats Available", f"{flight['available_seats']} / {flight['total_seats']}")

st.subheader("Passenger")
st.write(f"**{passenger['name']}** ({passenger['email']}) — Age {passenger['age']}")

# ---------------------------------------------------------------------
# Seat map
# ---------------------------------------------------------------------
st.subheader("\U0001F4BA Select a Seat")

seats = get_seats_for_flight(flight_id)
if "selected_seat_id" not in st.session_state:
    st.session_state["selected_seat_id"] = None

# group seats by row number for a clean grid layout
rows = {}
for s in seats:
    row_num = "".join(filter(str.isdigit, s["seat_number"]))
    rows.setdefault(row_num, []).append(s)

legend1, legend2, legend3 = st.columns(3)
legend1.markdown("\U0001F7E9 Available")
legend2.markdown("\U0001F7E5 Booked")
legend3.markdown("\U0001F535 Selected")

for row_num in sorted(rows.keys(), key=int):
    cols = st.columns(len(rows[row_num]))
    for col, seat in zip(cols, sorted(rows[row_num], key=lambda s: s["seat_number"])):
        is_selected = st.session_state["selected_seat_id"] == seat["seat_id"]
        if seat["status"] == "BOOKED":
            col.button(f"\U0001F7E5 {seat['seat_number']}", key=f"seat_{seat['seat_id']}", disabled=True, use_container_width=True)
        else:
            label = f"\U0001F535 {seat['seat_number']}" if is_selected else f"\U0001F7E9 {seat['seat_number']}"
            if col.button(label, key=f"seat_{seat['seat_id']}", use_container_width=True):
                st.session_state["selected_seat_id"] = seat["seat_id"]
                st.rerun()

selected_seat = next((s for s in seats if s["seat_id"] == st.session_state["selected_seat_id"]), None)

st.divider()

# ---------------------------------------------------------------------
# Fare + confirm
# ---------------------------------------------------------------------
if selected_seat:
    fare = float(flight["base_fare"])
    if selected_seat["seat_class"] == "BUSINESS":
        fare = round(fare * 1.6, 2)

    st.info(f"Selected seat: **{selected_seat['seat_number']}** ({selected_seat['seat_class']}) \u2014 Fare: **{format_currency(fare)}**")

    if st.button("\u2705 Confirm Booking", type="primary", use_container_width=True):
        try:
            booking_id, booking_ref = book_flight(
                passenger_id=passenger["passenger_id"],
                flight_id=flight_id,
                seat_id=selected_seat["seat_id"],
                travel_date=travel_date,
                fare=fare,
            )

            st.session_state["selected_seat_id"] = None
            st.session_state.pop("selected_flight_id", None)

            st.success("Booking Confirmed!")
            with st.container(border=True):
                st.markdown(f"**Booking ID:** {booking_ref}")
                st.markdown(f"**Passenger:** {passenger['name']}")
                st.markdown(f"**Flight:** {flight['flight_number']}")
                st.markdown(f"**Route:** {flight['source_city']} \u2192 {flight['destination_city']}")
                st.markdown(f"**Seat:** {selected_seat['seat_number']}")
                st.markdown(f"**Fare:** {format_currency(fare)}")
                st.markdown(f"**Status:** CONFIRMED")

            # ---------------------------------------------------------
            # Run BOTH AI models against the freshly updated DB state
            # ---------------------------------------------------------
            st.divider()
            st.subheader("\U0001F916 Your Booking AI Analysis")
            with st.spinner("Running cancellation risk model..."):
                risk_result = predict_cancellation_risk(booking_id)
            rc1, rc2 = st.columns(2)
            rc1.metric("Cancellation / No-Show Probability", f"{risk_result['probability'] * 100:.1f}%")
            rc2.metric("Risk Level", risk_badge(risk_result["risk_level"]))

            st.subheader("\U0001F4C8 Flight Occupancy Forecast")
            with st.spinner("Running occupancy model..."):
                occ_result = predict_flight_occupancy(flight_id, booking_id=booking_id)
            oc1, oc2, oc3 = st.columns(3)
            oc1.metric("Current Bookings", f"{occ_result['current_bookings']} / {occ_result['flight_capacity']}")
            oc2.metric("Predicted Actual Passengers", occ_result["predicted_passengers"])
            oc3.metric("Predicted Occupancy", f"{occ_result['predicted_occupancy']}%")
            st.markdown(f"**Occupancy Level:** {occupancy_badge(occ_result['occupancy_level'])}")

            if st.button("View My Bookings"):
                st.switch_page("pages/3_My_Bookings.py")

        except BookingError as e:
            st.error(str(e))
            st.rerun()
else:
    st.warning("Please select an available seat above to continue.")
