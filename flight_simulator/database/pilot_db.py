# Database utilities for logging flights, keeping pilot achievements and statistics.

import sqlite3
import datetime
from flight_simulator.settings import DB_PATH

def get_connection():
    """Returns a connection to the SQLite database, creating it if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Flight History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS flights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        aircraft TEXT,
        start_airport TEXT,
        end_airport TEXT,
        duration_sec REAL,
        landing_status TEXT, -- 'Landed Safely', 'Crashed', 'Aborted'
        landing_g_force REAL,
        mission_name TEXT
    )
    """)
    
    # Pilot Statistics table (singleton record or updated dynamically)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stats (
        key TEXT PRIMARY KEY,
        value REAL
    )
    """)
    
    # Mission Progress table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS missions (
        name TEXT PRIMARY KEY,
        stars INTEGER, -- 0 to 5
        high_score INTEGER,
        completed INTEGER -- 1 for True, 0 for False
    )
    """)
    
    # Aircraft Unlocks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS aircraft_unlocks (
        name TEXT PRIMARY KEY,
        unlocked INTEGER -- 1 for True, 0 for False
    )
    """)
    
    # Initialize some default stats if they don't exist
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_flight_hours', 0.0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_takeoffs', 0.0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_landings', 0.0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_crashes', 0.0)")
    cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('pilot_xp', 0.0)")
    
    # Default aircraft unlocks
    cursor.execute("INSERT OR IGNORE INTO aircraft_unlocks (name, unlocked) VALUES ('Passenger Jet', 1)")
    cursor.execute("INSERT OR IGNORE INTO aircraft_unlocks (name, unlocked) VALUES ('Fighter Jet', 0)")
    cursor.execute("INSERT OR IGNORE INTO aircraft_unlocks (name, unlocked) VALUES ('Cargo Transporter', 1)")
    cursor.execute("INSERT OR IGNORE INTO aircraft_unlocks (name, unlocked) VALUES ('Private Business Jet', 0)")
    
    conn.commit()
    conn.close()

def log_flight(aircraft, start_airport, end_airport, duration_sec, landing_status, landing_g_force, mission_name=None):
    """Logs a completed flight in the database and updates statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO flights (timestamp, aircraft, start_airport, end_airport, duration_sec, landing_status, landing_g_force, mission_name)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (now, aircraft, start_airport, end_airport, duration_sec, landing_status, landing_g_force, mission_name))
    
    # Update Stats
    hours = duration_sec / 3600.0
    cursor.execute("UPDATE stats SET value = value + ? WHERE key = 'total_flight_hours'", (hours,))
    cursor.execute("UPDATE stats SET value = value + 1 WHERE key = 'total_takeoffs'")
    
    xp_gained = int(duration_sec * 0.1) # 1 XP per 10 seconds of flight
    
    if landing_status == "Landed Safely":
        cursor.execute("UPDATE stats SET value = value + 1 WHERE key = 'total_landings'")
        # Extra landing XP based on G-force (smoother landing = more XP)
        g_bonus = max(0, int((3.0 - landing_g_force) * 100)) if landing_g_force else 50
        xp_gained += 150 + g_bonus
    elif landing_status == "Crashed":
        cursor.execute("UPDATE stats SET value = value + 1 WHERE key = 'total_crashes'")
        xp_gained += 10 # very minor XP for trying
        
    cursor.execute("UPDATE stats SET value = value + ? WHERE key = 'pilot_xp'", (xp_gained,))
    
    # Auto-unlock aircraft based on XP thresholds
    cursor.execute("SELECT value FROM stats WHERE key = 'pilot_xp'")
    xp = cursor.fetchone()[0]
    
    if xp >= 500: # Unlock Private Jet at 500 XP
        cursor.execute("UPDATE aircraft_unlocks SET unlocked = 1 WHERE name = 'Private Business Jet'")
    if xp >= 1500: # Unlock Fighter Jet at 1500 XP
        cursor.execute("UPDATE aircraft_unlocks SET unlocked = 1 WHERE name = 'Fighter Jet'")
        
    conn.commit()
    conn.close()
    return xp_gained

def get_stats():
    """Retrieves all pilot statistics as a dictionary."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM stats")
    rows = cursor.fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def get_unlocked_aircraft():
    """Retrieves a dict of aircraft and their unlock status."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, unlocked FROM aircraft_unlocks")
    rows = cursor.fetchall()
    conn.close()
    return {row['name']: bool(row['unlocked']) for row in rows}

def unlock_aircraft_forced(name):
    """Force unlocks an aircraft."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE aircraft_unlocks SET unlocked = 1 WHERE name = ?", (name,))
    conn.commit()
    conn.close()

def save_mission_progress(name, stars, high_score, completed=True):
    """Saves progress for a particular mission."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO missions (name, stars, high_score, completed)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(name) DO UPDATE SET
        stars = MAX(stars, excluded.stars),
        high_score = MAX(high_score, excluded.high_score),
        completed = MAX(completed, excluded.completed)
    """, (name, stars, high_score, 1 if completed else 0))
    conn.commit()
    conn.close()

def get_mission_progress():
    """Gets progress of all missions."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, stars, high_score, completed FROM missions")
    rows = cursor.fetchall()
    conn.close()
    return {row['name']: {'stars': row['stars'], 'high_score': row['high_score'], 'completed': bool(row['completed'])} for row in rows}

def get_flight_history(limit=10):
    """Retrieves the recent flight history logs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, aircraft, start_airport, end_airport, duration_sec, landing_status, landing_g_force, mission_name FROM flights ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
