# Flight physics simulation engine with realistic aerodynamics.

import math
from ursina import Vec3
from flight_simulator.settings import GRAVITY, AIR_DENSITY_SEA_LEVEL, FLUID_DAMPING, STALL_ANGLE_DEG

class AircraftPhysics:
    def __init__(self, preset_name, preset_data):
        self.preset_name = preset_name
        
        # Load preset parameters
        self.mass_dry = preset_data["mass_dry"]
        self.max_fuel = preset_data["max_fuel"]
        self.wing_area = preset_data["wing_area"]
        self.max_thrust = preset_data["max_thrust"]
        self.engine_spool_rate = preset_data["engine_spool_rate"]
        self.roll_rate = preset_data["roll_rate"]
        self.pitch_rate = preset_data["pitch_rate"]
        self.yaw_rate = preset_data["yaw_rate"]
        self.drag_coeff_base = preset_data["drag_coeff_base"]
        self.induced_drag_factor = preset_data["induced_drag_factor"]
        self.cl_max = preset_data["cl_max"]
        self.flap_lift_bonus = preset_data["flap_lift_bonus"]
        self.flap_drag_penalty = preset_data["flap_drag_penalty"]
        self.gear_drag_penalty = preset_data["gear_drag_penalty"]
        
        # Initial State Variables
        self.position = Vec3(0, 500, 0)  # Start at 500m altitude
        self.velocity = Vec3(0, 0, 150)   # Start flying forward at 150 m/s (~290 knots)
        self.rotation = Vec3(0, 0, 0)      # pitch, yaw, roll
        self.angular_velocity = Vec3(0, 0, 0)
        
        # Systems state
        self.throttle = 0.6               # 0.0 to 1.0
        self.spooled_thrust = 0.6 * self.max_thrust
        self.fuel = self.max_fuel * 0.8    # 80% fuel at start
        self.gear_deployed = True
        self.flaps = 0.0                   # 0.0 to 1.0 (flaps up to full)
        
        # Output telemetry
        self.airspeed_knots = 290.0
        self.aoa_deg = 0.0
        self.stalled = False
        self.g_force = 1.0
        self.vertical_speed_fpm = 0.0      # feet per minute
        self.crashed = False
        self.on_ground = False
        
        # Controls history
        self.pitch_input = 0.0
        self.roll_input = 0.0
        self.yaw_input = 0.0
        
        # Calibration / helper variables
        self.last_acceleration = Vec3(0,0,0)

    @property
    def mass(self):
        """Total mass of the aircraft (dry + fuel)."""
        return self.mass_dry + max(0.0, self.fuel)

    def update(self, dt, control_inputs, wind_vector, turbulence_offset=Vec3(0,0,0)):
        """
        Updates the physics state of the aircraft.
        control_inputs: dict with keys 'pitch' (-1 to 1), 'roll' (-1 to 1), 'yaw' (-1 to 1),
                                     'throttle' (0 to 1), 'flaps' (0 to 1), 'gear' (bool), 'brakes' (bool)
        wind_vector: Vec3 world wind velocity (m/s)
        turbulence_offset: Vec3 wind turbulence contribution
        """
        if self.crashed:
            return

        dt = min(dt, 0.1)  # Clamp dt to prevent numerical instability
        if dt <= 0:
            return

        # Extract controls
        pitch_in = control_inputs.get("pitch", 0.0)
        roll_in = control_inputs.get("roll", 0.0)
        yaw_in = control_inputs.get("yaw", 0.0)
        self.throttle = control_inputs.get("throttle", self.throttle)
        self.flaps = control_inputs.get("flaps", self.flaps)
        self.gear_deployed = control_inputs.get("gear", self.gear_deployed)
        brakes_on = control_inputs.get("brakes", False)
        
        self.pitch_input = pitch_in
        self.roll_input = roll_in
        self.yaw_input = yaw_in

        # --- 1. Environmental calculations ---
        # Air density decreases with altitude
        h = max(0.0, self.position.y)
        air_density = AIR_DENSITY_SEA_LEVEL * math.exp(-h / 8500.0)

        # Net wind velocity
        net_wind = wind_vector + turbulence_offset
        
        # Air-relative velocity vector (airspeed vector)
        vel_air = self.velocity - net_wind
        speed_mps = vel_air.length()
        
        # Speed in Knots (1 m/s = 1.94384 knots)
        self.airspeed_knots = speed_mps * 1.94384

        # Calculate local axes based on pitch (rot.x), yaw (rot.y), roll (rot.z)
        # Using trigonometric definitions (Ursina standard)
        rad_pitch = math.radians(self.rotation.x)
        rad_yaw = math.radians(self.rotation.y)
        rad_roll = math.radians(self.rotation.z)

        # Calculate local forward, up, and right vectors in world space
        # Forward: +Z in local space
        forward_x = math.sin(rad_yaw) * math.cos(rad_pitch)
        forward_y = -math.sin(rad_pitch)
        forward_z = math.cos(rad_yaw) * math.cos(rad_pitch)
        local_forward = Vec3(forward_x, forward_y, forward_z).normalized()

        # Up: +Y in local space
        # Using rotation matrix components
        up_x = -math.sin(rad_yaw) * math.sin(rad_pitch) * math.cos(rad_roll) + math.cos(rad_yaw) * math.sin(rad_roll)
        up_y = math.cos(rad_pitch) * math.cos(rad_roll)
        up_z = -math.cos(rad_yaw) * math.sin(rad_pitch) * math.cos(rad_roll) - math.sin(rad_yaw) * math.sin(rad_roll)
        local_up = Vec3(up_x, up_y, up_z).normalized()

        # Right: +X in local space
        local_right = local_forward.cross(local_up).normalized()

        # Decompose airspeed into local axes
        forward_airspeed = vel_air.dot(local_forward)
        up_airspeed = vel_air.dot(local_up)
        right_airspeed = vel_air.dot(local_right)

        # --- 2. Aerodynamic Angles ---
        # Angle of Attack (AoA)
        if abs(forward_airspeed) > 0.5:
            self.aoa_deg = -math.degrees(math.atan2(up_airspeed, forward_airspeed))
        else:
            self.aoa_deg = 0.0

        # Sideslip angle (Beta)
        if speed_mps > 0.5:
            sideslip_deg = math.degrees(math.atan2(right_airspeed, forward_airspeed))
        else:
            sideslip_deg = 0.0

        # --- 3. Dynamic Pressure ---
        # q = 0.5 * rho * v^2
        q = 0.5 * air_density * (speed_mps ** 2)

        # --- 4. Engine Spooling & Fuel Consumption ---
        if self.fuel > 0:
            # Thrust decreases at higher altitudes (due to lower density)
            density_ratio = air_density / AIR_DENSITY_SEA_LEVEL
            max_thrust_altitude = self.max_thrust * math.pow(density_ratio, 0.7)
            target_thrust = self.throttle * max_thrust_altitude
            # Spooling lag
            self.spooled_thrust += (target_thrust - self.spooled_thrust) * self.engine_spool_rate * dt
            # Fuel burn proportional to throttle and max engine power
            fuel_burn = (0.00008 * self.max_thrust * (0.1 + 0.9 * self.throttle)) * dt
            self.fuel = max(0.0, self.fuel - fuel_burn)
        else:
            # Out of fuel, engine dies
            self.spooled_thrust += (0.0 - self.spooled_thrust) * 0.5 * dt

        # --- 5. Aerodynamic Coefficients ---
        # Lift Coefficient (C_L)
        # Standard linear lift curve slope: C_L = C_L_0 + C_L_alpha * AoA
        # Cl_alpha typically ~0.1 per degree.
        cl_alpha = 0.1
        c_l_ideal = cl_alpha * self.aoa_deg + self.flap_lift_bonus * self.flaps
        
        # Stall check
        stall_threshold = STALL_ANGLE_DEG
        if abs(self.aoa_deg) > stall_threshold:
            self.stalled = True
            # Lift drops off significantly
            c_l = c_l_ideal * 0.25 * math.copysign(1, self.aoa_deg)
        else:
            self.stalled = False
            c_l = c_l_ideal
            
        # Clamp lift coefficient
        c_l = max(-self.cl_max - self.flap_lift_bonus, min(c_l, self.cl_max + self.flap_lift_bonus))

        # Drag Coefficient (C_D)
        # C_D = C_D0 + induced_drag + configuration_drag
        induced_drag = (c_l ** 2) * self.induced_drag_factor
        gear_drag = self.gear_drag_penalty if self.gear_deployed else 0.0
        flap_drag = self.flap_drag_penalty * self.flaps
        c_d = self.drag_coeff_base + induced_drag + gear_drag + flap_drag
        
        if self.stalled:
            # Massive drag penalty when stalled
            c_d += 0.25

        # --- 6. Forces Calculations ---
        # Thrust: along local forward
        thrust_vec = local_forward * self.spooled_thrust

        # Drag: opposite to airspeed vector
        if speed_mps > 0.1:
            drag_direction = -vel_air.normalized()
            drag_force = q * self.wing_area * c_d
            drag_vec = drag_direction * drag_force
        else:
            drag_vec = Vec3(0,0,0)

        # Lift: perpendicular to velocity, aligned with local up
        # We project local up onto the plane perpendicular to the velocity
        if speed_mps > 0.1:
            vel_norm = vel_air.normalized()
            lift_direction = local_up - vel_norm * local_up.dot(vel_norm)
            if lift_direction.length() > 0.01:
                lift_direction = lift_direction.normalized()
            else:
                lift_direction = local_up
            
            lift_force = q * self.wing_area * c_l
            lift_vec = lift_direction * lift_force
        else:
            lift_vec = Vec3(0,0,0)

        # Gravity: down in world space
        gravity_vec = Vec3(0, -self.mass * GRAVITY, 0)

        # Ground Reactions (when wheels touch runway)
        ground_vec = Vec3(0,0,0)
        on_ground_this_frame = False
        
        # Ground level is 0
        if self.position.y <= 0:
            on_ground_this_frame = True
            self.position.y = 0
            
            # Decompose current velocity
            vert_vel = self.velocity.y
            
            # Landing Check:
            # If descent rate > 12 m/s (~2300 fpm) or extreme attitude, it's a crash!
            if vert_vel < -8.5:  # ~1700 ft/min landing gear limit
                self.crashed = True
                self.velocity = Vec3(0,0,0)
                return
            
            # If wings strike the ground (roll or pitch > 20 degrees while touching ground)
            if abs(self.rotation.z) > 25.0 or self.rotation.x < -15.0 or self.rotation.x > 25.0:
                self.crashed = True
                self.velocity = Vec3(0,0,0)
                return
                
            # Smoothly rebound / rest on ground
            # Apply normal force to counter gravity and vertical velocity
            self.velocity.y = 0
            gravity_vec.y = 0
            lift_vec.y = max(0.0, lift_vec.y)  # Lift can only help push up, not down
            
            # Ground steering & friction
            # Rolling resistance
            friction_coeff = 0.015
            if brakes_on:
                friction_coeff = 0.15  # Brakes applied
                
            # Ground friction force acts opposite to horizontal movement
            horiz_vel = Vec3(self.velocity.x, 0, self.velocity.z)
            horiz_speed = horiz_vel.length()
            if horiz_speed > 0.1:
                friction_force = self.mass * GRAVITY * friction_coeff
                ground_friction_vec = -horiz_vel.normalized() * friction_force
                ground_vec += ground_friction_vec
                
            # Force orientation to match ground tracking (prevent sliding sideways easily)
            # Sideways drag on tires is high
            sideways_vel = self.velocity.dot(local_right)
            # Cancel most sideways sliding if gear is down on the ground
            if self.gear_deployed:
                self.velocity -= local_right * sideways_vel * 0.95

        self.on_ground = on_ground_this_frame

        # --- 7. Acceleration & Translation ---
        net_force = thrust_vec + lift_vec + drag_vec + gravity_vec + ground_vec
        accel = net_force / self.mass
        self.last_acceleration = accel
        
        # Integrate velocity
        self.velocity += accel * dt
        
        # Integrate position
        self.position += self.velocity * dt

        # --- 8. Rotational Dynamics (Torques) ---
        # Control surface effectiveness scales with dynamic pressure q
        # Max control surface deflection maps to rates defined in settings
        # We scale responsiveness by dynamic pressure ratio (normalized to cruise airspeed)
        # Safe cruise speed ~100 m/s
        cruise_q = 0.5 * AIR_DENSITY_SEA_LEVEL * (90 ** 2)
        q_ratio = min(2.5, q / cruise_q) if speed_mps > 5.0 else (speed_mps / 5.0)

        # Add stall buffering / loss of control effectiveness
        control_effectiveness = 1.0
        if self.stalled:
            control_effectiveness = 0.15 # Buffering, lose 85% control authority
            
        # Target rotational velocities (deg/s) based on user input
        target_roll_rate = roll_in * self.roll_rate * q_ratio * control_effectiveness
        target_pitch_rate = pitch_in * self.pitch_rate * q_ratio * control_effectiveness
        target_yaw_rate = yaw_in * self.yaw_rate * q_ratio * control_effectiveness
        
        # Natural aerodynamic stability restores alignment (wind vane effect)
        # Pitch stability: nose wants to align with airspeed vector (AoA -> 0)
        # Yaw stability: nose wants to align with airspeed vector (Beta -> 0)
        # Roll stability: dihedral wing effect tends to level wings slightly
        if speed_mps > 10.0:
            stability_pitch = -self.aoa_deg * 0.05 * q_ratio
            stability_yaw = -sideslip_deg * 0.08 * q_ratio
            
            # Dihedral effect: levels wings if rolling sideways
            stability_roll = -rad_roll * 0.02 * q_ratio
        else:
            stability_pitch = 0.0
            stability_yaw = 0.0
            stability_roll = 0.0
            
        # Stall pitching moment (nose drops naturally when stalled to recover)
        stall_moment = 0.0
        if self.stalled and self.aoa_deg > 0:
            stall_moment = -4.0 * q_ratio  # Pitch nose down

        # Ground steering (rudder turns nose on ground)
        if self.on_ground and self.gear_deployed:
            # Taxi steering: yaw is directly coupled to steering wheel input at low speed
            target_yaw_rate += -yaw_in * 15.0 * (1.0 - min(1.0, speed_mps / 30.0))
            
            # Level roll on ground
            self.rotation.z *= 0.8
            self.angular_velocity.z = 0

        # Calculate angular accelerations (simplified spring-damper tracking)
        # Rotational velocities lag toward targets
        lag = 8.0  # how fast rotations respond (rad/sec)
        self.angular_velocity.x += (target_pitch_rate + stability_pitch + stall_moment - self.angular_velocity.x) * lag * dt
        self.angular_velocity.y += (target_yaw_rate + stability_yaw - self.angular_velocity.y) * lag * dt
        self.angular_velocity.z += (target_roll_rate + stability_roll - self.angular_velocity.z) * lag * dt

        # Integrate rotations (pitch, yaw, roll)
        self.rotation.x += self.angular_velocity.x * dt
        self.rotation.y += self.angular_velocity.y * dt
        self.rotation.z += self.angular_velocity.z * dt

        # Keep angles within standard bounds
        self.rotation.y = self.rotation.y % 360
        # Clamp pitch to +/- 89 degrees to avoid gimbal lock in simple Euler integration
        self.rotation.x = max(-89.0, min(self.rotation.x, 89.0))
        # Keep roll within +/- 180
        if self.rotation.z > 180:
            self.rotation.z -= 360
        elif self.rotation.z < -180:
            self.rotation.z += 360

        # --- 9. Auxiliary Telemetry Updates ---
        # Vertical speed in feet per minute (1 m/s = 196.85 fpm)
        self.vertical_speed_fpm = self.velocity.y * 196.8504
        
        # G-Force calculation: accel project onto local up divided by gravity
        # We add 1.0 G to account for gravity when at rest
        gravity_local_up = local_up.dot(Vec3(0, -GRAVITY, 0))
        net_accel_no_g = accel - Vec3(0, -GRAVITY, 0)
        self.g_force = (net_accel_no_g.dot(local_up) - gravity_local_up) / GRAVITY
        # Keep G-Force display realistic
        if self.on_ground:
            self.g_force = 1.0
