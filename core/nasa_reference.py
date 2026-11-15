"""NASA-sourced reference material used by ASTRA-MED.

Only items actually published by/about NASA are listed here, with citations.
Anything that is an engineering assumption is labelled ASSUMPTION and is NOT NASA data.
"""

SOURCES = [
    {"id": "EDOMP",
     "title": "Extended Duration Orbiter Medical Project: cardiovascular descriptive studies "
              "(DSO 463/602)",
     "publisher": "NASA Technical Reports Server (NTRS 20040201532)",
     "url": "https://ntrs.nasa.gov/citations/20040201532"},
    {"id": "STS-50",
     "title": "EDOMP variability of blood pressure and heart rate (STS-50/USML-1), 14 astronauts",
     "publisher": "NASA Technical Reports Server (NTRS 19950007809)",
     "url": "https://ntrs.nasa.gov/citations/19950007809"},
    {"id": "SSM",
     "title": "Spaceflight Standard Measures (actigraphy, HR/BP, biochemistry)",
     "publisher": "NASA Human Research Program (NTRS 20180002943)",
     "url": "https://ntrs.nasa.gov/citations/20180002943"},
    {"id": "MERCURY",
     "title": "Physiological responses of Mercury astronauts (pre/post-flight table)",
     "publisher": "Published paper summarizing NASA Mercury flights (PMC5849611)",
     "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5849611"},
    {"id": "OSDR",
     "title": "NASA Open Science Data Repository (Inspiration4 clinical/omics data)",
     "publisher": "NASA Ames / OSDR",
     "url": "https://osdr.nasa.gov"},
]

# Documented qualitative findings (EDOMP, NTRS 20040201532)
NASA_FINDINGS = [
    "In-flight heart rate and diastolic pressure, and their variability, were reduced.",
    "Diurnal (24 h) variation of heart rate and diastolic pressure was reduced in flight.",
    "Spaceflight did not increase dysrhythmias in 24 h Holter monitoring.",
    "Measures collected by NASA Standard Measures include HR, BP, actigraphy/sleep, biochemistry.",
]

# Mercury flights, pre/post-flight (source table uses deg F; converted to deg C here)
# (flight, temp_pre_F, temp_post_F, hr_pre_bpm, hr_post_bpm)
_MERCURY_RAW = [
    ("MR-3", 99.0, 100.2, 68, 76),
    ("MR-4", 97.8, 100.4, 68, 90),
    ("MA-6", 98.2, 99.2, 68, 76),
    ("MA-7", 97.2, 97.6, 60, 78),
    ("MA-8", 97.6, 99.4, 72, 92),
    ("MA-9", 97.4, 99.4, 76, 86),
]


def _c(f):
    return round((f - 32) * 5 / 9, 2)


MERCURY_DATA = [
    {"flight": f, "temp_pre_c": _c(tp), "temp_post_c": _c(tq),
     "hr_pre": hp, "hr_post": hq, "hr_change": hq - hp}
    for f, tp, tq, hp, hq in _MERCURY_RAW
]

# ASSUMPTIONS (not NASA numbers). NASA reports the direction (reduced), not these factors.
# Tunable in Settings in a later phase.
IN_FLIGHT_VARIABILITY_FACTOR = 0.75   # scales HR/diastolic random variability
IN_FLIGHT_DIURNAL_FACTOR = 0.5        # scales the 24 h swing amplitude
GROUND_DIURNAL_AMPLITUDE = {"heart_rate": 6.0, "diastolic": 4.0}  # bpm / mmHg, ASSUMPTION
