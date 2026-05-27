# Dynamic procedural sound generator utilizing Pygame mixer and NumPy.

import pygame
import numpy as np
import math
from flight_simulator.settings import (
    SOUND_ENABLED, ENGINE_VOLUME_MULTIPLIER, 
    AMBIENT_VOLUME_MULTIPLIER, WARN_ALARM_VOLUME
)

class SoundManager:
    def __init__(self):
        self.enabled = SOUND_ENABLED
        self.channels = {}
        self.sounds = {}
        
        if not self.enabled:
            print("[Sound Manager] Sound is disabled in settings.")
            return

        try:
            # Initialize Pygame Mixer
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            print("[Sound Manager] Pygame mixer initialized successfully.")
            self._synthesize_procedural_sounds()
            self._start_ambient_loops()
        except Exception as e:
            print(f"[Sound Manager] Failed to initialize Pygame mixer: {e}. Running in silent mode.")
            self.enabled = False

    def _synthesize_procedural_sounds(self):
        """Synthesizes math-based waveforms using NumPy and loads them as Pygame Sounds."""
        sample_rate = 44100
        
        # Helper: Create 16-bit stereo numpy array from mono float array
        def make_pygame_sound(mono_array):
            # Scale to 16-bit range (-32767 to 32767)
            scaled = np.int16(mono_array * 32767)
            # Make stereo
            stereo = np.column_stack((scaled, scaled))
            return pygame.mixer.Sound(buffer=stereo)

        # 1. TURBINE WHINE (Sine wave with harmonics)
        # Duration: 1.0 second loop
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        # Base frequency 250 Hz (idle) with 2nd, 3rd, 4th harmonics
        base_freq = 220.0
        wave = 0.5 * np.sin(2 * np.pi * base_freq * t)
        wave += 0.25 * np.sin(2 * np.pi * (base_freq * 2) * t)
        wave += 0.12 * np.sin(2 * np.pi * (base_freq * 3) * t)
        wave += 0.08 * np.sin(2 * np.pi * (base_freq * 5) * t)
        # Apply smoothing fade in/out at loop boundaries to prevent clicking
        fade = np.ones_like(t)
        fade_len = 800
        fade[:fade_len] = np.linspace(0, 1, fade_len)
        fade[-fade_len:] = np.linspace(1, 0, fade_len)
        self.sounds["turbine"] = make_pygame_sound(wave * fade * 0.3)

        # 2. WIND NOISE (White noise bandpass filtered)
        # Generate raw white noise
        white_noise = np.random.uniform(-1.0, 1.0, int(sample_rate * 2.0))
        # Simple rolling average to act as low-pass filter (rumble)
        filtered = np.convolve(white_noise, np.ones(25)/25, mode='same')
        # Normalize
        filtered /= np.max(np.abs(filtered))
        # Loop boundary smoothing
        t_wind = np.linspace(0, 2.0, len(filtered), endpoint=False)
        fade_wind = np.ones_like(t_wind)
        fade_len_w = 2000
        fade_wind[:fade_len_w] = np.linspace(0, 1, fade_len_w)
        fade_wind[-fade_len_w:] = np.linspace(1, 0, fade_len_w)
        self.sounds["wind"] = make_pygame_sound(filtered * fade_wind * 0.25)

        # 3. WARNING ALARM KLAXON (Dual alternating beeps)
        # 0.5 second beep duration (250ms at 800Hz, 250ms silence)
        alarm_dur = 0.5
        t_alarm = np.linspace(0, alarm_dur, int(sample_rate * alarm_dur), endpoint=False)
        beep_wave = np.sin(2 * np.pi * 950.0 * t_alarm)
        # Silence second half
        beep_wave[int(len(t_alarm)/2):] = 0.0
        # Smooth clicks
        beep_fade = np.ones_like(t_alarm)
        beep_fade[int(len(t_alarm)/2)-200:int(len(t_alarm)/2)] = np.linspace(1, 0, 200)
        beep_fade[:200] = np.linspace(0, 1, 200)
        self.sounds["alarm"] = make_pygame_sound(beep_wave * beep_fade * 0.5)

        # 4. GEAR CLUNK (Low frequency rumble for extension/retraction)
        gear_dur = 1.5
        t_gear = np.linspace(0, gear_dur, int(sample_rate * gear_dur), endpoint=False)
        gear_wave = np.random.uniform(-1.0, 1.0, len(t_gear))
        # Heavy low pass filter
        gear_filtered = np.convolve(gear_wave, np.ones(100)/100, mode='same')
        # Exponential envelope (starts loud, decays)
        envelope = np.exp(-3.0 * t_gear)
        self.sounds["gear_clunk"] = make_pygame_sound(gear_filtered * envelope * 0.8)

        print("[Sound Manager] Procedural audio waveforms synthesized.")

    def _start_ambient_loops(self):
        """Starts looping engine and wind sounds on dedicated channels."""
        self.channels["turbine"] = pygame.mixer.Channel(0)
        self.channels["wind"] = pygame.mixer.Channel(1)
        self.channels["alarm"] = pygame.mixer.Channel(2)
        self.channels["effects"] = pygame.mixer.Channel(3)

        self.channels["turbine"].play(self.sounds["turbine"], loops=-1)
        self.channels["turbine"].set_volume(0.1)

        self.channels["wind"].play(self.sounds["wind"], loops=-1)
        self.channels["wind"].set_volume(0.0)

    def update(self, dt, airspeed_knots, spooled_thrust_ratio, stalled, pull_up_warn):
        """
        Dynamically adjusts volume/pitch of engine & wind and triggers warning beeps.
        """
        if not self.enabled:
            return

        # 1. Adjust engine turbine pitch and volume based on spool ratio (0.0 to 1.0)
        # Note: Pygame doesn't allow direct pitch modification, so we approximate
        # by adjusting volume mix of high frequency whistle and low rumble.
        # Spooled thrust controls turbine channel volume
        engine_vol = (0.05 + 0.35 * spooled_thrust_ratio) * ENGINE_VOLUME_MULTIPLIER
        self.channels["turbine"].set_volume(engine_vol)

        # 2. Adjust wind whistle volume based on airspeed
        # Speed 0 knots -> volume 0.0, speed 300 knots -> volume 0.45
        wind_vol = min(0.6, (airspeed_knots / 350.0)) * AMBIENT_VOLUME_MULTIPLIER
        self.channels["wind"].set_volume(wind_vol)

        # 3. Adjust alarm states (Stall and Pull Up trigger beeps)
        if stalled or pull_up_warn:
            if not self.channels["alarm"].get_busy():
                self.channels["alarm"].play(self.sounds["alarm"], loops=-1)
                self.channels["alarm"].set_volume(WARN_ALARM_VOLUME)
        else:
            if self.channels["alarm"].get_busy():
                self.channels["alarm"].stop()

    def play_gear_sound(self):
        """Triggers a low clunk rumble when landing gear position changes."""
        if not self.enabled:
            return
        self.channels["effects"].play(self.sounds["gear_clunk"])

    def stop_all(self):
        """Shuts down audio channels."""
        if not self.enabled:
            return
        for chan in self.channels.values():
            chan.stop()
        print("[Sound Manager] All sounds stopped.")
