"""
pages/4_Cancel_Booking.py
--------------------------------------------------------------------
Confirms and processes cancellation of a single booking as a database
transaction, then immediately re-runs the occupancy model against the
freshly updated flight state (per spec section 14/17). The passenger's
own cancellation-risk prediction is NOT re-shown as an active risk for
a cancelled booking, since it's no longer meaningful.
--------------------------------------------------------------------
"""

import streamlit as st

from database.db_connection import BookingError, cancel_booking, get_booking_by_id
from ml.occupancy_prediction import predict_flight_occupancy
from utils.helpers import format_currency, occupancy_badge, require_login

st.set_page_config(page_title="Cancel Booking", page_icon="\u274C", layout="wide")

passenger = require_login()

st.title("\u274C Cancel Booking")

booking_id = st.session_state.get("cancel_booking_id")
if booking_id is None:
    st.warning("No booking selected. Please choose a booking to cancel from My Bookings.")
    if st.button("Go to My Bookings"):
        st.switch_page("pages/3_My_Bookings.py")
    st.stop()

booking = get_booking_by_id(booking_id)
if booking is None or booking["passenger_id"] != passenger["passenger_id"]:
    st.error("Booking not found.")
    st.stop()

if booking["booking_status"] != "CONFIRMED":
    st.info("This booking is not active, so it can't be cancelled.")
    if st.button("Back to My Bookings"):
        st.session_state.pop("cancel_booking_id", None)
        st.switch_page("pages/3_My_Bookings.py")
    st.stop()

with st.container(border=True):
    st.markdown(f"**Booking ID:** {booking['booking_ref']}")
    st.markdown(f"**Flight:** {booking['flight_number']} \u2014 {booking['source_city']} \u2192 {booking['destination_city']}")
    st.markdown(f"**Travel Date:** {booking['travel_date']}")
    st.markdown(f"**Seat:** {booking['seat_number']}")
    st.markdown(f"**Fare Paid:** {format_currency(booking['fare'])}")

st.warning(
    "Refund policy: 90% refund if cancelled more than 7 days before travel, "
    "50% if cancelled 2-7 days before, and no refund within 2 days of travel."
)

reason = st.text_input("Reason for cancellation (optional)", value="Cancelled by passenger")

if st.button("Confirm Cancellation", type="primary"):
    try:
        refund_amount, flight_id = cancel_booking(booking_id, passenger["passenger_id"], reason=reason or "Cancelled by passenger")

        st.session_state.pop("cancel_booking_id", None)

        st.success("Booking Cancelled Successfully")
        with st.container(border=True):
            st.markdown(f"**Booking ID:** {booking['booking_ref']}")
            st.markdown(f"**Refund:** {format_currency(refund_amount)}")
            st.markdown(f"**Seat:** Released")

        st.divider()
        st.subheader("\U0001F4C8 Updated AI Flight Analysis")
        with st.spinner("Recalculating occupancy forecast..."):
            occ_result = predict_flight_occupancy(flight_id)

        oc1, oc2, oc3 = st.columns(3)
        oc1.metric("Current Bookings", f"{occ_result['current_bookings']} / {occ_result['flight_capacity']}")
        oc2.metric("Predicted Actual Passengers", occ_result["predicted_passengers"])
        oc3.metric("Predicted Occupancy", f"{occ_result['predicted_occupancy']}%")
        st.markdown(f"**Occupancy Level:** {occupancy_badge(occ_result['occupancy_level'])}")

        if st.button("Back to My Bookings"):
            st.switch_page("pages/3_My_Bookings.py")

    except BookingError as e:
        st.error(str(e))
