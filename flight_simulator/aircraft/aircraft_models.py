# Procedural 3D model assembly and control surface animations for aircraft.

import math
from ursina import Entity, Vec3, color, destroy, Text

class AircraftVisual(Entity):
    def __init__(self, aircraft_type, **kwargs):
        super().__init__(**kwargs)
        self.aircraft_type = aircraft_type
        
        # Sub-entity lists for animation
        self.turbines = []
        self.flaps_l = None
        self.flaps_r = None
        self.aileron_l = None
        self.aileron_r = None
        self.elevators = []
        self.rudder = None
        self.landing_gear_nodes = []
        self.nav_lights = []
        
        # Gear animation state
        self.gear_anim_y = 1.0  # 1.0 = deployed, 0.0 = retracted
        
        # Build specific models
        if aircraft_type == "Passenger Jet":
            self._build_passenger_jet()
        elif aircraft_type == "Fighter Jet":
            self._build_fighter_jet()
        elif aircraft_type == "Cargo Transporter":
            self._build_cargo_plane()
        elif aircraft_type == "Private Business Jet":
            self._build_private_jet()

    def _build_passenger_jet(self):
        """Assembles a dual-engine commercial passenger liner."""
        # 1. Fuselage (Central Tube)
        fuselage = Entity(
            parent=self,
            model='cube',
            color=color.white,
            scale=Vec3(3.5, 3.5, 45.0),
            position=Vec3(0, 0, 0)
        )
        
        # Windows (left side)
        for z_pos in range(-12, 18, 3):
            Entity(
                parent=fuselage,
                model='quad',
                color=color.rgb(10, 10, 10),
                scale=(0.04, 0.05),
                position=(-0.505, 0.1, z_pos / 45.0)
            )
        # Windows (right side)
        for z_pos in range(-12, 18, 3):
            Entity(
                parent=fuselage,
                model='quad',
                color=color.rgb(10, 10, 10),
                scale=(0.04, 0.05),
                position=(0.505, 0.1, z_pos / 45.0)
            )

        # Airbus Branding text (left side)
        airbus_lbl_l = Entity(parent=self, position=Vec3(-1.8, 0.3, 10.0), rotation_y=-90)
        Text(parent=airbus_lbl_l, text="AIRBUS", color=color.rgb(18, 56, 120), scale=3, use_tags=False)
        Text(parent=airbus_lbl_l, text="A320", color=color.gray, scale=2, position=(1.2, -0.01), use_tags=False)

        # Airbus Branding text (right side)
        airbus_lbl_r = Entity(parent=self, position=Vec3(1.8, 0.3, 10.0), rotation_y=90)
        Text(parent=airbus_lbl_r, text="AIRBUS", color=color.rgb(18, 56, 120), scale=3, use_tags=False)
        Text(parent=airbus_lbl_r, text="A320", color=color.gray, scale=2, position=(-1.2, -0.01), use_tags=False)
        
        # Cockpit nose cone
        nose = Entity(
            parent=self,
            model='sphere',
            color=color.white,
            scale=Vec3(3.5, 3.4, 6.0),
            position=Vec3(0, -0.05, 23.5)
        )
        # Cockpit windshield (black glass bands)
        windshield = Entity(
            parent=nose,
            model='quad',
            color=color.rgb(10, 10, 12),
            scale=(2.5, 0.7),
            position=(0, 0.4, 0.4),
            rotation_x=-15
        )

        # 2. Main Wings (Sweep-back design)
        # Left Wing
        wing_l = Entity(
            parent=self,
            model='cube',
            color=color.light_gray,
            scale=Vec3(22.0, 0.2, 4.0),
            position=Vec3(-12.5, -0.5, -2.0),
            rotation_y=-25,
            rotation_z=-4  # Dihedral angle
        )
        # Right Wing
        wing_r = Entity(
            parent=self,
            model='cube',
            color=color.light_gray,
            scale=Vec3(22.0, 0.2, 4.0),
            position=Vec3(12.5, -0.5, -2.0),
            rotation_y=25,
            rotation_z=4
        )

        # Slanted vertical winglets (Sharklets)
        winglet_l = Entity(
            parent=wing_l,
            model='cube',
            color=color.rgb(18, 56, 120),
            scale=Vec3(0.2, 2.5, 1.2),
            position=Vec3(-10.8, 1.0, 0.0),
            rotation_z=-15
        )
        winglet_r = Entity(
            parent=wing_r,
            model='cube',
            color=color.rgb(18, 56, 120),
            scale=Vec3(0.2, 2.5, 1.2),
            position=Vec3(10.8, 1.0, 0.0),
            rotation_z=15
        )

        # Flaps and Ailerons on Left Wing (hinged at the back edge)
        # Left Flap (inner trailing edge)
        self.flaps_l = Entity(
            parent=wing_l,
            model='cube',
            color=color.dark_gray,
            scale=Vec3(10.0, 0.15, 0.8),
            position=Vec3(0.2, 0.0, -0.6)  # Trailing edge
        )
        # Left Aileron (outer trailing edge)
        self.aileron_l = Entity(
            parent=wing_l,
            model='cube',
            color=color.gray,
            scale=Vec3(8.0, 0.15, 0.8),
            position=Vec3(-0.6, 0.0, -0.6)
        )

        # Flaps and Ailerons on Right Wing
        self.flaps_r = Entity(
            parent=wing_r,
            model='cube',
            color=color.dark_gray,
            scale=Vec3(10.0, 0.15, 0.8),
            position=Vec3(-0.2, 0.0, -0.6)
        )
        self.aileron_r = Entity(
            parent=wing_r,
            model='cube',
            color=color.gray,
            scale=Vec3(8.0, 0.15, 0.8),
            position=Vec3(0.6, 0.0, -0.6)
        )

        # 3. Engines (Under-wing Turbines)
        # Left Engine
        eng_l_pod = Entity(
            parent=wing_l,
            model='cylinder',
            color=color.white,
            scale=Vec3(1.8, 1.8, 5.5),
            position=Vec3(0.4, -1.8, 0.8),
            rotation_y=25, # align with flight path
            rotation_x=90
        )
        eng_l_stripe = Entity(
            parent=eng_l_pod,
            model='cylinder',
            color=color.rgb(18, 56, 120),
            scale=Vec3(1.02, 0.1, 1.02),
            position=Vec3(0, 0.1, 0)
        )
        eng_l_turbine = Entity(
            parent=eng_l_pod,
            model='cube',
            color=color.dark_gray,
            scale=Vec3(1.6, 0.1, 1.6),
            position=Vec3(0, 0.48, 0)
        )
        self.turbines.append(eng_l_turbine)
        
        # Right Engine
        eng_r_pod = Entity(
            parent=wing_r,
            model='cylinder',
            color=color.white,
            scale=Vec3(1.8, 1.8, 5.5),
            position=Vec3(-0.4, -1.8, 0.8),
            rotation_y=-25,
            rotation_x=90
        )
        eng_r_stripe = Entity(
            parent=eng_r_pod,
            model='cylinder',
            color=color.rgb(18, 56, 120),
            scale=Vec3(1.02, 0.1, 1.02),
            position=Vec3(0, 0.1, 0)
        )
        eng_r_turbine = Entity(
            parent=eng_r_pod,
            model='cube',
            color=color.dark_gray,
            scale=Vec3(1.6, 0.1, 1.6),
            position=Vec3(0, 0.48, 0)
        )
        self.turbines.append(eng_r_turbine)

        # 4. Tail Section (Vertical Fin & Horizontal Stabilizers)
        tail_fin = Entity(
            parent=self,
            model='cube',
            color=color.rgb(18, 56, 120), # Airbus blue
            scale=Vec3(0.4, 9.0, 6.0),
            position=Vec3(0, 5.0, -18.0),
            rotation_x=20
        )
        self.rudder = Entity(
            parent=tail_fin,
            model='cube',
            color=color.rgb(18, 56, 120),
            scale=Vec3(0.35, 8.0, 1.2),
            position=Vec3(0, -0.05, -0.6)
        )
        
        # Tail Fin text (left side)
        tail_lbl_l = Entity(parent=tail_fin, position=Vec3(-0.52, 0.1, 0.0), rotation_y=-90)
        Text(parent=tail_lbl_l, text="A320", color=color.white, scale=3, use_tags=False)

        # Tail Fin text (right side)
        tail_lbl_r = Entity(parent=tail_fin, position=Vec3(0.52, 0.1, 0.0), rotation_y=90)
        Text(parent=tail_lbl_r, text="A320", color=color.white, scale=3, use_tags=False)
        
        # Horizontal Stabilizers
        stab_l = Entity(
            parent=self,
            model='cube',
            color=color.light_gray,
            scale=Vec3(8.0, 0.15, 3.0),
            position=Vec3(-5.0, 1.0, -19.5),
            rotation_y=-15
        )
        stab_r = Entity(
            parent=self,
            model='cube',
            color=color.light_gray,
            scale=Vec3(8.0, 0.15, 3.0),
            position=Vec3(5.0, 1.0, -19.5),
            rotation_y=15
        )
        
        # Elevators on Stabilizers
        el_l = Entity(parent=stab_l, model='cube', color=color.gray, scale=Vec3(7.5, 0.1, 0.7), position=Vec3(0, 0, -0.6))
        el_r = Entity(parent=stab_r, model='cube', color=color.gray, scale=Vec3(7.5, 0.1, 0.7), position=Vec3(0, 0, -0.6))
        self.elevators.extend([el_l, el_r])

        # 5. Landing Gear (Tri-cycle layout)
        # Nose Gear
        gear_nose = Entity(parent=self, position=Vec3(0, -1.8, 16.0))
        gear_nose_strut = Entity(parent=gear_nose, model='cylinder', color=color.gray, scale=Vec3(0.15, 2.5, 0.15), rotation_x=90)
        gear_nose_wheel = Entity(parent=gear_nose, model='cylinder', color=color.black, scale=Vec3(0.8, 0.3, 0.8), position=Vec3(0, -1.25, 0))
        
        # Left Main Gear
        gear_l = Entity(parent=self, position=Vec3(-5.0, -2.0, -2.0))
        gear_l_strut = Entity(parent=gear_l, model='cylinder', color=color.gray, scale=Vec3(0.25, 3.0, 0.25), rotation_x=90)
        gear_l_wheel = Entity(parent=gear_l, model='cylinder', color=color.black, scale=Vec3(1.3, 0.5, 1.3), position=Vec3(0, -1.5, 0))
        
        # Right Main Gear
        gear_r = Entity(parent=self, position=Vec3(5.0, -2.0, -2.0))
        gear_r_strut = Entity(parent=gear_r, model='cylinder', color=color.gray, scale=Vec3(0.25, 3.0, 0.25), rotation_x=90)
        gear_r_wheel = Entity(parent=gear_r, model='cylinder', color=color.black, scale=Vec3(1.3, 0.5, 1.3), position=Vec3(0, -1.5, 0))
        
        self.landing_gear_nodes.extend([gear_nose, gear_l, gear_r])

        # 6. Navigation Lights (Wingtips and Tail)
        light_l = Entity(parent=wing_l, model='sphere', color=color.red, scale=0.6, position=Vec3(-10.8, 0.1, 0.0), emissive=True)
        light_r = Entity(parent=wing_r, model='sphere', color=color.green, scale=0.6, position=Vec3(10.8, 0.1, 0.0), emissive=True)
        light_tail = Entity(parent=tail_fin, model='sphere', color=color.white, scale=0.6, position=Vec3(0.0, 4.4, -2.8), emissive=True)
        self.nav_lights.extend([light_l, light_r, light_tail])

    def _build_fighter_jet(self):
        """Assembles a highly aerodynamic, dual-exhaust fighter jet (F-18 style)."""
        # Fuselage (sharp and angular)
        fuselage = Entity(parent=self, model='cube', color=color.rgb(112, 128, 144), scale=Vec3(2.2, 1.6, 28.0), position=Vec3(0, 0, 0))
        nose = Entity(parent=self, model='cone', color=color.rgb(100, 100, 100), scale=Vec3(2.0, 6.0, 2.0), position=Vec3(0, -0.1, 15.5), rotation_x=90)
        
        # Canopy (glass bubble)
        canopy = Entity(parent=self, model='sphere', color=color.rgba(255, 200, 0, 100), scale=Vec3(1.4, 1.1, 5.0), position=Vec3(0, 1.1, 6.0))

        # Main Wings (extreme delta-sweep)
        wing_l = Entity(parent=self, model='cube', color=color.rgb(112, 128, 144), scale=Vec3(8.0, 0.1, 4.0), position=Vec3(-4.8, -0.2, -2.0), rotation_y=-35, rotation_z=-2)
        wing_r = Entity(parent=self, model='cube', color=color.rgb(112, 128, 144), scale=Vec3(8.0, 0.1, 4.0), position=Vec3(4.8, -0.2, -2.0), rotation_y=35, rotation_z=2)
        
        self.flaps_l = Entity(parent=wing_l, model='cube', color=color.black, scale=Vec3(4.0, 0.08, 0.8), position=Vec3(0.1, 0, -0.6))
        self.flaps_r = Entity(parent=wing_r, model='cube', color=color.black, scale=Vec3(4.0, 0.08, 0.8), position=Vec3(-0.1, 0, -0.6))
        self.aileron_l = Entity(parent=wing_l, model='cube', color=color.dark_gray, scale=Vec3(3.2, 0.08, 0.8), position=Vec3(-0.4, 0, -0.6))
        self.aileron_r = Entity(parent=wing_r, model='cube', color=color.dark_gray, scale=Vec3(3.2, 0.08, 0.8), position=Vec3(0.4, 0, -0.6))

        # Dual Vertical Fins (tilted)
        tail_l = Entity(parent=self, model='cube', color=color.rgb(112, 128, 144), scale=Vec3(0.15, 5.0, 4.0), position=Vec3(-1.0, 2.5, -11.0), rotation_x=15, rotation_z=15)
        tail_r = Entity(parent=self, model='cube', color=color.rgb(112, 128, 144), scale=Vec3(0.15, 5.0, 4.0), position=Vec3(1.0, 2.5, -11.0), rotation_x=15, rotation_z=-15)
        self.rudder = Entity(parent=tail_l, model='cube', color=color.gray, scale=Vec3(0.12, 4.2, 0.8), position=Vec3(0, -0.1, -0.5))

        # Horizontal Stabilators (moving)
        stab_l = Entity(parent=self, model='cube', color=color.rgb(112, 128, 144), scale=Vec3(4.5, 0.08, 2.5), position=Vec3(-3.2, -0.1, -12.0), rotation_y=-20)
        stab_r = Entity(parent=self, model='cube', color=color.rgb(112, 128, 144), scale=Vec3(4.5, 0.08, 2.5), position=Vec3(3.2, -0.1, -12.0), rotation_y=20)
        self.elevators.extend([stab_l, stab_r]) # On fighter, the whole stab acts as elevator

        # Engine nozzles (afterburners)
        nozzle_l = Entity(parent=self, model='cylinder', color=color.dark_gray, scale=Vec3(0.8, 1.2, 0.8), position=Vec3(-0.6, -0.1, -14.2), rotation_x=90)
        nozzle_r = Entity(parent=self, model='cylinder', color=color.dark_gray, scale=Vec3(0.8, 1.2, 0.8), position=Vec3(0.6, -0.1, -14.2), rotation_x=90)
        # Inside orange glow representing thrust flame
        flame = Entity(parent=self, model='cone', color=color.orange, scale=Vec3(0.7, 0.01, 0.7), position=Vec3(0, -0.1, -14.8), rotation_x=-90)
        self.turbines.append(flame) # use turbine loop to expand flame

        # Retractable Landing Gear nodes
        gear_n = Entity(parent=self, position=Vec3(0, -1.0, 8.0))
        Entity(parent=gear_n, model='cylinder', color=color.gray, scale=Vec3(0.1, 1.2, 0.1), rotation_x=90)
        Entity(parent=gear_n, model='cylinder', color=color.black, scale=Vec3(0.5, 0.2, 0.5), position=Vec3(0, -0.6, 0))

        gear_l = Entity(parent=self, position=Vec3(-2.2, -1.0, -3.0))
        Entity(parent=gear_l, model='cylinder', color=color.gray, scale=Vec3(0.15, 1.5, 0.15), rotation_x=90)
        Entity(parent=gear_l, model='cylinder', color=color.black, scale=Vec3(0.8, 0.3, 0.8), position=Vec3(0, -0.75, 0))

        gear_r = Entity(parent=self, position=Vec3(2.2, -1.0, -3.0))
        Entity(parent=gear_r, model='cylinder', color=color.gray, scale=Vec3(0.15, 1.5, 0.15), rotation_x=90)
        Entity(parent=gear_r, model='cylinder', color=color.black, scale=Vec3(0.8, 0.3, 0.8), position=Vec3(0, -0.75, 0))
        
        self.landing_gear_nodes.extend([gear_n, gear_l, gear_r])

        # Lights
        light_l = Entity(parent=wing_l, model='sphere', color=color.red, scale=0.4, position=Vec3(-3.9, 0.1, 0), emissive=True)
        light_r = Entity(parent=wing_r, model='sphere', color=color.green, scale=0.4, position=Vec3(3.9, 0.1, 0), emissive=True)
        self.nav_lights.extend([light_l, light_r])

    def _build_cargo_plane(self):
        """Assembles a mammoth cargo transport aircraft (C-17 style)."""
        # Huge fuselage (wide and deep)
        fuselage = Entity(parent=self, model='cube', color=color.gray, scale=Vec3(6.5, 6.5, 55.0), position=Vec3(0, 0, 0))
        nose = Entity(parent=self, model='sphere', color=color.gray, scale=Vec3(6.5, 6.3, 7.0), position=Vec3(0, 0.1, 28.0))
        cockpit = Entity(parent=nose, model='quad', color=color.black, scale=(4.0, 1.0), position=(0, 0.8, 0.5), rotation_x=-20)

        # High-wing mount (wings on top of fuselage)
        wing_l = Entity(parent=self, model='cube', color=color.light_gray, scale=Vec3(32.0, 0.3, 7.0), position=Vec3(-18.0, 3.0, 2.0), rotation_y=-20, rotation_z=-6)
        wing_r = Entity(parent=self, model='cube', color=color.light_gray, scale=Vec3(32.0, 0.3, 7.0), position=Vec3(18.0, 3.0, 2.0), rotation_y=20, rotation_z=6)

        self.flaps_l = Entity(parent=wing_l, model='cube', color=color.dark_gray, scale=Vec3(16.0, 0.2, 1.2), position=Vec3(0.2, 0, -1.0))
        self.flaps_r = Entity(parent=wing_r, model='cube', color=color.dark_gray, scale=Vec3(16.0, 0.2, 1.2), position=Vec3(-0.2, 0, -1.0))
        self.aileron_l = Entity(parent=wing_l, model='cube', color=color.gray, scale=Vec3(10.0, 0.2, 1.0), position=Vec3(-0.6, 0, -1.0))
        self.aileron_r = Entity(parent=wing_r, model='cube', color=color.gray, scale=Vec3(10.0, 0.2, 1.0), position=Vec3(0.6, 0, -1.0))

        # Quad under-wing engines
        for side, wing in [(-1, wing_l), (1, wing_r)]:
            for off_x, name in [(0.3, 'inner'), (0.7, 'outer')]:
                eng_pod = Entity(parent=wing, model='cylinder', color=color.gray, scale=Vec3(2.5, 2.5, 6.0), position=Vec3(side * off_x * 15.0, -3.0, 1.5), rotation_y=side*20, rotation_x=90)
                turbine = Entity(parent=eng_pod, model='cube', color=color.black, scale=Vec3(2.2, 0.1, 2.2), position=Vec3(0, 0.48, 0))
                self.turbines.append(turbine)

        # T-Tail configuration (Stabilizer on top of vertical fin)
        tail_fin = Entity(parent=self, model='cube', color=color.gray, scale=Vec3(0.6, 15.0, 9.0), position=Vec3(0, 8.0, -23.0), rotation_x=25)
        self.rudder = Entity(parent=tail_fin, model='cube', color=color.dark_gray, scale=Vec3(0.5, 13.0, 1.8), position=Vec3(0, -0.1, -0.6))
        
        t_stab = Entity(parent=tail_fin, model='cube', color=color.light_gray, scale=Vec3(16.0, 0.2, 4.0), position=Vec3(0, 7.3, -2.5))
        self.elevators.append(Entity(parent=t_stab, model='cube', color=color.gray, scale=Vec3(15.0, 0.15, 1.0), position=Vec3(0, 0, -0.8)))

        # Sponson gear housing on sides of fuselage with multiple wheels
        # Left Side gear
        gear_box_l = Entity(parent=self, model='cube', color=color.gray, scale=Vec3(1.5, 3.0, 12.0), position=Vec3(-3.8, -1.5, 0.0))
        gear_l_node = Entity(parent=self, position=Vec3(-3.8, -2.5, 0.0))
        # 3 wheel pairs on left
        for z_off in [-3.0, 0.0, 3.0]:
            Entity(parent=gear_l_node, model='cylinder', color=color.black, scale=Vec3(1.8, 0.8, 1.8), position=Vec3(0, -0.8, z_off), rotation_z=90)
            
        # Right Side gear
        gear_box_r = Entity(parent=self, model='cube', color=color.gray, scale=Vec3(1.5, 3.0, 12.0), position=Vec3(3.8, -1.5, 0.0))
        gear_r_node = Entity(parent=self, position=Vec3(3.8, -2.5, 0.0))
        for z_off in [-3.0, 0.0, 3.0]:
            Entity(parent=gear_r_node, model='cylinder', color=color.black, scale=Vec3(1.8, 0.8, 1.8), position=Vec3(0, -0.8, z_off), rotation_z=90)
            
        # Nose Gear
        gear_n_node = Entity(parent=self, position=Vec3(0, -3.2, 20.0))
        Entity(parent=gear_n_node, model='cylinder', color=color.gray, scale=Vec3(0.2, 3.0, 0.2), rotation_x=90)
        Entity(parent=gear_n_node, model='cylinder', color=color.black, scale=Vec3(1.2, 0.6, 1.2), position=Vec3(0, -1.5, 0))
        
        self.landing_gear_nodes.extend([gear_n_node, gear_l_node, gear_r_node])

        # Lights
        light_l = Entity(parent=wing_l, model='sphere', color=color.red, scale=0.8, position=Vec3(-15.8, 0.15, 0), emissive=True)
        light_r = Entity(parent=wing_r, model='sphere', color=color.green, scale=0.8, position=Vec3(15.8, 0.15, 0), emissive=True)
        self.nav_lights.extend([light_l, light_r])

    def _build_private_jet(self):
        """Assembles a sleek private executive business jet."""
        # Fuselage (slim, pointed nose)
        fuselage = Entity(parent=self, model='cube', color=color.white, scale=Vec3(2.5, 2.5, 28.0), position=Vec3(0, 0, 0))
        nose = Entity(parent=self, model='sphere', color=color.white, scale=Vec3(2.5, 2.4, 4.5), position=Vec3(0, -0.02, 14.0))
        
        # Gold accent stripe along fuselage
        stripe_l = Entity(parent=self, model='quad', color=color.gold, scale=(26.0, 0.15), position=(-1.26, -0.3, 0), rotation_y=90)
        stripe_r = Entity(parent=self, model='quad', color=color.gold, scale=(26.0, 0.15), position=(1.26, -0.3, 0), rotation_y=-90)

        # Wings (aft swept, low wing)
        wing_l = Entity(parent=self, model='cube', color=color.white, scale=Vec3(12.0, 0.15, 2.5), position=Vec3(-7.0, -0.6, -1.0), rotation_y=-22, rotation_z=-3)
        wing_r = Entity(parent=self, model='cube', color=color.white, scale=Vec3(12.0, 0.15, 2.5), position=Vec3(7.0, -0.6, -1.0), rotation_y=22, rotation_z=3)

        self.flaps_l = Entity(parent=wing_l, model='cube', color=color.dark_gray, scale=Vec3(6.0, 0.1, 0.6), position=Vec3(0.2, 0, -0.4))
        self.flaps_r = Entity(parent=wing_r, model='cube', color=color.dark_gray, scale=Vec3(6.0, 0.1, 0.6), position=Vec3(-0.2, 0, -0.4))
        self.aileron_l = Entity(parent=wing_l, model='cube', color=color.gray, scale=Vec3(5.0, 0.1, 0.6), position=Vec3(-0.5, 0, -0.4))
        self.aileron_r = Entity(parent=wing_r, model='cube', color=color.gray, scale=Vec3(5.0, 0.1, 0.6), position=Vec3(0.5, 0, -0.4))

        # Rear-mounted twin engines (aft fuselage mount)
        eng_l = Entity(parent=self, model='cylinder', color=color.white, scale=Vec3(1.2, 1.2, 4.0), position=Vec3(-1.8, 0.8, -9.0), rotation_x=90)
        turbine_l = Entity(parent=eng_l, model='cube', color=color.black, scale=Vec3(1.0, 0.05, 1.0), position=Vec3(0, 0.48, 0))
        
        eng_r = Entity(parent=self, model='cylinder', color=color.white, scale=Vec3(1.2, 1.2, 4.0), position=Vec3(1.8, 0.8, -9.0), rotation_x=90)
        turbine_r = Entity(parent=eng_r, model='cube', color=color.black, scale=Vec3(1.0, 0.05, 1.0), position=Vec3(0, 0.48, 0))
        self.turbines.extend([turbine_l, turbine_r])

        # T-Tail vertical fin & horizontal stab
        tail_fin = Entity(parent=self, model='cube', color=color.white, scale=Vec3(0.3, 6.0, 4.0), position=Vec3(0, 3.5, -11.0), rotation_x=30)
        self.rudder = Entity(parent=tail_fin, model='cube', color=color.dark_gray, scale=Vec3(0.25, 5.0, 0.8), position=Vec3(0, -0.1, -0.5))
        
        t_stab = Entity(parent=tail_fin, model='cube', color=color.white, scale=Vec3(7.0, 0.1, 2.0), position=Vec3(0, 2.9, -1.0))
        self.elevators.append(Entity(parent=t_stab, model='cube', color=color.gray, scale=Vec3(6.5, 0.08, 0.5), position=Vec3(0, 0, -0.4)))

        # Gear (retractable)
        gear_n = Entity(parent=self, position=Vec3(0, -1.2, 10.0))
        Entity(parent=gear_n, model='cylinder', color=color.gray, scale=Vec3(0.1, 1.5, 0.1), rotation_x=90)
        Entity(parent=gear_n, model='cylinder', color=color.black, scale=Vec3(0.6, 0.25, 0.6), position=Vec3(0, -0.75, 0))

        gear_l = Entity(parent=self, position=Vec3(-3.0, -1.2, -1.5))
        Entity(parent=gear_l, model='cylinder', color=color.gray, scale=Vec3(0.15, 1.8, 0.15), rotation_x=90)
        Entity(parent=gear_l, model='cylinder', color=color.black, scale=Vec3(0.9, 0.35, 0.9), position=Vec3(0, -0.9, 0))

        gear_r = Entity(parent=self, position=Vec3(3.0, -1.2, -1.5))
        Entity(parent=gear_r, model='cylinder', color=color.gray, scale=Vec3(0.15, 1.8, 0.15), rotation_x=90)
        Entity(parent=gear_r, model='cylinder', color=color.black, scale=Vec3(0.9, 0.35, 0.9), position=Vec3(0, -0.9, 0))
        
        self.landing_gear_nodes.extend([gear_n, gear_l, gear_r])

        # Lights
        light_l = Entity(parent=wing_l, model='sphere', color=color.red, scale=0.5, position=Vec3(-5.9, 0.08, 0), emissive=True)
        light_r = Entity(parent=wing_r, model='sphere', color=color.green, scale=0.5, position=Vec3(5.9, 0.08, 0), emissive=True)
        self.nav_lights.extend([light_l, light_r])

    def animate(self, dt, controls, thrust_ratio, spooled_thrust, time):
        """Animates control surfaces, landing gears, engines, and strobe navigation lights."""
        # 1. Turbines rotation
        # Spin proportional to actual thrust spooled
        spin_speed = spooled_thrust * 0.01
        for turbine in self.turbines:
            # Check if afterburner flame (for fighter jet)
            if self.aircraft_type == "Fighter Jet":
                # scale flame length based on thrust ratio
                # spooled thrust ratio
                flame_len = spooled_thrust / 130000.0
                turbine.scale_y = flame_len * 6.5 + 0.01
                # toggle visibility
                turbine.enabled = flame_len > 0.4
            else:
                turbine.rotation_y += spin_speed * dt * 100

        # 2. Control surfaces
        # Ailerons (roll): roll left makes left aileron rotate up, right down
        r_in = controls.get("roll", 0.0)
        if self.aileron_l:
            self.aileron_l.rotation_x = -r_in * 30
        if self.aileron_r:
            self.aileron_r.rotation_x = r_in * 30

        # Flaps: move down with flaps percentage
        fl_val = controls.get("flaps", 0.0)
        if self.flaps_l:
            self.flaps_l.rotation_x = fl_val * 40
        if self.flaps_r:
            self.flaps_r.rotation_x = fl_val * 40

        # Rudder (yaw)
        y_in = controls.get("yaw", 0.0)
        if self.rudder:
            self.rudder.rotation_y = -y_in * 25

        # Elevators (pitch)
        p_in = controls.get("pitch", 0.0)
        for el in self.elevators:
            # Whole horizontal stabilizer or elevator rotates
            el.rotation_x = p_in * 20

        # 3. Retractable landing gear animation
        gear_deploy = controls.get("gear", True)
        target_anim = 1.0 if gear_deploy else 0.0
        
        # Smoothly interpolate gear retraction
        if self.gear_anim_y != target_anim:
            self.gear_anim_y += (target_anim - self.gear_anim_y) * 2.0 * dt
            # Clamp close values
            if abs(self.gear_anim_y - target_anim) < 0.01:
                self.gear_anim_y = target_anim
                
            # Apply scale/rotation to hide gears inside body
            for node in self.landing_gear_nodes:
                # Pivot gears: scale down/up to simulate tucking inside fuselage
                node.scale_y = self.gear_anim_y
                # If fully retracted, disable rendering of wheels to optimize
                node.enabled = self.gear_anim_y > 0.05

        # 4. Blink navigation lights
        # Periodic blinking (every 1.5 seconds)
        blink = int(time * 2.0) % 2 == 0
        for light in self.nav_lights:
            light.enabled = blink

    def destroy_mesh(self):
        """Clears aircraft subcomponents from memory."""
        # Unparent all child entities to prevent leak
        for c in self.children:
            destroy(c)
        destroy(self)
