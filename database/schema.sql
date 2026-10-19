-- =====================================================================
-- AI-Based Airline Reservation, Prediction & Recommendation System
-- MySQL 8.x schema — tables, constraints, indexes, views, functions,
-- stored procedures, and triggers.
--
--   mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS airline_ai_system;"
--   mysql -u root -p airline_ai_system < database/schema.sql
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP VIEW IF EXISTS recommendation_stats_view;
DROP VIEW IF EXISTS cancellation_analytics_view;
DROP VIEW IF EXISTS passenger_booking_history;
DROP VIEW IF EXISTS flight_occupancy_view;
DROP VIEW IF EXISTS active_bookings_view;

DROP TABLE IF EXISTS system_metric;
DROP TABLE IF EXISTS recommendation_event;
DROP TABLE IF EXISTS passenger_cluster;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS prediction;
DROP TABLE IF EXISTS cancellation;
DROP TABLE IF EXISTS payment;
DROP TABLE IF EXISTS booking;
DROP TABLE IF EXISTS seat;
DROP TABLE IF EXISTS flight;
DROP TABLE IF EXISTS airport;
DROP TABLE IF EXISTS admin_user;
DROP TABLE IF EXISTS passenger;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- PASSENGER
-- ---------------------------------------------------------------------
CREATE TABLE passenger (
    passenger_id     INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(120) NOT NULL,
    email            VARCHAR(150) NOT NULL,
    phone            VARCHAR(20)  NOT NULL,
    age              INT          NOT NULL,
    gender           VARCHAR(20)  NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    account_status   VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT uq_passenger_email UNIQUE (email),
    CONSTRAINT chk_passenger_age CHECK (age BETWEEN 0 AND 120),
    CONSTRAINT chk_passenger_status CHECK (account_status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- ADMIN / DEVELOPER
-- ---------------------------------------------------------------------
CREATE TABLE admin_user (
    admin_id         INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(120) NOT NULL,
    email            VARCHAR(150) NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,
    role             VARCHAR(20)  NOT NULL,
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    account_status   VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT uq_admin_email UNIQUE (email),
    CONSTRAINT chk_admin_role CHECK (role IN ('ADMIN', 'DEVELOPER')),
    CONSTRAINT chk_admin_status CHECK (account_status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- AIRPORT
-- ---------------------------------------------------------------------
CREATE TABLE airport (
    airport_id       INT AUTO_INCREMENT PRIMARY KEY,
    airport_code     VARCHAR(10)  NOT NULL,
    airport_name     VARCHAR(150) NOT NULL,
    city             VARCHAR(100) NOT NULL,
    country          VARCHAR(100) NOT NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT uq_airport_code UNIQUE (airport_code),
    CONSTRAINT chk_airport_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- FLIGHT
-- ---------------------------------------------------------------------
CREATE TABLE flight (
    flight_id              INT AUTO_INCREMENT PRIMARY KEY,
    flight_number          VARCHAR(20)    NOT NULL,
    airline                VARCHAR(100)   NOT NULL,
    source_airport         INT            NOT NULL,
    destination_airport    INT            NOT NULL,
    departure_time         DATETIME       NOT NULL,
    arrival_time           DATETIME       NOT NULL,
    duration_minutes       INT            NOT NULL,
    total_seats            INT            NOT NULL,
    available_seats        INT            NOT NULL,
    base_fare              DECIMAL(10, 2) NOT NULL,
    flight_status          VARCHAR(20)    NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT fk_flight_source FOREIGN KEY (source_airport) REFERENCES airport(airport_id),
    CONSTRAINT fk_flight_dest   FOREIGN KEY (destination_airport) REFERENCES airport(airport_id),
    CONSTRAINT chk_route CHECK (source_airport <> destination_airport),
    CONSTRAINT chk_total_seats CHECK (total_seats > 0),
    CONSTRAINT chk_available_seats CHECK (available_seats >= 0),
    CONSTRAINT chk_seats_cap CHECK (available_seats <= total_seats),
    CONSTRAINT chk_base_fare CHECK (base_fare > 0),
    CONSTRAINT chk_duration CHECK (duration_minutes > 0),
    CONSTRAINT chk_flight_status CHECK (flight_status IN ('ACTIVE', 'INACTIVE', 'CANCELLED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_flight_number ON flight(flight_number);
CREATE INDEX idx_flight_source ON flight(source_airport);
CREATE INDEX idx_flight_dest ON flight(destination_airport);
CREATE INDEX idx_flight_departure ON flight(departure_time);
CREATE INDEX idx_flight_status ON flight(flight_status);
-- Composite index for the dominant search: route + date range.
CREATE INDEX idx_flight_search ON flight(source_airport, destination_airport, departure_time);

-- ---------------------------------------------------------------------
-- SEAT
-- ---------------------------------------------------------------------
CREATE TABLE seat (
    seat_id        INT AUTO_INCREMENT PRIMARY KEY,
    flight_id      INT         NOT NULL,
    seat_number    VARCHAR(10) NOT NULL,
    seat_class     VARCHAR(20) NOT NULL DEFAULT 'ECONOMY',
    status         VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    CONSTRAINT fk_seat_flight FOREIGN KEY (flight_id) REFERENCES flight(flight_id) ON DELETE CASCADE,
    CONSTRAINT uq_seat_per_flight UNIQUE (flight_id, seat_number),
    CONSTRAINT chk_seat_class CHECK (seat_class IN ('ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS')),
    CONSTRAINT chk_seat_status CHECK (status IN ('AVAILABLE', 'BOOKED', 'BLOCKED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_seat_flight ON seat(flight_id);
CREATE INDEX idx_seat_status ON seat(status);

-- ---------------------------------------------------------------------
-- BOOKING
-- ---------------------------------------------------------------------
CREATE TABLE booking (
    booking_id       INT AUTO_INCREMENT PRIMARY KEY,
    booking_ref      VARCHAR(20)    NOT NULL,
    passenger_id     INT            NOT NULL,
    flight_id        INT            NOT NULL,
    seat_id          INT            NOT NULL,
    booking_date     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    travel_date      DATE           NOT NULL,
    fare             DECIMAL(10, 2) NOT NULL,
    booking_status   VARCHAR(20)    NOT NULL DEFAULT 'CONFIRMED',
    payment_status   VARCHAR(20)    NOT NULL DEFAULT 'PENDING',
    CONSTRAINT uq_booking_ref UNIQUE (booking_ref),
    CONSTRAINT fk_booking_passenger FOREIGN KEY (passenger_id) REFERENCES passenger(passenger_id),
    CONSTRAINT fk_booking_flight    FOREIGN KEY (flight_id) REFERENCES flight(flight_id),
    CONSTRAINT fk_booking_seat      FOREIGN KEY (seat_id) REFERENCES seat(seat_id),
    CONSTRAINT chk_booking_fare CHECK (fare >= 0),
    CONSTRAINT chk_booking_status CHECK (booking_status IN ('CONFIRMED', 'CANCELLED', 'COMPLETED')),
    CONSTRAINT chk_payment_status CHECK (payment_status IN ('PENDING', 'PAID', 'FAILED', 'REFUNDED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_booking_passenger ON booking(passenger_id);
CREATE INDEX idx_booking_flight ON booking(flight_id);
CREATE INDEX idx_booking_status ON booking(booking_status);
CREATE INDEX idx_booking_date ON booking(booking_date);
CREATE INDEX idx_booking_travel_date ON booking(travel_date);
CREATE INDEX idx_booking_ref ON booking(booking_ref);

-- ---------------------------------------------------------------------
-- PAYMENT  (simulated — never a live gateway)
-- ---------------------------------------------------------------------
CREATE TABLE payment (
    payment_id       INT AUTO_INCREMENT PRIMARY KEY,
    booking_id       INT            NOT NULL,
    transaction_id   VARCHAR(40)    NOT NULL,
    amount           DECIMAL(10, 2) NOT NULL,
    payment_method   VARCHAR(20)    NOT NULL,
    payment_status   VARCHAR(20)    NOT NULL,
    payment_date     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_transaction_id UNIQUE (transaction_id),
    CONSTRAINT fk_payment_booking FOREIGN KEY (booking_id) REFERENCES booking(booking_id),
    CONSTRAINT chk_payment_amount CHECK (amount >= 0),
    CONSTRAINT chk_payment_method CHECK (payment_method IN ('UPI', 'CARD', 'NET_BANKING', 'WALLET')),
    CONSTRAINT chk_pay_status CHECK (payment_status IN ('PENDING', 'PAID', 'FAILED', 'REFUNDED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_payment_booking ON payment(booking_id);

-- ---------------------------------------------------------------------
-- CANCELLATION
-- ---------------------------------------------------------------------
CREATE TABLE cancellation (
    cancellation_id   INT AUTO_INCREMENT PRIMARY KEY,
    booking_id        INT            NOT NULL,
    cancellation_date DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason            VARCHAR(255),
    refund_amount     DECIMAL(10, 2) NOT NULL,
    refund_status     VARCHAR(20)    NOT NULL DEFAULT 'PROCESSED',
    CONSTRAINT fk_cancel_booking FOREIGN KEY (booking_id) REFERENCES booking(booking_id),
    CONSTRAINT chk_refund_amount CHECK (refund_amount >= 0),
    CONSTRAINT chk_refund_status CHECK (refund_status IN ('PENDING', 'PROCESSED', 'NONE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_cancellation_booking ON cancellation(booking_id);

-- ---------------------------------------------------------------------
-- PREDICTION  (supports multiple AI prediction types)
-- ---------------------------------------------------------------------
CREATE TABLE prediction (
    prediction_id           INT AUTO_INCREMENT PRIMARY KEY,
    booking_id              INT            NULL,
    flight_id               INT            NOT NULL,
    passenger_id            INT            NULL,
    prediction_type         VARCHAR(40)    NOT NULL,
    prediction_value        DECIMAL(10, 4) NULL,
    risk_level              VARCHAR(10)    NULL,
    predicted_passengers    INT            NULL,
    predicted_occupancy     DECIMAL(5, 2)  NULL,
    occupancy_level         VARCHAR(10)    NULL,
    recommendation          VARCHAR(255)   NULL,
    cluster_id              INT            NULL,
    model_version           VARCHAR(60)    NOT NULL DEFAULT 'unknown',
    prediction_timestamp    DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_prediction_booking FOREIGN KEY (booking_id) REFERENCES booking(booking_id),
    CONSTRAINT fk_prediction_flight  FOREIGN KEY (flight_id) REFERENCES flight(flight_id),
    CONSTRAINT fk_prediction_passenger FOREIGN KEY (passenger_id) REFERENCES passenger(passenger_id),
    CONSTRAINT chk_prediction_type CHECK (prediction_type IN (
        'CANCELLATION_RISK', 'OCCUPANCY', 'CLUSTER', 'RECOMMENDATION'
    ))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_prediction_booking ON prediction(booking_id);
CREATE INDEX idx_prediction_flight ON prediction(flight_id);
CREATE INDEX idx_prediction_type ON prediction(prediction_type);
CREATE INDEX idx_prediction_passenger ON prediction(passenger_id);

-- ---------------------------------------------------------------------
-- PASSENGER CLUSTER ASSIGNMENT (runtime clustering output)
-- ---------------------------------------------------------------------
CREATE TABLE passenger_cluster (
    assignment_id     INT AUTO_INCREMENT PRIMARY KEY,
    passenger_id      INT          NOT NULL,
    cluster_id        INT          NOT NULL,
    cluster_label     VARCHAR(80)  NOT NULL,
    model_version     VARCHAR(60)  NOT NULL,
    assigned_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cluster_passenger FOREIGN KEY (passenger_id) REFERENCES passenger(passenger_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_cluster_passenger ON passenger_cluster(passenger_id);

-- ---------------------------------------------------------------------
-- RECOMMENDATION EVENTS (for CTR/conversion when users interact)
-- ---------------------------------------------------------------------
CREATE TABLE recommendation_event (
    event_id          INT AUTO_INCREMENT PRIMARY KEY,
    passenger_id      INT            NOT NULL,
    flight_id         INT            NOT NULL,
    event_type        VARCHAR(20)    NOT NULL,
    recommendation_score DECIMAL(6,2) NULL,
    created_at        DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_revent_passenger FOREIGN KEY (passenger_id) REFERENCES passenger(passenger_id),
    CONSTRAINT fk_revent_flight FOREIGN KEY (flight_id) REFERENCES flight(flight_id),
    CONSTRAINT chk_revent_type CHECK (event_type IN ('SHOWN', 'CLICKED', 'BOOKED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- AUDIT LOG
-- ---------------------------------------------------------------------
CREATE TABLE audit_log (
    log_id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id           INT          NULL,
    user_role         VARCHAR(20)  NULL,
    action            VARCHAR(40)  NOT NULL,
    table_name        VARCHAR(40)  NULL,
    record_id         INT          NULL,
    action_timestamp  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description       VARCHAR(500) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_time ON audit_log(action_timestamp);

-- ---------------------------------------------------------------------
-- SYSTEM METRICS (query / transaction timings)
-- ---------------------------------------------------------------------
CREATE TABLE system_metric (
    metric_id     INT AUTO_INCREMENT PRIMARY KEY,
    metric_name   VARCHAR(60)     NOT NULL,
    metric_value  DECIMAL(12, 4)  NOT NULL,
    unit          VARCHAR(20)     NOT NULL DEFAULT 'ms',
    success       TINYINT(1)      NOT NULL DEFAULT 1,
    recorded_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_metric_name ON system_metric(metric_name);

-- =====================================================================
-- VIEWS
-- =====================================================================

CREATE OR REPLACE VIEW active_bookings_view AS
SELECT
    b.booking_ref     AS PNR,
    p.name            AS Passenger,
    f.flight_number   AS Flight,
    src.city          AS Source,
    dst.city          AS Destination,
    s.seat_number     AS Seat,
    b.fare            AS Fare,
    b.booking_status  AS Status,
    b.booking_id,
    b.passenger_id,
    b.flight_id,
    b.travel_date,
    b.payment_status
FROM booking b
JOIN passenger p ON b.passenger_id = p.passenger_id
JOIN flight f    ON b.flight_id = f.flight_id
JOIN seat s      ON b.seat_id = s.seat_id
JOIN airport src ON f.source_airport = src.airport_id
JOIN airport dst ON f.destination_airport = dst.airport_id
WHERE b.booking_status = 'CONFIRMED';

CREATE OR REPLACE VIEW flight_occupancy_view AS
SELECT
    f.flight_number                         AS Flight,
    f.total_seats                           AS Capacity,
    (f.total_seats - f.available_seats)     AS `Booked Seats`,
    f.available_seats                       AS `Available Seats`,
    ROUND((f.total_seats - f.available_seats) / f.total_seats * 100, 2) AS `Occupancy %`,
    f.flight_id,
    f.airline,
    src.city AS source_city,
    dst.city AS destination_city,
    f.departure_time,
    f.total_seats,
    f.available_seats,
    (f.total_seats - f.available_seats) AS current_bookings,
    ROUND((f.total_seats - f.available_seats) / f.total_seats * 100, 2) AS current_occupancy_pct
FROM flight f
JOIN airport src ON f.source_airport = src.airport_id
JOIN airport dst ON f.destination_airport = dst.airport_id;

CREATE OR REPLACE VIEW passenger_booking_history AS
SELECT
    p.name            AS Passenger,
    b.booking_ref     AS PNR,
    f.flight_number   AS Flight,
    b.travel_date     AS `Travel Date`,
    s.seat_number     AS Seat,
    b.fare            AS Fare,
    b.booking_status  AS Status,
    p.passenger_id,
    b.booking_id,
    b.booking_ref,
    f.flight_number,
    src.city AS source_city,
    dst.city AS destination_city,
    b.travel_date,
    b.fare,
    b.booking_status,
    b.booking_date,
    p.name AS passenger_name
FROM passenger p
JOIN booking b ON p.passenger_id = b.passenger_id
JOIN flight f  ON b.flight_id = f.flight_id
JOIN seat s    ON b.seat_id = s.seat_id
JOIN airport src ON f.source_airport = src.airport_id
JOIN airport dst ON f.destination_airport = dst.airport_id;

CREATE OR REPLACE VIEW cancellation_analytics_view AS
SELECT
    c.cancellation_id,
    b.booking_ref,
    p.name AS passenger_name,
    f.flight_number,
    src.city AS source_city,
    dst.city AS destination_city,
    c.cancellation_date,
    c.reason,
    c.refund_amount,
    c.refund_status,
    b.fare AS original_fare
FROM cancellation c
JOIN booking b ON c.booking_id = b.booking_id
JOIN passenger p ON b.passenger_id = p.passenger_id
JOIN flight f ON b.flight_id = f.flight_id
JOIN airport src ON f.source_airport = src.airport_id
JOIN airport dst ON f.destination_airport = dst.airport_id;

CREATE OR REPLACE VIEW recommendation_stats_view AS
SELECT
    f.flight_number,
    COUNT(*) AS times_shown,
    SUM(CASE WHEN e.event_type = 'CLICKED' THEN 1 ELSE 0 END) AS times_clicked,
    SUM(CASE WHEN e.event_type = 'BOOKED' THEN 1 ELSE 0 END) AS times_booked,
    AVG(e.recommendation_score) AS avg_score
FROM recommendation_event e
JOIN flight f ON e.flight_id = f.flight_id
GROUP BY f.flight_number;

-- =====================================================================
-- FUNCTIONS
-- =====================================================================

DELIMITER $$

DROP FUNCTION IF EXISTS fn_calculate_refund$$
CREATE FUNCTION fn_calculate_refund(p_fare DECIMAL(10,2), p_travel_date DATE)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
    DECLARE days_left INT;
    SET days_left = DATEDIFF(p_travel_date, CURDATE());
    IF days_left > 7 THEN
        RETURN ROUND(p_fare * 0.90, 2);
    ELSEIF days_left >= 2 THEN
        RETURN ROUND(p_fare * 0.50, 2);
    ELSE
        RETURN 0.00;
    END IF;
END$$

DROP FUNCTION IF EXISTS fn_calculate_occupancy$$
CREATE FUNCTION fn_calculate_occupancy(p_flight_id INT)
RETURNS DECIMAL(5,2)
READS SQL DATA
BEGIN
    DECLARE cap INT;
    DECLARE avail INT;
    SELECT total_seats, available_seats INTO cap, avail
    FROM flight WHERE flight_id = p_flight_id;
    IF cap IS NULL OR cap = 0 THEN
        RETURN 0.00;
    END IF;
    RETURN ROUND((cap - avail) / cap * 100, 2);
END$$

DROP FUNCTION IF EXISTS fn_calculate_cancellation_rate$$
CREATE FUNCTION fn_calculate_cancellation_rate(p_flight_id INT)
RETURNS DECIMAL(6,4)
READS SQL DATA
BEGIN
    DECLARE total_b INT;
    DECLARE cancelled_b INT;
    SELECT COUNT(*) INTO total_b FROM booking WHERE flight_id = p_flight_id;
    SELECT COUNT(*) INTO cancelled_b FROM booking
        WHERE flight_id = p_flight_id AND booking_status = 'CANCELLED';
    IF total_b = 0 THEN
        RETURN 0.0000;
    END IF;
    RETURN ROUND(cancelled_b / total_b, 4);
END$$

-- =====================================================================
-- STORED PROCEDURES
-- =====================================================================

DROP PROCEDURE IF EXISTS sp_search_flights$$
CREATE PROCEDURE sp_search_flights(
    IN p_source_city VARCHAR(100),
    IN p_dest_city VARCHAR(100),
    IN p_travel_date DATE
)
BEGIN
    SELECT f.*, src.city AS source_city, src.airport_code AS source_code,
           dst.city AS destination_city, dst.airport_code AS destination_code
    FROM flight f
    JOIN airport src ON f.source_airport = src.airport_id
    JOIN airport dst ON f.destination_airport = dst.airport_id
    WHERE src.city = p_source_city
      AND dst.city = p_dest_city
      AND DATE(f.departure_time) = p_travel_date
      AND f.flight_status = 'ACTIVE'
      AND src.status = 'ACTIVE'
      AND dst.status = 'ACTIVE'
    ORDER BY f.departure_time;
END$$

DROP PROCEDURE IF EXISTS sp_book_flight$$
CREATE PROCEDURE sp_book_flight(
    IN p_passenger_id INT,
    IN p_flight_id INT,
    IN p_seat_id INT,
    IN p_travel_date DATE,
    IN p_fare DECIMAL(10,2),
    IN p_payment_method VARCHAR(20),
    IN p_booking_ref VARCHAR(20),
    IN p_transaction_id VARCHAR(40),
    OUT p_booking_id INT,
    OUT p_status VARCHAR(20)
)
BEGIN
    DECLARE v_seat_status VARCHAR(20);
    DECLARE v_seats_left INT;
    DECLARE v_flight_status VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_booking_id = NULL;
        SET p_status = 'FAILED';
    END;

    START TRANSACTION;

    SELECT status INTO v_seat_status FROM seat WHERE seat_id = p_seat_id FOR UPDATE;
    SELECT available_seats, flight_status INTO v_seats_left, v_flight_status
        FROM flight WHERE flight_id = p_flight_id FOR UPDATE;

    IF v_seat_status IS NULL OR v_seat_status <> 'AVAILABLE' THEN
        ROLLBACK;
        SET p_booking_id = NULL;
        SET p_status = 'SEAT_UNAVAILABLE';
    ELSEIF v_seats_left IS NULL OR v_seats_left <= 0 OR v_flight_status <> 'ACTIVE' THEN
        ROLLBACK;
        SET p_booking_id = NULL;
        SET p_status = 'FLIGHT_UNAVAILABLE';
    ELSE
        INSERT INTO booking (booking_ref, passenger_id, flight_id, seat_id, booking_date,
                             travel_date, fare, booking_status, payment_status)
        VALUES (p_booking_ref, p_passenger_id, p_flight_id, p_seat_id, NOW(),
                p_travel_date, p_fare, 'CONFIRMED', 'PAID');
        SET p_booking_id = LAST_INSERT_ID();

        INSERT INTO payment (booking_id, transaction_id, amount, payment_method, payment_status, payment_date)
        VALUES (p_booking_id, p_transaction_id, p_fare, p_payment_method, 'PAID', NOW());

        COMMIT;
        SET p_status = 'OK';
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_cancel_booking$$
CREATE PROCEDURE sp_cancel_booking(
    IN p_booking_id INT,
    IN p_passenger_id INT,
    IN p_reason VARCHAR(255),
    OUT p_refund DECIMAL(10,2),
    OUT p_status VARCHAR(20)
)
BEGIN
    DECLARE v_owner INT;
    DECLARE v_bstatus VARCHAR(20);
    DECLARE v_fare DECIMAL(10,2);
    DECLARE v_travel DATE;
    DECLARE v_refund DECIMAL(10,2);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_refund = 0;
        SET p_status = 'FAILED';
    END;

    START TRANSACTION;

    SELECT passenger_id, booking_status, fare, travel_date
      INTO v_owner, v_bstatus, v_fare, v_travel
      FROM booking WHERE booking_id = p_booking_id FOR UPDATE;

    IF v_owner IS NULL THEN
        ROLLBACK;
        SET p_refund = 0;
        SET p_status = 'NOT_FOUND';
    ELSEIF v_owner <> p_passenger_id THEN
        ROLLBACK;
        SET p_refund = 0;
        SET p_status = 'UNAUTHORIZED';
    ELSEIF v_bstatus <> 'CONFIRMED' THEN
        ROLLBACK;
        SET p_refund = 0;
        SET p_status = 'NOT_ACTIVE';
    ELSE
        SET v_refund = fn_calculate_refund(v_fare, v_travel);
        UPDATE booking
            SET booking_status = 'CANCELLED',
                payment_status = IF(v_refund > 0, 'REFUNDED', payment_status)
            WHERE booking_id = p_booking_id;
        UPDATE payment SET payment_status = IF(v_refund > 0, 'REFUNDED', payment_status)
            WHERE booking_id = p_booking_id AND payment_status = 'PAID';
        INSERT INTO cancellation (booking_id, cancellation_date, reason, refund_amount, refund_status)
            VALUES (p_booking_id, NOW(), p_reason, v_refund,
                    IF(v_refund > 0, 'PROCESSED', 'NONE'));
        COMMIT;
        SET p_refund = v_refund;
        SET p_status = 'OK';
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_generate_booking_summary$$
CREATE PROCEDURE sp_generate_booking_summary(IN p_booking_id INT)
BEGIN
    SELECT b.booking_ref AS PNR, p.name AS passenger, f.flight_number, f.airline,
           src.city AS source_city, dst.city AS destination_city,
           f.departure_time, f.arrival_time, s.seat_number, s.seat_class,
           b.fare, b.booking_status, b.payment_status, b.travel_date
    FROM booking b
    JOIN passenger p ON b.passenger_id = p.passenger_id
    JOIN flight f ON b.flight_id = f.flight_id
    JOIN seat s ON b.seat_id = s.seat_id
    JOIN airport src ON f.source_airport = src.airport_id
    JOIN airport dst ON f.destination_airport = dst.airport_id
    WHERE b.booking_id = p_booking_id;
END$$

-- =====================================================================
-- TRIGGERS
-- Seat / available_seats updates live HERE (not also in application
-- code) so a booking cannot double-decrement inventory.
-- =====================================================================

DROP TRIGGER IF EXISTS trg_prevent_overbooking$$
CREATE TRIGGER trg_prevent_overbooking
BEFORE INSERT ON booking
FOR EACH ROW
BEGIN
    DECLARE seats_left INT;
    DECLARE seat_st VARCHAR(20);
    IF NEW.booking_status = 'CONFIRMED' THEN
        SELECT available_seats INTO seats_left FROM flight WHERE flight_id = NEW.flight_id;
        IF seats_left IS NULL OR seats_left <= 0 THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'No available seats on this flight';
        END IF;
        SELECT status INTO seat_st FROM seat WHERE seat_id = NEW.seat_id;
        IF seat_st IS NULL OR seat_st <> 'AVAILABLE' THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Seat is not available';
        END IF;
    END IF;
END$$

DROP TRIGGER IF EXISTS trg_after_booking_insert$$
CREATE TRIGGER trg_after_booking_insert
AFTER INSERT ON booking
FOR EACH ROW
BEGIN
    IF NEW.booking_status = 'CONFIRMED' THEN
        UPDATE seat SET status = 'BOOKED' WHERE seat_id = NEW.seat_id;
        UPDATE flight SET available_seats = available_seats - 1 WHERE flight_id = NEW.flight_id;
    END IF;
    INSERT INTO audit_log (user_id, user_role, action, table_name, record_id, description)
    VALUES (NEW.passenger_id, 'PASSENGER', 'BOOKING_CREATED', 'booking', NEW.booking_id,
            CONCAT('PNR ', NEW.booking_ref, ' created'));
END$$

DROP TRIGGER IF EXISTS trg_after_booking_update$$
CREATE TRIGGER trg_after_booking_update
AFTER UPDATE ON booking
FOR EACH ROW
BEGIN
    IF OLD.booking_status = 'CONFIRMED' AND NEW.booking_status = 'CANCELLED' THEN
        UPDATE seat SET status = 'AVAILABLE' WHERE seat_id = NEW.seat_id AND status = 'BOOKED';
        UPDATE flight SET available_seats = available_seats + 1 WHERE flight_id = NEW.flight_id;
        INSERT INTO audit_log (user_id, user_role, action, table_name, record_id, description)
        VALUES (NEW.passenger_id, 'PASSENGER', 'BOOKING_CANCELLED', 'booking', NEW.booking_id,
                CONCAT('PNR ', NEW.booking_ref, ' cancelled'));
    END IF;
END$$

DROP TRIGGER IF EXISTS trg_after_payment_insert$$
CREATE TRIGGER trg_after_payment_insert
AFTER INSERT ON payment
FOR EACH ROW
BEGIN
    IF NEW.payment_status = 'PAID' THEN
        INSERT INTO audit_log (user_id, user_role, action, table_name, record_id, description)
        VALUES (NULL, 'SYSTEM', 'PAYMENT_COMPLETED', 'payment', NEW.payment_id,
                CONCAT('txn ', NEW.transaction_id));
    END IF;
END$$

DELIMITER ;
