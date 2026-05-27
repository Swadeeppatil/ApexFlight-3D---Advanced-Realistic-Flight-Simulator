# Autopilot system for altitude hold, cruise control, auto takeoff, and ILS auto landing.

import math
from ursina import Vec3

class PIDController:
    def __init__(self, kp, ki, kd, output_min, output_max):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        
        self.integral = 0.0
        self.last_error = 0.0
        self.has_run = False

    def update(self, error, dt):
        if dt <= 0:
            return 0.0
            
        # Proportional term
        p = self.kp * error
        
        # Integral term (windup clamping)
        self.integral += error * dt
        i = self.ki * self.integral
        # Clamp integral to prevent huge spikes
        i = max(self.output_min, min(i, self.output_max))
        
        # Derivative term
        if self.has_run:
            derivative = (error - self.last_error) / dt
        else:
            derivative = 0.0
            self.has_run = True
            
        d = self.kd * derivative
        self.last_error = error
        
        # Total output
        output = p + i + d
        return max(self.output_min, min(output, self.output_max))

    def reset(self):
        self.integral = 0.0
        self.last_error = 0.0
        self.has_run = False


class AutopilotSystem:
    def __init__(self):
        self.mode = "MANUAL"  # MANUAL, ALT_HOLD, WAYPOINT, AUTO_TAKEOFF, AUTO_LAND
        
        # Target states
        self.target_altitude = 2000.0  # feet
        self.target_heading = 90.0     # degrees
        self.target_airspeed = 160.0    # knots
        
        # PID Controllers
        # Pitch PID: adjusts pitch input based on altitude error (feet)
        self.pitch_pid = PIDController(kp=0.003, ki=0.0001, kd=0.005, output_min=-0.8, output_max=0.8)
        # Roll PID: adjusts roll input based on heading error (degrees)
        self.roll_pid = PIDController(kp=0.04, ki=0.001, kd=0.05, output_min=-0.6, output_max=0.6)
        # Throttle PID: adjusts throttle input based on speed error (knots)
        self.throttle_pid = PIDController(kp=0.02, ki=0.002, kd=0.01, output_min=0.0, output_max=1.0)
        # Yaw PID (for runway alignment on ground)
        self.yaw_pid = PIDController(kp=0.08, ki=0.001, kd=0.02, output_min=-0.5, output_max=0.5)

        # Auto Takeoff Phase Tracking
        # 0 = stationary, 1 = rolling, 2 = rotation (pulling up), 3 = climbing to altitude, 4 = finished
        self.takeoff_phase = 0

    def engage_mode(self, mode, current_physics=None):
        """Engages the selected autopilot mode, resetting PIDs."""
        self.mode = mode
        self.pitch_pid.reset()
        self.roll_pid.reset()
        self.throttle_pid.reset()
        self.yaw_pid.reset()
        
        if current_physics:
            # Sync targets with current state for smooth transition
            self.target_altitude = current_physics.position.y * 3.28084
            self.target_heading = current_physics.rotation.y
            self.target_airspeed = current_physics.airspeed_knots
            
        if mode == "AUTO_TAKEOFF":
            self.takeoff_phase = 1
            self.target_airspeed = 180.0
            self.target_altitude = 2000.0
            
        print(f"[Autopilot] Mode engaged: {mode}")

    def update(self, dt, physics, target_waypoint=None):
        """
        Calculates autopilot control override inputs.
        Returns a dict of overrides: {'pitch', 'roll', 'yaw', 'throttle', 'flaps', 'gear'}
        or None if in MANUAL mode.
        """
        if self.mode == "MANUAL":
            return None
            
        # Get physics metrics
        alt_feet = physics.position.y * 3.28084
        speed_kt = physics.airspeed_knots
        heading = physics.rotation.y
        roll = physics.rotation.z

        overrides = {
            "pitch": 0.0,
            "roll": 0.0,
            "yaw": 0.0,
            "throttle": physics.throttle,
            "flaps": physics.flaps,
            "gear": physics.gear_deployed,
            "brakes": False
        }

        # --- MODE 1: AUTO TAKEOFF ---
        if self.mode == "AUTO_TAKEOFF":
            # Phase 1: Runway roll
            if self.takeoff_phase == 1:
                overrides["throttle"] = 1.0
                overrides["flaps"] = 0.5  # Takeoff flaps
                overrides["gear"] = True
                
                # Keep runway alignment (heading ~90 or whatever heading they started at)
                # Keep wings level
                hdg_error = self.target_heading - heading
                if hdg_error > 180: hdg_error -= 360
                elif hdg_error < -180: hdg_error += 360
                
                overrides["yaw"] = self.yaw_pid.update(hdg_error, dt)
                overrides["roll"] = -roll * 0.02 # keep flat
                overrides["pitch"] = 0.0 # keep nose down
                
                # Rotate at 120 knots
                if speed_kt >= 120.0:
                    self.takeoff_phase = 2
                    print("[Autopilot] V1 / Rotate! Pulling nose up.")
            
            # Phase 2: Rotation (pull up)
            elif self.takeoff_phase == 2:
                overrides["throttle"] = 1.0
                overrides["flaps"] = 0.5
                overrides["gear"] = True
                
                # Steer heading
                hdg_error = self.target_heading - heading
                if hdg_error > 180: hdg_error -= 360
                elif hdg_error < -180: hdg_error += 360
                overrides["roll"] = self.roll_pid.update(hdg_error, dt)
                
                # Pull back pitch to 12 degrees
                pitch_error = 12.0 - physics.rotation.x
                overrides["pitch"] = pitch_error * 0.05
                
                # Positive rate of climb -> retract gear
                if physics.vertical_speed_fpm > 400:
                    overrides["gear"] = False
                    self.takeoff_phase = 3
                    print("[Autopilot] Positive rate of climb. Gear Retracted.")
                    
            # Phase 3: Climb to cruise altitude
            elif self.takeoff_phase == 3:
                overrides["throttle"] = 0.85
                overrides["flaps"] = 0.0  # flaps up
                overrides["gear"] = False
                
                # Maintain climb altitude heading
                hdg_error = self.target_heading - heading
                if hdg_error > 180: hdg_error -= 360
                elif hdg_error < -180: hdg_error += 360
                overrides["roll"] = self.roll_pid.update(hdg_error, dt)
                
                # Pitch controls altitude climb rate
                alt_error = self.target_altitude - alt_feet
                overrides["pitch"] = self.pitch_pid.update(alt_error, dt)
                
                # Once reached altitude, switch to Cruise (ALT_HOLD)
                if abs(alt_error) < 100.0:
                    self.mode = "ALT_HOLD"
                    self.target_airspeed = 180.0
                    print("[Autopilot] Cruise altitude reached. Switching to Cruise (Altitude Hold).")

        # --- MODE 2: ALTITUDE & HEADING HOLD (Cruise) ---
        elif self.mode == "ALT_HOLD":
            # Throttle controls speed
            speed_error = self.target_airspeed - speed_kt
            overrides["throttle"] = self.throttle_pid.update(speed_error, dt)
            
            # Pitch controls altitude
            alt_error = self.target_altitude - alt_feet
            overrides["pitch"] = self.pitch_pid.update(alt_error, dt)
            
            # Roll controls heading
            hdg_error = self.target_heading - heading
            if hdg_error > 180: hdg_error -= 360
            elif hdg_error < -180: hdg_error += 360
            
            # Dampen roll angle (max 25 degrees roll during turn)
            target_roll = max(-25.0, min(hdg_error * 1.5, 25.0))
            roll_error = target_roll - roll
            overrides["roll"] = roll_error * 0.025
            overrides["yaw"] = hdg_error * 0.005 # assist turn with rudder

        # --- MODE 3: WAYPOINT NAVIGATION ---
        elif self.mode == "WAYPOINT":
            if not target_waypoint:
                self.mode = "ALT_HOLD"
                return overrides
                
            # Determine heading to waypoint
            wp_pos = target_waypoint["position"]
            relative_vec = wp_pos - physics.position
            
            # Heading target in degrees
            target_hdg = math.degrees(math.atan2(relative_vec.x, relative_vec.z)) % 360
            self.target_heading = target_hdg
            
            # Target altitude (waypoint height or default)
            target_alt_ft = wp_pos.y * 3.28084
            # Keep minimum altitude
            self.target_altitude = max(1000.0, target_alt_ft)
            
            # Standard speed
            self.target_airspeed = 200.0
            
            # Run same control loop as Cruise
            speed_error = self.target_airspeed - speed_kt
            overrides["throttle"] = self.throttle_pid.update(speed_error, dt)
            
            alt_error = self.target_altitude - alt_feet
            overrides["pitch"] = self.pitch_pid.update(alt_error, dt)
            
            hdg_error = self.target_heading - heading
            if hdg_error > 180: hdg_error -= 360
            elif hdg_error < -180: hdg_error += 360
            
            target_roll = max(-25.0, min(hdg_error * 1.5, 25.0))
            roll_error = target_roll - roll
            overrides["roll"] = roll_error * 0.025
            overrides["yaw"] = hdg_error * 0.005

        # --- MODE 4: AUTO LAND (ILS Glideslope & Localizer Alignment) ---
        elif self.mode == "AUTO_LAND":
            if not target_waypoint or "Runway" not in target_waypoint.get("name", ""):
                # Can't autoland without runway waypoint
                self.mode = "ALT_HOLD"
                return overrides
                
            rw_pos = target_waypoint["position"]
            rw_heading = target_waypoint.get("heading", 0.0)
            
            # Horizontal distance to runway
            horiz_dist = math.sqrt((rw_pos.x - physics.position.x)**2 + (rw_pos.z - physics.position.z)**2)
            
            # 1. Glideslope (Pitch & Throttle Control)
            # Standard ILS glideslope is 3 degrees. Target altitude = horiz_dist * tan(3)
            # tan(3 deg) ~ 0.0524
            target_alt = rw_pos.y + horiz_dist * 0.0524
            target_alt_ft = target_alt * 3.28084
            
            # Decelerate as we get closer
            if horiz_dist > 5000:
                self.target_airspeed = 150.0
                overrides["flaps"] = 0.5
                overrides["gear"] = False
            elif horiz_dist > 2000:
                self.target_airspeed = 135.0
                overrides["flaps"] = 1.0 # flaps full
                overrides["gear"] = True # deploy gear
            else:
                self.target_airspeed = 125.0 # landing reference speed
                overrides["flaps"] = 1.0
                overrides["gear"] = True
                
            # Flare phase (altitude < 50 feet)
            is_flare = (alt_feet - rw_pos.y * 3.28084) < 45.0
            
            if is_flare:
                # Flare pitch: pull nose up gently to 4.5 degrees
                pitch_error = 4.5 - physics.rotation.x
                overrides["pitch"] = pitch_error * 0.05
                overrides["throttle"] = 0.0 # cut engine power
                
                # Keep wings level during touchdown
                overrides["roll"] = -roll * 0.03
                
                # Check if we landed
                if physics.on_ground:
                    overrides["brakes"] = True  # Hold brakes
                    # Center down runway
                    hdg_error = rw_heading - heading
                    if hdg_error > 180: hdg_error -= 360
                    elif hdg_error < -180: hdg_error += 360
                    overrides["yaw"] = self.yaw_pid.update(hdg_error, dt)
                    
                    if speed_kt < 2.0:
                        self.mode = "MANUAL"
                        print("[Autopilot] Auto-landing complete. Welcome to your destination!")
            else:
                # Standard ILS approach pitch
                alt_error = target_alt_ft - alt_feet
                overrides["pitch"] = self.pitch_pid.update(alt_error, dt)
                
                # Throttle maintains target landing speed
                speed_error = self.target_airspeed - speed_kt
                overrides["throttle"] = self.throttle_pid.update(speed_error, dt)
                
                # 2. Localizer (Roll / Runway alignment Control)
                # Align with runway heading
                hdg_error = rw_heading - heading
                if hdg_error > 180: hdg_error -= 360
                elif hdg_error < -180: hdg_error += 360
                
                # Calculate lateral offset from center line to guide back to localizer
                # Vector from runway center pointing along runway heading
                rad_rw = math.radians(rw_heading)
                rw_dir = Vec3(math.sin(rad_rw), 0, math.cos(rad_rw))
                
                # Vector from runway to player
                rw_to_p = physics.position - rw_pos
                rw_to_p.y = 0
                
                # Cross product or projection to find lateral deviation (right is positive)
                lateral_deviation = rw_to_p.cross(rw_dir).y # vertical cross magnitude
                
                # Correct heading: steer into center line
                # 10m deviation -> correct heading by 4 degrees
                correction_hdg = max(-15.0, min(lateral_deviation * 0.12, 15.0))
                target_hdg = (rw_heading - correction_hdg) % 360
                
                hdg_error = target_hdg - heading
                if hdg_error > 180: hdg_error -= 360
                elif hdg_error < -180: hdg_error += 360
                
                target_roll = max(-20.0, min(hdg_error * 1.5, 20.0))
                roll_error = target_roll - roll
                overrides["roll"] = roll_error * 0.035
                overrides["yaw"] = hdg_error * 0.005
                
        return overrides
