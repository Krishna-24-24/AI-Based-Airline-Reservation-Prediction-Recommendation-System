"""
pages/1_Flight_Search.py
--------------------------------------------------------------------
Lets the passenger search for flights by source, destination, and
travel date, and select one to proceed to booking.
--------------------------------------------------------------------
"""

from datetime import date, timedelta

import streamlit as st

from database.db_connection import get_all_airports, search_flights
from utils.helpers import format_currency, require_login

st.set_page_config(page_title="Flight Search", page_icon="\U0001F50D", layout="wide")

passenger = require_login()

st.title("\U0001F50D Search Flights")

airports = get_all_airports()
cities = sorted({a["city"] for a in airports})

with st.form("search_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        source = st.selectbox("Source", cities, index=0 if cities else None)
    with col2:
        dest_options = [c for c in cities if c != source]
        destination = st.selectbox("Destination", dest_options, index=0 if dest_options else None)
    with col3:
        travel_date = st.date_input(
            "Travel Date",
            value=date.today() + timedelta(days=1),
            min_value=date.today(),
        )
    search_clicked = st.form_submit_button("Search Flights", use_container_width=True)

# Persist the search + results in session_state so they survive the
# rerun triggered by clicking a "Select" button below (form_submit_button's
# own return value resets to False on that rerun, so we can't rely on it
# alone to keep the results visible).
if search_clicked:
    if source == destination:
        st.error("Source and destination cannot be the same.")
        st.session_state.pop("search_results", None)
    else:
        flights = search_flights(source, destination, travel_date)
        st.session_state["search_results"] = flights
        st.session_state["search_summary"] = {
            "source": source, "destination": destination, "date": str(travel_date)
        }

if "search_results" in st.session_state:
    flights = st.session_state["search_results"]
    summary = st.session_state.get("search_summary", {})

    if not flights:
        st.info(
            f"No flights found from {summary.get('source')} to "
            f"{summary.get('destination')} on {summary.get('date')}."
        )
    else:
        st.success(
            f"Found {len(flights)} flight(s) from {summary.get('source')} to "
            f"{summary.get('destination')} on {summary.get('date')}."
        )
        for f in flights:
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1.5])
                with c1:
                    st.markdown(f"**{f['flight_number']}**")
                    st.caption(f['airline'])
                with c2:
                    st.markdown(f"**Departure**")
                    st.caption(f["departure_time"].strftime("%d %b %Y, %H:%M"))
                with c3:
                    st.markdown(f"**Arrival**")
                    st.caption(f["arrival_time"].strftime("%d %b %Y, %H:%M"))
                with c4:
                    st.markdown(f"**Fare**")
                    st.caption(format_currency(f["base_fare"]))
                    st.caption(f"{f['available_seats']} seats left")
                with c5:
                    if st.button("Select", key=f"select_{f['flight_id']}", use_container_width=True):
                        st.session_state["selected_flight_id"] = f["flight_id"]
                        st.session_state["selected_travel_date"] = summary.get("date")
                        st.switch_page("pages/2_Book_Flight.py")