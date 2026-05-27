# Weather simulation system containing rain, storms, fog, day/night cycles, and wind.

import math
import random
from ursina import Entity, Vec3, color, scene, Light, DirectionalLight, lerp
color.lerp = lerp
from flight_simulator.settings import DAY_CYCLE_SPEED, WIND_DIRECTIONS, TURBULENCE_FACTORS

class WeatherSystem:
    def __init__(self):
        self.state = "Clear"  # Clear, Rain, Storm, Fog
        self.time_of_day = 12.0  # 0.0 to 24.0 (12 is noon)
        self.wind_preset = "None"
        self.turbulence_preset = "None"
        
        # Setup Sky and Lighting references
        self.sky = None
        for e in scene.entities:
            if e.__class__.__name__ == 'Sky':
                self.sky = e
                break
        if not self.sky:
            from ursina import Sky
            self.sky = Sky()
            
        self.sky.color = color.light_gray
        
        # Lights
        self.sun = DirectionalLight(y=10, shadow_map_resolution=(1024, 1024))
        self.sun.look_at(Vec3(0, -1, 0))
        
        # Environmental effects
        self.rain_particles = []
        self.rain_holder = Entity()
        self.cloud_holder = Entity()
        self.clouds = []
        
        # Lightning timer
        self.lightning_active = False
        self.lightning_timer = 0.0
        self.next_lightning_in = 10.0
        
        # Wind & turbulence values
        self.wind_base = Vec3(0,0,0)
        self.turbulence_scale = 0.0
        
        # Setup static clouds
        self._spawn_clouds()

    def set_weather(self, state):
        """Sets the active weather state."""
        self.state = state
        if state == "Clear":
            scene.fog_density = 0.0001
            scene.fog_color = color.light_gray
            self.rain_holder.disable()
        elif state == "Rain":
            scene.fog_density = 0.002
            scene.fog_color = color.gray
            self.rain_holder.enable()
            self._spawn_rain_droplets()
        elif state == "Storm":
            scene.fog_density = 0.005
            scene.fog_color = color.dark_gray
            self.rain_holder.enable()
            self._spawn_rain_droplets()
            self.wind_preset = "Storm Gale"
            self.turbulence_preset = "Severe"
        elif state == "Fog":
            scene.fog_density = 0.015
            scene.fog_color = color.smoke
            self.rain_holder.disable()
            self.wind_preset = "None"
            self.turbulence_preset = "Light"
            
        self._update_wind_turbulence()

    def set_time_of_day(self, hour):
        """Sets the time of day (0-24)."""
        self.time_of_day = hour % 24.0

    def _update_wind_turbulence(self):
        """Updates wind and turbulence vector bases based on current selections."""
        self.wind_base = Vec3(*WIND_DIRECTIONS.get(self.wind_preset, (0,0,0)))
        self.turbulence_scale = TURBULENCE_FACTORS.get(self.turbulence_preset, 0.0)

    def get_wind_vector(self):
        """Returns the current wind velocity vector."""
        return self.wind_base

    def get_turbulence_offset(self, dt, aircraft_pos):
        """Generates random high-frequency turbulence vector acting on aircraft."""
        if self.turbulence_scale <= 0.001:
            return Vec3(0,0,0)
            
        # Generate pseudo-random forces based on time and position
        t = time_of_day_rad = (self.time_of_day * math.pi / 12.0) + aircraft_pos.x * 0.01
        tx = math.sin(t * 15.0) * math.cos(t * 7.0)
        ty = math.cos(t * 18.0) * math.sin(t * 11.0)
        tz = math.sin(t * 10.0) * math.sin(t * 14.0)
        
        return Vec3(tx, ty, tz) * self.turbulence_scale * 8.0

    def _spawn_clouds(self):
        """Generates simple procedural clouds in the sky."""
        from ursina import destroy
        # Clear existing clouds
        for c in self.clouds:
            destroy(c)
        self.clouds.clear()
        
        # Spawn clouds in a large area around the scene center
        # Clouds are clusters of low-poly white cubes/spheres
        for _ in range(30):
            cx = random.uniform(-4000, 4000)
            cy = random.uniform(800, 1500) # Altitude
            cz = random.uniform(-4000, 4000)
            
            # Make a cluster
            cluster_parent = Entity(parent=self.cloud_holder, position=Vec3(cx, cy, cz))
            self.clouds.append(cluster_parent)
            
            # Number of meshes in the cloud cluster
            for _ in range(random.randint(3, 7)):
                scale = Vec3(random.uniform(100, 250), random.uniform(30, 80), random.uniform(100, 200))
                offset = Vec3(random.uniform(-100, 100), random.uniform(-10, 10), random.uniform(-100, 100))
                
                Entity(
                    parent=cluster_parent,
                    model='cube',
                    color=color.white if self.state == "Clear" else color.light_gray,
                    scale=scale,
                    position=offset,
                    alpha=0.6
                )

    def _spawn_rain_droplets(self):
        """Creates rain mesh particles under the rain holder."""
        # Clean old ones
        for c in self.rain_holder.children:
            from ursina import destroy
            destroy(c)
            
        # Spawn 80 rain lines in a box around player (local space)
        for _ in range(80):
            rx = random.uniform(-50, 50)
            ry = random.uniform(-20, 60)
            rz = random.uniform(-50, 50)
            
            Entity(
                parent=self.rain_holder,
                model='cube',
                color=color.cyan,
                scale=Vec3(0.04, random.uniform(1.0, 3.0), 0.04),
                position=Vec3(rx, ry, rz),
                alpha=0.5
            )

    def update(self, dt, aircraft_pos):
        """Updates day/night cycle, cloud drift, rain alignment, and weather events."""
        # 1. Day / Night Cycle
        # Update sun angle
        self.time_of_day = (self.time_of_day + dt * DAY_CYCLE_SPEED) % 24.0
        
        # Map time of day to angle: 0h = midnight (-90 deg), 12h = noon (90 deg)
        angle = (self.time_of_day - 6.0) / 24.0 * 360.0 # Sunrise at 6.0 AM
        self.sun.rotation_x = angle
        self.sun.rotation_y = 45 # Constant angle offset for shadows
        
        # Color Sky & Adjust Light Intensity based on sun elevation
        elevation = math.sin(math.radians(angle))
        
        if elevation > 0.1:  # Day
            # Sky shifts from light orange/blue to full sky blue
            day_blend = min(1.0, elevation * 5.0)
            sky_col = color.lerp(color.orange, color.azure, day_blend)
            
            # Damp sky color if foggy/rainy
            if self.state in ["Rain", "Storm"]:
                sky_col = color.lerp(sky_col, color.dark_gray, 0.7)
            elif self.state == "Fog":
                sky_col = color.lerp(sky_col, color.smoke, 0.8)
                
            self.sky.color = sky_col
            self.sun.color = color.lerp(color.yellow, color.white, day_blend)
            # Increase ambient light
            scene.ambient_light = color.rgb(100 + 100 * day_blend, 100 + 100 * day_blend, 100 + 100 * day_blend)
        elif elevation > -0.1:  # Sunset / Sunrise transitions
            # Red/Orange sky
            blend = (elevation + 0.1) / 0.2
            sky_col = color.lerp(color.black, color.orange, blend)
            self.sky.color = sky_col
            self.sun.color = color.orange
            scene.ambient_light = color.rgb(50, 30, 20)
        else:  # Night
            # Dark night sky
            night_blend = min(1.0, -elevation * 5.0)
            sky_col = color.lerp(color.black, color.rgb(5, 5, 20), night_blend)
            self.sky.color = sky_col
            self.sun.color = color.rgb(10, 10, 40) # Soft moonlight
            scene.ambient_light = color.rgb(15, 15, 25)

        # 2. Rain particle tracker
        # Rain container follows the player so rain appears infinite
        if self.state in ["Rain", "Storm"]:
            self.rain_holder.position = aircraft_pos
            # Move rain droplets downwards relative to gravity, wrapping them if they go too low
            for drop in self.rain_holder.children:
                drop.y -= 45.0 * dt  # Rain fall speed
                # Reset if dropped too low
                if drop.y < -20.0:
                    drop.y = random.uniform(30.0, 60.0)
                    drop.x = random.uniform(-50, 50)
                    drop.z = random.uniform(-50, 50)

        # 3. Storm lightning simulation
        if self.state == "Storm":
            self.lightning_timer += dt
            if self.lightning_active:
                if self.lightning_timer > 0.15:  # Flash duration
                    self.lightning_active = False
                    self.lightning_timer = 0.0
                    self.next_lightning_in = random.uniform(5.0, 18.0)
                    # Restore default sky color
                    self.sky.color = color.dark_gray
            else:
                if self.lightning_timer >= self.next_lightning_in:
                    self.lightning_active = True
                    self.lightning_timer = 0.0
                    # Bright flash
                    self.sky.color = color.white
                    scene.ambient_light = color.white
                    # Trigger a thunder sound (simulate or print)
                    print("[Weather System] *Lightning Flash* / *Thunder Crack*")

        # 4. Slow Cloud Drift
        # Move clouds based on wind velocity
        for cloud in self.clouds:
            cloud.position += self.wind_base * 0.1 * dt
            # Wrap clouds if they drift too far out of bounds
            if cloud.x > 5000: cloud.x = -5000
            elif cloud.x < -5000: cloud.x = 5000
            if cloud.z > 5000: cloud.z = -5000
            elif cloud.z < -5000: cloud.z = 5000
