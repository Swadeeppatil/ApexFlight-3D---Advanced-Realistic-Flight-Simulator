# Flight Selection menus, Aircraft Hangar dashboard, Pilot profile stats, settings.

import os
from ursina import Entity, Button, Text, camera, color, destroy, Vec3, Vec2, invoke, time
from flight_simulator.settings import AIRCRAFT_PRESETS
from flight_simulator.database.pilot_db import get_stats, get_unlocked_aircraft, get_flight_history

class UIManager:
    def __init__(self, start_flight_callback, toggle_cv_callback, exit_game_callback):
        self.start_flight_callback = start_flight_callback
        self.toggle_cv_callback = toggle_cv_callback
        self.exit_game_callback = exit_game_callback
        
        # UI state
        self.menu_parent = None
        self.active_tab = "HANGAR" # HANGAR, STATS, SETTINGS, MISSIONS
        self.selected_aircraft = "Passenger Jet"
        self.cv_controls_enabled = True
        
        # Weather/Time configurations for flight launch
        self.selected_weather = "Clear"
        self.selected_time = 12.0 # Noon
        
        # Sound and Sens sliders
        self.sound_enabled = True
        self.control_sensitivity = 1.5
        
        # Unlocked status
        self.unlocked_aircraft = {"Passenger Jet": True, "Cargo Transporter": True, "Private Business Jet": False, "Fighter Jet": False}
        self.pilot_xp = 0
        self.pilot_rank = "Student Pilot"
        
        # Hangar 3D Preview entity
        self.hangar_preview_aircraft = None
        self.hangar_rotator = None

        # Build UI on initialization
        self.show_main_menu()

    def show_main_menu(self):
        """Displays the main aviation cockpit menu."""
        # Clean old elements
        self.hide_menu()
        
        # Load latest db stats and unlocks
        self._load_pilot_data()
        
        # Primary container for menu
        self.menu_parent = Entity(parent=camera.ui)
        
        # Background glass panel
        Entity(
            parent=self.menu_parent,
            model='quad',
            color=color.rgba(12, 18, 15, 230),
            scale=(1.4, 0.85),
            position=(0, 0),
            z=10
        )
        
        # Left navigation side bar
        self._build_sidebar()
        
        # Right workspace panel (depends on active_tab)
        if self.active_tab == "HANGAR":
            self._build_hangar_tab()
        elif self.active_tab == "STATS":
            self._build_stats_tab()
        elif self.active_tab == "SETTINGS":
            self._build_settings_tab()
        elif self.active_tab == "MISSIONS":
            self._build_missions_tab()

    def hide_menu(self):
        """Removes the main menu UI elements from camera.ui."""
        self._destroy_hangar_preview()
        if self.menu_parent:
            destroy(self.menu_parent)
            self.menu_parent = None

    def _load_pilot_data(self):
        """Queries SQLite database to update local stats and unlocks."""
        try:
            db_stats = get_stats()
            self.pilot_xp = int(db_stats.get("pilot_xp", 0))
            self.unlocked_aircraft = get_unlocked_aircraft()
            
            # Rank brackets
            if self.pilot_xp < 200:
                self.pilot_rank = "Student Pilot"
            elif self.pilot_xp < 500:
                self.pilot_rank = "Private Pilot (PPL)"
            elif self.pilot_xp < 1200:
                self.pilot_rank = "Commercial Aviator (CPL)"
            else:
                self.pilot_rank = "Airline Captain (ATP)"
        except Exception as e:
            print(f"[UI Manager] DB stats fetch failed (normal on first startup): {e}")

    def _build_sidebar(self):
        """Generates left menu navigation panel."""
        sb_parent = Entity(parent=self.menu_parent, position=(-0.5, 0))
        
        # App Title
        Text(
            parent=sb_parent,
            text="APEXFLIGHT 3D",
            color=color.rgb(0, 255, 120),
            scale=2.2,
            position=(-0.16, 0.35)
        )
        Text(
            parent=sb_parent,
            text=f"Rank: {self.pilot_rank}\nXP: {self.pilot_xp}",
            color=color.light_gray,
            scale=0.9,
            position=(-0.16, 0.28)
        )

        tabs = [
            ("HANGAR", "AIRCRAFT HANGAR", 0.16),
            ("MISSIONS", "FLIGHT MISSIONS", 0.08),
            ("STATS", "PILOT STATISTICS", 0.0),
            ("SETTINGS", "SYSTEM SETTINGS", -0.08)
        ]
        
        for tab_id, label, y_pos in tabs:
            is_active = self.active_tab == tab_id
            btn = Button(
                parent=sb_parent,
                text=label,
                color=color.rgba(0, 255, 100, 80) if is_active else color.rgba(30, 40, 35, 120),
                scale=(0.32, 0.06),
                position=(-0.02, y_pos),
                highlight_color=color.rgba(0, 255, 120, 160)
            )
            # Create click callback closure
            def click_cb(tid=tab_id):
                self.active_tab = tid
                self.show_main_menu()
            btn.on_click = click_cb

        # Exit Button
        btn_exit = Button(
            parent=sb_parent,
            text="EXIT SIMULATOR",
            color=color.rgba(180, 50, 50, 150),
            scale=(0.32, 0.06),
            position=(-0.02, -0.3),
            highlight_color=color.rgba(220, 50, 50, 220)
        )
        btn_exit.on_click = self.exit_game_callback

    def _build_hangar_tab(self):
        """Hangar panel: displays stats, unlocks, and sets up 3D airplane rotating model."""
        pane = Entity(parent=self.menu_parent, position=(0.2, 0))
        
        # Tab Header
        Text(parent=pane, text="AIRCRAFT SELECTION HANGAR", color=color.rgb(0, 255, 255), scale=1.6, position=(-0.35, 0.35))
        
        # Aircraft List buttons
        ac_types = ["Passenger Jet", "Cargo Transporter", "Private Business Jet", "Fighter Jet"]
        for idx, ac_name in enumerate(ac_types):
            is_selected = self.selected_aircraft == ac_name
            is_unlocked = self.unlocked_aircraft.get(ac_name, False)
            
            lbl_text = ac_name
            if not is_unlocked:
                # Add unlock thresholds labels
                req = "Locked"
                if ac_name == "Private Business Jet": req = "Locked (500 XP)"
                elif ac_name == "Fighter Jet": req = "Locked (1500 XP)"
                lbl_text = f"{ac_name}\n[{req}]"
                
            ac_btn = Button(
                parent=pane,
                text=lbl_text,
                color=color.rgba(0, 180, 255, 120) if is_selected else (color.rgba(40, 50, 60, 120) if is_unlocked else color.rgba(20, 20, 20, 160)),
                scale=(0.22, 0.08 if not is_unlocked else 0.06),
                position=(-0.25, 0.22 - idx * 0.09),
                highlight_color=color.rgba(0, 220, 255, 180) if is_unlocked else color.rgba(30,30,30,160)
            )
            
            def ac_select_cb(name=ac_name, unlocked=is_unlocked):
                if unlocked:
                    self.selected_aircraft = name
                    self.show_main_menu()
            ac_btn.on_click = ac_select_cb

        # Load performance stats of the selected aircraft
        data = AIRCRAFT_PRESETS[self.selected_aircraft]
        
        # Stats Display Panel
        stats_box = Entity(parent=pane, position=(0.15, -0.05))
        Text(parent=stats_box, text=f"MODEL: {self.selected_aircraft}", scale=1.3, color=color.white, position=(-0.22, 0.38))
        
        perf_metrics = [
            ("Weight (Dry)", f"{int(data['mass_dry'])} kg", data['mass_dry'] / 150000.0),
            ("Max Thrust", f"{int(data['max_thrust'])} N", data['max_thrust'] / 450000.0),
            ("Wing Area", f"{int(data['wing_area'])} sq.m", data['wing_area'] / 300.0),
            ("Maneuverability", "HIGH" if data['roll_rate'] > 30 else ("MEDIUM" if data['roll_rate'] > 15 else "STABLE"), data['roll_rate'] / 120.0),
        ]
        
        for idx, (label, val_str, ratio) in enumerate(perf_metrics):
            y_off = 0.28 - idx * 0.075
            Text(parent=stats_box, text=label, scale=0.8, color=color.light_gray, position=(-0.22, y_off))
            Text(parent=stats_box, text=val_str, scale=0.8, color=color.white, position=(0.05, y_off))
            
            # Progress bar visual
            Entity(parent=stats_box, model='quad', color=color.dark_gray, scale=(0.35, 0.012), position=(-0.05, y_off - 0.025), z=1)
            fill_len = ratio * 0.35
            Entity(
                parent=stats_box,
                model='quad',
                color=color.rgb(0, 220, 255),
                scale=(fill_len, 0.012),
                position=(-0.05 - (0.35 - fill_len)/2.0, y_off - 0.025),
                z=0.9
            )

        # Launch Flight button (Free Flight)
        launch_btn = Button(
            parent=pane,
            text="LAUNCH FREE FLIGHT",
            color=color.rgba(0, 255, 120, 160),
            scale=(0.4, 0.07),
            position=(0.1, -0.28),
            highlight_color=color.rgba(0, 255, 150, 220)
        )
        def start_free():
            self.start_flight_callback(
                aircraft_name=self.selected_aircraft, 
                weather=self.selected_weather, 
                time_hour=self.selected_time, 
                mission_name=None
            )
        launch_btn.on_click = start_free
        
        # Setup 3D Hangar preview rotation
        self._setup_hangar_preview()

    def _setup_hangar_preview(self):
        """Spawns a rotating 3D version of the aircraft on the screen."""
        self._destroy_hangar_preview()
        
        from flight_simulator.aircraft.aircraft_models import AircraftVisual
        
        # Create preview aircraft positioned in world space
        # Camera is reset, we position preview plane in front of menu
        self.hangar_preview_aircraft = AircraftVisual(
            aircraft_type=self.selected_aircraft,
            position=Vec3(0, -3.2, 10.0), # Positioned in front of default menu camera
            rotation=Vec3(15, -45, 0),
            scale=0.35 if self.selected_aircraft == "Fighter Jet" else (0.1 if self.selected_aircraft == "Cargo Transporter" else 0.15)
        )
        
        # Attach rotator node
        # The rotation is handled in update, but we can set up an entity to update rotation every frame
        self.hangar_rotator = Entity()
        def rotate_preview():
            if self.hangar_preview_aircraft and self.hangar_preview_aircraft.enabled:
                self.hangar_preview_aircraft.rotation_y += 18 * time.dt
        self.hangar_rotator.update = rotate_preview

    def _destroy_hangar_preview(self):
        """Cleans up preview aircraft."""
        if self.hangar_rotator:
            destroy(self.hangar_rotator)
            self.hangar_rotator = None
        if self.hangar_preview_aircraft:
            self.hangar_preview_aircraft.destroy_mesh()
            self.hangar_preview_aircraft = None

    def _build_missions_tab(self):
        """Missions panel: lists challenges (takeoff, ILS storm, engine fire landing)."""
        pane = Entity(parent=self.menu_parent, position=(0.2, 0))
        Text(parent=pane, text="FLIGHT MISSIONS CHALLENGES", color=color.rgb(0, 255, 255), scale=1.6, position=(-0.35, 0.35))
        
        missions = [
            {
                "name": "First Solo Takeoff",
                "desc": "Takeoff, climb to 2000ft in a Private Jet under clear skies.",
                "weather": "Clear", "time": 12.0, "aircraft": "Private Business Jet", "unl_req": "Private Business Jet"
            },
            {
                "name": "Storm ILS Landing",
                "desc": "Land a heavy Cargo plane in zero visibility during a severe storm.",
                "weather": "Storm", "time": 17.5, "aircraft": "Cargo Transporter", "unl_req": "Cargo Transporter"
            },
            {
                "name": "Engine Out Glide Challenge",
                "desc": "Flameout at 5000ft. Glide to Metro International runway safely.",
                "weather": "Fog", "time": 9.0, "aircraft": "Passenger Jet", "unl_req": "Passenger Jet"
            },
            {
                "name": "Fighter Interception (Combat)",
                "desc": "Interceptor mission! Dodge lock-ons and lock onto enemy drone paths.",
                "weather": "Clear", "time": 12.0, "aircraft": "Fighter Jet", "unl_req": "Fighter Jet"
            }
        ]
        
        for idx, ms in enumerate(missions):
            y_pos = 0.22 - idx * 0.14
            is_unlocked = self.unlocked_aircraft.get(ms["unl_req"], False)
            
            box = Entity(
                parent=pane,
                model='quad',
                color=color.rgba(20, 30, 40, 100) if is_unlocked else color.rgba(10, 10, 10, 140),
                scale=(0.85, 0.12),
                position=(0.05, y_pos)
            )
            
            # Mission metadata
            Text(parent=box, text=ms["name"].upper(), scale=1.0, color=color.rgb(0, 255, 120) if is_unlocked else color.dark_gray, position=(-0.48, 0.35))
            Text(parent=box, text=ms["desc"], scale=0.8, color=color.light_gray if is_unlocked else color.gray, position=(-0.48, -0.05))
            Text(parent=box, text=f"Aircraft: {ms['aircraft']} | Weather: {ms['weather']}", scale=0.7, color=color.gray, position=(-0.48, -0.38))
            
            if is_unlocked:
                btn_start = Button(
                    parent=box,
                    text="FLY MISSION",
                    color=color.rgba(0, 255, 120, 180),
                    scale=(0.18, 0.6),
                    position=(0.38, 0),
                    highlight_color=color.rgba(0, 255, 150, 230)
                )
                # closure
                def start_ms(m_data=ms):
                    self.start_flight_callback(
                        aircraft_name=m_data["aircraft"],
                        weather=m_data["weather"],
                        time_hour=m_data["time"],
                        mission_name=m_data["name"]
                    )
                btn_start.on_click = start_ms
            else:
                Text(parent=box, text="[AIRCRAFT LOCKED]", scale=0.75, color=color.red, position=(0.28, 0))

    def _build_stats_tab(self):
        """Stats panel: displays logs and metrics from DB."""
        pane = Entity(parent=self.menu_parent, position=(0.2, 0))
        Text(parent=pane, text="PILOT LOGBOOK & STATISTICS", color=color.rgb(0, 255, 255), scale=1.6, position=(-0.35, 0.35))
        
        # Load total records
        try:
            db_stats = get_stats()
            total_hours = db_stats.get("total_flight_hours", 0.0)
            takeoffs = int(db_stats.get("total_takeoffs", 0))
            landings = int(db_stats.get("total_landings", 0))
            crashes = int(db_stats.get("total_crashes", 0))
            
            # Layout Summary boxes
            metrics = [
                ("HOURS", f"{total_hours:.2f}h"),
                ("TAKEOFFS", str(takeoffs)),
                ("LANDINGS", str(landings)),
                ("CRASHES", str(crashes))
            ]
            
            for idx, (label, val) in enumerate(metrics):
                mb = Entity(parent=pane, model='quad', color=color.rgba(20, 40, 30, 100), scale=(0.18, 0.1), position=(-0.3 + idx * 0.22, 0.22))
                Text(parent=mb, text=label, scale=0.7, color=color.light_gray, position=(-0.45, 0.25))
                Text(parent=mb, text=val, scale=1.3, color=color.rgb(0, 255, 120), position=(-0.45, -0.15))
        except Exception as e:
            print(f"[UI Manager] Stats render error: {e}")

        # Flight Logbook Table (recent flights)
        Text(parent=pane, text="RECENT LOGGED FLIGHTS", color=color.light_gray, scale=1.0, position=(-0.42, 0.1))
        
        logs = get_flight_history(limit=5)
        
        # Draw table headers
        headers = [("TIMESTAMP", -0.42), ("AIRCRAFT", -0.2), ("ROUTE", 0.05), ("DURATION", 0.25), ("STATUS", 0.42)]
        for h_name, x_p in headers:
            Text(parent=pane, text=h_name, scale=0.7, color=color.rgb(0, 255, 255), position=(x_p, 0.05))
            
        # Draw log rows
        if not logs:
            Text(parent=pane, text="No flights logged yet. Complete a flight to populate logbook.", scale=0.8, color=color.gray, position=(-0.42, -0.05))
        else:
            for r_idx, row in enumerate(logs):
                y_p = -0.01 - r_idx * 0.05
                # format route
                route_str = f"{row['start_airport'][:4]} -> {row['end_airport'][:4]}" if row['start_airport'] else "Local Flight"
                # duration
                dur_str = f"{int(row['duration_sec'])}s" if row['duration_sec'] < 60 else f"{int(row['duration_sec']/60)}m {int(row['duration_sec']%60)}s"
                
                # columns
                Text(parent=pane, text=row['timestamp'][:16], scale=0.75, color=color.white, position=(-0.42, y_p))
                Text(parent=pane, text=row['aircraft'], scale=0.75, color=color.white, position=(-0.2, y_p))
                Text(parent=pane, text=route_str, scale=0.75, color=color.white, position=(0.05, y_p))
                Text(parent=pane, text=dur_str, scale=0.75, color=color.white, position=(0.25, y_p))
                
                status_color = color.rgb(0, 255, 100) if "Landed" in row['landing_status'] else color.rgb(255, 50, 50)
                Text(parent=pane, text=row['landing_status'], scale=0.75, color=status_color, position=(0.42, y_p))

    def _build_settings_tab(self):
        """Settings panel: toggles for weather selection, time of day, sensitivity, OpenCV controls."""
        pane = Entity(parent=self.menu_parent, position=(0.2, 0))
        Text(parent=pane, text="FLIGHT & SYSTEM PREFERENCES", color=color.rgb(0, 255, 255), scale=1.6, position=(-0.35, 0.35))
        
        # 1. Weather Setup
        Text(parent=pane, text="ENVIRONMENT WEATHER", scale=0.9, color=color.light_gray, position=(-0.42, 0.24))
        weathers = ["Clear", "Rain", "Storm", "Fog"]
        for idx, w in enumerate(weathers):
            is_active = self.selected_weather == w
            btn = Button(
                parent=pane,
                text=w,
                color=color.rgba(0, 180, 255, 120) if is_active else color.rgba(30, 40, 45, 100),
                scale=(0.14, 0.05),
                position=(-0.34 + idx * 0.16, 0.18),
                highlight_color=color.rgba(0, 220, 255, 180)
            )
            def set_w(weather_name=w):
                self.selected_weather = weather_name
                self.show_main_menu()
            btn.on_click = set_w

        # 2. Time of Day
        Text(parent=pane, text="TIME OF DAY", scale=0.9, color=color.light_gray, position=(-0.42, 0.08))
        times = [("Sunrise", 6.0), ("Noon", 12.0), ("Sunset", 17.5), ("Midnight", 0.0)]
        for idx, (label, hr) in enumerate(times):
            is_active = self.selected_time == hr
            btn = Button(
                parent=pane,
                text=label,
                color=color.rgba(0, 180, 255, 120) if is_active else color.rgba(30, 40, 45, 100),
                scale=(0.14, 0.05),
                position=(-0.34 + idx * 0.16, 0.02),
                highlight_color=color.rgba(0, 220, 255, 180)
            )
            def set_t(h_val=hr):
                self.selected_time = h_val
                self.show_main_menu()
            btn.on_click = set_t

        # 3. Control Mode Configuration
        Text(parent=pane, text="PRIMARY CONTROL OPTIONS", scale=0.9, color=color.light_gray, position=(-0.42, -0.08))
        
        cv_toggle_btn = Button(
            parent=pane,
            text=f"CV CAM CONTROLS: {'ACTIVE (WEBCAM)' if self.cv_controls_enabled else 'DISABLED (KEYBOARD)'}",
            color=color.rgba(0, 255, 120, 140) if self.cv_controls_enabled else color.rgba(180, 50, 50, 120),
            scale=(0.42, 0.06),
            position=(-0.16, -0.15),
            highlight_color=color.rgba(0, 255, 150, 200)
        )
        def toggle_cv():
            self.cv_controls_enabled = not self.cv_controls_enabled
            self.toggle_cv_callback(self.cv_controls_enabled)
            self.show_main_menu()
        cv_toggle_btn.on_click = toggle_cv
        
        # Sensitivity
        Text(parent=pane, text=f"Steering Sensitivity: {self.control_sensitivity:.1f}x", scale=0.8, color=color.white, position=(-0.42, -0.22))
        
        # Add sensitivity adjustment buttons
        sens_dec = Button(parent=pane, text="-", color=color.dark_gray, scale=(0.05, 0.04), position=(-0.05, -0.22))
        sens_inc = Button(parent=pane, text="+", color=color.dark_gray, scale=(0.05, 0.04), position=(0.05, -0.22))
        
        def adjust_sens(change):
            self.control_sensitivity = max(0.5, min(self.control_sensitivity + change, 3.0))
            self.show_main_menu()
            # Update settings in settings.py or global state if needed
            import flight_simulator.settings as st
            st.GESTURE_SENSITIVITY = self.control_sensitivity
            
        sens_dec.on_click = lambda: adjust_sens(-0.1)
        sens_inc.on_click = lambda: adjust_sens(0.1)
