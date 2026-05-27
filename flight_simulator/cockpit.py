# Cockpit HUD cockpit layout and glass cockpit telemetry display.

import math
from ursina import Entity, camera, color, Text, destroy, Vec3, Vec2
from flight_simulator.settings import OVERSPEED_KNOTS

class CockpitHUD:
    def __init__(self, aircraft_physics):
        self.physics = aircraft_physics
        self.hud_elements = []
        
        # Primary container for PFD (Primary Flight Display)
        self.pfd_parent = Entity(parent=camera.ui)
        self.hud_elements.append(self.pfd_parent)
        
        # Glass HUD colors
        self.color_glass_bg = color.rgba(10, 25, 15, 120)
        self.color_glass_border = color.rgba(0, 255, 100, 200)
        self.color_hud_green = color.rgb(0, 255, 100)
        self.color_hud_cyan = color.rgb(0, 255, 255)
        self.color_warning = color.rgb(255, 50, 50)
        self.color_amber = color.rgb(255, 150, 0)

        self._build_instruments()

    def _build_instruments(self):
        """Constructs the primary glass cockpit instruments on camera.ui."""
        # 1. Background PFD Box (Central HUD Glass Plate)
        self.hud_plate = Entity(
            parent=self.pfd_parent,
            model='quad',
            color=self.color_glass_bg,
            scale=(0.9, 0.65),
            position=(0, -0.05),
            z=1
        )
        
        # Border
        self.hud_border = Entity(
            parent=self.pfd_parent,
            model='line',
            color=self.color_glass_border,
            scale=(0.9, 0.65),
            position=(0, -0.05),
            z=0.9
        )
        
        # 2. Artificial Horizon (Center of HUD)
        # Sky/Ground dividing box
        self.horizon_box_parent = Entity(parent=self.pfd_parent, position=(0, 0), scale=(0.35, 0.35))
        
        self.horizon_sky = Entity(
            parent=self.horizon_box_parent,
            model='quad',
            color=color.rgba(0, 100, 255, 100),
            scale=(1.0, 0.5),
            position=(0, 0.25),
            z=2
        )
        self.horizon_ground = Entity(
            parent=self.horizon_box_parent,
            model='quad',
            color=color.rgba(139, 69, 19, 100),
            scale=(1.0, 0.5),
            position=(0, -0.25),
            z=2
        )
        
        # Pitch Ladder marks inside Horizon
        self.pitch_ladder = Entity(parent=self.horizon_box_parent, z=1.5)
        self.pitch_lines = []
        for p in range(-40, 41, 10):
            if p == 0:
                continue
            line = Entity(
                parent=self.pitch_ladder,
                model='quad',
                color=self.color_hud_green,
                scale=(0.12, 0.005),
                position=(0, p * 0.01) # 10 deg = 0.1 y-units
            )
            # Add small text labels for pitch degrees
            lbl_l = Text(
                parent=self.pitch_ladder,
                text=str(p),
                color=self.color_hud_green,
                scale=0.8,
                position=(-0.1, p * 0.01 + 0.015)
            )
            lbl_r = Text(
                parent=self.pitch_ladder,
                text=str(p),
                color=self.color_hud_green,
                scale=0.8,
                position=(0.08, p * 0.01 + 0.015)
            )
            self.pitch_lines.append(line)
            
        # Fixed aircraft reference symbol in the center of the artificial horizon
        self.horizon_aircraft_symbol = Entity(
            parent=self.pfd_parent,
            model='quad',
            color=self.color_hud_cyan,
            scale=(0.08, 0.008),
            position=(0, 0),
            z=0.8
        )
        self.horizon_aircraft_dot = Entity(
            parent=self.pfd_parent,
            model='quad',
            color=self.color_hud_cyan,
            scale=(0.01, 0.01),
            position=(0, 0),
            z=0.8
        )
        # Left and right wing ticks
        self.horizon_wing_l = Entity(parent=self.pfd_parent, model='quad', color=self.color_hud_cyan, scale=(0.03, 0.005), position=(-0.06, 0), z=0.8)
        self.horizon_wing_r = Entity(parent=self.pfd_parent, model='quad', color=self.color_hud_cyan, scale=(0.03, 0.005), position=(0.06, 0), z=0.8)
        
        # 3. Speed Tape (Left Side)
        self.speed_bg = Entity(
            parent=self.pfd_parent,
            model='quad',
            color=color.rgba(20, 20, 20, 180),
            scale=(0.09, 0.45),
            position=(-0.25, 0),
            z=0.9
        )
        self.speed_border = Entity(
            parent=self.pfd_parent,
            model='line',
            color=self.color_glass_border,
            scale=(0.09, 0.45),
            position=(-0.25, 0),
            z=0.8
        )
        self.speed_tape_parent = Entity(parent=self.pfd_parent, position=(-0.25, 0))
        self.speed_labels = []
        for s in range(0, 500, 20):
            lbl = Text(
                parent=self.speed_tape_parent,
                text=str(s),
                color=self.color_hud_green,
                scale=0.8,
                position=(-0.035, s * 0.0015 - 0.22)
            )
            self.speed_labels.append((s, lbl))
            
        # Target Speed indicator arrow in center
        self.speed_pointer = Text(
            parent=self.pfd_parent,
            text=">",
            color=self.color_hud_cyan,
            scale=1.5,
            position=(-0.29, -0.01),
            z=0.7,
            use_tags=False
        )
        self.speed_digital = Text(
            parent=self.pfd_parent,
            text="000 KT",
            color=self.color_hud_cyan,
            scale=1.2,
            position=(-0.28, 0.24),
            z=0.7
        )

        # 4. Altitude Tape (Right Side)
        self.alt_bg = Entity(
            parent=self.pfd_parent,
            model='quad',
            color=color.rgba(20, 20, 20, 180),
            scale=(0.09, 0.45),
            position=(0.25, 0),
            z=0.9
        )
        self.alt_border = Entity(
            parent=self.pfd_parent,
            model='line',
            color=self.color_glass_border,
            scale=(0.09, 0.45),
            position=(0.25, 0),
            z=0.8
        )
        self.alt_tape_parent = Entity(parent=self.pfd_parent, position=(0.25, 0))
        self.alt_labels = []
        for a in range(0, 10000, 500):
            lbl = Text(
                parent=self.alt_tape_parent,
                text=f"{a}",
                color=self.color_hud_green,
                scale=0.75,
                position=(-0.03, a * 0.0001 - 0.22)
            )
            self.alt_labels.append((a, lbl))
            
        self.alt_pointer = Text(
            parent=self.pfd_parent,
            text="<",
            color=self.color_hud_cyan,
            scale=1.5,
            position=(0.27, -0.01),
            z=0.7,
            use_tags=False
        )
        self.alt_digital = Text(
            parent=self.pfd_parent,
            text="0000 FT",
            color=self.color_hud_cyan,
            scale=1.2,
            position=(0.21, 0.24),
            z=0.7
        )

        # 5. Compass Heading Tape (Top Center)
        self.heading_bg = Entity(
            parent=self.pfd_parent,
            model='quad',
            color=color.rgba(20, 20, 20, 180),
            scale=(0.4, 0.05),
            position=(0, 0.24),
            z=0.9
        )
        self.heading_border = Entity(
            parent=self.pfd_parent,
            model='line',
            color=self.color_glass_border,
            scale=(0.4, 0.05),
            position=(0, 0.24),
            z=0.8
        )
        self.heading_tape_parent = Entity(parent=self.pfd_parent, position=(0, 0.24))
        self.heading_labels = []
        
        cardinals = {0: "N", 90: "E", 180: "S", 270: "W"}
        for deg in range(0, 360, 10):
            text_val = cardinals.get(deg, str(deg // 10))
            lbl = Text(
                parent=self.heading_tape_parent,
                text=text_val,
                color=self.color_hud_cyan if deg in cardinals else self.color_hud_green,
                scale=0.75 if deg in cardinals else 0.65,
                position=(deg * 0.005 - 0.9, -0.015)
            )
            self.heading_labels.append((deg, lbl))
            
        # Center Heading marker
        self.heading_pointer = Text(
            parent=self.pfd_parent,
            text="V",
            color=self.color_hud_cyan,
            scale=1.0,
            position=(-0.01, 0.28),
            z=0.7
        )
        self.heading_digital = Text(
            parent=self.pfd_parent,
            text="HDG 000",
            color=self.color_hud_cyan,
            scale=1.0,
            position=(-0.05, 0.32),
            z=0.7
        )

        # 6. Status gauges panel (Right Side of dashboard: Engine & Fuel)
        self.engine_panel_parent = Entity(parent=self.pfd_parent, position=(0.37, -0.05))
        
        # Engine Label
        self.lbl_eng = Text(parent=self.engine_panel_parent, text="ENGINE & APU", scale=0.8, color=self.color_hud_cyan, position=(-0.05, 0.25))
        
        # Throttle Bar
        Text(parent=self.engine_panel_parent, text="THR", scale=0.7, color=self.color_hud_green, position=(-0.05, 0.18))
        self.gauge_throttle_bg = Entity(parent=self.engine_panel_parent, model='quad', color=color.dark_gray, scale=(0.08, 0.015), position=(0.02, 0.17), z=0.8)
        self.gauge_throttle_fill = Entity(parent=self.engine_panel_parent, model='quad', color=self.color_hud_cyan, scale=(0.08, 0.015), position=(0.02, 0.17), z=0.7)
        self.lbl_throttle_val = Text(parent=self.engine_panel_parent, text="0%", scale=0.7, color=self.color_hud_green, position=(0.07, 0.18))

        # Turbine RPM Bar
        Text(parent=self.engine_panel_parent, text="RPM", scale=0.7, color=self.color_hud_green, position=(-0.05, 0.12))
        self.gauge_rpm_bg = Entity(parent=self.engine_panel_parent, model='quad', color=color.dark_gray, scale=(0.08, 0.015), position=(0.02, 0.11), z=0.8)
        self.gauge_rpm_fill = Entity(parent=self.engine_panel_parent, model='quad', color=self.color_hud_green, scale=(0.08, 0.015), position=(0.02, 0.11), z=0.7)
        self.lbl_rpm_val = Text(parent=self.engine_panel_parent, text="0%", scale=0.7, color=self.color_hud_green, position=(0.07, 0.12))

        # Fuel Bar
        Text(parent=self.engine_panel_parent, text="FUEL", scale=0.7, color=self.color_hud_green, position=(-0.05, 0.06))
        self.gauge_fuel_bg = Entity(parent=self.engine_panel_parent, model='quad', color=color.dark_gray, scale=(0.08, 0.015), position=(0.02, 0.05), z=0.8)
        self.gauge_fuel_fill = Entity(parent=self.engine_panel_parent, model='quad', color=self.color_hud_green, scale=(0.08, 0.015), position=(0.02, 0.05), z=0.7)
        self.lbl_fuel_val = Text(parent=self.engine_panel_parent, text="100%", scale=0.7, color=self.color_hud_green, position=(0.07, 0.06))

        # Systems status: Gear, Flaps, Brakes
        self.lbl_gear_status = Text(parent=self.engine_panel_parent, text="GEAR: DOWN", scale=0.7, color=self.color_hud_green, position=(-0.05, -0.02))
        self.lbl_flaps_status = Text(parent=self.engine_panel_parent, text="FLAPS: UP", scale=0.7, color=self.color_hud_green, position=(-0.05, -0.06))
        self.lbl_brakes_status = Text(parent=self.engine_panel_parent, text="BRAKES: OFF", scale=0.7, color=self.color_hud_green, position=(-0.05, -0.1))
        
        # Flight statistics display (G-Force, Vertical Speed)
        self.lbl_gforce = Text(parent=self.engine_panel_parent, text="G-FORCE: 1.0G", scale=0.75, color=self.color_hud_green, position=(-0.05, -0.16))
        self.lbl_vspeed = Text(parent=self.engine_panel_parent, text="V/S: 0 FPM", scale=0.75, color=self.color_hud_green, position=(-0.05, -0.21))

        # 7. Navigation Radar (Left Side of dashboard)
        self.radar_panel_parent = Entity(parent=self.pfd_parent, position=(-0.37, -0.05))
        self.lbl_nav_radar = Text(parent=self.radar_panel_parent, text="NAV RADAR (10 NM)", scale=0.8, color=self.color_hud_cyan, position=(-0.05, 0.25))
        
        # Radar scope circle representation
        self.radar_circle = Entity(
            parent=self.radar_panel_parent,
            model='circle',
            color=color.rgba(0, 100, 50, 40),
            scale=(0.18, 0.18),
            position=(0, 0.05),
            z=0.8
        )
        self.radar_circle_border = Entity(
            parent=self.radar_panel_parent,
            model='circle',
            color=self.color_glass_border,
            scale=(0.18, 0.18),
            position=(0, 0.05),
            z=0.7,
            alpha=0.6
        )
        # Radar center sweep line or crosshair
        self.radar_cross_h = Entity(parent=self.radar_panel_parent, model='quad', color=self.color_glass_border, scale=(0.18, 0.002), position=(0, 0.05), z=0.7, alpha=0.3)
        self.radar_cross_v = Entity(parent=self.radar_panel_parent, model='quad', color=self.color_glass_border, scale=(0.002, 0.18), position=(0, 0.05), z=0.7, alpha=0.3)
        
        # Blips in radar (airports & planes)
        self.radar_blips = [] # List of (entity, type ['airport', 'traffic'])
        self.lbl_next_wp = Text(parent=self.radar_panel_parent, text="WP: --", scale=0.7, color=self.color_hud_green, position=(-0.07, -0.1))
        self.lbl_dist_wp = Text(parent=self.radar_panel_parent, text="DIST: -- NM", scale=0.7, color=self.color_hud_green, position=(-0.07, -0.14))
        
        # 8. ILS Glideslope / Localizer Crosshairs
        self.ils_loc_bar = Entity(parent=self.pfd_parent, model='quad', color=self.color_amber, scale=(0.002, 0.2), position=(0, 0), z=0.5, enabled=False)
        self.ils_gs_bar = Entity(parent=self.pfd_parent, model='quad', color=self.color_amber, scale=(0.2, 0.002), position=(0, 0), z=0.5, enabled=False)
        
        # 9. Autopilot indicator status
        self.lbl_ap_status = Text(
            parent=self.pfd_parent,
            text="AP: MANUAL",
            color=self.color_hud_green,
            scale=0.9,
            position=(-0.05, 0.18),
            z=0.7
        )

        # 10. Master Warning Annunciator (Top Center)
        self.warning_bg = Entity(
            parent=self.pfd_parent,
            model='quad',
            color=color.rgba(20, 20, 20, 220),
            scale=(0.3, 0.06),
            position=(0, -0.28),
            z=0.8,
            enabled=False
        )
        self.warning_text = Text(
            parent=self.warning_bg,
            text="STALL",
            color=self.color_warning,
            scale=1.5,
            position=(-0.06, -0.015),
            z=0.7
        )
        self.warning_flash_state = False
        self.flash_timer = 0.0

    def set_autopilot_text(self, mode_str):
        """Updates HUD autopilot annunciator."""
        self.lbl_ap_status.text = f"AP: {mode_str}"
        if "MANUAL" in mode_str:
            self.lbl_ap_status.color = self.color_hud_green
        else:
            self.lbl_ap_status.color = self.color_hud_cyan

    def update_hud(self, dt, ai_planes, airports, target_waypoint):
        """Drives the instrumentation needles, sliding tapes, and alarms based on physics state."""
        # 1. Pitch & Roll Artificial Horizon updates
        # Scale: pitch in degrees. We shift the pitch ladder vertically.
        # pitch * 0.01 matches 0.1 offset per 10 degrees.
        self.pitch_ladder.y = -self.physics.rotation.x * 0.01
        
        # Roll: rotate the dividing division and pitch ladder
        self.horizon_box_parent.rotation_z = self.physics.rotation.z

        # 2. Speed Tape update
        # Slide the labels based on current airspeed
        # Speed 100 knots should shift tape down. 1 knot = 0.0015 y-offset.
        speed = self.physics.airspeed_knots
        self.speed_tape_parent.y = -speed * 0.0015
        self.speed_digital.text = f"{int(speed):03d} KT"
        
        # Highlight overspeed
        if speed > OVERSPEED_KNOTS:
            self.speed_digital.color = self.color_warning
        else:
            self.speed_digital.color = self.color_hud_cyan

        # 3. Altitude Tape update
        # Slide labels based on altitude (feet)
        # 1 foot = 0.0001 y-offset.
        alt_feet = self.physics.position.y * 3.28084
        self.alt_tape_parent.y = -alt_feet * 0.0001
        self.alt_digital.text = f"{int(alt_feet):04d} FT"

        # 4. Heading Tape update
        # Compass slides horizontally. Heading 0 to 360.
        # 1 degree = 0.005 x-offset.
        hdg = self.physics.rotation.y
        self.heading_tape_parent.x = -hdg * 0.005
        self.heading_digital.text = f"HDG {int(hdg):03d}"

        # 5. Engine indicators (spool bar, throttle bar, fuel bar)
        t_fill_scale = self.physics.throttle * 0.08
        self.gauge_throttle_fill.scale_x = t_fill_scale
        # shift origin to keep left alignment
        self.gauge_throttle_fill.x = 0.02 - (0.08 - t_fill_scale) / 2.0
        self.lbl_throttle_val.text = f"{int(self.physics.throttle * 100)}%"

        rpm_percent = self.physics.spooled_thrust / self.physics.max_thrust
        rpm_scale = rpm_percent * 0.08
        self.gauge_rpm_fill.scale_x = rpm_scale
        self.gauge_rpm_fill.x = 0.02 - (0.08 - rpm_scale) / 2.0
        self.lbl_rpm_val.text = f"{int(rpm_percent * 100)}%"

        fuel_percent = self.physics.fuel / self.physics.max_fuel
        fuel_scale = fuel_percent * 0.08
        self.gauge_fuel_fill.scale_x = fuel_scale
        self.gauge_fuel_fill.x = 0.02 - (0.08 - fuel_scale) / 2.0
        self.lbl_fuel_val.text = f"{int(fuel_percent * 100)}%"
        # warning if low fuel
        if fuel_percent < 0.15:
            self.gauge_fuel_fill.color = self.color_warning
        else:
            self.gauge_fuel_fill.color = self.color_hud_green

        # Gear, Flaps, Brakes indicators
        self.lbl_gear_status.text = f"GEAR: {'DOWN' if self.physics.gear_deployed else 'UP'}"
        self.lbl_gear_status.color = self.color_hud_green if self.physics.gear_deployed else self.color_amber
        self.lbl_flaps_status.text = f"FLAPS: {int(self.physics.flaps * 100)}%"
        self.lbl_flaps_status.color = self.color_hud_green if self.physics.flaps > 0 else self.color_hud_cyan
        self.lbl_brakes_status.text = f"BRAKES: {'ON' if self.physics.pitch_input == 0 and self.physics.on_ground and speed < 5 else ('PARK' if self.physics.on_ground and speed == 0 else 'OFF')}" # brakes helper
        # Wait, let's tie to actual physics control brakes
        # We'll update brakes text based on physics brakes

        self.lbl_gforce.text = f"G-FORCE: {self.physics.g_force:.2f}G"
        # Color G-Force if extreme
        if self.physics.g_force > 4.0 or self.physics.g_force < -1.5:
            self.lbl_gforce.color = self.color_warning
        else:
            self.lbl_gforce.color = self.color_hud_green

        self.lbl_vspeed.text = f"V/S: {int(self.physics.vertical_speed_fpm):+d} FPM"
        if abs(self.physics.vertical_speed_fpm) > 2000:
            self.lbl_vspeed.color = self.color_amber
        else:
            self.lbl_vspeed.color = self.color_hud_green

        # 6. Alarms & Warning Flasher
        self.flash_timer += dt
        if self.flash_timer >= 0.25: # Blink frequency (250ms)
            self.warning_flash_state = not self.warning_flash_state
            self.flash_timer = 0.0

        # Run warnings check
        warning_active = False
        warning_msg = ""
        
        if self.physics.stalled:
            warning_active = True
            warning_msg = "STALL STALL"
        elif alt_feet < 500 and self.physics.vertical_speed_fpm < -1200 and not self.physics.on_ground:
            warning_active = True
            warning_msg = "PULL UP"
        elif speed > OVERSPEED_KNOTS:
            warning_active = True
            warning_msg = "OVERSPEED"
        elif fuel_percent < 0.15:
            warning_active = True
            warning_msg = "LOW FUEL"
        elif not self.physics.gear_deployed and alt_feet < 200 and not self.physics.on_ground:
            warning_active = True
            warning_msg = "GEAR UNSAFE"

        if warning_active:
            self.warning_bg.enabled = True
            self.warning_text.text = warning_msg
            if self.warning_flash_state:
                self.warning_bg.color = color.rgba(255, 0, 0, 180)
                self.warning_text.color = color.white
            else:
                self.warning_bg.color = color.rgba(20, 20, 20, 220)
                self.warning_text.color = self.color_warning
        else:
            self.warning_bg.enabled = False

        # 7. ILS indicator bars
        # If target waypoint is an airport runway and we are near (within 10 NM / 18500 meters), show ILS
        if target_waypoint and "Runway" in target_waypoint.get("name", ""):
            r_pos = target_waypoint["position"]
            r_heading = target_waypoint.get("heading", 0.0)
            
            dist = (r_pos - self.physics.position).length()
            if dist < 18500.0:  # 10 nautical miles
                self.ils_loc_bar.enabled = True
                self.ils_gs_bar.enabled = True
                
                # ILS glideslope calculation (ideally 3 degrees)
                # Angle to runway touchdown point
                horiz_dist = math.sqrt((r_pos.x - self.physics.position.x)**2 + (r_pos.z - self.physics.position.z)**2)
                current_slope = math.degrees(math.atan2(self.physics.position.y - r_pos.y, horiz_dist))
                slope_error = current_slope - 3.0 # Deviation from 3 deg
                
                # ILS localizer alignment
                # Target heading vs current angle
                vec_to_runway = (r_pos - self.physics.position).normalized()
                angle_to_runway = math.degrees(math.atan2(vec_to_runway.x, vec_to_runway.z)) % 360
                # Deviation from runway center line
                # Localizer range: +/- 5 degrees
                loc_error = angle_to_runway - r_heading
                if loc_error > 180: loc_error -= 360
                elif loc_error < -180: loc_error += 360
                
                # Scale ILS crosshair positions on screen (PFD center)
                # loc error: 1 deg = 0.02 x units
                self.ils_loc_bar.x = max(-0.1, min(loc_error * -0.02, 0.1))
                # gs error: 1 deg = 0.03 y units
                self.ils_gs_bar.y = max(-0.1, min(slope_error * 0.03, 0.1))
            else:
                self.ils_loc_bar.enabled = False
                self.ils_gs_bar.enabled = False
        else:
            self.ils_loc_bar.enabled = False
            self.ils_gs_bar.enabled = False

        # 8. Update Navigation Radar Plotting
        # Clean old radar blips
        for b in self.radar_blips:
            destroy(b)
        self.radar_blips.clear()
        
        # Max scale: 10 nautical miles (18520 meters)
        radar_range = 18520.0
        
        # Find player heading to rotate radar points
        rad_heading = math.radians(self.physics.rotation.y)
        
        # Plot airports on radar
        for ap in airports:
            ap_pos = ap["position"]
            relative_vec = ap_pos - self.physics.position
            dist = relative_vec.length()
            
            if dist < radar_range:
                # Rotate relative vectors to match aircraft heading
                rx = relative_vec.x * math.cos(rad_heading) - relative_vec.z * math.sin(rad_heading)
                rz = relative_vec.x * math.sin(rad_heading) + relative_vec.z * math.cos(rad_heading)
                
                # Scale to radar size (radius 0.09)
                blip_x = (rx / radar_range) * 0.08
                blip_y = (rz / radar_range) * 0.08 + 0.05
                
                blip = Entity(
                    parent=self.radar_panel_parent,
                    model='quad',
                    color=color.white if "Mountain" not in ap["name"] else color.orange,
                    scale=(0.008, 0.008),
                    position=(blip_x, blip_y),
                    z=0.7
                )
                self.radar_blips.append(blip)

        # Plot AI planes on radar
        for plane in ai_planes:
            p_pos = plane.position
            relative_vec = p_pos - self.physics.position
            dist = relative_vec.length()
            
            if dist < radar_range:
                rx = relative_vec.x * math.cos(rad_heading) - relative_vec.z * math.sin(rad_heading)
                rz = relative_vec.x * math.sin(rad_heading) + relative_vec.z * math.cos(rad_heading)
                
                blip_x = (rx / radar_range) * 0.08
                blip_y = (rz / radar_range) * 0.08 + 0.05
                
                # Color code green for friendly traffic
                blip = Entity(
                    parent=self.radar_panel_parent,
                    model='circle',
                    color=self.color_hud_green,
                    scale=(0.006, 0.006),
                    position=(blip_x, blip_y),
                    z=0.7
                )
                self.radar_blips.append(blip)

        # Display Waypoint Info
        if target_waypoint:
            self.lbl_next_wp.text = f"WP: {target_waypoint['name']}"
            wp_dist_nm = (target_waypoint['position'] - self.physics.position).length() * 0.000539957
            self.lbl_dist_wp.text = f"DIST: {wp_dist_nm:.1f} NM"
        else:
            self.lbl_next_wp.text = "WP: NONE"
            self.lbl_dist_wp.text = "DIST: -- NM"

    def destroy(self):
        """Cleans up HUD entities when unloading the flight simulator."""
        for elem in self.hud_elements:
            destroy(elem)
        for b in self.radar_blips:
            destroy(b)
        self.hud_elements.clear()
        self.radar_blips.clear()


class CockpitCabin(Entity):
    def __init__(self, parent_plane, camera_pos, **kwargs):
        super().__init__(parent=parent_plane, **kwargs)
        self.position = camera_pos
        self.enabled = False
        
        # Sub-entities for animations
        self.yoke_l = None
        self.yoke_r = None
        
        self.build_cabin()

    def build_cabin(self):
        # 1. Main Dashboard Panel
        self.dash = Entity(
            parent=self,
            model='cube',
            color=color.rgb(75, 75, 78), # Slate grey dashboard panel
            scale=(2.4, 0.7, 0.2),
            position=(0, -0.4, 0.8)
        )
        
        # Glare shield (dashboard top cover lip)
        self.glare_shield = Entity(
            parent=self,
            model='cube',
            color=color.rgb(30, 30, 32), # Matte black
            scale=(2.42, 0.08, 0.4),
            position=(0, -0.06, 0.7),
            rotation_x=5
        )

        # 2. Dual Glass Screens (Garmin G1000 bezels & screens)
        # Left screen bezel (PFD)
        self.pfd_bezel = Entity(
            parent=self.dash,
            model='quad',
            color=color.rgb(40, 40, 42),
            scale=(0.3, 0.7),
            position=(-0.25, 0, -0.52)
        )
        # Left screen display
        self.pfd_screen = Entity(
            parent=self.pfd_bezel,
            model='quad',
            color=color.rgb(10, 15, 25), # Dark screen glass
            scale=(0.9, 0.8),
            position=(0, 0, -0.01)
        )
        
        # Right screen bezel (MFD / GPS)
        self.mfd_bezel = Entity(
            parent=self.dash,
            model='quad',
            color=color.rgb(40, 40, 42),
            scale=(0.3, 0.7),
            position=(0.25, 0, -0.52)
        )
        # Right screen display
        self.mfd_screen = Entity(
            parent=self.mfd_bezel,
            model='quad',
            color=color.rgb(10, 15, 25),
            scale=(0.9, 0.8),
            position=(0, 0, -0.01)
        )

        # 3. Backup Round Instruments (Center Column)
        for i, y_pos in enumerate([0.15, -0.05, -0.25]):
            dial_bezel = Entity(
                parent=self.dash,
                model='cylinder',
                color=color.rgb(20, 20, 20),
                scale=(0.06, 0.015, 0.06),
                position=(0.0, y_pos, -0.52),
                rotation_x=90
            )
            # Inner circle (dial face)
            Entity(
                parent=dial_bezel,
                model='cylinder',
                color=color.rgb(240, 240, 240) if i == 1 else color.black, # artificial horizon sky/ground
                scale=(0.9, 1.1, 0.9),
                position=(0, 0.01, 0)
            )

        # 4. Yokes
        self.yoke_l = self._create_yoke(x_pos=-0.45)
        self.yoke_r = self._create_yoke(x_pos=0.45)

        # 5. Cabin Side Interior Panels & Windows
        self.wall_l = Entity(
            parent=self,
            model='cube',
            color=color.rgb(180, 180, 180), # Light grey leather upholstery
            scale=(0.1, 1.8, 2.5),
            position=(-1.1, -0.1, 0.6)
        )
        self.wall_r = Entity(
            parent=self,
            model='cube',
            color=color.rgb(180, 180, 180),
            scale=(0.1, 1.8, 2.5),
            position=(1.1, -0.1, 0.6)
        )
        
        # Cabin side windows (dark frames on side walls)
        Entity(parent=self.wall_l, model='quad', color=color.rgb(35, 35, 38), scale=(0.85, 0.5), position=(0.52, 0.2, 0.0))
        Entity(parent=self.wall_r, model='quad', color=color.rgb(35, 35, 38), scale=(0.85, 0.5), position=(-0.52, 0.2, 0.0))

        # 6. Cabin Roof (Ceiling trim)
        self.roof = Entity(
            parent=self,
            model='cube',
            color=color.rgb(160, 160, 165), # Light beige/grey roof
            scale=(2.4, 0.1, 2.5),
            position=(0, 0.8, 0.6)
        )

        # 7. Seats (Behind the pilot/co-pilot camera viewpoint)
        self.seat_l = Entity(
            parent=self,
            model='cube',
            color=color.rgb(55, 55, 60), # Charcoal seat bottom
            scale=(0.55, 0.8, 0.55),
            position=(-0.45, -0.9, -0.2)
        )
        # Seat backrest
        Entity(parent=self.seat_l, model='cube', color=color.rgb(45, 45, 50), scale=(1.0, 1.25, 0.2), position=(0, 0.65, -0.4))
        
        self.seat_r = Entity(
            parent=self,
            model='cube',
            color=color.rgb(55, 55, 60),
            scale=(0.55, 0.8, 0.55),
            position=(0.45, -0.9, -0.2)
        )
        Entity(parent=self.seat_r, model='cube', color=color.rgb(45, 45, 50), scale=(1.0, 1.25, 0.2), position=(0, 0.65, -0.4))

    def _create_yoke(self, x_pos):
        # Yoke mount point
        yoke_base = Entity(parent=self, position=(x_pos, -0.45, 0.72))
        
        # Control rod sliding out of dashboard
        Entity(
            parent=yoke_base,
            model='cylinder',
            color=color.rgb(120, 120, 120), # Chrome shaft
            scale=(0.025, 0.35, 0.025),
            rotation_x=90
        )
        
        # Control Yoke Handle assembly
        yoke_handle = Entity(parent=yoke_base, position=(0, 0, -0.15))
        
        # Horizontal crossbar
        Entity(parent=yoke_handle, model='cube', color=color.rgb(25, 25, 25), scale=(0.22, 0.03, 0.03))
        # Left grip horn
        Entity(parent=yoke_handle, model='cube', color=color.rgb(25, 25, 25), scale=(0.03, 0.1, 0.03), position=(-0.11, 0.03, 0.0))
        # Right grip horn
        Entity(parent=yoke_handle, model='cube', color=color.rgb(25, 25, 25), scale=(0.03, 0.1, 0.03), position=(0.11, 0.03, 0.0))
        
        return yoke_handle

    def update_controls(self, pitch_input, roll_input):
        """Rotates and translates control yokes dynamically according to pilot flight inputs."""
        if self.yoke_l and self.yoke_r:
            # Rotate yokes left/right for Aileron roll input (up to 45 degrees)
            self.yoke_l.rotation_z = roll_input * -45.0
            self.yoke_r.rotation_z = roll_input * -45.0
            
            # Push/pull yokes forward/back for Elevator pitch input
            self.yoke_l.z = -0.15 + pitch_input * 0.05
            self.yoke_r.z = -0.15 + pitch_input * 0.05
