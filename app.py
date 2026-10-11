
import os, sqlite3, math, random
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "smartmaritime.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-development-secret")

app = Flask(__name__)
app.secret_key = SECRET_KEY

DEMO_SHIPS = [
    {"mmsi":"419000101","name":"CHENNAI STAR","type":"Cargo","lat":13.0827,"lon":80.2707,"speed":12.4,"course":78,"destination":"Chennai Port","status":"Underway"},
    {"mmsi":"419000102","name":"BAY VOYAGER","type":"Tanker","lat":13.0950,"lon":80.2950,"speed":9.1,"course":235,"destination":"Ennore Port","status":"Underway"},
    {"mmsi":"419000103","name":"CORAL WAVE","type":"Fishing","lat":13.0610,"lon":80.2450,"speed":4.2,"course":18,"destination":"Fishing grounds","status":"Underway"},
    {"mmsi":"419000104","name":"OCEAN CREST","type":"Passenger","lat":13.1100,"lon":80.2200,"speed":7.8,"course":160,"destination":"Chennai Port","status":"Approaching"},
    {"mmsi":"419000105","name":"HARBOR RUNNER","type":"Tug","lat":13.0700,"lon":80.2900,"speed":3.5,"course":300,"destination":"Berth 4","status":"Harbour"},
    {"mmsi":"419000106","name":"BLUE HORIZON","type":"Cargo","lat":13.1250,"lon":80.2550,"speed":11.0,"course":195,"destination":"Visakhapatnam","status":"Underway"},
]

def db_conn():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'operator',
      verified INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS ships (
      mmsi TEXT PRIMARY KEY, name TEXT NOT NULL, vessel_type TEXT NOT NULL,
      lat REAL NOT NULL, lon REAL NOT NULL, speed REAL NOT NULL,
      course REAL NOT NULL, destination TEXT NOT NULL, status TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS alerts (
      id INTEGER PRIMARY KEY AUTOINCREMENT, severity TEXT NOT NULL,
      title TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL,
      acknowledged INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS sos (
      id INTEGER PRIMARY KEY AUTOINCREMENT, vessel TEXT NOT NULL,
      location TEXT NOT NULL, message TEXT NOT NULL, priority TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'OPEN', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS maintenance (
      id INTEGER PRIMARY KEY AUTOINCREMENT, vessel TEXT NOT NULL,
      equipment TEXT NOT NULL, due_date TEXT NOT NULL, priority TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Pending', notes TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS harbour_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, vessel TEXT NOT NULL,
      movement TEXT NOT NULL, berth TEXT NOT NULL, eta TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Scheduled'
    );
    """)
    user = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not user:
        # Demo credentials only. Change the password before deployment.
        conn.execute("INSERT INTO users(username,password,role,verified) VALUES(?,?,?,1)",
                     ("admin", "Marine@123", "admin"))
    count = conn.execute("SELECT COUNT(*) FROM ships").fetchone()[0]
    if count == 0:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        for s in DEMO_SHIPS:
            conn.execute("""INSERT INTO ships VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (s["mmsi"],s["name"],s["type"],s["lat"],s["lon"],s["speed"],s["course"],s["destination"],s["status"],now))
    if conn.execute("SELECT COUNT(*) FROM maintenance").fetchone()[0] == 0:
        conn.executemany("""INSERT INTO maintenance(vessel,equipment,due_date,priority,status,notes)
          VALUES(?,?,?,?,?,?)""", [
            ("CHENNAI STAR","Main engine inspection",(datetime.now()+timedelta(days=2)).date().isoformat(),"High","Pending","Demo maintenance item"),
            ("BAY VOYAGER","Navigation lights",(datetime.now()+timedelta(days=5)).date().isoformat(),"Medium","Pending","Check before next voyage"),
            ("OCEAN CREST","Life-saving equipment",(datetime.now()+timedelta(days=1)).date().isoformat(),"High","In progress","Scheduled safety inspection"),
        ])
    if conn.execute("SELECT COUNT(*) FROM harbour_events").fetchone()[0] == 0:
        conn.executemany("""INSERT INTO harbour_events(vessel,movement,berth,eta,status) VALUES(?,?,?,?,?)""", [
            ("CHENNAI STAR","Arrival","Berth 2",(datetime.now()+timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"),"Scheduled"),
            ("OCEAN CREST","Arrival","Berth 1",(datetime.now()+timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"),"Approaching"),
            ("BLUE HORIZON","Departure","Berth 5",(datetime.now()+timedelta(hours=5)).strftime("%Y-%m-%d %H:%M"),"Scheduled"),
        ])
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped

def rows(query, params=()):
    return db_conn().execute(query, params).fetchall()

def haversine_nm(lat1, lon1, lat2, lon2):
    r_km = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    km = 2*r_km*math.asin(math.sqrt(min(1,a)))
    return km / 1.852

def risk_summary(ships):
    # Demonstration proximity risk estimate, not a certified navigation system.
    result = []
    for i, a in enumerate(ships):
        for b in ships[i+1:]:
            d = haversine_nm(a["lat"],a["lon"],b["lat"],b["lon"])
            # Conservative demo thresholds based on current separation only.
            if d < 0.45:
                severity = "HIGH"
            elif d < 0.9:
                severity = "MEDIUM"
            else:
                continue
            result.append({"severity":severity,"title":f'{a["name"]} / {b["name"]}',
                           "details":f'Current separation is about {d:.2f} nautical miles. Check heading, speed and local conditions.',
                           "distance":d})
    result.sort(key=lambda x: x["distance"])
    return result

def marine_forecast():
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    forecast = []
    for step in range(7):
        valid_at = now + timedelta(hours=step * 4)
        phase = (valid_at.hour / 24) * math.tau
        wind = max(4, 14 + 5 * math.sin(phase - 0.8))
        wave = max(0.2, 0.8 + 0.35 * math.sin(phase + 0.4))
        forecast.append({
            "time": valid_at.strftime("%a %H:%M"),
            "wind_kmh": round(wind, 1),
            "wind_direction": round((105 + 35 * math.sin(phase)) % 360),
            "wave_m": round(wave, 2),
            "period_s": round(5.5 + 1.3 * math.cos(phase), 1),
            "tide_m": round(1.0 + 0.45 * math.sin(phase - 1.1), 2),
            "condition": "Rough" if wave >= 1.05 else "Moderate" if wave >= 0.75 else "Calm",
        })
    return {
        "generated_at": datetime.now().astimezone().strftime("%d %b %Y, %H:%M:%S"),
        "source": "LOCAL SCENARIO MODEL",
        "forecast": forecast,
    }

@app.context_processor
def inject_globals():
    return {"current_user": session.get("username"), "current_role": session.get("role")}

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("live_map"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        user = db_conn().execute("SELECT * FROM users WHERE username=? AND password=? AND verified=1",
                                 (username,password)).fetchone()
        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(request.args.get("next") or url_for("live_map"))
        flash("Invalid credentials or account is not verified.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    ships = rows("SELECT * FROM ships ORDER BY name")
    risk = risk_summary([dict(x) for x in ships])
    sos_open = rows("SELECT * FROM sos WHERE status='OPEN' ORDER BY id DESC")
    stats = {
      "ships":len(ships),
      "underway":sum(1 for s in ships if s["status"] in ("Underway","Approaching")),
      "risks":len(risk),
      "sos":len(sos_open)
    }
    return render_template("dashboard.html", stats=stats, ships=ships, risks=risk[:4], sos=sos_open[:3])

@app.route("/live-map")
@login_required
def live_map():
    ships = rows("SELECT * FROM ships ORDER BY name")
    current_conditions = marine_forecast()["forecast"][0]
    next_harbour_event = rows(
        "SELECT * FROM harbour_events WHERE eta>=? ORDER BY eta LIMIT 1",
        (datetime.now().strftime("%Y-%m-%d %H:%M"),),
    )
    risks = risk_summary([dict(ship) for ship in ships])
    return render_template(
        "live_map.html",
        ships=ships,
        ships_json=json_for_map(ships),
        current_conditions=current_conditions,
        next_harbour_event=next_harbour_event[0] if next_harbour_event else None,
        risk_count=len(risks),
    )

def json_for_map(ships):
    import json
    return json.dumps([{"name":s["name"],"lat":s["lat"],"lon":s["lon"],"speed":s["speed"],"course":s["course"],"status":s["status"],"type":s["vessel_type"]} for s in ships])

@app.route("/nearby-ships")
@login_required
def nearby_ships():
    ships = rows("SELECT * FROM ships ORDER BY name")
    return render_template("nearby_ships.html", ships=ships)

@app.route("/collision-risk")
@login_required
def collision_risk():
    ships = rows("SELECT * FROM ships ORDER BY name")
    risks = risk_summary([dict(s) for s in ships])
    return render_template("collision_risk.html", risks=risks)

@app.route("/weather-waves")
@login_required
def weather_waves():
    return render_template("weather_waves.html", conditions=marine_forecast())

@app.route("/sos", methods=["GET","POST"])
@login_required
def sos():
    if request.method == "POST":
        vessel = request.form.get("vessel","").strip()
        location = request.form.get("location","").strip()
        message = request.form.get("message","").strip()
        priority = request.form.get("priority","HIGH")
        if vessel and location and message:
            db_conn().execute("INSERT INTO sos(vessel,location,message,priority,status,created_at) VALUES(?,?,?,?,?,?)",
                (vessel,location,message,priority,"OPEN",datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            db_conn().execute("INSERT INTO alerts(severity,title,details,created_at) VALUES(?,?,?,?)",
                (priority,"SOS request received",f"{vessel} at {location}: {message}",datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            db_conn().commit()
            flash("SOS logged in the demo database. This does not contact real emergency services.", "success")
            return redirect(url_for("sos"))
        flash("Please complete all SOS fields.", "error")
    requests_list = rows("SELECT * FROM sos ORDER BY id DESC")
    ships = rows("SELECT name FROM ships ORDER BY name")
    return render_template("sos.html", requests_list=requests_list, ships=ships)

@app.route("/sos/<int:sos_id>/resolve", methods=["POST"])
@login_required
def resolve_sos(sos_id):
    db_conn().execute("UPDATE sos SET status='RESOLVED' WHERE id=?", (sos_id,))
    db_conn().commit()
    flash("SOS marked as resolved in the demo database.", "success")
    return redirect(url_for("sos"))

@app.route("/communication", methods=["GET","POST"])
@login_required
def communication():
    if request.method == "POST":
        recipient = request.form.get("recipient","").strip()
        message = request.form.get("message","").strip()
        if recipient and message:
            db_conn().execute("INSERT INTO alerts(severity,title,details,created_at) VALUES(?,?,?,?)",
                ("INFO","Demo message queued",f"To {recipient}: {message}",datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            db_conn().commit()
            flash("Message saved to the local demo alert log; no radio or ship-to-ship transmission occurs.", "success")
    messages = rows("SELECT * FROM alerts ORDER BY id DESC LIMIT 15")
    ships = rows("SELECT name FROM ships ORDER BY name")
    return render_template("communication.html", messages=messages, ships=ships)

@app.route("/maintenance", methods=["GET","POST"])
@login_required
def maintenance():
    if request.method == "POST":
        vessel=request.form.get("vessel","").strip()
        equipment=request.form.get("equipment","").strip()
        due_date=request.form.get("due_date","").strip()
        priority=request.form.get("priority","Medium")
        notes=request.form.get("notes","").strip()
        if vessel and equipment and due_date:
            db_conn().execute("INSERT INTO maintenance(vessel,equipment,due_date,priority,status,notes) VALUES(?,?,?,?,?,?)",
                              (vessel,equipment,due_date,priority,"Pending",notes))
            db_conn().commit()
            flash("Maintenance item added.", "success")
            return redirect(url_for("maintenance"))
        flash("Vessel, equipment and due date are required.", "error")
    items=rows("SELECT * FROM maintenance ORDER BY due_date")
    ships=rows("SELECT name FROM ships ORDER BY name")
    return render_template("maintenance.html", items=items, ships=ships)

@app.route("/maintenance/<int:item_id>/done", methods=["POST"])
@login_required
def maintenance_done(item_id):
    db_conn().execute("UPDATE maintenance SET status='Completed' WHERE id=?", (item_id,))
    db_conn().commit()
    return redirect(url_for("maintenance"))

@app.route("/harbour-control", methods=["GET","POST"])
@login_required
def harbour_control():
    if request.method == "POST":
        vessel=request.form.get("vessel","").strip()
        movement=request.form.get("movement","Arrival")
        berth=request.form.get("berth","").strip()
        eta=request.form.get("eta","").strip()
        if vessel and berth and eta:
            db_conn().execute("INSERT INTO harbour_events(vessel,movement,berth,eta,status) VALUES(?,?,?,?,?)",
                              (vessel,movement,berth,eta,"Scheduled"))
            db_conn().commit()
            flash("Harbour movement added.", "success")
            return redirect(url_for("harbour_control"))
        flash("Please complete vessel, berth and ETA.", "error")
    events=rows(
        "SELECT * FROM harbour_events WHERE eta>=? ORDER BY eta",
        (datetime.now().strftime("%Y-%m-%d %H:%M"),),
    )
    ships=rows("SELECT name FROM ships ORDER BY name")
    movement_counts = {
        "arrivals": sum(event["movement"] == "Arrival" for event in events),
        "departures": sum(event["movement"] == "Departure" for event in events),
        "scheduled": len(events),
    }
    return render_template("harbour_control.html", events=events, ships=ships, movement_counts=movement_counts)

@app.route("/api/ships")
@login_required
def api_ships():
    ships = rows("SELECT * FROM ships ORDER BY name")
    return {"ships":[dict(s) for s in ships], "mode":"SIMULATION", "note":"Locally simulated positions; not live AIS."}

@app.post("/api/ships/tick")
@login_required
def advance_simulated_ships():
    conn = db_conn()
    ships = rows("SELECT * FROM ships ORDER BY name")
    now = datetime.now(timezone.utc)
    simulated_seconds = 60
    for ship in ships:
        if ship["status"] == "Harbour":
            continue
        distance_nm = ship["speed"] * simulated_seconds / 3600
        course_rad = math.radians(ship["course"])
        lat = ship["lat"] + distance_nm * math.cos(course_rad) / 60
        lon_scale = max(math.cos(math.radians(ship["lat"])), 0.01)
        lon = ship["lon"] + distance_nm * math.sin(course_rad) / (60 * lon_scale)
        course = ship["course"]
        if not 13.035 <= lat <= 13.16 or not 80.17 <= lon <= 80.35:
            course = (course + 180) % 360
        conn.execute(
            "UPDATE ships SET lat=?,lon=?,course=?,updated_at=? WHERE mmsi=?",
            (lat, lon, course, now.isoformat(timespec="seconds").replace("+00:00", "Z"), ship["mmsi"]),
        )
    conn.commit()
    updated_ships = rows("SELECT * FROM ships ORDER BY name")
    return {
        "ships": [dict(ship) for ship in updated_ships],
        "simulated_seconds": simulated_seconds,
        "updated_at": now.astimezone().strftime("%H:%M:%S"),
        "mode": "SIMULATION",
    }

@app.get("/api/weather-forecast")
@login_required
def api_weather_forecast():
    return marine_forecast()

@app.post("/api/assistant")
@login_required
def operations_assistant():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {"error": "Send a JSON object containing message and language."}, 400
    message = payload.get("message", "")
    language = payload.get("language", "en")
    if not isinstance(message, str) or not message.strip() or len(message) > 500:
        return {"error": "Message must contain 1-500 characters."}, 400
    if language not in ("en", "ta"):
        return {"error": "Language must be 'en' or 'ta'."}, 400

    text = message.strip().lower()
    is_tamil = language == "ta"
    weather_terms = ("weather", "wave", "wind", "forecast", "weather", "காலநிலை", "வானிலை", "அலை", "காற்று", "முன்னறிவிப்பு")
    harbour_terms = ("harbour", "harbor", "berth", "arrival", "departure", "துறைமுகம்", "வருகை", "புறப்பாடு", "நங்கூரம்")
    ship_terms = ("ship", "vessel", "fleet", "ais", "கப்பல்", "கப்பல்கள்", "கப்பல்களின்")
    safety_terms = ("sos", "emergency", "danger", "help", "உதவி", "அவசரம்", "ஆபத்து")

    if any(term in text for term in safety_terms):
        reply = (
            "SOS entries are saved only in this app. This system cannot contact rescue services. In a real emergency, contact the local coast guard/emergency authority by approved radio or phone."
            if not is_tamil else
            "SOS தகவல் இந்த app-ல் மட்டும் சேமிக்கப்படும்; மீட்புப் படையினரை இது தொடர்புகொள்ளாது. உண்மையான அவசரநிலையில், அங்கீகரிக்கப்பட்ட வானொலி அல்லது தொலைபேசி மூலம் உள்ளூர் கடலோரக் காவல்/அவசர சேவையைத் தொடர்புகொள்ளவும்."
        )
    elif any(term in text for term in weather_terms):
        conditions = marine_forecast()["forecast"][0]
        reply = (
            f"Current local scenario: wind {conditions['wind_kmh']} km/h, waves {conditions['wave_m']} m, {conditions['condition'].lower()}. This is a calculated example, not an observed forecast. Open Weather & Waves for the 24-hour scenario."
            if not is_tamil else
            f"தற்போதைய உள்ளூர் கணிப்பு: காற்று {conditions['wind_kmh']} km/h, அலை {conditions['wave_m']} m, நிலை {conditions['condition']}. இது கணினி உருவாக்கிய மாதிரி மட்டுமே; உண்மையான வானிலை முன்னறிவிப்பு அல்ல. 24 மணி நேர மாதிரிக்கு Weather & Waves பக்கத்தைப் பார்க்கவும்."
        )
    elif any(term in text for term in harbour_terms):
        events = rows("SELECT movement, status, COUNT(*) AS amount FROM harbour_events GROUP BY movement, status")
        summary = ", ".join(f"{event['movement'].lower()} {event['status'].lower()}: {event['amount']}" for event in events) or "no local harbour schedules"
        reply = (
            f"Local harbour board: {summary}. These are manually entered schedules; the app is not connected to a port authority."
            if not is_tamil else
            f"உள்ளூர் துறைமுகப் பலகை: {summary}. இவை app-ல் கைமுறையாகச் சேர்க்கப்பட்ட திட்டங்கள்; துறைமுக அதிகார அமைப்புடன் இணைப்பு இல்லை."
        )
    elif any(term in text for term in ship_terms):
        ships = rows("SELECT status, COUNT(*) AS amount FROM ships GROUP BY status")
        summary = ", ".join(f"{ship['amount']} {ship['status'].lower()}" for ship in ships)
        reply = (
            f"Fleet board currently contains {sum(ship['amount'] for ship in ships)} locally simulated vessels ({summary}). Positions are not live AIS."
            if not is_tamil else
            f"கப்பல் பலகையில் {sum(ship['amount'] for ship in ships)} உள்ளூர் மாதிரி கப்பல்கள் உள்ளன ({summary}). இடங்கள் live AIS தரவு அல்ல."
        )
    else:
        reply = (
            "I can help with the vessel list, weather and wave scenario, harbour schedule, or SOS workflow. Ask about one of those. I work offline with this app's local data; I do not provide live maritime intelligence."
            if not is_tamil else
            "கப்பல் பட்டியல், வானிலை/அலை மாதிரி, துறைமுக அட்டவணை அல்லது SOS நடைமுறை பற்றி உதவ முடியும். இவற்றில் ஒன்றைக் கேளுங்கள். இந்த app-இன் உள்ளூர் தரவுடன் மட்டும் பதிலளிக்கிறேன்; நேரடி கடல்சார் தகவல் வழங்குவதில்லை."
        )
    return {"reply": reply, "language": language, "mode": "LOCAL_ASSISTANT"}

@app.route("/api/refresh-demo", methods=["POST"])
@login_required
def refresh_demo():
    # Small deterministic-ish drift to make the map appear active during demonstrations.
    conn=db_conn()
    ships=rows("SELECT * FROM ships")
    now=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    for s in ships:
        lat=s["lat"] + random.uniform(-0.0007,0.0007)
        lon=s["lon"] + random.uniform(-0.0007,0.0007)
        conn.execute("UPDATE ships SET lat=?,lon=?,updated_at=? WHERE mmsi=?",(lat,lon,now,s["mmsi"]))
    conn.commit()
    flash("Simulated vessel positions refreshed.", "success")
    return redirect(request.referrer or url_for("live_map"))

@app.route("/alerts")
@login_required
def alerts():
    items=rows("SELECT * FROM alerts ORDER BY id DESC LIMIT 100")
    return render_template("alerts.html", items=items)

@app.route("/alerts/<int:alert_id>/ack", methods=["POST"])
@login_required
def acknowledge_alert(alert_id):
    db_conn().execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))
    db_conn().commit()
    return redirect(url_for("alerts"))

if __name__ == "__main__":
    init_db()
    print("\nSmartMarineSafety is starting...")
    print("Demo login: admin / Marine@123")
    print("Open http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
