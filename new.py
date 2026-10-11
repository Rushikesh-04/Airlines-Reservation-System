import json
import os
import secrets
from datetime import datetime
from io import BytesIO

from flask import Flask, flash, g, redirect, render_template, request, send_file, session, url_for
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
AIRPORTS = [
    "Mumbai",
    "Shirdi",
    "Jalgaon",
    "Chhatrapati Sambhajinagar",
]
DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
TIMES = ["1:00 AM", "7:00 AM", "1:00 PM", "4:00 PM", "9:00 PM"]
CLASSES = {"Economic": "Economy", "BusinessClass": "Business"}

# These routes are the sample services already listed in the original desktop app.
SAMPLE_SERVICES = [
    ("Mumbai", "Shirdi", "Monday"),
    ("Mumbai", "Shirdi", "Tuesday"),
    ("Mumbai", "Shirdi", "Friday"),
    ("Mumbai", "Shirdi", "Sunday"),
    ("Mumbai", "Jalgaon", "Wednesday"),
    ("Mumbai", "Jalgaon", "Thursday"),
    ("Shirdi", "Jalgaon", "Thursday"),
    ("Shirdi", "Chhatrapati Sambhajinagar", "Thursday"),
    ("Chhatrapati Sambhajinagar", "Jalgaon", "Sunday"),
    ("Chhatrapati Sambhajinagar", "Mumbai", "Monday"),
    ("Mumbai", "Chhatrapati Sambhajinagar", "Sunday"),
    ("Jalgaon", "Shirdi", "Thursday"),
    ("Jalgaon", "Chhatrapati Sambhajinagar", "Sunday"),
    ("Jalgaon", "Mumbai", "Saturday"),
]

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
FIRESTORE_DB = None


def get_db():
    if FIRESTORE_DB is None:
        raise RuntimeError(
            "Firebase Firestore is not initialized. Configure FIREBASE_SERVICE_ACCOUNT_JSON."
        )
    return FIRESTORE_DB


def create_booking_reference():
    return f"BS{secrets.token_hex(4).upper()}"


def initialize_database():
    if not FIREBASE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT_JSON must be set to use Firebase Firestore."
        )
    initialize_firestore()


def initialize_firestore():
    global FIRESTORE_DB

    import firebase_admin
    from firebase_admin import credentials, firestore

    try:
        service_account = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError as error:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON must contain valid service-account JSON.") from error

    if not isinstance(service_account, dict) or not service_account.get("project_id"):
        raise RuntimeError("Firebase service-account JSON must include a project_id.")

    firebase_app = firebase_admin.initialize_app(
        credentials.Certificate(service_account),
        {"projectId": service_account["project_id"]},
    )
    FIRESTORE_DB = firestore.client(app=firebase_app)

    schedule = FIRESTORE_DB.collection("flight_schedule")
    existing_flight_codes = {document.id for document in schedule.stream()}
    batch = FIRESTORE_DB.batch()
    added_flights = 0
    for index, (boarding, destination, day) in enumerate(SAMPLE_SERVICES):
        flight_code = f"BS{201 + index}"
        if flight_code in existing_flight_codes:
            continue
        batch.set(
            schedule.document(flight_code),
            {
                "flight_code": flight_code,
                "boarding": boarding,
                "destination": destination,
                "day": day,
                "departure_time": TIMES[index % len(TIMES)],
            },
        )
        added_flights += 1
    if added_flights:
        batch.commit()


def validate_last_four(value):
    return len(value) == 4 and value.isdigit()


def scheduled_flight_exists(db, boarding, destination, day, departure_time):
    for document in db.collection("flight_schedule").stream():
        flight = document.to_dict()
        if (
            flight.get("boarding") == boarding
            and flight.get("destination") == destination
            and flight.get("day") == day
            and flight.get("departure_time") == departure_time
        ):
            return True
    return False


@app.get("/")
def index():
    db = get_db()
    boarding = request.args.get("boarding", "").strip()
    destination = request.args.get("destination", "").strip()
    day = request.args.get("day", "").strip()
    departure_time = request.args.get("time", "").strip()
    if departure_time not in TIMES:
        departure_time = ""
    flights = []
    search_performed = any((boarding, destination, day))

    if search_performed:
        if (
            boarding not in AIRPORTS
            or destination not in AIRPORTS
            or day not in DAYS
            or boarding == destination
        ):
            flash("Choose a valid origin, destination, and travel day.", "error")
        else:
            flights = []
            for document in db.collection("flight_schedule").stream():
                flight = document.to_dict()
                if (
                    flight.get("boarding") == boarding
                    and flight.get("destination") == destination
                    and flight.get("day") == day
                ):
                    flights.append(flight)
            flights.sort(key=lambda flight: flight.get("departure_time", ""))

    return render_template(
        "index.html",
        airports=AIRPORTS,
        days=DAYS,
        times=TIMES,
        classes=CLASSES,
        flights=flights,
        search_performed=search_performed,
        recent_booking_ref=session.get("recent_booking_ref", ""),
        search_values={
            "boarding": boarding,
            "destination": destination,
            "day": day,
            "time": departure_time,
        },
    )


@app.post("/book")
def book():
    boarding = request.form.get("boarding", "").strip()
    destination = request.form.get("destination", "").strip()
    citizen_last4 = request.form.get("citizen_last4", "").strip()
    seat_class = request.form.get("seat_class", "").strip()
    day = request.form.get("day", "").strip()
    departure_time = request.form.get("departure_time", "").strip()

    if (
        boarding not in AIRPORTS
        or destination not in AIRPORTS
        or boarding == destination
        or not validate_last_four(citizen_last4)
        or seat_class not in CLASSES
        or day not in DAYS
        or departure_time not in TIMES
    ):
        flash("Please complete every field with valid booking details.", "error")
        return redirect(url_for("index", _anchor="book"))

    db = get_db()
    if not scheduled_flight_exists(db, boarding, destination, day, departure_time):
        flash("That flight is not on the schedule. Search flights and choose an available departure.", "error")
        return redirect(url_for("index", _anchor="flights"))

    booking_ref = create_booking_reference()
    reservation = {
        "booking_ref": booking_ref,
        "citizen_last4": citizen_last4,
        "boarding": boarding,
        "destination": destination,
        "seat_class": seat_class,
        "day": day,
        "departure_time": departure_time,
        "booked_at": datetime.now().isoformat(timespec="seconds"),
    }
    db.collection("reservations").document(booking_ref).create(reservation)
    session["recent_booking_ref"] = booking_ref
    return redirect(url_for("index", _anchor="manage"))


@app.post("/cancel")
def cancel():
    booking_ref = request.form.get("booking_ref", "").strip().upper()
    citizen_last4 = request.form.get("citizen_last4", "").strip()
    if not booking_ref or not validate_last_four(citizen_last4):
        flash("Enter your booking reference and the last four digits of your citizenship number.", "error")
        return redirect(url_for("index", _anchor="manage"))

    db = get_db()
    reservation_ref = db.collection("reservations").document(booking_ref)
    reservation = reservation_ref.get()
    cancelled = (
        reservation.exists
        and reservation.to_dict().get("citizen_last4") == citizen_last4
    )
    if cancelled:
        reservation_ref.delete()
    if cancelled:
        if session.get("recent_booking_ref") == booking_ref:
            session.pop("recent_booking_ref")
        flash("Your reservation has been cancelled.", "success")
    else:
        flash("We couldn't find a booking matching those details.", "error")
    return redirect(url_for("index", _anchor="manage"))


@app.post("/ticket")
def ticket():
    booking_ref = request.form.get("booking_ref", "").strip().upper()
    citizen_last4 = request.form.get("citizen_last4", "").strip()
    if not booking_ref or not validate_last_four(citizen_last4):
        flash("Enter your booking reference and the last four digits to download your ticket.", "error")
        return redirect(url_for("index", _anchor="manage"))

    reservation_document = (
        get_db().collection("reservations").document(booking_ref).get()
    )
    reservation = reservation_document.to_dict() if reservation_document.exists else None
    if reservation and reservation.get("citizen_last4") != citizen_last4:
        reservation = None
    if reservation is None:
        flash("We couldn't find a booking matching those details.", "error")
        return redirect(url_for("index", _anchor="manage"))

    pdf = BytesIO()
    document = canvas.Canvas(pdf, pagesize=letter)
    page_width, page_height = letter
    document.setFillColor(colors.HexColor("#19362e"))
    document.rect(0, page_height - 155, page_width, 155, fill=1, stroke=0)
    document.setFillColor(colors.white)
    document.setFont("Helvetica-Bold", 23)
    document.drawString(48, page_height - 70, "BLUE SKY AIRLINES")
    document.setFont("Helvetica", 11)
    document.drawString(48, page_height - 96, "YOUR JOURNEY, beautifully planned.")
    document.setFillColor(colors.HexColor("#24483e"))
    document.setFont("Helvetica-Bold", 17)
    document.drawString(48, page_height - 205, "BOARDING PASS")
    document.setStrokeColor(colors.HexColor("#dce4ef"))
    document.line(48, page_height - 220, page_width - 48, page_height - 220)

    labels = [
        ("BOOKING REFERENCE", reservation["booking_ref"]),
        ("FROM", reservation["boarding"]),
        ("TO", reservation["destination"]),
        ("CABIN", CLASSES.get(reservation["seat_class"], reservation["seat_class"])),
        ("TRAVEL DAY", reservation["day"]),
        ("DEPARTURE", reservation["departure_time"]),
        ("PASSENGER ID", f"**** {reservation['citizen_last4']}"),
    ]
    y = page_height - 265
    for label, value in labels:
        document.setFillColor(colors.HexColor("#718096"))
        document.setFont("Helvetica-Bold", 9)
        document.drawString(48, y, label)
        document.setFillColor(colors.HexColor("#24483e"))
        document.setFont("Helvetica-Bold", 13)
        document.drawString(48, y - 20, value)
        y -= 61

    document.save()
    pdf.seek(0)
    return send_file(
        pdf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"ticket_{booking_ref}.pdf",
    )


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


initialize_database()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
