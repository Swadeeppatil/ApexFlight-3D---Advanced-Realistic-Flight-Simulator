# AI traffic system simulating autonomous aircraft flight paths, collision avoidance, and radio calls.

import math
import random
from ursina import Entity, Vec3, color, destroy
from flight_simulator.aircraft.aircraft_models import AircraftVisual

class AIAircraft:
    def __init__(self, name, aircraft_type, airports, start_ap_idx, target_ap_idx):
        self.name = name
        self.aircraft_type = aircraft_type
        self.airports = airports
        self.current_ap = airports[start_ap_idx]
        self.target_ap = airports[target_ap_idx]
        
        # State: 'PARKED', 'TAXIOUT', 'TAKEOFF', 'CLIMB', 'CRUISE', 'DESCENT', 'APPROACH', 'LANDED', 'TAXIOIN'
        self.state = "PARKED"
        self.state_timer = random.uniform(5.0, 15.0) # stay parked initially
        
        # Position and motion (simplified flight model for performance)
        self.position = self.current_ap["gates"][0]["position"] + Vec3(0, 0.2, 0)
        self.velocity = Vec3(0,0,0)
        self.rotation = Vec3(0, self.current_ap["runway"]["heading"], 0)
        self.speed_knots = 0.0
        
        # Spawn visual model
        self.visual = AircraftVisual(
            aircraft_type=aircraft_type,
            position=self.position,
            rotation=self.rotation,
            scale=1.0 if aircraft_type == "Fighter Jet" else 0.6 # scale down for visual balance
        )
        # Custom visual scale adjustments
        if aircraft_type == "Passenger Jet":
            self.visual.scale = 0.4
        elif aircraft_type == "Cargo Transporter":
            self.visual.scale = 0.25

        # Path tracking
        self.waypoint = None
        self.flight_level = random.choice([2500, 3500, 4500]) # cruise altitude in feet
        self.gear_deployed = True
        self.flaps = 0.0
        
        # Collision avoidance state
        self.evasive_vector = Vec3(0,0,0)
        self.evasive_timer = 0.0

    def update(self, dt, airports, all_traffic, player_physics, atc_logger, elapsed_time):
        """Drives the state machine for taking off, flying, landing, taxiing, and dodging obstacles."""
        if dt <= 0:
            return
            
        self.state_timer -= dt
        
        # Determine player position for collision avoidance
        player_pos = player_physics.position
        
        # --- 1. STATE MACHINE ---
        if self.state == "PARKED":
            self.speed_knots = 0.0
            self.gear_deployed = True
            self.flaps = 0.0
            
            # Idle on gate
            if self.state_timer <= 0:
                self.state = "TAXIOUT"
                self.state_timer = 15.0 # time to taxi to runway
                atc_logger(f"ATC: '{self.name}, pushback and taxi approved to holding point.'")
                
        elif self.state == "TAXIOUT":
            # Taxi toward runway entry point (start of runway)
            rw_start = self.current_ap["runway"]["position"]
            target_heading = self.current_ap["runway"]["heading"]
            
            # Position at start of runway
            # We offset behind the touchdown zone
            offset_z = -self.current_ap["runway"].get("length", 1200)/2
            # Heading vector pointing opposite to runway heading
            rad_rw = math.radians(target_heading)
            rw_dir = Vec3(math.sin(rad_rw), 0, math.cos(rad_rw))
            
            # Holding point is behind start of runway
            holding_point = rw_start - rw_dir * 100.0
            
            dist = (holding_point - self.position).length()
            self.speed_knots = 15.0 # Taxi speed
            
            # Move toward holding point
            dir_vec = (holding_point - self.position).normalized()
            self.position += dir_vec * (self.speed_knots * 0.514) * dt
            # steer rotation
            target_rot_y = math.degrees(math.atan2(dir_vec.x, dir_vec.z)) % 360
            self.rotation.y += (target_rot_y - self.rotation.y) * 2.0 * dt
            
            if dist < 15.0 or self.state_timer <= 0:
                self.state = "TAKEOFF"
                self.position = holding_point # place on runway
                self.rotation.y = target_heading
                self.speed_knots = 0.0
                self.state_timer = 4.0 # line up wait
                atc_logger(f"ATC: '{self.name}, wind calm, Runway {int(target_heading/10):02d}, cleared for takeoff.'")

        elif self.state == "TAKEOFF":
            # Set lining up position
            rw_heading = self.current_ap["runway"]["heading"]
            rad_rw = math.radians(rw_heading)
            rw_dir = Vec3(math.sin(rad_rw), 0, math.cos(rad_rw))
            
            if self.state_timer > 0:
                # spool engines
                self.speed_knots = 0.0
            else:
                # Roll down runway, accelerate
                self.speed_knots = min(140.0, self.speed_knots + 25.0 * dt)
                self.position += rw_dir * (self.speed_knots * 0.514) * dt
                self.rotation.y = rw_heading
                
                # Rotate at 110 knots
                if self.speed_knots >= 110.0:
                    self.state = "CLIMB"
                    self.state_timer = 20.0
                    self.gear_deployed = False # retract gear
                    atc_logger(f"ATC: '{self.name}, airborne. Contact departure on 119.7.'")
                    
        elif self.state == "CLIMB":
            # Climb to flight level heading toward target airport
            target_pos = self.target_ap["position"] + Vec3(0, self.flight_level * 0.3048, 0) # feet to meters
            
            # Airspeed
            self.speed_knots = min(180.0, self.speed_knots + 10.0 * dt)
            
            # Climb vector
            dir_to_target = (target_pos - self.position).normalized()
            self.position += dir_to_target * (self.speed_knots * 0.514) * dt
            
            # Heading pitch/roll
            target_rot_y = math.degrees(math.atan2(dir_to_target.x, dir_to_target.z)) % 360
            self.rotation.y += (target_rot_y - self.rotation.y) * 1.5 * dt
            self.rotation.x = 10.0 # climb pitch
            self.rotation.z = 0.0
            self.gear_deployed = False
            
            # Climb complete when altitude > 80% flight level
            if self.position.y >= self.flight_level * 0.3048 * 0.8:
                self.state = "CRUISE"
                atc_logger(f"ATC: '{self.name}, radar contact at flight level {int(self.flight_level/100)}.'")

        elif self.state == "CRUISE":
            # Fly toward target airport at constant speed/altitude
            target_pos = self.target_ap["position"] + Vec3(0, self.flight_level * 0.3048, 0)
            
            self.speed_knots = 200.0
            self.gear_deployed = False
            
            dir_to_target = (target_pos - self.position).normalized()
            
            # Dodge other traffic (evasive vector adds offset)
            net_dir = (dir_to_target + self.evasive_vector).normalized()
            self.position += net_dir * (self.speed_knots * 0.514) * dt
            
            target_rot_y = math.degrees(math.atan2(net_dir.x, net_dir.z)) % 360
            self.rotation.y += (target_rot_y - self.rotation.y) * 1.0 * dt
            self.rotation.x = 0.0 # level
            
            # Calculate roll based on turn rate
            turn_rate = (target_rot_y - self.rotation.y)
            if turn_rate > 180: turn_rate -= 360
            elif turn_rate < -180: turn_rate += 360
            self.rotation.z = max(-20, min(turn_rate * 1.5, 20))
            
            # Descend when within 6000 meters of target
            dist_to_ap = (self.target_ap["position"] - self.position).length()
            if dist_to_ap < 6000.0:
                self.state = "DESCENT"
                atc_logger(f"ATC: '{self.name}, descend and maintain 1500 feet. Expect ILS approach runway.'")

        elif self.state == "DESCENT":
            # Descend to approach altitude (500 feet / 150 meters)
            approach_fix = self.target_ap["position"] + Vec3(0, 150, 0)
            # Offset approach fix to align with runway entry point (approx 3000m out)
            rw_heading = self.target_ap["runway"]["heading"]
            rad_rw = math.radians(rw_heading)
            rw_dir = Vec3(math.sin(rad_rw), 0, math.cos(rad_rw))
            entry_point = approach_fix - rw_dir * 3000.0
            
            self.speed_knots = max(130.0, self.speed_knots - 15.0 * dt)
            self.gear_deployed = False
            
            dir_to_fix = (entry_point - self.position).normalized()
            self.position += dir_to_fix * (self.speed_knots * 0.514) * dt
            
            target_rot_y = math.degrees(math.atan2(dir_to_fix.x, dir_to_fix.z)) % 360
            self.rotation.y += (target_rot_y - self.rotation.y) * 2.0 * dt
            self.rotation.x = -8.0 # pitch down
            self.rotation.z = 0.0
            
            dist_to_entry = (entry_point - self.position).length()
            if dist_to_entry < 250.0:
                self.state = "APPROACH"
                self.gear_deployed = True # deploy gear
                self.flaps = 1.0 # full flaps
                atc_logger(f"ATC: '{self.name}, fully established ILS approach. Cleared to land Runway {int(rw_heading/10):02d}.'")

        elif self.state == "APPROACH":
            # Track runway center line and glide down to touchdown point
            rw_touchdown = self.target_ap["runway"]["position"]
            rw_heading = self.target_ap["runway"]["heading"]
            
            self.speed_knots = 110.0
            self.gear_deployed = True
            
            # Vector down to runway
            dir_to_rw = (rw_touchdown - self.position).normalized()
            self.position += dir_to_rw * (self.speed_knots * 0.514) * dt
            
            self.rotation.y = rw_heading
            self.rotation.x = -3.0 # approach pitch
            self.rotation.z = 0.0
            
            # Touchdown when altitude <= airport elevation
            if self.position.y <= self.target_ap["position"].y + 0.5:
                self.state = "LANDED"
                self.position.y = self.target_ap["position"].y + 0.1
                self.state_timer = 10.0 # rollout time
                atc_logger(f"ATC: '{self.name}, welcome. Exit runway next taxiway contact ground.'")

        elif self.state == "LANDED":
            # Roll out down runway, decelerate
            rw_heading = self.target_ap["runway"]["heading"]
            rad_rw = math.radians(rw_heading)
            rw_dir = Vec3(math.sin(rad_rw), 0, math.cos(rad_rw))
            
            self.speed_knots = max(10.0, self.speed_knots - 30.0 * dt)
            self.position += rw_dir * (self.speed_knots * 0.514) * dt
            self.rotation.x = 0.0
            self.rotation.z = 0.0
            
            if self.state_timer <= 0 or self.speed_knots <= 15.0:
                # Taxi to gate
                self.state = "TAXIOIN"
                self.state_timer = 15.0
                
        elif self.state == "TAXIOIN":
            # Taxi from runway to gate parking
            gate_pos = self.target_ap["gates"][0]["position"] + Vec3(0, 0.2, 0)
            dist = (gate_pos - self.position).length()
            
            self.speed_knots = 12.0
            dir_to_gate = (gate_pos - self.position).normalized()
            self.position += dir_to_gate * (self.speed_knots * 0.514) * dt
            
            target_rot_y = math.degrees(math.atan2(dir_to_gate.x, dir_to_gate.z)) % 360
            self.rotation.y += (target_rot_y - self.rotation.y) * 2.0 * dt
            
            if dist < 10.0 or self.state_timer <= 0:
                # Swap airports and reset to PARKED
                self.current_ap, self.target_ap = self.target_ap, self.current_ap
                self.state = "PARKED"
                self.state_timer = random.uniform(20.0, 45.0) # wait before next flight
                atc_logger(f"ATC: '{self.name}, shut down at gate. Welcome to your destination.'")

        # --- 2. COLLISION AVOIDANCE ALGORITHM ---
        # AI checks distance to other aircraft and player
        self.evasive_timer -= dt
        if self.evasive_timer <= 0:
            self.evasive_timer = 0.5 # check twice a second
            self.evasive_vector = Vec3(0,0,0)
            
            # Check player
            to_player = player_pos - self.position
            p_dist = to_player.length()
            if p_dist < 400.0 and self.state in ["CLIMB", "CRUISE", "DESCENT"]:
                # Collision alert! Steer away sideways
                # Pitch up or steer right
                steer_right = to_player.cross(Vec3(0,1,0)).normalized()
                self.evasive_vector = -steer_right * 1.5 - Vec3(0, 0.5, 0) # dive and turn
                print(f"[Traffic Alert] AI '{self.name}' executing TCAS collision avoidance with player!")

            # Check other AI
            for other in all_traffic:
                if other == self:
                    continue
                to_other = other.position - self.position
                o_dist = to_other.length()
                if o_dist < 300.0 and self.state in ["CLIMB", "CRUISE", "DESCENT"]:
                    # steer away
                    self.evasive_vector += -to_other.normalized() * 1.2
                    
        # Apply physics movements to visual Entity
        self.visual.position = self.position
        self.visual.rotation = self.rotation
        
        # Animate flaps/gears on AI planes
        self.visual.animate(
            dt=dt,
            controls={"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "flaps": self.flaps, "gear": self.gear_deployed},
            thrust_ratio=self.speed_knots / 250.0,
            spooled_thrust=self.speed_knots * 100.0,
            time=elapsed_time
        )

    def destroy(self):
        """Removes the AI aircraft visual entity."""
        self.visual.destroy_mesh()


class AITrafficSystem:
    def __init__(self, airports):
        self.airports = airports
        self.traffic = []
        self.elapsed_time = 0.0

        # Spawning default AI planes
        self._spawn_initial_traffic()

    def _spawn_initial_traffic(self):
        """Creates AI planes mapping flight numbers and routes."""
        # Commercial airlines and fighter jets
        routes = [
            ("Apex Flight 302", "Passenger Jet", 0, 1), # KMSP to KASE
            ("Cargo Box 901", "Cargo Transporter", 1, 0), # KASE to KMSP
            ("Patriot Wing 1", "Fighter Jet", 0, 1),
            ("Executive Charter 77", "Private Business Jet", 1, 0)
        ]
        
        for name, p_type, start_idx, end_idx in routes:
            ai = AIAircraft(name, p_type, self.airports, start_idx, end_idx)
            self.traffic.append(ai)

    def update(self, dt, player_physics, atc_logger):
        """Drives the AI aircraft updates and collision matrices."""
        self.elapsed_time += dt
        
        for plane in self.traffic:
            plane.update(
                dt=dt, 
                airports=self.airports, 
                all_traffic=self.traffic, 
                player_physics=player_physics,
                atc_logger=atc_logger,
                elapsed_time=self.elapsed_time
            )

    def destroy(self):
        """Cleans up all spawned AI planes."""
        for plane in self.traffic:
            plane.destroy()
        self.traffic.clear()
