# ASTRA-MED 🚀

### Astronaut Health Monitoring & Mission Control System

**Monitoring Human Health Beyond Earth.**

*A mission-control inspired desktop experience for exploring crew
wellness, simulated telemetry, intelligent anomaly screening, and
mission operations.*
:::

------------------------------------------------------------------------

## 🌌 The vision --- from my perspective

I built **ASTRA-MED** around a simple but ambitious idea: when humans
travel beyond Earth, looking after the crew should be as carefully
engineered as the spacecraft carrying them.

Space is an extraordinary environment, and mission teams need a clear
picture of the people behind every mission. ASTRA-MED brings that idea
into a single desktop application: a place where crew profiles,
vital-sign trends, mission progress, alerts, historical records, and
AI-assisted analysis come together.

This project is my exploration of how software engineering, data
analysis, interface design, and responsible AI concepts can work
together in a space-health monitoring scenario. It is designed as a
simulation and learning project---not as a real clinical system.

## ✨ What ASTRA-MED can do

  -----------------------------------------------------------------------
  Area                                What it offers
  ----------------------------------- -----------------------------------
  **Mission Overview**                A central dashboard for mission
                                      status, crew health indicators, and
                                      operational snapshots.

  **Live Astronaut Monitoring**       Continuously refreshed simulated
                                      telemetry, vital-sign tiles, ECG
                                      visualization, and pause/resume
                                      controls.

  **Vital Signs Analytics**           Time-series trends, blood-pressure
                                      and sleep views, correlations,
                                      comparisons, date filters, and
                                      chart navigation.

  **Health History**                  Searchable and paginated
                                      health-reading history,
                                      comparisons, graphs, and data
                                      exports.

  **AI Health Analysis**              Isolation Forest anomaly screening,
                                      astronaut-specific baselines,
                                      anomaly scores, explainable
                                      signals, and model retraining.

  **Alerts & Notifications**          Threshold-based and AI-related
                                      alerts, severity filters,
                                      acknowledgement actions, and
                                      notification counters.

  **Astronaut Profiles**              Crew records and profile
                                      management.

  **Mission Management**              Create and manage missions, assign
                                      crew, track dates, status, and
                                      calculated progress.

  **Medical Reports**                 Generate PDF reports with optional
                                      charts, anomaly findings, alert
                                      history, and permitted
                                      medical-history content.

  **System Settings**                 Configure the application,
                                      thresholds, monitoring behavior,
                                      users, backups, imports, and audit
                                      logs.
  -----------------------------------------------------------------------

## 🧭 A closer look at the engineering

### Simulated telemetry pipeline

ASTRA-MED generates a stream of fictional astronaut readings for ten
parameters:

-   Heart rate
-   Blood oxygen saturation (SpO₂)
-   Systolic blood pressure
-   Diastolic blood pressure
-   Body temperature
-   Respiratory rate
-   Activity
-   Sleep
-   Hydration
-   Stress

The simulator uses mean-reverting behavior, daily rhythms, activity
coupling, and occasional excursions to create data that is useful for
demonstrating monitoring and analysis workflows. An in-flight mode
incorporates selected behavior described in the project's NASA reference
module.

A background monitoring thread produces telemetry batches. The desktop
interface consumes them through a thread-safe queue, while readings are
periodically persisted to SQLite.

### AI-assisted anomaly screening

The anomaly-analysis workflow combines:

1.  **Personal baselines** calculated for each astronaut when enough
    historical readings are available.
2.  **Z-score normalization** to express readings relative to those
    baselines.
3.  **Isolation Forest** to identify unusual multivariate patterns.
4.  **An extreme-deviation rule** that flags a parameter at or beyond
    four standard deviations from its baseline.
5.  **Explainable reasons and trend analysis** to help users understand
    which measurements contributed to a flag.

The model is a statistical screening aid. An anomaly is not a diagnosis,
and a normal result is not proof of health.

### Alert behavior

The alert engine evaluates readings against configurable reference
ranges. It supports severity changes, recovery notifications, and a
cooldown period to reduce repeated alerts while a value remains in the
same state. AI-related alerts use informational severity.

### Security and permissions

The application includes two roles:

-   **Administrator:** manages users, astronauts, missions, settings,
    backups, imports, and operational data.
-   **Medical Officer:** reviews health information, acknowledges
    alerts, generates reports, edits thresholds, and accesses restricted
    medical history.

The permission model follows least-privilege principles. Passwords are
hashed using PBKDF2-HMAC-SHA256 with per-user salts (200,000
iterations), and repeated failed login attempts trigger a temporary
account lockout. Access-denial events are recorded in the application
log.

## 🛠️ Built with

  Technology             Role in the project
  ---------------------- ----------------------------------------
  Python                 Core application language
  CustomTkinter          Desktop interface and themed widgets
  SQLite                 Local relational data storage
  Pandas & NumPy         Data handling and numerical operations
  SciPy                  Statistical analysis
  Matplotlib & Seaborn   Charts and visual analytics
  Scikit-learn           Isolation Forest anomaly detection
  Joblib                 Persisting the trained model
  ReportLab              PDF report generation
  OpenPyXL               Excel export and formatting
  Pillow                 Image and asset support

## 🗂️ Project structure

``` text
Astronaut_Health_Monitoring/
│
├── main.py                    # Application entry point and page orchestration
├── config.py                  # Global configuration, ranges, roles, and paths
├── requirements.txt            # Python dependencies
├── run_tests.py               # Backend and GUI smoke-test runner
│
├── components/                # Reusable UI components
│   ├── login.py
│   ├── sidebar.py
│   ├── topbar.py
│   ├── cards.py
│   ├── charts.py
│   ├── table.py
│   └── dialogs.py
│
├── modules/                   # Application pages and workflows
│   ├── dashboard.py
│   ├── astronaut_monitoring.py
│   ├── analytics.py
│   ├── health_history.py
│   ├── ai_analysis.py
│   ├── alerts.py
│   ├── astronaut_profiles.py
│   ├── mission_management.py
│   ├── reports.py
│   └── settings.py
│
├── core/                      # Monitoring, simulation, AI, and business logic
│   ├── telemetry_simulator.py
│   ├── monitoring_engine.py
│   ├── analytics_engine.py
│   ├── anomaly_detector.py
│   ├── alert_engine.py
│   ├── authentication.py
│   └── nasa_reference.py
│
├── database/                  # SQLite schema, data access, and demo seed data
├── services/                  # PDF, export, and backup services
├── utils/                     # Helpers, validation, and logging
├── tests/                     # Backend tests and GUI smoke tests
├── assets/                    # Images, icons, and fonts
├── models/                    # Saved model artifacts
├── reports/                   # Generated reports and exports
└── backups/                   # Database backups
```

## 🚀 Getting started

### Requirements

-   Python **3.11 or newer**
-   Windows is the documented setup environment.
-   A working desktop environment with Tkinter support.

### 1. Get the project

Clone the repository or download the project files, then open a terminal
in the project directory---the folder containing `main.py`.

``` bash
git clone <your-repository-url>
cd Astronaut_Health_Monitoring
```

If you downloaded the ZIP, extract it and open a terminal in the
extracted project folder instead.

### 2. Create a virtual environment

**Windows PowerShell / Command Prompt**

``` bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux**

``` bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Launch ASTRA-MED

``` bash
python main.py
```

On first launch, the application initializes its SQLite database and,
when the database is empty, seeds fictional demo users, crew, missions,
historical readings, alerts, and medical notes. It also attempts to load
or train the anomaly-detection model.

## 🔐 Demo access

The project seeds the following demonstration accounts on first
initialization:

  Username   Initial password   Role
  ---------- ------------------ -----------------
  `admin`    `admin123`         Administrator
  `medic`    `medic123`         Medical Officer

**Important:** These are public demo credentials, not secure production
credentials. Change the password from **Settings → Account** immediately
after signing in. Do not deploy the application with the default
credentials.

## 🧪 Run the tests

Run the project's test suite from the project root:

``` bash
python run_tests.py
```

The runner executes backend unit tests and a headless GUI smoke test.
The backend tests cover areas including database behavior,
authentication, alerts, telemetry simulation, analytics, anomaly
detection, exports, PDF generation, backup/restore, and
monitoring-engine behavior.

The headless GUI smoke test checks application wiring and logic; it does
not replace testing the interface on a real desktop.

## 📦 Optional: build a Windows executable

PyInstaller can be used to package the application:

``` bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name ASTRA-MED --collect-all customtkinter main.py
```

Review the generated build and distribution folders and test the
executable on the target machine. Additional packaging configuration may
be needed for assets, model files, and other runtime resources.

## ⚠️ Important scope, data, and safety notes

-   **All telemetry in this project is simulated.** It is not collected
    from astronauts, wearable devices, spacecraft systems, or medical
    sensors.
-   ASTRA-MED is **not a medical device**. It must not be used to
    diagnose, treat, monitor, or make real-world medical decisions about
    any person.
-   Reference ranges are illustrative defaults for simulated data and
    can be configured in the application. They are not universal
    clinical thresholds.
-   AI anomaly scores and alerts are experimental statistical
    outputs---not clinical conclusions.
-   The NASA-related behavior in the simulator is informed by references
    documented in `core/nasa_reference.py`. Simulation scaling factors
    are engineering assumptions, not official NASA measurements.
-   Real sensor integration and production clinical workflows are
    outside the current project's scope.
-   The existing interface was developed in an environment where GUI
    display verification was limited. Please validate layout, scaling,
    and appearance on your own desktop setup.

## 🛰️ Project direction

ASTRA-MED is a foundation for exploring mission-health software.
Possible future directions include:

-   Connecting validated telemetry sources through a clearly defined
    sensor-integration layer.
-   Adding configurable mission-specific monitoring profiles.
-   Improving model evaluation, calibration, and explainability.
-   Expanding automated test coverage and desktop usability testing.
-   Strengthening deployment, packaging, and operational security.

These are ideas for future development, not claims about features
already implemented.

## 👨‍🚀 A note from the creator

I created ASTRA-MED to bring together several areas of technology I
enjoy exploring: Python development, desktop application architecture,
data visualization, statistical analysis, machine learning, and
thoughtful system design.

More than a dashboard, this project represents a question that inspires
me:

**How can we use software and data to help mission teams look after the
people who take humanity farther?**

Thank you for exploring ASTRA-MED. Whether you're here to study the
code, test the simulation, or build on the idea, I hope it gives you a
useful starting point.

------------------------------------------------------------------------


**ASTRA-MED**\
*Monitoring Human Health Beyond Earth.* 🌍 → 🚀
:::
