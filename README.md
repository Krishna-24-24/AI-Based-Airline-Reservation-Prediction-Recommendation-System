# AI-Based Airline Reservation System with Passenger Risk and Flight Occupancy Prediction

A full-stack **DBMS + Machine Learning** application: a working airline
reservation system (search, book, cancel) built on **MySQL**, with two
**scikit-learn** models wired directly into the booking/cancellation
transactions so that AI predictions update automatically, in real time,
whenever the database changes.

---

## 1. Project Overview

Passengers can register, search flights, pick a seat from a live seat
map, book a flight, view their booking history, and cancel a booking —
all backed by real MySQL tables and real SQL transactions. On top of
that ordinary reservation system, every booking and cancellation
automatically triggers two ML predictions that are computed from the
*current* database state and written back into the database:

1. **Cancellation / No-Show Risk** — for a specific booking, the
   probability that passenger will cancel or fail to show up.
2. **Flight Occupancy Forecast** — for a specific flight, how many of
   the currently booked passengers are actually expected to travel.

## 2. Problem Statement

Airlines routinely overbook or under-plan because raw booking counts
don't reflect real passenger behaviour — a meaningful share of
"confirmed" passengers cancel or simply don't show up. This project
demonstrates how a reservation system's own transactional data can be
turned into two decision-support signals (per-booking risk, per-flight
occupancy) without any manual data entry or a separate offline
pipeline — the moment a row changes in MySQL, the next prediction
reflects it.

## 3. Objectives

- Build a genuinely relational, transactional MySQL backend (not a
  toy CRUD app): proper keys, constraints, joins, views, indexes,
  and multi-statement transactions with rollback.
- Train two real scikit-learn models on realistic (synthetic, since
  no proprietary airline dataset is available) historical data.
- Integrate the two systems so ML predictions are always derived from
  live database state, are persisted for auditability, and update
  automatically after every booking/cancellation.
- Present all of this through a clean, multi-page Streamlit UI.

## 4. Technologies Used

| Layer            | Technology                          |
|-------------------|--------------------------------------|
| UI                 | Streamlit (multi-page app)           |
| Application logic  | Python 3.10+                         |
| Database           | MySQL 8.x                            |
| DB driver          | mysql-connector-python               |
| ML                 | scikit-learn (Random Forest x2, Logistic/Linear Regression as baselines) |
| Data processing    | pandas, numpy                        |
| Model persistence  | joblib                               |
| Auth               | bcrypt (password hashing)            |

## 5. System Architecture

```
USER
 |
 v
STREAMLIT UI  (app.py + pages/)
 |
 |-- Search Flights   -- Book Flight   -- My Bookings   -- Cancel Booking
 |
 v
PYTHON APPLICATION LOGIC  (database/db_connection.py)
 |
 v
MYSQL DATABASE  (database/schema.sql)
 |-- passenger, airport, flight, seat, booking, cancellation, prediction
 |
 v
FEATURE ENGINEERING  (ml/feature_engineering.py)
 |
 v
ML MODELS  (models/*.pkl, loaded by ml/*.py)
 |-- Cancellation / No-Show Risk Model  (Random Forest Classifier)
 |-- Flight Occupancy Prediction Model  (Random Forest Regressor)
 |
 v
PREDICTIONS  --> written to `prediction` table --> shown in Streamlit
```

## 6. Database Architecture

### ER Diagram (description)

- **passenger** (1) —— (many) **booking**: a passenger can have many
  bookings; each booking belongs to exactly one passenger.
- **flight** (1) —— (many) **booking**: a flight can have many
  bookings; each booking is for exactly one flight.
- **flight** (1) —— (many) **seat**: each flight has its own set of
  seats (a `seat` row belongs to one flight).
- **seat** (1) —— (0..1 active) **booking**: a seat is referenced by a
  booking; only one *active* (CONFIRMED) booking can exist per seat at
  a time (enforced by the app's transaction, not just a DB constraint,
  since MySQL has no simple partial-unique-index syntax).
- **booking** (1) —— (0..1) **cancellation**: a cancelled booking has
  exactly one cancellation record.
- **booking** (1) —— (many) **prediction**: every time a prediction is
  (re)computed for a booking, a new row is appended, so history is
  preserved (rather than overwritten).
- **flight** (1) —— (many) **prediction**: same idea for
  occupancy predictions, per flight.
- **airport** (1) —— (many) **flight** (twice: as source and as
  destination).

### Tables

See `database/schema.sql` for full DDL. Summary:

- `passenger` — passenger_id (PK), name, email (unique), phone, age, gender, password_hash
- `airport` — airport_id (PK), airport_code (unique), airport_name, city, country
- `flight` — flight_id (PK), flight_number, airline, source_airport (FK), destination_airport (FK), departure_time, arrival_time, duration_minutes, total_seats, available_seats, base_fare
- `seat` — seat_id (PK), flight_id (FK), seat_number, seat_class, status
- `booking` — booking_id (PK), booking_ref, passenger_id (FK), flight_id (FK), seat_id (FK), booking_date, travel_date, fare, booking_status, payment_status
- `cancellation` — cancellation_id (PK), booking_id (FK), cancellation_date, reason, refund_amount
- `prediction` — prediction_id (PK), booking_id (FK, nullable), flight_id (FK), cancellation_probability, cancellation_risk, predicted_passengers, predicted_occupancy, occupancy_level, prediction_timestamp

### SQL Concepts Used

- **Primary/Foreign keys** on every entity and relationship above.
- **Constraints**: `NOT NULL`, `UNIQUE` (email, airport_code, booking_ref,
  seat per flight), `CHECK` (age range, non-negative seats/fares, valid
  status enums, source \u2260 destination).
- **Normalization**: the schema is in 3NF — e.g. airport details are
  not duplicated on every flight row, passenger details are not
  duplicated on every booking row.
- **Joins**: used throughout `db_connection.py` and in every view
  (passenger + booking + flight + seat + airport).
- **Transactions**: `book_flight()` and `cancel_booking()` each run
  as an explicit multi-statement transaction with `SELECT ... FOR
  UPDATE` row locking, and roll back on any failure (seat already
  taken, no seats left, unauthorized cancellation, etc.).
- **Views**: `active_bookings_view`, `flight_occupancy_view`,
  `passenger_booking_history`.
- **Indexes**: on `flight_number`, `source_airport`,
  `destination_airport`, `departure_time`, `passenger_id`,
  `flight_id`, `booking_status`, etc. — see the `CREATE INDEX`
  statements in `schema.sql`.
- **Trigger**: `trg_prevent_overbooking` — a database-level safety net
  (`BEFORE INSERT`) that rejects a CONFIRMED booking if the flight has
  no seats left, even if something bypassed the application layer.

## 7. ML Architecture

Training and prediction are deliberately **separate processes**:

```
TRAINING (offline, run manually)
Historical CSV -> Data Cleaning -> Feature Engineering -> Train/Test Split
-> Model Training (RF primary, LR/Linear baseline) -> Evaluation -> joblib.dump()

RUNTIME PREDICTION (inside the Streamlit app)
MySQL (current state) -> Feature Engineering (ml/feature_engineering.py)
-> joblib.load() the saved model (cached in memory)
-> model.predict() / predict_proba()
-> INSERT INTO prediction (...)
-> st.metric(...) in the UI
```

The app **never retrains** a model while running — it loads the
`.pkl` file once and reuses it for every prediction, which is both
realistic (a production system doesn't retrain on every click) and
fast.

### Model 1 — Cancellation / No-Show Risk (Classification)

- **Algorithm**: Random Forest Classifier (primary), Logistic
  Regression trained alongside as a comparison baseline; the training
  script prints both sets of metrics and keeps the Random Forest
  unless the baseline is clearly better.
- **Features**: `days_before_departure`, `ticket_fare`,
  `passenger_age`, `previous_bookings`, `previous_cancellations`,
  `previous_no_shows`, `travel_frequency`, `previous_completed_trips`,
  `is_weekend`, `flight_duration`, `booking_lead_time`.
- **Target**: `cancelled_or_no_show` (0/1).
- **Dataset**: `data/airline_booking_history.csv`, ~8,000 synthetic
  rows generated by `models/generate_booking_history.py` using a
  logistic function (not random labels) so that, e.g., more previous
  cancellations/no-shows and very last-minute bookings genuinely
  increase the labeled risk, while loyal/frequent travellers show
  lower risk — the same kind of relationship a real airline dataset
  would show.
- **Evaluation**: accuracy, precision, recall, F1, confusion matrix
  (printed by `models/train_cancellation_model.py`).
- **Output**: probability -> risk level via configurable thresholds in
  `ml/feature_engineering.py` (`CANCELLATION_RISK_THRESHOLDS`):
  0–40% LOW, 40–70% MEDIUM, 70–100% HIGH.

### Model 2 — Flight Occupancy Prediction (Regression)

- **Algorithm**: Random Forest Regressor (primary), Linear Regression
  trained alongside as a comparison baseline.
- **Features**: `flight_capacity`, `current_bookings`,
  `days_before_departure`, `historical_average_occupancy`,
  `historical_cancellation_rate`, `historical_no_show_rate`,
  `route_demand`, `day_of_week`, `is_weekend`, and one-hot encoded
  `season`.
- **Target**: `actual_passengers`.
- **Dataset**: `data/flight_history.csv`, ~6,000 synthetic rows
  generated by `models/generate_flight_history.py`, where
  `actual_passengers` is derived from `current_bookings` minus a
  realistic number of cancellations/no-shows (driven by the row's own
  historical rates), not random noise.
- **Evaluation**: MAE, RMSE, R\u00b2 (printed by
  `models/train_occupancy_model.py`).
- **Output**: `predicted_occupancy = predicted_actual_passengers /
  flight_capacity * 100`, bucketed into LOW/MEDIUM/HIGH via
  `OCCUPANCY_LEVEL_THRESHOLDS`.

At **prediction time**, `historical_average_occupancy`,
`historical_cancellation_rate`, `historical_no_show_rate`, and
`route_demand` are computed live from MySQL by looking at that
specific route's other flights (`ml/occupancy_prediction.py ->
_route_history()`) — not hard-coded — falling back to sensible
system-wide defaults for a brand-new route with no history yet.

## 8. Booking Workflow

1. User searches flights (source, destination, date) -> SQL query
   with joins against `flight` + `airport`.
2. User picks a flight and a still-`AVAILABLE` seat from the live
   seat map.
3. On **Confirm Booking**, `book_flight()` runs as one transaction:
   lock the seat and flight rows (`SELECT ... FOR UPDATE`), re-verify
   availability, `INSERT` the booking, mark the seat `BOOKED`,
   decrement `flight.available_seats`, commit (or roll back on any
   failure).
4. Immediately after commit, the app calls
   `predict_cancellation_risk(booking_id)` and
   `predict_flight_occupancy(flight_id, booking_id=booking_id)`,
   both of which pull fresh data from MySQL, run the saved models,
   store the result in `prediction`, and return it to the UI.

## 9. Cancellation Workflow

1. From **My Bookings**, the user selects an active booking to
   cancel.
2. `cancel_booking()` runs as one transaction: lock and re-verify the
   booking belongs to the user and is still `CONFIRMED`, compute the
   refund (90% if >7 days out, 50% if 2–7 days out, 0% within 2 days),
   set `booking_status = 'CANCELLED'`, release the seat back to
   `AVAILABLE`, increment `flight.available_seats`, insert a
   `cancellation` row, commit (or roll back).
3. Immediately after commit, `predict_flight_occupancy(flight_id)` is
   re-run and the updated forecast is displayed. The passenger's own
   cancellation-risk number is not shown as an active prediction for a
   cancelled booking, since it's no longer meaningful.

## 10. How DBMS and ML Communicate

`ml/cancellation_prediction.py` and `ml/occupancy_prediction.py` never
receive numbers typed in by a user — every feature they build comes
from a `database/db_connection.py` query against the *current* state
of `booking`, `flight`, `seat`, and `passenger`. Every prediction they
produce is written straight back into the `prediction` table via
`save_prediction()` before it's shown in Streamlit, so the AI output
is always reproducible from the database alone. This is the
DBMS -> Feature Engineering -> ML -> Prediction -> UI loop described in
the architecture diagram above, and it's what makes the two systems
integrated rather than two disconnected demos glued together.

## 11. Project Structure

```
airline_ai_system/
├── app.py                        # Home page: login/register, nav
├── database/
│   ├── db_connection.py          # All SQL lives here (parameterized)
│   ├── schema.sql                # Full MySQL DDL: tables, views, trigger
│   └── seed_data.py              # Sample airports/flights/seats/passengers
├── models/
│   ├── generate_booking_history.py  # Synthetic dataset #1 generator
│   ├── generate_flight_history.py   # Synthetic dataset #2 generator
│   ├── train_cancellation_model.py  # Trains + evaluates + saves model #1
│   ├── train_occupancy_model.py     # Trains + evaluates + saves model #2
│   ├── cancellation_model.pkl       # (generated by training script)
│   └── occupancy_model.pkl          # (generated by training script)
├── ml/
│   ├── feature_engineering.py    # Shared feature order/encoding (train+runtime)
│   ├── cancellation_prediction.py# Runtime prediction #1 (reads MySQL)
│   └── occupancy_prediction.py   # Runtime prediction #2 (reads MySQL)
├── pages/
│   ├── 1_Flight_Search.py
│   ├── 2_Book_Flight.py
│   ├── 3_My_Bookings.py
│   ├── 4_Cancel_Booking.py
│   └── 5_Admin_Dashboard.py
├── data/
│   ├── airline_booking_history.csv  # (generated)
│   └── flight_history.csv           # (generated)
├── utils/
│   └── helpers.py                 # Formatting, badges, auth helpers
├── .streamlit/
│   └── secrets.toml.example       # Copy to secrets.toml and fill in
├── requirements.txt
└── README.md
```

## 12. Installation & Setup

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 2 — Set up MySQL

```bash
mysql -u root -p -e "CREATE DATABASE airline_ai_system;"
mysql -u root -p airline_ai_system < database/schema.sql
```

### Step 3 — Configure credentials

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml with your MySQL host/user/password
```

(Alternatively, set `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`,
`DB_PORT` as environment variables — `db_connection.py` will use those
if no `secrets.toml` is found.)

### Step 4 — Seed sample data

```bash
python database/seed_data.py
```

This creates airports, ~30 days of flights and seats, and two demo
passenger accounts (see the login screen for credentials).

### Step 5 — Generate training data and train the models

```bash
python models/generate_booking_history.py
python models/generate_flight_history.py
python models/train_cancellation_model.py
python models/train_occupancy_model.py
```

This produces `data/*.csv` and `models/*.pkl`. (The repo already
includes these files pre-generated, so this step is only needed if you
want to regenerate them, e.g. after changing a feature.)

### Step 6 — Run the app

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`), log
in with the demo account or register a new one, and start booking.

## 13. Demonstration Scenario

1. Log in, go to **Search Flights**, search Chennai \u2192 Delhi for
   tomorrow's date.
2. Select a flight, then select an available seat (e.g. 14A) on the
   live seat map.
3. Click **Confirm Booking** — watch the booking get created and the
   seat map update, then watch the two AI panels ("Your Booking AI
   Analysis" and "Flight Occupancy Forecast") populate immediately.
4. Go to **My Bookings**, find the booking, click **Cancel Booking**,
   confirm — watch the refund get calculated and the **Updated AI
   Flight Analysis** panel show the occupancy forecast recalculated
   with one fewer booking.
5. Open **Admin Dashboard** to see the aggregate stats (including
   high-risk bookings and average predicted occupancy) update to
   reflect the same underlying data.

This is the full `DBMS -> Transaction -> ML -> Prediction -> UI` loop
described in the architecture section, working end to end.

## 14. Notes on Data Consistency

- Booking a seat that's just been taken by someone else, or booking
  onto a full flight, is caught by `SELECT ... FOR UPDATE` row locking
  inside `book_flight()`'s transaction — the second request is
  rejected with a clear error rather than corrupting `available_seats`.
- Cancelling someone else's booking, or cancelling a booking twice, is
  rejected by `cancel_booking()`'s ownership/status checks before any
  write happens.
- `flight.available_seats` can never exceed `total_seats` or go
  negative — enforced by `CHECK` constraints in `schema.sql` in
  addition to the application-level transaction logic.
