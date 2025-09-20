from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import math

@dataclass
class Station:
    id: str
    x: float
    y: float
    type: str = "residential"
    capacity: int = 30
    waiting: int = 0
    connected: bool = False

@dataclass
class Line:
    id: str
    color: Tuple[int, int, int]
    stations: List[str] = field(default_factory=list)
    capacity: int = 20
    speed: float = 1.0

@dataclass
class Passenger:
    id: str
    origin: str
    dest: str
    progress: float = 0.0
    onboard: Optional[str] = None

@dataclass
class World:
    stations: Dict[str, Station] = field(default_factory=dict)
    lines: Dict[str, Line] = field(default_factory=dict)
    passengers: Dict[str, Passenger] = field(default_factory=dict)
    tick: int = 0

