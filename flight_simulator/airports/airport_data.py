# Static airport data and gate positions.

from ursina import Vec3

AIRPORTS_DATA = [
    {
        "name": "Metro International (KMSP)",
        "icao": "KMSP",
        "position": Vec3(0, 0, 0),
        "runways": [
            {"name": "Runway 09 (ILS 09R)", "heading": 90.0, "length": 2500.0, "width": 60.0, "offset": Vec3(0, 0.1, 0)},
        ],
        "gates": [
            {"name": "Gate A1", "position": Vec3(-100, 0.2, 150)},
            {"name": "Gate A2", "position": Vec3(-150, 0.2, 150)}
        ]
    },
    {
        "name": "Mountain High Outpost (KASE)",
        "icao": "KASE",
        "position": Vec3(5000, 300, -6000), # Elevated at 300m
        "runways": [
            {"name": "Runway 21 (ILS 21L)", "heading": 210.0, "length": 1200.0, "width": 40.0, "offset": Vec3(0, 0.1, 0)},
        ],
        "gates": [
            {"name": "Cargo Dock C1", "position": Vec3(100, 0.2, 80)} # Relative to airport center
        ]
    }
]
