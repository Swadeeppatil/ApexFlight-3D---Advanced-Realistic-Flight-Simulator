# Airport visual generation, gates, refueling triggers, passenger boarding, and tower communications.

import math
import random
from ursina import Entity, Vec3, color, destroy, Text, camera
from flight_simulator.settings import REFUEL_RATE, PASSENGER_BOARDING_RATE

from flight_simulator.airports.airport_data import AIRPORTS_DATA

class AirportSystem:
    def __init__(self):
        self.airports = []
        self.visual_entities = []
        self.refuel_active = False
        self.boarding_active = False
        
        # Boarding stats
        self.passengers_boarded = 0
        self.passengers_target = 150
        
        # ATC Chat history
        self.atc_chatter = []
        self.atc_timer = 0.0
        self.next_atc_chatter_in = 3.0
        
        # On-screen ATC log
        self.atc_ui_log = []
        self.atc_parent_ui = Entity(parent=camera.ui)
        
        self._generate_airports()

    def get_airports(self):
        """Returns airport definitions."""
        # Convert local gate positions to global positions
        output = []
        for ap in AIRPORTS_DATA:
            global_gates = []
            for g in ap["gates"]:
                global_gates.append({
                    "name": g["name"],
                    "position": ap["position"] + g["position"]
                })
            
            runway_data = ap["runways"][0]
            global_runway = {
                "name": runway_data["name"],
                "heading": runway_data["heading"],
                "position": ap["position"] + runway_data["offset"]
            }
            
            output.append({
                "name": ap["name"],
                "icao": ap["icao"],
                "position": ap["position"],
                "runway": global_runway,
                "gates": global_gates
            })
        return output

    def _generate_airports(self):
        """Spawns 3D models and lighting for runways, towers, and terminal structures."""
        for ap in AIRPORTS_DATA:
            ap_pos = ap["position"]
            
            # --- 1. Spawning Runways ---
            for rw in ap["runways"]:
                rw_pos = ap_pos + rw["offset"]
                heading = rw["heading"]
                length = rw["length"]
                width = rw["width"]
                
                # Asphalt runway mesh
                runway_entity = Entity(
                    model='cube',
                    color=color.rgb(40, 40, 42),
                    scale=Vec3(width, 0.2, length),
                    position=rw_pos,
                    rotation_y=heading,
                    collider='box'
                )
                self.visual_entities.append(runway_entity)
                
                # Runway center stripes
                # Draw lines every 80m
                num_stripes = int(length / 80)
                for i in range(num_stripes):
                    offset_z = (i - num_stripes/2) * 80.0
                    stripe_pos = rw_pos + Vec3(
                        offset_z * math.sin(math.radians(heading)),
                        0.12,
                        offset_z * math.cos(math.radians(heading))
                    )
                    
                    stripe = Entity(
                        model='quad',
                        color=color.white,
                        scale=(2.0, 8.0), # Width, length of stripe
                        position=stripe_pos,
                        rotation_x=90,
                        rotation_y=heading
                    )
                    self.visual_entities.append(stripe)

                # --- 2. Spawning Runway Lighting ---
                # White edge lights, red ends, green starts
                num_edge_lights = int(length / 50)
                for i in range(num_edge_lights + 1):
                    offset_z = (i - num_edge_lights/2) * 50.0
                    
                    # Left edge
                    left_pos = rw_pos + Vec3(
                        -width/2 * math.cos(math.radians(heading)) + offset_z * math.sin(math.radians(heading)),
                        0.25,
                        width/2 * math.sin(math.radians(heading)) + offset_z * math.cos(math.radians(heading))
                    )
                    # Right edge
                    right_pos = rw_pos + Vec3(
                        width/2 * math.cos(math.radians(heading)) + offset_z * math.sin(math.radians(heading)),
                        0.25,
                        -width/2 * math.sin(math.radians(heading)) + offset_z * math.cos(math.radians(heading))
                    )
                    
                    # Spawn lights
                    for pos in [left_pos, right_pos]:
                        col = color.white
                        # Check start/end for color changes (red end, green start)
                        if i == 0:
                            col = color.green
                        elif i == num_edge_lights:
                            col = color.red
                            
                        light = Entity(
                            model='sphere',
                            color=col,
                            scale=0.8,
                            position=pos,
                            emissive=True
                        )
                        self.visual_entities.append(light)

                # PAPI Approach lights (visual glideslope guide: 4 lights, red/white)
                # Positioned 300m from runway start, left side
                papi_offset_z = -length/2 + 300.0
                for pl in range(4):
                    papi_pos = rw_pos + Vec3(
                        (-width/2 - 15 - pl*3.0) * math.cos(math.radians(heading)) + papi_offset_z * math.sin(math.radians(heading)),
                        0.4,
                        (width/2 + 15 + pl*3.0) * math.sin(math.radians(heading)) + papi_offset_z * math.cos(math.radians(heading))
                    )
                    papi_light = Entity(
                        model='sphere',
                        color=color.red if pl < 2 else color.white, # Simulates 3 deg slope
                        scale=1.2,
                        position=papi_pos,
                        emissive=True
                    )
                    self.visual_entities.append(papi_light)

            # --- 3. Spawning Terminal Structure & Control Tower ---
            # Terminal Building
            term_pos = ap_pos + Vec3(-200, 0, 100) if ap["icao"] == "KMSP" else ap_pos + Vec3(120, 0, 40)
            terminal = Entity(
                model='cube',
                color=color.rgb(100, 105, 115),
                scale=Vec3(80, 15, 60),
                position=term_pos,
                collider='box'
            )
            self.visual_entities.append(terminal)
            
            # Control Tower (High column with glass house)
            tower_pos = term_pos + Vec3(0, 0, -60)
            tower_shaft = Entity(
                model='cube',
                color=color.rgb(120, 120, 122),
                scale=Vec3(8, 40, 8),
                position=tower_pos + Vec3(0, 20, 0),
                collider='box'
            )
            tower_cabin = Entity(
                model='cube',
                color=color.rgba(0, 150, 255, 100), # glass cabin
                scale=Vec3(12, 6, 12),
                position=tower_pos + Vec3(0, 43, 0)
            )
            tower_roof = Entity(
                model='cone',
                color=color.white,
                scale=Vec3(14, 4, 14),
                position=tower_pos + Vec3(0, 47, 0)
            )
            self.visual_entities.extend([tower_shaft, tower_cabin, tower_roof])

            # --- 4. Spawning Gate Parking Bays ---
            for gate in ap["gates"]:
                gate_pos = ap_pos + gate["position"]
                
                # Ground gate boundaries (yellow box outline)
                gate_circle = Entity(
                    model='ring',
                    color=color.yellow,
                    scale=(25, 25),
                    position=gate_pos,
                    rotation_x=90
                )
                self.visual_entities.append(gate_circle)
                
                # Floating Text label
                lbl = Entity(
                    model='quad',
                    scale=(10, 3),
                    position=gate_pos + Vec3(0, 8, 0),
                    billboard=True
                )
                lbl_txt = Text(
                    parent=lbl,
                    text=gate["name"],
                    color=color.black,
                    scale=5.0,
                    position=(-0.35, 0.1)
                )
                self.visual_entities.append(lbl)

    def update(self, dt, aircraft_physics):
        """Processes gate proximity checks (boarding & refueling) and displays ATC radio log."""
        p_pos = aircraft_physics.position
        p_speed = aircraft_physics.airspeed_knots
        
        # Check proximity to all gates across all airports
        near_gate = False
        active_gate_name = ""
        
        for ap in self.get_airports():
            for gate in ap["gates"]:
                dist = (gate["position"] - p_pos).length()
                if dist < 20.0:  # Within 20 meters of parking bay
                    near_gate = True
                    active_gate_name = f"{ap['icao']} {gate['name']}"
                    break
            if near_gate:
                break
                
        # 1. Handle Refueling
        # Only active if parked (on ground, speed < 1 knot)
        if near_gate and aircraft_physics.on_ground and p_speed < 1.0:
            if aircraft_physics.fuel < aircraft_physics.max_fuel:
                self.refuel_active = True
                aircraft_physics.fuel = min(aircraft_physics.max_fuel, aircraft_physics.fuel + REFUEL_RATE * dt)
            else:
                self.refuel_active = False
        else:
            self.refuel_active = False

        # 2. Handle Passenger Boarding
        if near_gate and aircraft_physics.on_ground and p_speed < 1.0:
            if self.passengers_boarded < self.passengers_target:
                self.boarding_active = True
                self.passengers_boarded = min(self.passengers_target, self.passengers_boarded + int(PASSENGER_BOARDING_RATE * dt + 0.5))
            else:
                self.boarding_active = False
        else:
            self.boarding_active = False
            # Reset boarding if plane taxied away from gate
            if not near_gate:
                self.passengers_boarded = 0

        # 3. Simulate ATC communications
        self.atc_timer += dt
        if self.atc_timer >= self.next_atc_chatter_in:
            self.atc_timer = 0.0
            self.next_atc_chatter_in = random.uniform(8.0, 16.0)
            self._generate_random_atc_call(aircraft_physics, active_gate_name)

        # Draw boarding / refuel alerts
        # (This will display text cues on the cockpit HUD screen)

    def _generate_random_atc_call(self, aircraft_physics, active_gate_name):
        """Generates random simulated ATC exchanges between towers and traffic."""
        calls = [
            "United 204, turn left heading 270, climb and maintain flight level 120.",
            "Delta 988, cleared to land Runway 09R, wind 090 at 8 knots.",
            "Skyhawk 172SP, traffic at 2 o'clock, 4 miles, heading south, altitude 2500.",
            "Federal Express 411, taxi to holding point Runway 09R via Taxiway Bravo.",
            "Speedbird 22, contact Center on 124.85, good day.",
            "American 90, wind shear reported on short final runway 09R, exercise caution."
        ]
        
        # Add situational calls for player
        if active_gate_name and aircraft_physics.on_ground:
            if self.boarding_active:
                calls.append(f"ATC: '{active_gate_name}, boarding in progress, advise ready for pushback.'")
            elif self.passengers_boarded >= self.passengers_target:
                calls.append(f"ATC: '{active_gate_name}, boarding complete, cleared for startup. Report runway holding point.'")
        elif aircraft_physics.position.y > 10.0 and aircraft_physics.airspeed_knots > 80:
            # Flying
            alt_ft = int(aircraft_physics.position.y * 3.28084)
            calls.append(f"ATC: 'November-206-Alpha, radar contact at {alt_ft} feet, squawk 4402.'")
            
        selected_call = random.choice(calls)
        self.log_atc_message(selected_call)

    def log_atc_message(self, message):
        """Logs message to the ATC queue and displays on screen."""
        self.atc_chatter.append(message)
        if len(self.atc_chatter) > 5:
            self.atc_chatter.pop(0)
            
        # Draw on UI
        for item in self.atc_ui_log:
            destroy(item)
        self.atc_ui_log.clear()
        
        # Repopulate
        for idx, msg in enumerate(reversed(self.atc_chatter)):
            # Draw at top-right
            txt = Text(
                parent=self.atc_parent_ui,
                text=msg,
                color=color.rgb(180, 220, 255) if "ATC" in msg else color.rgb(150, 150, 150),
                scale=0.75,
                position=(0.35, 0.45 - idx * 0.035),
                z=0.2
            )
            self.atc_ui_log.append(txt)

    def destroy(self):
        """Cleans up spawned airport structures."""
        for ent in self.visual_entities:
            destroy(ent)
        for item in self.atc_ui_log:
            destroy(item)
        destroy(self.atc_parent_ui)
        self.visual_entities.clear()
        self.atc_ui_log.clear()
