# Main flight simulator application entry point and execution loop.

import sys
import os
import random
import time
from ursina import *
color.rgba = color.rgba32

# Set up asset and module loading paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flight_simulator.settings import (
    WINDOW_TITLE, WINDOW_SIZE, SHOW_FPS, TARGET_FPS, VSYNC,
    AIRCRAFT_PRESETS, DB_PATH
)
from flight_simulator.database.pilot_db import init_db, log_flight, save_mission_progress
from flight_simulator.aircraft_physics import AircraftPhysics
from flight_simulator.aircraft.aircraft_models import AircraftVisual
from flight_simulator.opencv_controls import OpenCVControls
from flight_simulator.weather_system import WeatherSystem
from flight_simulator.cockpit import CockpitHUD
from flight_simulator.airport_system import AirportSystem
from flight_simulator.ai_traffic import AITrafficSystem
from flight_simulator.autopilot import AutopilotSystem
from flight_simulator.sound_manager import SoundManager
from flight_simulator.ui_manager import UIManager

class ApexFlightSim:
    def __init__(self):
        self.app = Ursina(
            title=WINDOW_TITLE,
            size=WINDOW_SIZE,
            vsync=VSYNC,
            show_ursina_logo=False,
            development_mode=False
        )
        window.fps_counter.enabled = SHOW_FPS
        
        # Initialize database
        init_db()

        # OpenCV thread-controller
        self.cv_controls = OpenCVControls()
        self.cv_controls_active = True
        self.cv_controls.start() # Start capturing webcam
        
        # Flight State variables
        self.game_state = "MENU" # MENU, FLIGHT, CRASHED, SUCCESS
        self.flight_time = 0.0
        self.active_mission = None
        self.touchdown_g = 1.0
        self.touchdown_detected = False
        
        # Environment References
        self.terrain_elements = []
        self.player_aircraft = None
        self.physics = None
        self.weather = None
        self.hud = None
        self.airports = None
        self.traffic = None
        self.autopilot = None
        self.sounds = None
        
        # Camera system: 0 = Cockpit, 1 = Chase, 2 = Wing, 3 = Landing Gear, 4 = Free Cinematic
        self.camera_view = 1
        self.camera_chase_dist = 40.0
        self.camera_chase_height = 8.0
        
        # Overlay screens (Crash/Success)
        self.overlay_parent = None
        
        # Start UI Manager
        self.ui_manager = UIManager(
            start_flight_callback=self.start_flight,
            toggle_cv_callback=self.set_cv_controls,
            exit_game_callback=self.exit_simulator
        )

    def set_cv_controls(self, active_bool):
        """Enables/disables computer vision gesture control tracking."""
        self.cv_controls_active = active_bool
        if active_bool:
            if not self.cv_controls.running:
                self.cv_controls.start()
        else:
            if self.cv_controls.running:
                self.cv_controls.stop()

    def start_flight(self, aircraft_name, weather, time_hour, mission_name=None):
        """Prepares and loads 3D entities, airports, traffic systems, and cockpit HUDs."""
        self.ui_manager.hide_menu()
        self.game_state = "FLIGHT"
        self.flight_time = 0.0
        self.active_mission = mission_name
        self.touchdown_detected = False
        self.touchdown_g = 1.0
        self.camera_view = 1 # Chase cam on takeoff
        
        # 1. Physics Engine Setup
        preset_data = AIRCRAFT_PRESETS[aircraft_name]
        self.physics = AircraftPhysics(aircraft_name, preset_data)
        
        # Adjust starting positions for specific missions
        if mission_name == "Storm ILS Landing":
            # Start player lined up with KMSP runway 09R, 7 NM out (13000m), at 1800 feet (550m)
            self.physics.position = Vec3(-12000, 500, 0)
            self.physics.velocity = Vec3(0, 0, 75) # 145 knots
            self.physics.rotation = Vec3(0, 90, 0)
            self.physics.gear_deployed = True
            self.physics.flaps = 0.5
        elif mission_name == "Engine Out Glide Challenge":
            # Start player at 5000ft (1500m) above Metro Airport, engines dead
            self.physics.position = Vec3(-4000, 1500, -3000)
            self.physics.velocity = Vec3(0, -5, 75)
            self.physics.rotation = Vec3(-3, 45, 0)
            self.physics.fuel = 0.0 # Force fuel dry!
            self.physics.gear_deployed = False
            self.physics.flaps = 0.0
        elif mission_name == "Fighter Interception (Combat)":
            # Start at high altitude in Fighter
            self.physics.position = Vec3(0, 3000, -2000)
            self.physics.velocity = Vec3(0, 0, 200) # Fast
            self.physics.rotation = Vec3(0, 0, 0)
            self.physics.gear_deployed = False
        else:
            # Free Flight or Takeoff Solo: Start parked on Runway 09 at KMSP
            self.physics.position = Vec3(-1000, 0.2, 0)
            self.physics.velocity = Vec3(0, 0, 0)
            self.physics.rotation = Vec3(0, 90, 0) # Lined up facing runway heading 90
            self.physics.gear_deployed = True
            self.physics.flaps = 0.0
            self.physics.throttle = 0.0
            self.physics.spooled_thrust = 0.0

        # 2. Weather System Setup
        self.weather = WeatherSystem()
        self.weather.set_weather(weather)
        self.weather.set_time_of_day(time_hour)

        # 3. Airport System Setup
        self.airports = AirportSystem()

        # 4. AIAircraft Traffic Setup
        self.traffic = AITrafficSystem(self.airports.get_airports())

        # 5. Autopilot System
        self.autopilot = AutopilotSystem()

        # 6. Cockpit HUD
        self.hud = CockpitHUD(self.physics)

        # 7. Dynamic Sound Engine
        self.sounds = SoundManager()

        # 8. Spawn Player 3D Plane
        self.player_aircraft = AircraftVisual(
            aircraft_type=aircraft_name,
            position=self.physics.position,
            rotation=self.physics.rotation
        )

        # 8b. Spawn 3D Cockpit Cabin parented to the plane
        from flight_simulator.cockpit import CockpitCabin
        cam_pos = Vec3(0, 1.2, 5.0) if self.physics.preset_name != "Fighter Jet" else Vec3(0, 1.0, 4.5)
        self.cockpit_cabin = CockpitCabin(parent_plane=self.player_aircraft, camera_pos=cam_pos)
        self.cockpit_cabin.enabled = (self.camera_view == 0)

        # 9. Build 3D Terrain & Obstacles
        self._build_3d_environment()

        # Adjust initial cameras
        camera.orthographic = False
        camera.fov = 65

    def _build_3d_environment(self):
        """Spawns green tiled terrain floor, city skyscrapers, and collision mountains."""
        self._clear_environment()

        # Grass Ground plane (High performance single mesh)
        ground = Entity(
            model='plane',
            scale=40000.0,
            texture='white_cube', # simple grid helper
            color=color.rgb(30, 85, 45),
            texture_scale=(400, 400),
            position=Vec3(0, -0.1, 0),
            collider='box'
        )
        self.terrain_elements.append(ground)

        # Metropolitan Skyline near Metro International (KMSP: around x=0, z=0)
        # Buildings are gray cubes of random heights with windows (colored stripes)
        for i in range(25):
            bx = random.uniform(-600, -200) if i%2==0 else random.uniform(200, 600)
            bz = random.uniform(-400, 400)
            bh = random.uniform(60, 200)
            
            building = Entity(
                model='cube',
                color=color.rgb(110, 115, 125),
                scale=Vec3(25, bh, 25),
                position=Vec3(bx, bh/2, bz),
                collider='box'
            )
            # Add window grids
            Entity(parent=building, model='quad', color=color.yellow, scale=(0.8, 0.8), position=(0, 0, 0.51), alpha=0.5)
            
            self.terrain_elements.append(building)

        # Dangerous Rocky Mountain Peaks around Mountain Outpost (KASE: x=5000, z=-6000)
        # Hit one and you crash!
        for i in range(12):
            mx = random.uniform(3800, 6200)
            mz = random.uniform(-7500, -4500)
            
            # Keep runway clear (runway at x=5000, z=-6000 heading 210)
            dist_to_runway = math.sqrt((mx - 5000)**2 + (mz - (-6000))**2)
            if dist_to_runway < 800.0:
                continue # don't spawn mountain directly on runway
                
            mh = random.uniform(800, 1600)
            mountain = Entity(
                model='cone',
                color=color.rgb(90, 85, 80),
                scale=Vec3(600, mh, 600),
                position=Vec3(mx, mh/2 - 100, mz),
                collider='mesh'
            )
            # Snow peak
            Entity(
                parent=mountain,
                model='cone',
                color=color.white,
                scale=Vec3(1.0, 0.2, 1.0),
                position=Vec3(0, 0.4, 0)
            )
            self.terrain_elements.append(mountain)

    def _clear_environment(self):
        """Cleans up terrain, buildings, and mountain entities from scene."""
        for elem in self.terrain_elements:
            destroy(elem)
        self.terrain_elements.clear()

    def stop_flight(self):
        """Unloads flight system modules, stops audio channels, and launches UIManager."""
        self.game_state = "MENU"
        
        # Stop sound manager
        if self.sounds:
            self.sounds.stop_all()
            self.sounds = None

        # Clean HUD
        if self.hud:
            self.hud.destroy()
            self.hud = None

        # Clean Cockpit Cabin
        if hasattr(self, 'cockpit_cabin') and self.cockpit_cabin:
            destroy(self.cockpit_cabin)
            self.cockpit_cabin = None

        # Clean Airports
        if self.airports:
            self.airports.destroy()
            self.airports = None

        # Clean AI traffic
        if self.traffic:
            self.traffic.destroy()
            self.traffic = None

        # Clean Player Plane Visual
        if self.player_aircraft:
            self.player_aircraft.destroy_mesh()
            self.player_aircraft = None

        self._clear_environment()
        self._destroy_overlay()
        
        # Reset camera
        camera.parent = scene
        camera.position = Vec3(0, 0, 0)
        camera.rotation = Vec3(0, 0, 0)

        # Relaunch menu
        self.ui_manager.show_main_menu()

    def set_camera_mode(self, view_mode):
        """Cycles cameras: Cockpit, Chase, Wing, Landing Gear, Free."""
        self.camera_view = view_mode
        print(f"[Camera System] Camera view changed: {view_mode}")
        if hasattr(self, 'cockpit_cabin') and self.cockpit_cabin:
            self.cockpit_cabin.enabled = (view_mode == 0)

    def trigger_crash(self):
        """Launches player crash screens, plays explosions, and logs to db."""
        if self.game_state == "CRASHED":
            return
            
        self.game_state = "CRASHED"
        print("[Flight Sim] CRASH ENCOUNTERED! Struct failure.")
        
        # Play explosion sound (simulate or print)
        if self.sounds:
            self.sounds.stop_all()
            
        # Log flight to DB
        try:
            log_flight(
                aircraft=self.physics.preset_name,
                start_airport="KMSP" if self.active_mission != "Storm ILS Landing" else "Air Start",
                end_airport="Crash Site",
                duration_sec=self.flight_time,
                landing_status="Crashed",
                landing_g_force=0.0,
                mission_name=self.active_mission
            )
        except Exception as e:
            print(f"[DB Log Error] Failed to log flight: {e}")

        # Shake camera
        camera.shake(duration=1.5, magnitude=10.0)

        # Build Red Crash overlay Screen
        self.overlay_parent = Entity(parent=camera.ui)
        Entity(parent=self.overlay_parent, model='quad', color=color.rgba(200, 0, 0, 180), scale=(1.5, 1.0), z=-1)
        Text(parent=self.overlay_parent, text="AIRCRAFT CRASH DETECTED", scale=2.5, color=color.white, position=(-0.4, 0.1))
        Text(parent=self.overlay_parent, text="Structural integrity compromised. Mission failed.\nReturning to menu in 3 seconds...", scale=1.0, color=color.light_gray, position=(-0.4, -0.1))
        
        # Trigger return to menu in 3 seconds
        invoke(self.stop_flight, delay=3.0)

    def trigger_success(self, rating_stars):
        """Launches mission success overlay screen and logs to database."""
        if self.game_state == "SUCCESS":
            return
            
        self.game_state = "SUCCESS"
        print("[Flight Sim] MISSION COMPLETED SUCCESSFULLY!")
        
        # Log to DB
        try:
            xp = log_flight(
                aircraft=self.physics.preset_name,
                start_airport="Air Start" if self.active_mission == "Storm ILS Landing" else "KMSP",
                end_airport="KMSP" if self.active_mission == "Engine Out Glide Challenge" else "KASE",
                duration_sec=self.flight_time,
                landing_status="Landed Safely",
                landing_g_force=self.touchdown_g,
                mission_name=self.active_mission
            )
            
            if self.active_mission:
                save_mission_progress(self.active_mission, stars=rating_stars, high_score=int(xp))
        except Exception as e:
            print(f"[DB Log Error] Failed to log flight success: {e}")

        # Build Success Screen
        self.overlay_parent = Entity(parent=camera.ui)
        Entity(parent=self.overlay_parent, model='quad', color=color.rgba(0, 150, 100, 220), scale=(1.5, 1.0), z=-1)
        Text(parent=self.overlay_parent, text="MISSION SUCCESSFUL!", scale=2.5, color=color.white, position=(-0.35, 0.15))
        Text(parent=self.overlay_parent, text=f"Smooth landing rating: {rating_stars} Stars\nTouchdown G-Force: {self.touchdown_g:.2f} Gs\nXP Gained. Returning to hangar...", scale=1.1, color=color.light_gray, position=(-0.35, -0.05))
        
        invoke(self.stop_flight, delay=4.0)

    def _destroy_overlay(self):
        if self.overlay_parent:
            destroy(self.overlay_parent)
            self.overlay_parent = None

    def exit_simulator(self):
        """Releases OpenCV and shuts down application."""
        self.cv_controls.stop()
        sys.exit()

    def update_flight_loop(self, dt):
        """Core flight updates: inputs, autopilot, physics, animations, cameras, sound mixer, mission checks."""
        self.flight_time += dt
        
        # --- 1. COLLECT PILOT CONTROL INPUTS ---
        # Default control structure
        inputs = {
            "pitch": 0.0,
            "roll": 0.0,
            "yaw": 0.0,
            "throttle": self.physics.throttle,
            "flaps": self.physics.flaps,
            "gear": self.physics.gear_deployed,
            "brakes": False
        }

        # Keyboard Toggles (always active as override/backup)
        # Pitch: nose down (W) vs nose up (S)
        if held_keys['w']: inputs["pitch"] = 0.8
        elif held_keys['s']: inputs["pitch"] = -0.8
        
        # Roll: roll left (A) vs roll right (D)
        if held_keys['a']: inputs["roll"] = -0.8
        elif held_keys['d']: inputs["roll"] = 0.8
        
        # Yaw: rudder left (Q) vs rudder right (E)
        if held_keys['q']: inputs["yaw"] = -0.5
        elif held_keys['e']: inputs["yaw"] = 0.5
        
        # Throttle: increase (shift) vs decrease (ctrl)
        if held_keys['left shift'] or held_keys['right shift']:
            inputs["throttle"] = min(1.0, self.physics.throttle + 0.15 * dt)
        elif held_keys['left control'] or held_keys['right control']:
            inputs["throttle"] = max(0.0, self.physics.throttle - 0.15 * dt)
            
        # Flaps: tap F to cycle
        # We handle toggling on key_up or key_down to prevent spamming. 
        # (See input() function below)
        
        # Brakes
        if held_keys['space']:
            inputs["brakes"] = True

        # Hook OpenCV inputs if active
        cv = self.cv_controls.get_inputs()
        if self.cv_controls_active and cv.get("active", False):
            # Smoothly blend CV inputs to avoid jerky motion
            inputs["pitch"] = cv["pitch"]
            inputs["roll"] = cv["roll"]
            inputs["yaw"] = cv["yaw"]
            inputs["throttle"] = cv["throttle"]
            inputs["flaps"] = cv["flaps"]
            inputs["gear"] = cv["gear"]
            inputs["brakes"] = cv["brakes"]

        # --- 2. RUN AUTOPILOT IF ACTIVE ---
        # Find nearest airport runway for autopilot ILS guidance
        target_wp = None
        airports_list = self.airports.get_airports()
        
        # Set target runway waypoint (e.g. Metro Airport Runway 09R)
        if self.active_mission == "Storm ILS Landing":
            target_wp = airports_list[0]["runway"]
        else:
            # default to KASE runway in cargo deliver, or KMSP
            target_wp = airports_list[1]["runway"] if self.physics.position.x < 3000 else airports_list[0]["runway"]

        ap_overrides = self.autopilot.update(dt, self.physics, target_wp)
        
        if ap_overrides:
            # Autopilot overrides control surfaces
            inputs = ap_overrides
            # Update HUD status
            self.hud.set_autopilot_text(self.autopilot.mode)
        else:
            self.hud.set_autopilot_text("MANUAL")

        # --- 3. RUN environmental winds & turbulence ---
        wind = self.weather.get_wind_vector()
        turbulence = self.weather.get_turbulence_offset(dt, self.physics.position)

        # --- 4. STEP PHYSICS ENGINE ---
        self.physics.update(dt, inputs, wind, turbulence)

        # Check for crashes
        if self.physics.crashed:
            self.trigger_crash()
            return

        # Check Touchdowns (when wheel hits runway)
        if self.physics.on_ground and not self.touchdown_detected and self.physics.airspeed_knots > 40:
            self.touchdown_detected = True
            self.touchdown_g = self.physics.g_force
            print(f"[Flight Sim] Touchdown detected! Landing G-Force: {self.touchdown_g:.2f} Gs")

        # --- 5. ANIMATE PLAYER 3D MODEL ---
        self.player_aircraft.position = self.physics.position
        self.player_aircraft.rotation = self.physics.rotation
        
        # Turbine whine & control surfaces
        self.player_aircraft.animate(
            dt=dt,
            controls=inputs,
            thrust_ratio=self.physics.throttle,
            spooled_thrust=self.physics.spooled_thrust,
            time=self.flight_time
        )
        # Update yoke animations in 3D cabin
        if hasattr(self, 'cockpit_cabin') and self.cockpit_cabin and self.cockpit_cabin.enabled:
            self.cockpit_cabin.update_controls(inputs["pitch"], inputs["roll"])
        # --- 6. DRIVE CAMERA SYSTEM ---
        self._update_camera_tracking(cv)

        # --- 7. STEP OTHER SIMULATOR MODULES ---
        # Update Weather particles/skies
        self.weather.update(dt, self.physics.position)
        
        # Update Airport gates
        self.airports.update(dt, self.physics)
        
        # Update AI Traffic
        self.traffic.update(dt, self.physics, self.airports.log_atc_message)
        
        # Update Cockpit HUD display tapes and needles
        self.hud.update_hud(dt, self.traffic.traffic, airports_list, target_wp)
        
        # Update Sound volumes/whines
        # alarm if low altitude pull up warning
        pull_up = (self.physics.position.y < 60.0 and self.physics.vertical_speed_fpm < -800 and not self.physics.on_ground)
        self.sounds.update(
            dt=dt, 
            airspeed_knots=self.physics.airspeed_knots, 
            spooled_thrust_ratio=self.physics.spooled_thrust / self.physics.max_thrust, 
            stalled=self.physics.stalled, 
            pull_up_warn=pull_up
        )

        # --- 8. EVALUATE MISSION CHALLENGE TARGETS ---
        self._evaluate_mission_objectives()

    def _update_camera_tracking(self, cv_inputs):
        """Positions camera based on selected view mode (Cockpit with Face Headtracking, Chase, Wing)."""
        if not self.player_aircraft:
            return
            
        plane = self.player_aircraft
        
        if self.camera_view == 0:  # COCKPIT VIEW (1st person inside nose)
            camera.parent = plane
            # Positioned inside nose cabin (forward/up)
            camera.position = Vec3(0, 1.2, 5.0) if self.physics.preset_name != "Fighter Jet" else Vec3(0, 1.0, 4.5)
            
            # Setup Head Tracking looking direction from OpenCV face landmarks
            if self.cv_controls_active and cv_inputs.get("face_detected", False):
                camera.rotation_y = cv_inputs["head_yaw"]
                camera.rotation_x = cv_inputs["head_pitch"]
            else:
                camera.rotation = Vec3(0, 0, 0) # align forward
                
        elif self.camera_view == 1:  # CHASE VIEW (3rd person)
            camera.parent = scene
            # Smooth camera tracking behind plane
            rad_yaw = math.radians(plane.rotation_y)
            rad_pitch = math.radians(plane.rotation_x)
            
            # Calculate ideal position behind plane
            back_dir = Vec3(-math.sin(rad_yaw), math.sin(rad_pitch), -math.cos(rad_yaw)).normalized()
            ideal_pos = plane.position + back_dir * self.camera_chase_dist + Vec3(0, self.camera_chase_height, 0)
            
            # Smooth interpolation
            camera.position = lerp(camera.position, ideal_pos, 0.15)
            camera.look_at(plane.position + plane.forward * 10.0)

        elif self.camera_view == 2:  # WING VIEW (Passenger wing window)
            camera.parent = plane
            camera.position = Vec3(-10.0, 1.0, -1.0)
            camera.rotation = Vec3(10, 45, 0) # looking at nose/engine

        elif self.camera_view == 3:  # LANDING GEAR CAM (looking down at struts)
            camera.parent = plane
            camera.position = Vec3(0, -2.5, 2.0)
            camera.rotation = Vec3(20, 0, 0) # looking down/back

        elif self.camera_view == 4:  # FREE CINEMATIC CAMERA (orbits plane)
            camera.parent = scene
            angle = self.flight_time * 0.4
            camera.position = plane.position + Vec3(math.sin(angle)*65, 10, math.cos(angle)*65)
            camera.look_at(plane)

    def _evaluate_mission_objectives(self):
        """Checks if current mission objectives are completed successfully."""
        if not self.active_mission or self.game_state != "FLIGHT":
            return
            
        alt_ft = self.physics.position.y * 3.28084
        speed = self.physics.airspeed_knots
        
        if self.active_mission == "First Solo Takeoff":
            # Target: climb to 2000 feet, speed > 130 knots, flying steady
            if alt_ft >= 2000.0 and speed > 130.0 and abs(self.physics.vertical_speed_fpm) < 400:
                # Successfully taken off!
                self.trigger_success(rating_stars=5)
                
        elif self.active_mission == "Storm ILS Landing":
            # Target: Land at KMSP runway 09R touchdown zone safely
            # touchdown point is KMSP runway center at Vec3(0, 0.1, 0)
            dist_to_touchdown = (self.physics.position - Vec3(0, 0, 0)).length()
            
            if self.physics.on_ground and speed < 2.0:
                if dist_to_touchdown < 1800.0:  # Landed on runway
                    # rate stars based on landing G-force
                    stars = 5
                    if self.touchdown_g > 2.5: stars = 2
                    elif self.touchdown_g > 1.8: stars = 3
                    elif self.touchdown_g > 1.3: stars = 4
                    
                    self.trigger_success(rating_stars=stars)
                else:
                    # Missed runway landing
                    print("[Mission Fail] Missed runway landing zone.")
                    self.trigger_crash()

        elif self.active_mission == "Engine Out Glide Challenge":
            # Target: glide and land at runway KMSP
            dist_to_touchdown = (self.physics.position - Vec3(0, 0, 0)).length()
            if self.physics.on_ground and speed < 2.0:
                if dist_to_touchdown < 1800.0:
                    self.trigger_success(rating_stars=5)
                else:
                    self.trigger_crash()

        elif self.active_mission == "Fighter Interception (Combat)":
            # Target: survive 60 seconds flying fighter jet at speed
            if self.flight_time >= 60.0:
                self.trigger_success(rating_stars=5)

    def input(self, key):
        """Binds global UI clicks and escape pauses."""
        if self.game_state == "FLIGHT":
            # Flaps: cycle flaps
            if key == 'f':
                # Flaps state: 0.0 -> 0.5 -> 1.0 -> 0.0
                if self.physics.flaps == 0.0:
                    self.physics.flaps = 0.5
                    print("[Pilot Input] Flaps set to Mid (15 deg)")
                elif self.physics.flaps == 0.5:
                    self.physics.flaps = 1.0
                    print("[Pilot Input] Flaps set to Full (30 deg)")
                else:
                    self.physics.flaps = 0.0
                    print("[Pilot Input] Flaps Retracted (0 deg)")
                    
            # Landing gear
            elif key == 'g':
                self.physics.gear_deployed = not self.physics.gear_deployed
                if self.sounds:
                    self.sounds.play_gear_sound()
                print(f"[Pilot Input] Landing Gear: {'Deploying' if self.physics.gear_deployed else 'Retracting'}")
                
            # Camera cycle
            elif key == 'v':
                self.camera_view = (self.camera_view + 1) % 5
                self.set_camera_mode(self.camera_view)
                
            # Autopilot Toggles
            elif key == 'x': # Toggle Altitude Hold
                if self.autopilot.mode == "ALT_HOLD":
                    self.autopilot.engage_mode("MANUAL")
                else:
                    self.autopilot.engage_mode("ALT_HOLD", self.physics)
            elif key == 'c': # Toggle Waypoint navigation
                if self.autopilot.mode == "WAYPOINT":
                    self.autopilot.engage_mode("MANUAL")
                else:
                    self.autopilot.engage_mode("WAYPOINT", self.physics)
            elif key == 'z': # Engage Auto takeoff
                self.autopilot.engage_mode("AUTO_TAKEOFF", self.physics)
            elif key == 'l': # Engage Auto land
                self.autopilot.engage_mode("AUTO_LAND", self.physics)
                
            # Return to menu
            elif key == 'escape':
                print("[Flight Sim] Escaped flight. Logging as Aborted.")
                try:
                    log_flight(
                        aircraft=self.physics.preset_name,
                        start_airport="Local Flight",
                        end_airport="Aborted",
                        duration_sec=self.flight_time,
                        landing_status="Aborted",
                        landing_g_force=0.0
                    )
                except Exception as e:
                    pass
                self.stop_flight()

    def run(self):
        self.app.run()

    def update_sim(self):
        """Ursina engine frame update handler."""
        dt = time.dt
        
        if self.game_state == "FLIGHT":
            self.update_flight_loop(dt)

sim_instance = None

def update():
    if sim_instance:
        sim_instance.update_sim()

def input(key):
    if sim_instance:
        sim_instance.input(key)

if __name__ == "__main__":
    sim_instance = ApexFlightSim()
    sim_instance.run()
