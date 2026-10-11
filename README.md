# SmartMarineSafety (No YOLO)

A runnable Flask + SQLite maritime operations interface. It includes:
- Demo login and session-based access
- Interactive Chennai coastal map with an automatically moving local vessel simulation
- Tamil/English local operations assistant (no chatbot API key required)
- Proximity-based demo collision-risk indicators
- 24-hour generated weather/wave scenario outlook
- SOS log, local communications log, maintenance tracker and harbour movement schedule
- SQLite database created automatically on first run

## Requirements
- Python 3.10 or newer
- VS Code (recommended)

## Run in VS Code

### 1. Open the project
Extract the ZIP and open the `SmartMarineSafety` folder in VS Code.

### 2. Create a virtual environment
Windows PowerShell terminal:
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If PowerShell blocks activation, use Command Prompt:
```bat
.venv\Scripts\activate.bat
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install packages
```bash
python -m pip install -r requirements.txt
```

### 4. Start the app
```bash
python app.py
```
Open this address in your browser:
`http://127.0.0.1:5000`

### 5. Demo login
- Username: `admin`
- Password: `Marine@123`

The database file `smartmaritime.db` is generated automatically. To reset the initial vessel and schedule records, stop the app and delete that database file, then run `python app.py` again.

## Important demo limitations
- The moving vessel tracks are **locally simulated**, not live AIS/GPS. No vessel tracking API is connected.
- The weather/wave view is a locally generated scenario, not an observed reading or forecast. No weather or buoy API is connected.
- The Tamil/English assistant answers a small set of operations questions from local app data. It is not a cloud AI/LLM and cannot provide live maritime intelligence.
- Harbour movements are locally entered schedules. No port authority connection is configured.
- Map tiles and the optional nautical overlay are loaded from OpenStreetMap/OpenSeaMap, so the basemap needs an internet connection; no API key is required.
- Collision alerts are a basic distance threshold demonstration. They do not calculate certified CPA/TCPA and must not be used for real navigation or safety decisions.
- SOS and communication only create local database records. They do not contact rescue services, VHF radio, satellites, or nearby vessels.
- Demo password is stored plainly for simplicity in this learning project. Before deployment, replace it with password hashing, CSRF protection, secure configuration, role-based permissions, HTTPS, logging, and security review.
- Never rely on this demo in an actual maritime emergency.

## Suggested next upgrades
1. Add password hashing and administrator-managed verified users.
2. Integrate a licensed AIS provider and validate data quality.
3. Integrate a marine weather/wave API.
4. Implement CPA/TCPA calculations and test them against expert-reviewed scenarios.
5. Add real notification delivery and audit logs.
