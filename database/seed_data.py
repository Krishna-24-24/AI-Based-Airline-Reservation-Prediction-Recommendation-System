"""
Seed realistic demo data (referential integrity preserved).

Run AFTER schema.sql:
    python database/seed_data.py
"""
import os
import random
import string
import sys
import uuid
from datetime import datetime, timedelta

import bcrypt
import mysql.connector

sys.path.append(".")
from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

try:
    import tomllib
except ImportError:
    tomllib = None

random.seed(42)

AIRPORTS = [
    ("MAA", "Chennai International Airport", "Chennai", "India"),
    ("DEL", "Indira Gandhi International Airport", "Delhi", "India"),
    ("BOM", "Chhatrapati Shivaji Maharaj Airport", "Mumbai", "India"),
    ("BLR", "Kempegowda International Airport", "Bengaluru", "India"),
    ("HYD", "Rajiv Gandhi International Airport", "Hyderabad", "India"),
    ("CCU", "Netaji Subhas Chandra Bose Airport", "Kolkata", "India"),
    ("GOI", "Goa International Airport", "Goa", "India"),
    ("COK", "Cochin International Airport", "Kochi", "India"),
    ("PNQ", "Pune Airport", "Pune", "India"),
    ("JAI", "Jaipur International Airport", "Jaipur", "India"),
    ("AMD", "Sardar Vallabhbhai Patel Airport", "Ahmedabad", "India"),
    ("LKO", "Chaudhary Charan Singh Airport", "Lucknow", "India"),
    ("IXC", "Chandigarh Airport", "Chandigarh", "India"),
    ("TRV", "Trivandrum International Airport", "Thiruvananthapuram", "India"),
    ("GAU", "Lokpriya Gopinath Bordoloi Airport", "Guwahati", "India"),
    ("PAT", "Jay Prakash Narayan Airport", "Patna", "India"),
    ("NAG", "Dr. Babasaheb Ambedkar Airport", "Nagpur", "India"),
    ("IXB", "Bagdogra Airport", "Bagdogra", "India"),
    ("VNS", "Lal Bahadur Shastri Airport", "Varanasi", "India"),
    ("BBI", "Biju Patnaik Airport", "Bhubaneswar", "India"),
    ("IDR", "Devi Ahilya Bai Holkar Airport", "Indore", "India"),
    ("IXR", "Birsa Munda Airport", "Ranchi", "India"),
]

AIRLINES = ["IndiGo", "Air India", "Vistara", "SpiceJet", "Akasa Air"]
SEAT_ROWS = 10
SEAT_COLS = ["A", "B", "C", "D", "E", "F"]
FIRST_NAMES = ["Rahul", "Ananya", "Vikram", "Priya", "Arjun", "Meera", "Karan", "Nisha",
               "Sanjay", "Divya", "Amit", "Sneha", "Rohit", "Isha", "Nikhil", "Pooja"]
LAST_NAMES = ["Kumar", "Iyer", "Sharma", "Patel", "Reddy", "Nair", "Singh", "Das",
              "Gupta", "Joshi", "Mehta", "Rao", "Kapoor", "Pillai"]


def connect():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    secrets_path = os.path.join(project_root, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path) and tomllib:
        with open(secrets_path, "rb") as f:
            secrets = tomllib.load(f)
        config = secrets["mysql"]
        return mysql.connector.connect(
            host=config["DB_HOST"],
            user=config["DB_USER"],
            password=config["DB_PASSWORD"],
            database=config["DB_NAME"],
            port=int(config.get("DB_PORT", 3306)),
        )
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", DB_HOST),
        user=os.environ.get("DB_USER", DB_USER),
        password=os.environ.get("DB_PASSWORD", DB_PASSWORD),
        database=os.environ.get("DB_NAME", DB_NAME),
        port=int(os.environ.get("DB_PORT", DB_PORT)),
    )


def hash_pw(plain):
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=4)).decode()


def seed_airports(cur):
    ids = {}
    for code, name, city, country in AIRPORTS:
        cur.execute(
            """INSERT INTO airport (airport_code, airport_name, city, country, status)
               VALUES (%s, %s, %s, %s, 'ACTIVE')""",
            (code, name, city, country),
        )
        ids[city] = cur.lastrowid
    return ids


def seed_flights_and_seats(cur, airport_ids):
    cities = list(airport_ids.keys())
    hub = cities[:5]
    guaranteed = [(a, b) for a in hub for b in hub if a != b]
    flight_ids = []
    flight_meta = {}
    count = 0
    for day_offset in range(1, 22):
        travel_date = datetime.now() + timedelta(days=day_offset)
        extras = [(a, b) for a in cities for b in cities if a != b and (a, b) not in guaranteed]
        sampled = random.sample(extras, k=min(8, len(extras)))
        routes = list(guaranteed) + sampled
        for src, dst in routes:
            airline = random.choice(AIRLINES)
            prefix = "".join(ch for ch in airline.upper() if ch.isalpha())[:2]
            flight_number = f"{prefix}{random.randint(100, 999)}"
            dep_hour = random.randint(5, 21)
            departure_time = travel_date.replace(
                hour=dep_hour, minute=random.choice([0, 15, 30, 45]), second=0, microsecond=0
            )
            duration_minutes = random.randint(70, 210)
            arrival_time = departure_time + timedelta(minutes=duration_minutes)
            total_seats = SEAT_ROWS * len(SEAT_COLS)
            base_fare = round(random.uniform(2800, 12000), 2)
            cur.execute(
                """INSERT INTO flight
                   (flight_number, airline, source_airport, destination_airport,
                    departure_time, arrival_time, duration_minutes, total_seats,
                    available_seats, base_fare, flight_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')""",
                (flight_number, airline, airport_ids[src], airport_ids[dst],
                 departure_time, arrival_time, duration_minutes, total_seats,
                 total_seats, base_fare),
            )
            fid = cur.lastrowid
            flight_ids.append(fid)
            flight_meta[fid] = {
                "departure": departure_time,
                "fare": base_fare,
                "src": src,
                "dst": dst,
            }
            count += 1
            for row in range(1, SEAT_ROWS + 1):
                for col in SEAT_COLS:
                    seat_number = f"{row}{col}"
                    if row <= 2:
                        seat_class = "BUSINESS"
                    elif row <= 4:
                        seat_class = "PREMIUM_ECONOMY"
                    else:
                        seat_class = "ECONOMY"
                    cur.execute(
                        """INSERT INTO seat (flight_id, seat_number, seat_class, status)
                           VALUES (%s, %s, %s, 'AVAILABLE')""",
                        (fid, seat_number, seat_class),
                    )
    return flight_ids, flight_meta, count


def seed_passengers(cur):
    ids = []
    demo = [
        ("Rahul Kumar", "rahul.kumar@example.com", "9876543210", 29, "Male"),
        ("Ananya Iyer", "ananya.iyer@example.com", "9876501234", 34, "Female"),
    ]
    pw = hash_pw("password123")
    for name, email, phone, age, gender in demo:
        cur.execute(
            """INSERT INTO passenger (name, email, phone, age, gender, password_hash, account_status)
               VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')""",
            (name, email, phone, age, gender, pw),
        )
        ids.append(cur.lastrowid)
    for i in range(500):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        email = f"passenger{i:04d}@example.com"
        phone = f"9{random.randint(100000000, 999999999)}"
        age = random.randint(18, 72)
        gender = random.choice(["Male", "Female", "Other"])
        cur.execute(
            """INSERT INTO passenger (name, email, phone, age, gender, password_hash, account_status)
               VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')""",
            (name, email, phone, age, gender, pw),
        )
        ids.append(cur.lastrowid)
    return ids


def seed_admins(cur):
    cur.execute(
        """INSERT INTO admin_user (name, email, password_hash, role, account_status)
           VALUES (%s, %s, %s, 'ADMIN', 'ACTIVE')""",
        ("System Admin", "admin@airline.local", hash_pw("Admin@123")),
    )
    cur.execute(
        """INSERT INTO admin_user (name, email, password_hash, role, account_status)
           VALUES (%s, %s, %s, 'DEVELOPER', 'ACTIVE')""",
        ("Developer", "developer@airline.local", hash_pw("Dev@123")),
    )


def seed_bookings(cur, passenger_ids, flight_ids, flight_meta, target=2800):
    created = 0
    cancelled = 0
    for fid in flight_ids:
        cur.execute("SELECT seat_id FROM seat WHERE flight_id = %s AND status = 'AVAILABLE'", (fid,))
        seats = [r[0] for r in cur.fetchall()]
        if not seats:
            continue
        n_book = min(len(seats), random.randint(8, min(42, len(seats))))
        chosen = random.sample(seats, n_book)
        meta = flight_meta[fid]
        travel_date = meta["departure"].date()
        for seat_id in chosen:
            if created >= target:
                break
            pid = random.choice(passenger_ids)
            fare = round(float(meta["fare"]) * random.choice([1.0, 1.0, 1.25, 1.6]), 2)
            ref = "BK" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            days_before = random.randint(1, 20)
            booking_date = datetime.now() - timedelta(days=days_before)
            try:
                cur.execute(
                    """INSERT INTO booking
                       (booking_ref, passenger_id, flight_id, seat_id, booking_date,
                        travel_date, fare, booking_status, payment_status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'CONFIRMED', 'PAID')""",
                    (ref, pid, fid, seat_id, booking_date, travel_date, fare),
                )
            except mysql.connector.Error:
                continue
            bid = cur.lastrowid
            txn = "TXN" + uuid.uuid4().hex[:16].upper()
            method = random.choice(["UPI", "CARD", "NET_BANKING", "WALLET"])
            cur.execute(
                """INSERT INTO payment (booking_id, transaction_id, amount, payment_method, payment_status, payment_date)
                   VALUES (%s, %s, %s, %s, 'PAID', %s)""",
                (bid, txn, fare, method, booking_date),
            )
            created += 1
            # Frequent-canceller passengers (low id modulo) cancel more often
            cancel_p = 0.22 if pid % 11 == 0 else 0.10
            if random.random() < cancel_p:
                cur.execute(
                    "UPDATE booking SET booking_status='CANCELLED', payment_status='REFUNDED' WHERE booking_id=%s",
                    (bid,),
                )
                cur.execute(
                    "UPDATE payment SET payment_status='REFUNDED' WHERE booking_id=%s",
                    (bid,),
                )
                refund = round(fare * random.choice([0.9, 0.5, 0.0]), 2)
                cur.execute(
                    """INSERT INTO cancellation (booking_id, cancellation_date, reason, refund_amount, refund_status)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (bid, booking_date + timedelta(hours=3), "Change of plans", refund,
                     "PROCESSED" if refund > 0 else "NONE"),
                )
                cancelled += 1
        if created >= target:
            break
    return created, cancelled


def main():
    conn = connect()
    cur = conn.cursor()
    try:
        print("Seeding airports...")
        airport_ids = seed_airports(cur)
        print("Seeding flights and seats...")
        flight_ids, flight_meta, n_flights = seed_flights_and_seats(cur, airport_ids)
        conn.commit()
        print("Seeding passengers...")
        pids = seed_passengers(cur)
        print("Seeding admin/developer accounts...")
        seed_admins(cur)
        conn.commit()
        print("Seeding bookings/payments/cancellations (triggers maintain seats)...")
        n_book, n_cancel = seed_bookings(cur, pids, flight_ids, flight_meta)
        conn.commit()
        print(f"Done. Airports={len(airport_ids)} flights={n_flights} passengers={len(pids)} "
              f"bookings={n_book} cancellations={n_cancel}")
        print("Demo passenger : rahul.kumar@example.com / password123")
        print("Demo admin     : admin@airline.local / Admin@123")
        print("Demo developer : developer@airline.local / Dev@123")
    except Exception as e:
        conn.rollback()
        print(f"Seeding failed, rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
