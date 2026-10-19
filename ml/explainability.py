"""Simple, feature-based explanations. Only claims backed by actual values."""


def explain_cancellation_risk(features, probability, risk_level):
    reasons = []
    lead = int(features.get("booking_lead_time", 0) or 0)
    days = int(features.get("days_before_departure", 0) or 0)
    prev_c = int(features.get("previous_cancellations", 0) or 0)
    prev_ns = int(features.get("previous_no_shows", 0) or 0)
    prev_done = int(features.get("previous_completed_trips", 0) or 0)
    fare = float(features.get("ticket_fare", 0) or 0)
    weekend = int(features.get("is_weekend", 0) or 0)

    if lead < 3 or days < 3:
        reasons.append(f"Booking made only {min(lead, days)} day(s) before departure")
    if prev_c >= 2:
        reasons.append(f"Passenger has {prev_c} previous cancellation(s)")
    if prev_ns >= 1:
        reasons.append(f"Passenger has {prev_ns} previous no-show(s)")
    if weekend and risk_level != "LOW":
        reasons.append("Travel date is a weekend (historically higher leisure cancellation)")
    if prev_done >= 5 and risk_level == "LOW":
        reasons.append(f"Passenger has {prev_done} completed trips (more reliable history)")
    if fare >= 8000 and risk_level == "LOW":
        reasons.append(f"Higher fare (₹{fare:,.0f}) is associated with lower walk-away risk")
    if not reasons:
        reasons.append(f"Model estimate is {probability*100:.1f}% based on booking and history features")
    return {
        "headline": f"Why is this booking {risk_level} RISK?",
        "reasons": reasons,
        "probability": probability,
        "risk_level": risk_level,
    }


def explain_recommendation(reasons_flags):
    """reasons_flags: list of (bool, text) — only True items are shown."""
    return [text for ok, text in reasons_flags if ok]
