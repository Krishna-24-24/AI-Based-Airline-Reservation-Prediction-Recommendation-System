"""
database/db_connection.py
--------------------------------------------------------------------
Single connection layer. Credentials come from Streamlit secrets or
environment variables — never hard-coded. All SQL is parameterized.
"""

import os
import random
import string
import time
import uuid
from contextlib import contextmanager
from datetime import datetime

import mysql.connector
from mysql.connector import Error as MySQLError

try:
    import streamlit as st
    _HAS_STREAMLIT = True
except ImportError:
    _HAS_STREAMLIT = False

from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, REFUND_POLICY


class BookingError(Exception):
    """Business-rule violation during booking/cancellation."""


class DatabaseError(Exception):
    """Wrapped DB failure for user-facing messages."""


def _get_config():
    if _HAS_STREAMLIT:
        try:
            if "mysql" in st.secrets:
                return {
                    "host": st.secrets["mysql"]["DB_HOST"],
                    "user": st.secrets["mysql"]["DB_USER"],
                    "password": st.secrets["mysql"]["DB_PASSWORD"],
                    "database": st.secrets["mysql"]["DB_NAME"],
                    "port": int(st.secrets["mysql"].get("DB_PORT", 3306)),
                }
        except Exception:
            pass
    return {
        "host": os.environ.get("DB_HOST", DB_HOST),
        "user": os.environ.get("DB_USER", DB_USER),
        "password": os.environ.get("DB_PASSWORD", DB_PASSWORD),
        "database": os.environ.get("DB_NAME", DB_NAME),
        "port": int(os.environ.get("DB_PORT", DB_PORT)),
    }


def get_db_connection():
    config = _get_config()
    try:
        return mysql.connector.connect(
            host=config["host"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            port=config["port"],
            autocommit=False,
        )
    except MySQLError as e:
        raise ConnectionError(f"Could not connect to MySQL: {e}") from e


@contextmanager
def db_cursor(dictionary=True, commit=False, metric_name=None):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=dictionary)
    started = time.perf_counter()
    success = True
    try:
        yield conn, cur
        if commit:
            conn.commit()
    except Exception:
        success = False
        conn.rollback()
        raise
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        try:
            if metric_name:
                _record_metric_on(conn, metric_name, elapsed_ms, success)
                conn.commit()
        except Exception:
            pass
        cur.close()
        conn.close()


def _record_metric_on(conn, name, value_ms, success=True):
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO system_metric (metric_name, metric_value, unit, success)
               VALUES (%s, %s, 'ms', %s)""",
            (name, round(value_ms, 4), 1 if success else 0),
        )
    except MySQLError:
        pass
    finally:
        cur.close()


def record_metric(name, value_ms, success=True):
    try:
        with db_cursor(commit=True) as (conn, cur):
            cur.execute(
                """INSERT INTO system_metric (metric_name, metric_value, unit, success)
                   VALUES (%s, %s, 'ms', %s)""",
                (name, round(value_ms, 4), 1 if success else 0),
            )
    except Exception:
        pass


def test_connection():
    try:
        with db_cursor() as (conn, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True, "Connected"
    except Exception as e:
        return False, str(e)


def insert_audit(user_id, user_role, action, table_name=None, record_id=None, description=None):
    try:
        with db_cursor(commit=True) as (conn, cur):
            cur.execute(
                """INSERT INTO audit_log (user_id, user_role, action, table_name, record_id, description)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (user_id, user_role, action, table_name, record_id, description),
            )
    except Exception:
        pass


# ---------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------

def get_all_airports(active_only=True):
    with db_cursor(metric_name="select_airports") as (conn, cur):
        sql = "SELECT * FROM airport"
        if active_only:
            sql += " WHERE status = 'ACTIVE'"
        sql += " ORDER BY city"
        cur.execute(sql)
        return cur.fetchall()


def get_airport_by_id(airport_id):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM airport WHERE airport_id = %s", (airport_id,))
        return cur.fetchone()


def get_passenger_by_email(email):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM passenger WHERE email = %s", (email,))
        return cur.fetchone()


def get_passenger_by_id(passenger_id):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM passenger WHERE passenger_id = %s", (passenger_id,))
        return cur.fetchone()


def get_admin_by_email(email):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM admin_user WHERE email = %s", (email,))
        return cur.fetchone()


def create_passenger(name, email, phone, age, gender, password_hash, account_status="ACTIVE"):
    with db_cursor(commit=True) as (conn, cur):
        cur.execute(
            """INSERT INTO passenger (name, email, phone, age, gender, password_hash, account_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (name, email, phone, age, gender, password_hash, account_status),
        )
        pid = cur.lastrowid
    insert_audit(pid, "PASSENGER", "REGISTER", "passenger", pid, f"Registered {email}")
    return pid


def search_flights(source_city, destination_city, travel_date, seat_class=None, min_seats=1):
    started = time.perf_counter()
    with db_cursor() as (conn, cur):
        sql = """
            SELECT f.*, src.city AS source_city, src.airport_code AS source_code,
                   dst.city AS destination_city, dst.airport_code AS destination_code
            FROM flight f
            JOIN airport src ON f.source_airport = src.airport_id
            JOIN airport dst ON f.destination_airport = dst.airport_id
            WHERE src.city = %s
              AND dst.city = %s
              AND DATE(f.departure_time) = %s
              AND f.flight_status = 'ACTIVE'
              AND src.status = 'ACTIVE'
              AND dst.status = 'ACTIVE'
              AND f.available_seats >= %s
            ORDER BY f.departure_time
        """
        cur.execute(sql, (source_city, destination_city, travel_date, min_seats))
        rows = cur.fetchall()
    record_metric("flight_search", (time.perf_counter() - started) * 1000.0)
    return rows


def get_flight_by_id(flight_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT f.*, src.city AS source_city, dst.city AS destination_city,
                   src.airport_code AS source_code, dst.airport_code AS destination_code
            FROM flight f
            JOIN airport src ON f.source_airport = src.airport_id
            JOIN airport dst ON f.destination_airport = dst.airport_id
            WHERE f.flight_id = %s
            """,
            (flight_id,),
        )
        return cur.fetchone()


def get_seats_for_flight(flight_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT * FROM seat WHERE flight_id = %s ORDER BY seat_number",
            (flight_id,),
        )
        return cur.fetchall()


def get_all_flights(limit=500):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT f.*, src.city AS source_city, dst.city AS destination_city
            FROM flight f
            JOIN airport src ON f.source_airport = src.airport_id
            JOIN airport dst ON f.destination_airport = dst.airport_id
            ORDER BY f.departure_time
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def _generate_booking_ref():
    return "BK" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _generate_txn_id():
    return "TXN" + uuid.uuid4().hex[:16].upper()


def calculate_refund(fare, travel_date):
    if isinstance(travel_date, str):
        travel_date = datetime.strptime(travel_date, "%Y-%m-%d").date()
    elif isinstance(travel_date, datetime):
        travel_date = travel_date.date()
    days_left = (travel_date - datetime.now().date()).days
    fare = float(fare)
    if days_left > 7:
        return round(fare * REFUND_POLICY["gt_7_days"], 2)
    if days_left >= 2:
        return round(fare * REFUND_POLICY["between_2_and_7_days"], 2)
    return round(fare * REFUND_POLICY["lt_2_days"], 2)


_calculate_refund = calculate_refund  # backward compatible name


def book_flight(passenger_id, flight_id, seat_id, travel_date, fare, payment_method="UPI"):
    """
    Atomic booking:
        BEGIN -> lock seat -> lock flight -> check -> insert booking
        -> insert payment -> COMMIT
    Seat / available_seats updates are applied by AFTER INSERT triggers.
    """
    if payment_method not in ("UPI", "CARD", "NET_BANKING", "WALLET"):
        raise BookingError("Invalid payment method.")
    started = time.perf_counter()
    conn = get_db_connection()
    success = False
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT status FROM seat WHERE seat_id = %s FOR UPDATE", (seat_id,))
        seat_row = cur.fetchone()
        if seat_row is None:
            raise BookingError("Seat does not exist.")
        if seat_row["status"] != "AVAILABLE":
            raise BookingError("This seat is not available. Please choose another seat.")

        cur.execute(
            "SELECT available_seats, flight_status FROM flight WHERE flight_id = %s FOR UPDATE",
            (flight_id,),
        )
        flight_row = cur.fetchone()
        if flight_row is None:
            raise BookingError("Flight does not exist.")
        if flight_row["flight_status"] != "ACTIVE":
            raise BookingError("This flight is not open for booking.")
        if flight_row["available_seats"] <= 0:
            raise BookingError("No seats available on this flight.")

        booking_ref = _generate_booking_ref()
        txn_id = _generate_txn_id()

        cur.execute(
            """INSERT INTO booking
               (booking_ref, passenger_id, flight_id, seat_id, booking_date,
                travel_date, fare, booking_status, payment_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'CONFIRMED', 'PAID')""",
            (booking_ref, passenger_id, flight_id, seat_id, datetime.now(), travel_date, fare),
        )
        booking_id = cur.lastrowid

        cur.execute(
            """INSERT INTO payment
               (booking_id, transaction_id, amount, payment_method, payment_status, payment_date)
               VALUES (%s, %s, %s, %s, 'PAID', %s)""",
            (booking_id, txn_id, fare, payment_method, datetime.now()),
        )

        conn.commit()
        success = True
        cur.close()
        return booking_id, booking_ref, txn_id

    except MySQLError as e:
        conn.rollback()
        raise BookingError("Booking could not be completed. Please try again.") from e
    except BookingError:
        conn.rollback()
        raise
    finally:
        record_metric("booking_transaction", (time.perf_counter() - started) * 1000.0, success=success)
        conn.close()


def cancel_booking(booking_id, passenger_id, reason="Cancelled by passenger"):
    started = time.perf_counter()
    conn = get_db_connection()
    success = False
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """SELECT booking_id, passenger_id, flight_id, seat_id, fare,
                      booking_status, travel_date
               FROM booking WHERE booking_id = %s FOR UPDATE""",
            (booking_id,),
        )
        booking = cur.fetchone()
        if booking is None:
            raise BookingError("Booking not found.")
        if booking["passenger_id"] != passenger_id:
            raise BookingError("You are not authorized to cancel this booking.")
        if booking["booking_status"] != "CONFIRMED":
            raise BookingError("This booking is not active and cannot be cancelled again.")

        refund_amount = calculate_refund(booking["fare"], booking["travel_date"])
        refund_status = "PROCESSED" if refund_amount > 0 else "NONE"
        pay_status = "REFUNDED" if refund_amount > 0 else "PAID"

        cur.execute(
            "UPDATE booking SET booking_status = 'CANCELLED', payment_status = %s WHERE booking_id = %s",
            (pay_status if refund_amount > 0 else booking.get("payment_status", "PAID"), booking_id),
        )
        cur.execute(
            "UPDATE payment SET payment_status = %s WHERE booking_id = %s AND payment_status = 'PAID'",
            (pay_status, booking_id),
        )
        cur.execute(
            """INSERT INTO cancellation (booking_id, cancellation_date, reason, refund_amount, refund_status)
               VALUES (%s, %s, %s, %s, %s)""",
            (booking_id, datetime.now(), reason, refund_amount, refund_status),
        )
        conn.commit()
        success = True
        cur.close()
        return refund_amount, booking["flight_id"]

    except MySQLError as e:
        conn.rollback()
        raise BookingError("Cancellation could not be completed. Please try again.") from e
    except BookingError:
        conn.rollback()
        raise
    finally:
        record_metric("cancellation_transaction", (time.perf_counter() - started) * 1000.0, success=success)
        conn.close()


def get_bookings_for_passenger(passenger_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT b.*, f.flight_number, f.airline, f.departure_time, f.arrival_time,
                   src.city AS source_city, dst.city AS destination_city,
                   s.seat_number, s.seat_class
            FROM booking b
            JOIN flight f ON b.flight_id = f.flight_id
            JOIN airport src ON f.source_airport = src.airport_id
            JOIN airport dst ON f.destination_airport = dst.airport_id
            JOIN seat s ON b.seat_id = s.seat_id
            WHERE b.passenger_id = %s
            ORDER BY b.booking_date DESC
            """,
            (passenger_id,),
        )
        return cur.fetchall()


def get_booking_by_id(booking_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT b.*, f.flight_number, f.airline, f.departure_time, f.arrival_time,
                   f.total_seats, f.available_seats, f.duration_minutes, f.base_fare,
                   src.city AS source_city, dst.city AS destination_city,
                   src.airport_code AS source_code, dst.airport_code AS destination_code,
                   s.seat_number, s.seat_class,
                   p.name AS passenger_name, p.age AS passenger_age, p.email AS passenger_email
            FROM booking b
            JOIN flight f ON b.flight_id = f.flight_id
            JOIN airport src ON f.source_airport = src.airport_id
            JOIN airport dst ON f.destination_airport = dst.airport_id
            JOIN seat s ON b.seat_id = s.seat_id
            JOIN passenger p ON b.passenger_id = p.passenger_id
            WHERE b.booking_id = %s
            """,
            (booking_id,),
        )
        return cur.fetchone()


def get_booking_by_ref(booking_ref):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT b.*, p.name AS passenger_name, f.flight_number
            FROM booking b
            JOIN passenger p ON b.passenger_id = p.passenger_id
            JOIN flight f ON b.flight_id = f.flight_id
            WHERE b.booking_ref = %s
            """,
            (booking_ref,),
        )
        return cur.fetchone()


def count_passenger_history(passenger_id, before_booking_id=None):
    with db_cursor() as (conn, cur):
        query = """
            SELECT
                COUNT(*) AS total_bookings,
                SUM(CASE WHEN booking_status = 'CANCELLED' THEN 1 ELSE 0 END) AS total_cancellations,
                SUM(CASE WHEN booking_status = 'COMPLETED' THEN 1 ELSE 0 END) AS total_completed
            FROM booking
            WHERE passenger_id = %s
        """
        params = [passenger_id]
        if before_booking_id is not None:
            query += " AND booking_id < %s"
            params.append(before_booking_id)
        cur.execute(query, tuple(params))
        row = cur.fetchone()
        return {
            "previous_bookings": int(row["total_bookings"] or 0),
            "previous_cancellations": int(row["total_cancellations"] or 0),
            "previous_completed_trips": int(row["total_completed"] or 0),
        }


def get_passenger_stats(passenger_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_bookings,
                SUM(CASE WHEN booking_status = 'CONFIRMED' THEN 1 ELSE 0 END) AS upcoming,
                SUM(CASE WHEN booking_status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancellations,
                SUM(CASE WHEN booking_status IN ('CONFIRMED','COMPLETED') THEN fare ELSE 0 END) AS total_spend,
                AVG(CASE WHEN booking_status IN ('CONFIRMED','COMPLETED') THEN fare END) AS avg_fare
            FROM booking
            WHERE passenger_id = %s
            """,
            (passenger_id,),
        )
        stats = cur.fetchone()
        cur.execute(
            """
            SELECT s.seat_class, COUNT(*) c
            FROM booking b JOIN seat s ON b.seat_id = s.seat_id
            WHERE b.passenger_id = %s AND b.booking_status IN ('CONFIRMED','COMPLETED')
            GROUP BY s.seat_class ORDER BY c DESC LIMIT 1
            """,
            (passenger_id,),
        )
        pref = cur.fetchone()
        stats["preferred_class"] = pref["seat_class"] if pref else "ECONOMY"
        cur.execute(
            """
            SELECT src.city AS source_city, dst.city AS destination_city, COUNT(*) c
            FROM booking b
            JOIN flight f ON b.flight_id = f.flight_id
            JOIN airport src ON f.source_airport = src.airport_id
            JOIN airport dst ON f.destination_airport = dst.airport_id
            WHERE b.passenger_id = %s AND b.booking_status IN ('CONFIRMED','COMPLETED')
            GROUP BY src.city, dst.city ORDER BY c DESC LIMIT 5
            """,
            (passenger_id,),
        )
        stats["favorite_routes"] = cur.fetchall()
        return stats


def get_passenger_preferences(passenger_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT
                AVG(HOUR(f.departure_time)) AS avg_dep_hour,
                AVG(f.duration_minutes) AS avg_duration,
                AVG(b.fare) AS avg_fare,
                AVG(CASE WHEN s.seat_class = 'BUSINESS' THEN 1 ELSE 0 END) AS business_ratio
            FROM booking b
            JOIN flight f ON b.flight_id = f.flight_id
            JOIN seat s ON b.seat_id = s.seat_id
            WHERE b.passenger_id = %s AND b.booking_status IN ('CONFIRMED','COMPLETED')
            """,
            (passenger_id,),
        )
        return cur.fetchone() or {}


# ---------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------

def save_prediction(flight_id, booking_id=None, cancellation_probability=None,
                    cancellation_risk=None, predicted_passengers=None,
                    predicted_occupancy=None, occupancy_level=None,
                    prediction_type=None, prediction_value=None, risk_level=None,
                    recommendation=None, cluster_id=None, model_version="unknown",
                    passenger_id=None):
    risk = risk_level or cancellation_risk
    value = prediction_value if prediction_value is not None else cancellation_probability
    if prediction_type is None:
        if cancellation_probability is not None or cancellation_risk is not None:
            prediction_type = "CANCELLATION_RISK"
        elif predicted_occupancy is not None or predicted_passengers is not None:
            prediction_type = "OCCUPANCY"
        elif cluster_id is not None:
            prediction_type = "CLUSTER"
        else:
            prediction_type = "RECOMMENDATION"
    with db_cursor(commit=True) as (conn, cur):
        cur.execute(
            """INSERT INTO prediction
               (booking_id, flight_id, passenger_id, prediction_type, prediction_value,
                risk_level, predicted_passengers, predicted_occupancy, occupancy_level,
                recommendation, cluster_id, model_version, prediction_timestamp)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (booking_id, flight_id, passenger_id, prediction_type, value, risk,
             predicted_passengers, predicted_occupancy, occupancy_level,
             recommendation, cluster_id, model_version, datetime.now()),
        )
        pid = cur.lastrowid
    insert_audit(passenger_id, "SYSTEM", "PREDICTION_GENERATED", "prediction", pid, prediction_type)
    return pid


def get_latest_prediction_for_booking(booking_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            """SELECT *, prediction_value AS cancellation_probability,
                      risk_level AS cancellation_risk
               FROM prediction
               WHERE booking_id = %s
               ORDER BY prediction_timestamp DESC LIMIT 1""",
            (booking_id,),
        )
        return cur.fetchone()


def get_latest_occupancy_prediction(flight_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            """SELECT * FROM prediction
               WHERE flight_id = %s AND prediction_type = 'OCCUPANCY'
               ORDER BY prediction_timestamp DESC LIMIT 1""",
            (flight_id,),
        )
        return cur.fetchone()


def log_recommendation_event(passenger_id, flight_id, event_type, score=None):
    with db_cursor(commit=True) as (conn, cur):
        cur.execute(
            """INSERT INTO recommendation_event
               (passenger_id, flight_id, event_type, recommendation_score)
               VALUES (%s, %s, %s, %s)""",
            (passenger_id, flight_id, event_type, score),
        )


def save_passenger_cluster(passenger_id, cluster_id, cluster_label, model_version):
    with db_cursor(commit=True) as (conn, cur):
        cur.execute(
            """INSERT INTO passenger_cluster (passenger_id, cluster_id, cluster_label, model_version)
               VALUES (%s, %s, %s, %s)""",
            (passenger_id, cluster_id, cluster_label, model_version),
        )


def fetch_passenger_feature_rows():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT
                p.passenger_id,
                COUNT(b.booking_id) AS total_bookings,
                SUM(CASE WHEN b.booking_status IN ('CONFIRMED','COMPLETED') THEN 1 ELSE 0 END) AS completed_trips,
                SUM(CASE WHEN b.booking_status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_bookings,
                COALESCE(AVG(b.fare), 0) AS average_fare,
                COALESCE(SUM(CASE WHEN b.booking_status IN ('CONFIRMED','COMPLETED') THEN b.fare ELSE 0 END), 0) AS total_spend,
                COALESCE(AVG(DATEDIFF(b.travel_date, DATE(b.booking_date))), 0) AS average_booking_lead_time,
                COALESCE(AVG(f.duration_minutes), 0) AS average_trip_duration,
                COALESCE(AVG(CASE WHEN s.seat_class = 'BUSINESS' THEN 1 ELSE 0 END), 0) AS business_class_ratio
            FROM passenger p
            LEFT JOIN booking b ON p.passenger_id = b.passenger_id
            LEFT JOIN flight f ON b.flight_id = f.flight_id
            LEFT JOIN seat s ON b.seat_id = s.seat_id
            GROUP BY p.passenger_id
            """
        )
        return cur.fetchall()


# ---------------------------------------------------------------------
# Admin CRUD
# ---------------------------------------------------------------------

def create_airport(code, name, city, country, status="ACTIVE"):
    with db_cursor(commit=True) as (conn, cur):
        cur.execute(
            """INSERT INTO airport (airport_code, airport_name, city, country, status)
               VALUES (%s, %s, %s, %s, %s)""",
            (code.upper(), name, city, country, status),
        )
        aid = cur.lastrowid
    insert_audit(None, "ADMIN", "AIRPORT_CREATED", "airport", aid, code)
    return aid


def update_airport(airport_id, **fields):
    allowed = {"airport_code", "airport_name", "city", "country", "status"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k} = %s")
            params.append(v)
    if not sets:
        return
    params.append(airport_id)
    with db_cursor(commit=True) as (conn, cur):
        cur.execute(f"UPDATE airport SET {', '.join(sets)} WHERE airport_id = %s", tuple(params))
    insert_audit(None, "ADMIN", "AIRPORT_UPDATED", "airport", airport_id, None)


def create_flight(flight_number, airline, source_airport, destination_airport,
                  departure_time, arrival_time, duration_minutes, total_seats, base_fare):
    if source_airport == destination_airport:
        raise BookingError("Source and destination must differ.")
    with db_cursor(commit=True) as (conn, cur):
        cur.execute(
            """INSERT INTO flight
               (flight_number, airline, source_airport, destination_airport,
                departure_time, arrival_time, duration_minutes, total_seats,
                available_seats, base_fare, flight_status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')""",
            (flight_number, airline, source_airport, destination_airport,
             departure_time, arrival_time, duration_minutes, total_seats,
             total_seats, base_fare),
        )
        fid = cur.lastrowid
    insert_audit(None, "ADMIN", "FLIGHT_CREATED", "flight", fid, flight_number)
    return fid


def update_flight(flight_id, **fields):
    allowed = {
        "flight_number", "airline", "departure_time", "arrival_time",
        "duration_minutes", "base_fare", "flight_status", "total_seats",
    }
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k} = %s")
            params.append(v)
    if not sets:
        return
    params.append(flight_id)
    with db_cursor(commit=True) as (conn, cur):
        cur.execute(f"UPDATE flight SET {', '.join(sets)} WHERE flight_id = %s", tuple(params))
    insert_audit(None, "ADMIN", "FLIGHT_UPDATED", "flight", flight_id, None)


def generate_seats_for_flight(flight_id, rows=10, cols=None):
    cols = cols or ["A", "B", "C", "D", "E", "F"]
    created = 0
    with db_cursor(commit=True) as (conn, cur):
        for r in range(1, rows + 1):
            for c in cols:
                seat_number = f"{r}{c}"
                if r <= 2:
                    seat_class = "BUSINESS"
                elif r <= 4:
                    seat_class = "PREMIUM_ECONOMY"
                else:
                    seat_class = "ECONOMY"
                try:
                    cur.execute(
                        """INSERT INTO seat (flight_id, seat_number, seat_class, status)
                           VALUES (%s, %s, %s, 'AVAILABLE')""",
                        (flight_id, seat_number, seat_class),
                    )
                    created += 1
                except MySQLError:
                    continue
        cur.execute(
            """UPDATE flight SET total_seats = (
                   SELECT COUNT(*) FROM seat WHERE flight_id = %s
               ), available_seats = (
                   SELECT COUNT(*) FROM seat WHERE flight_id = %s AND status = 'AVAILABLE'
               ) WHERE flight_id = %s""",
            (flight_id, flight_id, flight_id),
        )
    insert_audit(None, "ADMIN", "SEAT_UPDATED", "seat", flight_id, f"generated {created} seats")
    return created


def set_seat_status(seat_id, status):
    if status not in ("AVAILABLE", "BOOKED", "BLOCKED"):
        raise BookingError("Invalid seat status.")
    with db_cursor(commit=True) as (conn, cur):
        cur.execute("SELECT status, flight_id FROM seat WHERE seat_id = %s FOR UPDATE", (seat_id,))
        row = cur.fetchone()
        if not row:
            raise BookingError("Seat not found.")
        if row["status"] == "BOOKED" and status == "BLOCKED":
            raise BookingError("Cannot block a booked seat.")
        cur.execute("UPDATE seat SET status = %s WHERE seat_id = %s", (status, seat_id))
        if row["status"] == "AVAILABLE" and status == "BLOCKED":
            cur.execute(
                "UPDATE flight SET available_seats = GREATEST(available_seats - 1, 0) WHERE flight_id = %s",
                (row["flight_id"],),
            )
        elif row["status"] == "BLOCKED" and status == "AVAILABLE":
            cur.execute(
                "UPDATE flight SET available_seats = available_seats + 1 WHERE flight_id = %s",
                (row["flight_id"],),
            )
    insert_audit(None, "ADMIN", "SEAT_UPDATED", "seat", seat_id, status)


def search_all_bookings(pnr=None, passenger=None, flight_number=None, status=None, travel_date=None, limit=200):
    clauses = ["1=1"]
    params = []
    if pnr:
        clauses.append("b.booking_ref = %s")
        params.append(pnr)
    if passenger:
        clauses.append("(p.name LIKE %s OR p.email LIKE %s)")
        params.extend([f"%{passenger}%", f"%{passenger}%"])
    if flight_number:
        clauses.append("f.flight_number = %s")
        params.append(flight_number)
    if status:
        clauses.append("b.booking_status = %s")
        params.append(status)
    if travel_date:
        clauses.append("b.travel_date = %s")
        params.append(travel_date)
    params.append(limit)
    with db_cursor() as (conn, cur):
        cur.execute(
            f"""
            SELECT b.*, p.name AS passenger_name, p.email, f.flight_number, f.airline,
                   src.city AS source_city, dst.city AS destination_city, s.seat_number
            FROM booking b
            JOIN passenger p ON b.passenger_id = p.passenger_id
            JOIN flight f ON b.flight_id = f.flight_id
            JOIN seat s ON b.seat_id = s.seat_id
            JOIN airport src ON f.source_airport = src.airport_id
            JOIN airport dst ON f.destination_airport = dst.airport_id
            WHERE {' AND '.join(clauses)}
            ORDER BY b.booking_date DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return cur.fetchall()


def get_cancellations(limit=300):
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT * FROM cancellation_analytics_view ORDER BY cancellation_date DESC LIMIT %s",
            (limit,),
        )
        return cur.fetchall()


def get_admin_stats():
    with db_cursor(metric_name="dashboard_query") as (conn, cur):
        stats = {}
        queries = {
            "total_flights": "SELECT COUNT(*) AS c FROM flight",
            "total_bookings": "SELECT COUNT(*) AS c FROM booking",
            "active_bookings": "SELECT COUNT(*) AS c FROM booking WHERE booking_status = 'CONFIRMED'",
            "cancelled_bookings": "SELECT COUNT(*) AS c FROM booking WHERE booking_status = 'CANCELLED'",
            "available_seats": "SELECT COALESCE(SUM(available_seats), 0) AS c FROM flight",
            "total_passengers": "SELECT COUNT(*) AS c FROM passenger",
            "total_seats": "SELECT COUNT(*) AS c FROM seat",
            "total_payments": "SELECT COUNT(*) AS c FROM payment",
            "total_cancellations": "SELECT COUNT(*) AS c FROM cancellation",
            "total_predictions": "SELECT COUNT(*) AS c FROM prediction",
            "total_airports": "SELECT COUNT(*) AS c FROM airport",
        }
        for key, sql in queries.items():
            cur.execute(sql)
            stats[key] = cur.fetchone()["c"]

        cur.execute("""SELECT COALESCE(SUM(amount),0) AS c FROM payment WHERE payment_status='PAID'""")
        stats["total_revenue"] = float(cur.fetchone()["c"])
        cur.execute("""SELECT COALESCE(SUM(refund_amount),0) AS c FROM cancellation""")
        stats["total_refunds"] = float(cur.fetchone()["c"])

        cur.execute(
            """SELECT COUNT(*) AS c FROM (
                   SELECT booking_id, risk_level,
                          ROW_NUMBER() OVER (PARTITION BY booking_id ORDER BY prediction_timestamp DESC) AS rn
                   FROM prediction WHERE prediction_type='CANCELLATION_RISK' AND risk_level IS NOT NULL
               ) t WHERE t.rn = 1 AND t.risk_level = 'HIGH'"""
        )
        stats["high_risk_bookings"] = cur.fetchone()["c"]

        cur.execute(
            """SELECT AVG(t.predicted_occupancy) AS avg_occ FROM (
                   SELECT flight_id, predicted_occupancy,
                          ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY prediction_timestamp DESC) AS rn
                   FROM prediction WHERE prediction_type='OCCUPANCY' AND predicted_occupancy IS NOT NULL
               ) t WHERE t.rn = 1"""
        )
        row = cur.fetchone()
        stats["avg_predicted_occupancy"] = float(row["avg_occ"]) if row and row["avg_occ"] is not None else 0.0

        cur.execute(
            """SELECT COUNT(*) AS c FROM (
                   SELECT flight_id, occupancy_level,
                          ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY prediction_timestamp DESC) AS rn
                   FROM prediction WHERE occupancy_level IS NOT NULL
               ) t WHERE t.rn = 1 AND t.occupancy_level = 'HIGH'"""
        )
        stats["high_occupancy_flights"] = cur.fetchone()["c"]
        cur.execute(
            """SELECT COUNT(*) AS c FROM (
                   SELECT flight_id, occupancy_level,
                          ROW_NUMBER() OVER (PARTITION BY flight_id ORDER BY prediction_timestamp DESC) AS rn
                   FROM prediction WHERE occupancy_level IS NOT NULL
               ) t WHERE t.rn = 1 AND t.occupancy_level = 'LOW'"""
        )
        stats["low_occupancy_flights"] = cur.fetchone()["c"]
        return stats


def get_all_flights_with_occupancy():
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM flight_occupancy_view ORDER BY departure_time")
        return cur.fetchall()


def get_bookings_by_day(limit_days=30):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT DATE(booking_date) AS d, COUNT(*) AS c
            FROM booking
            GROUP BY DATE(booking_date)
            ORDER BY d DESC
            LIMIT %s
            """,
            (limit_days,),
        )
        return cur.fetchall()


def get_bookings_by_route():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT src.city AS source_city, dst.city AS destination_city, COUNT(*) AS c,
                   SUM(b.fare) AS revenue
            FROM booking b
            JOIN flight f ON b.flight_id = f.flight_id
            JOIN airport src ON f.source_airport = src.airport_id
            JOIN airport dst ON f.destination_airport = dst.airport_id
            WHERE b.booking_status IN ('CONFIRMED','COMPLETED')
            GROUP BY src.city, dst.city
            ORDER BY c DESC
            LIMIT 20
            """
        )
        return cur.fetchall()


def get_bookings_by_class():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT s.seat_class, COUNT(*) AS c, COALESCE(SUM(b.fare),0) AS revenue
            FROM booking b JOIN seat s ON b.seat_id = s.seat_id
            WHERE b.booking_status IN ('CONFIRMED','COMPLETED')
            GROUP BY s.seat_class
            """
        )
        return cur.fetchall()


def get_developer_stats():
    stats = get_admin_stats()
    with db_cursor() as (conn, cur):
        cur.execute("SELECT COUNT(*) AS c FROM information_schema.tables WHERE table_schema = DATABASE()")
        stats["table_count"] = cur.fetchone()["c"]
        cur.execute(
            """
            SELECT metric_name, AVG(metric_value) AS avg_ms, COUNT(*) AS n,
                   SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS failures
            FROM system_metric
            GROUP BY metric_name
            """
        )
        stats["metrics"] = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS c FROM audit_log")
        stats["audit_count"] = cur.fetchone()["c"]
        cur.execute(
            """SELECT SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok,
                      SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS fail
               FROM system_metric WHERE metric_name IN ('booking_transaction','cancellation_transaction')"""
        )
        row = cur.fetchone() or {}
        stats["tx_success"] = int(row.get("ok") or 0)
        stats["tx_fail"] = int(row.get("fail") or 0)
    return stats


def get_audit_logs(limit=200):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM audit_log ORDER BY action_timestamp DESC LIMIT %s", (limit,))
        return cur.fetchall()


def get_recommendation_stats():
    with db_cursor() as (conn, cur):
        cur.execute("SELECT COUNT(*) AS c FROM recommendation_event")
        total = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM recommendation_event WHERE event_type='SHOWN'")
        shown = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM recommendation_event WHERE event_type='CLICKED'")
        clicked = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM recommendation_event WHERE event_type='BOOKED'")
        booked = cur.fetchone()["c"]
        cur.execute("SELECT AVG(recommendation_score) AS a FROM recommendation_event WHERE recommendation_score IS NOT NULL")
        avg = cur.fetchone()["a"]
        cur.execute(
            """SELECT f.flight_number, COUNT(*) c, AVG(e.recommendation_score) avg_score
               FROM recommendation_event e JOIN flight f ON e.flight_id = f.flight_id
               WHERE e.event_type='SHOWN'
               GROUP BY f.flight_number ORDER BY c DESC LIMIT 10"""
        )
        top = cur.fetchall()
        return {
            "total_events": total,
            "shown": shown,
            "clicked": clicked,
            "booked": booked,
            "avg_score": float(avg) if avg is not None else None,
            "top_flights": top,
            "has_click_data": clicked > 0,
            "has_conversion_data": booked > 0,
        }
