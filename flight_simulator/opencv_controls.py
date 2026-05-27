# OpenCV and MediaPipe controller module running in a background thread.

import cv2
import mediapipe as mp
import threading
import time
import math
from ursina import Vec3
from flight_simulator.settings import (
    WEBCAM_ID, CAMERA_RESOLUTION, GESTURE_SENSITIVITY, 
    WEBCAM_PREVIEW_SHOW
)

class OpenCVControls:
    def __init__(self):
        # Shared Thread-Safe States
        self.lock = threading.Lock()
        self.roll = 0.0          # -1.0 to 1.0
        self.pitch = 0.0         # -1.0 to 1.0
        self.yaw = 0.0           # -1.0 to 1.0
        self.throttle = 0.5      # 0.0 to 1.0
        self.flaps = 0.0         # 0.0 (up), 0.5 (mid), 1.0 (full)
        self.gear_deploy = True  # True (down), False (up)
        self.brakes = False      # Parking/landing brakes
        
        # Head-tracking camera values
        self.head_pitch = 0.0    # -30 to 30 deg
        self.head_yaw = 0.0      # -60 to 60 deg
        
        self.hand_detected = False
        self.face_detected = False
        self.running = False
        self.thread = None
        self.cap = None

        # MediaPipe initializations
        self.mp_hands = mp.solutions.hands
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils

    def start(self):
        """Starts the background tracking thread."""
        self.running = True
        self.thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self.thread.start()
        print("[OpenCV Controls] Background tracking thread started.")

    def stop(self):
        """Stops the tracking loop and releases camera."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        print("[OpenCV Controls] Tracking thread stopped and resources released.")

    def get_inputs(self):
        """Returns a snapshot of the current control inputs (thread-safe)."""
        with self.lock:
            return {
                "roll": self.roll,
                "pitch": self.pitch,
                "yaw": self.yaw,
                "throttle": self.throttle,
                "flaps": self.flaps,
                "gear": self.gear_deploy,
                "brakes": self.brakes,
                "head_pitch": self.head_pitch,
                "head_yaw": self.head_yaw,
                "active": self.hand_detected
            }

    def _count_fingers(self, hand_landmarks, handedness):
        """Counts how many fingers are extended on a hand."""
        # MediaPipe finger tip & joint indices
        # Thumb: 4, 3, 2. Index: 8, 6. Middle: 12, 10. Ring: 16, 14. Pinky: 20, 18.
        tips = [8, 12, 16, 20]
        pips = [6, 10, 14, 18]
        
        fingers = []
        
        # Check if left or right hand (MediaPipe swaps them due to camera mirroring)
        is_left_hand = handedness.classification[0].label == "Right" # Mirrored
        
        # Thumb detection
        if is_left_hand:
            # Left hand: Thumb is extended if tip X is greater than base X
            if hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x:
                fingers.append(1)
            else:
                fingers.append(0)
        else:
            # Right hand: Thumb is extended if tip X is less than base X
            if hand_landmarks.landmark[4].x < hand_landmarks.landmark[3].x:
                fingers.append(1)
            else:
                fingers.append(0)

        # Other 4 fingers
        for tip, pip in zip(tips, pips):
            if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[pip].y:
                fingers.append(1)
            else:
                fingers.append(0)
                
        return sum(fingers)

    def _tracking_loop(self):
        """Background thread executing capture and computer vision calculations."""
        # Try to open webcam
        self.cap = cv2.VideoCapture(WEBCAM_ID)
        if not self.cap.isOpened():
            print(f"[OpenCV Controls] WARNING: Could not open webcam (ID: {WEBCAM_ID}). Fallback to keyboard controls.")
            self.running = False
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_RESOLUTION[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_RESOLUTION[1])

        # MediaPipe contexts
        with self.mp_hands.Hands(
            max_num_hands=2,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        ) as hands, \
        self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as face_mesh:

            while self.running:
                success, frame = self.cap.read()
                if not success:
                    time.sleep(0.01)
                    continue

                # Mirror frame horizontally for intuitive interaction
                frame = cv2.flip(frame, 1)
                h, w, c = frame.shape

                # Convert to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Run detections
                hand_results = hands.process(rgb_frame)
                face_results = face_mesh.process(rgb_frame)

                # Initialize local inputs for this frame
                t_roll = 0.0
                t_pitch = 0.0
                t_yaw = 0.0
                t_throttle = self.throttle # Keep current throttle unless adjusted
                t_flaps = self.flaps
                t_gear = self.gear_deploy
                t_brakes = self.brakes
                
                hand_found = False

                # 1. PROCESS HANDS FOR FLIGHT CONTROLS
                if hand_results.multi_hand_landmarks:
                    hand_found = True
                    # Categorize hands based on label
                    right_hand_landmarks = None  # Yoke
                    left_hand_landmarks = None   # Throttle / Flaps
                    
                    for lm, handedness in zip(hand_results.multi_hand_landmarks, hand_results.multi_handedness):
                        label = handedness.classification[0].label # Left or Right
                        
                        # Note: Since frame is flipped, "Left" on screen is physical Right hand
                        if label == "Right":  # Screen-right is Left hand (physical)
                            right_hand_landmarks = (lm, handedness)
                        else:                 # Screen-left is Right hand (physical)
                            left_hand_landmarks = (lm, handedness)

                    # --- RIGHT HAND (Yoke: Roll & Pitch) ---
                    if right_hand_landmarks:
                        lm, handedness = right_hand_landmarks
                        self.mp_drawing.draw_landmarks(frame, lm, self.mp_hands.HAND_CONNECTIONS)
                        
                        # Wrist point (landmark 0) is the center of controls
                        wrist = lm.landmark[0]
                        
                        # Center of screen is (0.5, 0.5). Define steering box:
                        # Pitch: Wrist Y offset from screen center
                        # Top-left is (0,0), bottom-right is (1,1)
                        # So raising hand (Y decreases) -> Pitch UP (value increases)
                        y_offset = 0.5 - wrist.y  # Positive is Up, Negative is Down
                        t_pitch = y_offset * GESTURE_SENSITIVITY * 2.0
                        t_pitch = max(-1.0, min(t_pitch, 1.0))

                        # Roll: Wrist X offset from right-half center (0.75)
                        x_offset = wrist.x - 0.75
                        t_roll = x_offset * GESTURE_SENSITIVITY * 3.0
                        t_roll = max(-1.0, min(t_roll, 1.0))
                        
                        # Yaw: Finger angle tilt (simplified yaw gesture, e.g. hand horizontal tilt)
                        # Using index finger base (5) to pinky base (17)
                        dx = lm.landmark[17].x - lm.landmark[5].x
                        dy = lm.landmark[17].y - lm.landmark[5].y
                        tilt_angle = math.atan2(dy, dx)
                        # Map tilt angle (-30 to +30 deg) to Yaw input
                        t_yaw = -math.degrees(tilt_angle) / 25.0
                        t_yaw = max(-1.0, min(t_yaw, 1.0))
                        
                        # Draw visual Yoke indicator on frame
                        cx, cy = int(0.75 * w), int(0.5 * h)
                        cv2.circle(frame, (cx, cy), 40, (150, 150, 150), 2) # Neutral zone
                        wx, wy = int(wrist.x * w), int(wrist.y * h)
                        cv2.circle(frame, (wx, wy), 8, (0, 255, 0), -1) # Hand cursor
                        cv2.line(frame, (cx, cy), (wx, wy), (0, 255, 0), 2)
                        cv2.putText(frame, f"YOKE (P: {t_pitch:.2f}, R: {t_roll:.2f})", 
                                    (cx - 80, cy - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                    # --- LEFT HAND (Throttle, Flaps, Gear, Brakes) ---
                    if left_hand_landmarks:
                        lm, handedness = left_hand_landmarks
                        self.mp_drawing.draw_landmarks(frame, lm, self.mp_hands.HAND_CONNECTIONS)
                        
                        wrist = lm.landmark[0]
                        
                        # Throttle: wrist Y on the left side of screen
                        # Y-axis inverted. Wrist at top (y=0.1) -> Throttle=1.0. Wrist at bottom (y=0.8) -> Throttle=0.0.
                        t_throttle = (0.8 - wrist.y) / 0.7
                        t_throttle = max(0.0, min(t_throttle, 1.0))

                        # Flaps: counted by extended fingers
                        fingers = self._count_fingers(lm, handedness)
                        if fingers <= 1:
                            t_flaps = 0.0 # Flaps Up
                        elif fingers <= 3:
                            t_flaps = 0.5 # Flaps Mid
                        else:
                            t_flaps = 1.0 # Flaps Full

                        # Gear: fist toggle
                        # If 0 fingers are extended (closed fist), retract gear.
                        # If 5 fingers extended (fully open), deploy gear.
                        # To prevent rapid oscillation, only change state when full gesture is detected
                        if fingers == 0:
                            t_gear = False
                        elif fingers == 5:
                            t_gear = True
                            
                        # Brakes: pinch thumb and index finger (finger count=1 and distance between tip 4 and 8 is small)
                        # We can simplify: if thumb and index are closed but others open, or if hand is at bottom of screen.
                        # Simple implementation: if total fingers == 1, engage brakes.
                        t_brakes = (fingers == 1)

                        # Draw Throttle indicator
                        tx = int(0.25 * w)
                        ty_target = int((0.8 - t_throttle * 0.7) * h)
                        cv2.line(frame, (tx, int(0.1*h)), (tx, int(0.8*h)), (150, 150, 150), 4) # slide rail
                        cv2.circle(frame, (tx, ty_target), 12, (255, 0, 0), -1) # throttle handle
                        cv2.putText(frame, f"THR: {int(t_throttle*100)}%", (tx - 40, int(0.08*h)), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                        cv2.putText(frame, f"FLAPS: {int(t_flaps*100)}%", (tx - 45, int(0.85*h)), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 120, 0), 1)
                        cv2.putText(frame, f"GEAR: {'DOWN' if t_gear else 'UP'}", (tx - 45, int(0.9*h)), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255) if t_gear else (0, 0, 255), 1)

                # 2. PROCESS FACE FOR COCKPIT HEAD TRACKING (LOOK AROUND)
                t_head_pitch = 0.0
                t_head_yaw = 0.0
                face_found = False
                
                if face_results.multi_face_landmarks:
                    face_found = True
                    face_landmarks = face_results.multi_face_landmarks[0]
                    
                    # Track relative positions of nose tip (landmark 4) vs forehead (10) and chin (152)
                    # and left/right eye corners (33, 263)
                    nose = face_landmarks.landmark[4]
                    left_eye = face_landmarks.landmark[33]
                    right_eye = face_landmarks.landmark[263]
                    forehead = face_landmarks.landmark[10]
                    chin = face_landmarks.landmark[152]
                    
                    # Head Yaw: Nose offset relative to the midpoint of the eyes
                    eye_midpoint_x = (left_eye.x + right_eye.x) / 2.0
                    yaw_offset = nose.x - eye_midpoint_x
                    t_head_yaw = yaw_offset * 1200.0  # Scale to degrees
                    t_head_yaw = max(-60.0, min(t_head_yaw, 60.0))

                    # Head Pitch: Nose vertical offset relative to forehead/chin midpoint
                    face_midpoint_y = (forehead.y + chin.y) / 2.0
                    pitch_offset = nose.y - face_midpoint_y
                    t_head_pitch = -pitch_offset * 1200.0 # Scale to degrees
                    t_head_pitch = max(-30.0, min(t_head_pitch, 30.0))
                    
                    # Draw a mini crosshair on the nose in preview
                    nx, ny = int(nose.x * w), int(nose.y * h)
                    cv2.drawMarker(frame, (nx, ny), (0, 0, 255), cv2.MARKER_CROSS, 10, 2)
                    cv2.putText(frame, f"HEAD (Y: {t_head_yaw:.1f}, P: {t_head_pitch:.1f})", 
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

                # Thread safe updates to shared states
                with self.lock:
                    self.roll = t_roll
                    self.pitch = t_pitch
                    self.yaw = t_yaw
                    self.throttle = t_throttle
                    self.flaps = t_flaps
                    self.gear_deploy = t_gear
                    self.brakes = t_brakes
                    self.head_pitch = t_head_pitch
                    self.head_yaw = t_head_yaw
                    self.hand_detected = hand_found
                    self.face_detected = face_found

                # Draw UI feedback on opencv frame
                cv2.putText(frame, "APEXFLIGHT CAM CONTROL ACTIVE", (int(w*0.3), h - 15), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # Show webcam window
                if WEBCAM_PREVIEW_SHOW:
                    cv2.imshow("ApexFlight - Pilot Webcam Control", frame)
                    # Poll keyboard in opencv window to prevent freezing
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        self.running = False
                        break
                else:
                    time.sleep(0.01)

            self.cap.release()
            cv2.destroyAllWindows()
