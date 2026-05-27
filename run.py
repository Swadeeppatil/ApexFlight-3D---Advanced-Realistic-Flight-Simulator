# Entry point launch script. Run this file to start the simulator.

import os
import sys

if __name__ == "__main__":
    print("[ApexFlight] Launching flight simulator module...")
    
    # Path to main.py inside flight_simulator folder
    main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flight_simulator", "main.py")
    
    # Execute main.py
    os.system(f'python "{main_path}"')
