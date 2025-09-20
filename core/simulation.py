from __future__ import annotations
import random
from .models import World, Station, Line, Passenger

def spawn_station(world: World, id_: str):
    import math, random
    x, y = random.randint(50, 600), random.randint(50, 400)
    s = Station(id=id_, x=x, y=y)
    world.stations[s.id] = s

def spawn_passenger(world: World, id_: str):
    if len(world.stations) < 2:
        return
    o, d = random.sample(list(world.stations.keys()), 2)
    p = Passenger(id=id_, origin=o, dest=d)
    world.passengers[p.id] = p
    world.stations[o].waiting += 1

def tick(world: World):
    world.tick += 1
    # spawn new stations occasionally
    if world.tick % 300 == 0:
        sid = f"S{len(world.stations)+1}"
        spawn_station(world, sid)
    # spawn passengers frequently
    if world.tick % 60 == 0:
        pid = f"P{len(world.passengers)+1}"
        spawn_passenger(world, pid)
    # TODO: simulate passenger movement on lines
