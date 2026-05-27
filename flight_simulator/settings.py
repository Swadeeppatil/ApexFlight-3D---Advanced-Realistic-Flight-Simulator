# Settings and Configurations for Flight Simulator

import os

# Base Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SAVES_DIR = os.path.join(BASE_DIR, "saves")
DATABASE_DIR = os.path.join(BASE_DIR, "database")

# Ensure folders exist
for folder in [ASSETS_DIR, SAVES_DIR, DATABASE_DIR]:
    os.makedirs(folder, exist_ok=True)

# Database
DB_PATH = os.path.join(DATABASE_DIR, "pilot_stats.db")

# Graphics & Window Settings
WINDOW_TITLE = "ApexFlight 3D - Advanced Simulator"
WINDOW_SIZE = (1280, 720)
SHOW_FPS = True
TARGET_FPS = 60
VSYNC = True

# OpenCV & MediaPipe Settings
WEBCAM_ID = 0
OPENCV_ENABLED = True
CAMERA_RESOLUTION = (640, 480)
GESTURE_SENSITIVITY = 1.5
PITCH_CALIBRATION_CENTER = 0.5  # Normalized hand height
ROLL_CALIBRATION_CENTER = 0.0   # Horizontal tilt level
WEBCAM_PREVIEW_SHOW = True

# Sound Settings
SOUND_ENABLED = True
ENGINE_VOLUME_MULTIPLIER = 0.5
AMBIENT_VOLUME_MULTIPLIER = 0.3
WARN_ALARM_VOLUME = 0.7

# Physics Constants
GRAVITY = 9.80665  # m/s^2
AIR_DENSITY_SEA_LEVEL = 1.225  # kg/m^3
FLUID_DAMPING = 0.05           # General aerodynamic drag dampening
STALL_ANGLE_DEG = 15.0         # Critical AoA in degrees
OVERSPEED_KNOTS = 350.0        # Max design speed for standard aircraft
REFUEL_RATE = 25.0             # Gallons per second
PASSENGER_BOARDING_RATE = 5    # Passengers per second

# Weather Settings
DAY_CYCLE_SPEED = 0.02         # Rotation speed of the sun/sky cycle
WIND_DIRECTIONS = {
    "None": (0.0, 0.0, 0.0),
    "Gentle Breeze": (5.0, 0.0, 2.0),
    "Heavy Crosswind": (20.0, 0.0, -15.0),
    "Storm Gale": (40.0, -5.0, -30.0)
}
TURBULENCE_FACTORS = {
    "None": 0.0,
    "Light": 0.1,
    "Moderate": 0.4,
    "Severe": 1.2
}

# Aircraft Presets
AIRCRAFT_PRESETS = {
    "Passenger Jet": {
        "mass_dry": 80000.0,       # kg
        "max_fuel": 20000.0,       # kg
        "wing_area": 120.0,        # m^2
        "max_thrust": 250000.0,    # N
        "engine_spool_rate": 0.2,  # Spool speed lag factor
        "roll_rate": 20.0,         # Max roll rate (deg/s)
        "pitch_rate": 10.0,        # Max pitch rate (deg/s)
        "yaw_rate": 5.0,           # Max yaw rate (deg/s)
        "drag_coeff_base": 0.025,  # C_D0
        "induced_drag_factor": 0.045,
        "cl_max": 1.6,             # Max lift coefficient before stall
        "flap_lift_bonus": 0.4,    # Extra C_L from full flaps
        "flap_drag_penalty": 0.03, # Extra C_D from full flaps
        "gear_drag_penalty": 0.025 # Extra C_D from deployed gear
    },
    "Fighter Jet": {
        "mass_dry": 12000.0,
        "max_fuel": 4000.0,
        "wing_area": 38.0,
        "max_thrust": 130000.0,    # Incorporates afterburner
        "engine_spool_rate": 0.6,
        "roll_rate": 120.0,        # Extremely responsive
        "pitch_rate": 45.0,
        "yaw_rate": 15.0,
        "drag_coeff_base": 0.015,
        "induced_drag_factor": 0.03,
        "cl_max": 1.3,
        "flap_lift_bonus": 0.2,
        "flap_drag_penalty": 0.015,
        "gear_drag_penalty": 0.015
    },
    "Cargo Transporter": {
        "mass_dry": 150000.0,
        "max_fuel": 60000.0,
        "wing_area": 300.0,
        "max_thrust": 450000.0,
        "engine_spool_rate": 0.1,
        "roll_rate": 12.0,
        "pitch_rate": 6.0,
        "yaw_rate": 3.0,
        "drag_coeff_base": 0.035,
        "induced_drag_factor": 0.055,
        "cl_max": 1.8,
        "flap_lift_bonus": 0.5,
        "flap_drag_penalty": 0.04,
        "gear_drag_penalty": 0.035
    },
    "Private Business Jet": {
        "mass_dry": 15000.0,
        "max_fuel": 5000.0,
        "wing_area": 45.0,
        "max_thrust": 60000.0,
        "engine_spool_rate": 0.35,
        "roll_rate": 35.0,
        "pitch_rate": 15.0,
        "yaw_rate": 8.0,
        "drag_coeff_base": 0.02,
        "induced_drag_factor": 0.035,
        "cl_max": 1.5,
        "flap_lift_bonus": 0.3,
        "flap_drag_penalty": 0.02,
        "gear_drag_penalty": 0.02
    }
}
