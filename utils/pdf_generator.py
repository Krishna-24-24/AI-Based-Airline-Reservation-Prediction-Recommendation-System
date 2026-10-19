"""Downloadable e-ticket PDF (simulated airline stationery)."""

from io import BytesIO

from fpdf import FPDF

from utils.helpers import format_currency


def build_eticket_pdf(booking):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "E-TICKET", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, str(booking.get("airline", "Airline")), ln=True)
    pdf.ln(4)
    lines = [
        ("PNR", booking.get("booking_ref")),
        ("Passenger", booking.get("passenger_name")),
        ("Flight", booking.get("flight_number")),
        ("From", f"{booking.get('source_city')} ({booking.get('source_code', '')})"),
        ("To", f"{booking.get('destination_city')} ({booking.get('destination_code', '')})"),
        ("Date", str(booking.get("travel_date"))),
        ("Departure", str(booking.get("departure_time"))),
        ("Arrival", str(booking.get("arrival_time"))),
        ("Seat", f"{booking.get('seat_number')} ({booking.get('seat_class')})"),
        ("Fare", format_currency(booking.get("fare"))),
        ("Payment", booking.get("payment_status")),
        ("Status", booking.get("booking_status")),
    ]
    pdf.set_font("Helvetica", "", 12)
    for label, value in lines:
        pdf.cell(50, 8, f"{label}:", border=0)
        pdf.cell(0, 8, str(value), ln=True)
    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, "This is a simulated e-ticket for academic demonstration. Not valid for travel.")
    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
