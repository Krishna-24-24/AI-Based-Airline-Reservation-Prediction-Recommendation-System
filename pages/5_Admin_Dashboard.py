"""
pages/5_Admin_Dashboard.py
--------------------------------------------------------------------
Read-only operational dashboard: flight/booking counts plus
AI-derived statistics (high-risk bookings, average predicted
occupancy, flights running hot/cold), pulled live from MySQL.
--------------------------------------------------------------------
"""

import pandas as pd
import streamlit as st

from database.db_connection import get_admin_stats, get_all_flights_with_occupancy
from utils.helpers import require_login

st.set_page_config(page_title="Admin Dashboard", page_icon="\U0001F4CA", layout="wide")

require_login()  # any logged-in user can view this demo dashboard

st.title("\U0001F4CA Admin Dashboard")

stats = get_admin_stats()

st.subheader("Flight & Booking Statistics")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Flights", stats["total_flights"])
c2.metric("Total Bookings", stats["total_bookings"])
c3.metric("Active Bookings", stats["active_bookings"])
c4.metric("Cancelled Bookings", stats["cancelled_bookings"])
c5.metric("Available Seats", stats["available_seats"])

st.divider()

st.subheader("\U0001F916 AI Statistics")
a1, a2, a3, a4 = st.columns(4)
a1.metric("High-Risk Bookings", stats["high_risk_bookings"])
a2.metric("Avg Predicted Occupancy", f"{stats['avg_predicted_occupancy']:.1f}%")
a3.metric("Flights: High Occupancy", stats["high_occupancy_flights"])
a4.metric("Flights: Low Occupancy", stats["low_occupancy_flights"])

st.divider()

st.subheader("Flight Occupancy Overview")
flights = get_all_flights_with_occupancy()
if flights:
    df = pd.DataFrame(flights)
    df["route"] = df["source_city"] + " \u2192 " + df["destination_city"]
    df_display = df[["flight_number", "airline", "route", "departure_time",
                      "total_seats", "current_bookings", "current_occupancy_pct"]]
    df_display = df_display.rename(columns={
        "flight_number": "Flight",
        "airline": "Airline",
        "route": "Route",
        "departure_time": "Departure",
        "total_seats": "Capacity",
        "current_bookings": "Bookings",
        "current_occupancy_pct": "Occupancy %",
    })
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.caption("Current occupancy by flight")
    chart_df = df.set_index("flight_number")[["current_occupancy_pct"]]
    st.bar_chart(chart_df)
else:
    st.info("No flights in the database yet.")
