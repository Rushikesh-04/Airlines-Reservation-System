# Blue Sky Airlines

A Flask airline reservation demo using Firebase Cloud Firestore. It supports flight search, economy and business bookings, booking cancellation, and downloadable PDF boarding passes. It does not connect to live airline inventory or payments.

## Run locally

```powershell
py -m pip install -r requirements.txt
$env:FIREBASE_SERVICE_ACCOUNT_JSON = Get-Content -Raw .\service-account.json
py new.py
```

Create/download a Firebase service-account key and save it locally as `service-account.json` before running this command. Never commit that key. Open `http://127.0.0.1:5000`.

The app stores reservations and the demo flight schedule in Firestore. Sample departure times are illustrative, not live flight availability.

## Deploy to Render with Firebase Firestore

The app uses Firebase Cloud Firestore for all reservation and schedule storage. Firestore data is separate from Render's temporary service filesystem and remains in your Firebase project across Render deploys. Firebase has a no-cost quota, subject to its current limits and billing terms.

1. Create a project at the [Firebase Console](https://console.firebase.google.com/).
2. In Firebase, open **Build → Firestore Database → Create database**. Choose **Production mode** and a database location. The Python Admin SDK authenticates as your server and accesses Firestore with privileged credentials; do not embed Admin credentials in browser code.
3. Open **Project settings → Service accounts → Generate new private key** and download the JSON key. Keep it private; anyone with this key can access project data.
4. Push `new.py`, `templates/`, `static/`, `requirements.txt`, and `render.yaml` to GitHub. Do not commit the service-account JSON file.
5. In [Render](https://dashboard.render.com/), select **New → Blueprint** and connect the repository. When prompted for `FIREBASE_SERVICE_ACCOUNT_JSON`, paste the entire JSON key file contents as the secret value. The Blueprint generates `FLASK_SECRET_KEY` and creates the free web service.
6. Deploy and open the `onrender.com` URL shown on the Render service page. If the service already exists, add `FIREBASE_SERVICE_ACCOUNT_JSON` under its **Environment** settings and save with a deploy.

The app adds any missing sample flights to Firestore's `flight_schedule` collection on startup without replacing existing flight documents. Reservations are stored in the `reservations` collection. A booking is accepted only when its route, day, and departure time match a scheduled flight. Existing data in your former local database is not copied automatically. Free Render services can spin down while idle; Firestore data remains available when the app wakes up.
