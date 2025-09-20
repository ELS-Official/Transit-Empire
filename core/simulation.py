from __future__ import annotations

import random

from .models import Line, Passenger, Station, World


def spawn_station(world: World, id_: str):
    x, y = random.randint(50, 600), random.randint(50, 400)
    station = Station(id=id_, x=x, y=y)
    world.stations[station.id] = station


def spawn_passenger(world: World, id_: str):
    if len(world.stations) < 2:
        return

    origin_id, dest_id = random.sample(list(world.stations.keys()), 2)
    passenger = Passenger(id=id_, origin=origin_id, dest=dest_id)
    world.passengers[passenger.id] = passenger
    world.stations[origin_id].waiting += 1


def create_line(world: World, station_ids, color):
    """Create a transit line connecting an ordered sequence of stations."""
    station_ids = list(station_ids)
    if len(station_ids) < 2:
        raise ValueError("Line requires at least two stations")
    if len(set(station_ids)) != len(station_ids):
        raise ValueError("Line cannot include the same station twice")

    for station_id in station_ids:
        if station_id not in world.stations:
            raise ValueError(f"Unknown station id: {station_id}")

    line_id = f"L{len(world.lines) + 1}"
    line = Line(id=line_id, color=color, stations=list(station_ids))
    world.lines[line.id] = line

    for station_id in station_ids:
        world.stations[station_id].connected = True

    return line


def extend_line(world: World, line_id: str, station_ids, *, at_start: bool = False):
    """Extend an existing line by adding stations to one end."""
    if line_id not in world.lines:
        raise ValueError(f"Unknown line id: {line_id}")

    additions = list(station_ids)
    if not additions:
        return world.lines[line_id]

    if len(set(additions)) != len(additions):
        raise ValueError("Cannot add the same station multiple times in one extension")

    line = world.lines[line_id]
    for station_id in additions:
        if station_id not in world.stations:
            raise ValueError(f"Unknown station id: {station_id}")
        if station_id in line.stations:
            raise ValueError("Station already exists on this line")

    if at_start:
        line.stations = list(reversed(additions)) + line.stations
    else:
        line.stations.extend(additions)

    for station_id in additions:
        world.stations[station_id].connected = True

    return line


def insert_stations(world: World, line_id: str, station_ids, *, after_index: int):
    """Insert stations into a line immediately after the given index."""
    if line_id not in world.lines:
        raise ValueError(f"Unknown line id: {line_id}")

    additions = list(station_ids)
    if not additions:
        return world.lines[line_id]

    line = world.lines[line_id]
    if len(line.stations) < 2:
        raise ValueError("Line must have at least two stations to insert between")
    if after_index < 0 or after_index >= len(line.stations) - 1:
        raise ValueError("Insertion index out of range")
    if len(set(additions)) != len(additions):
        raise ValueError("Cannot insert the same station multiple times")

    for station_id in additions:
        if station_id not in world.stations:
            raise ValueError(f"Unknown station id: {station_id}")
        if station_id in line.stations:
            raise ValueError("Station already exists on this line")

    insert_pos = after_index + 1
    line.stations[insert_pos:insert_pos] = additions

    for station_id in additions:
        world.stations[station_id].connected = True

    return line


def tick(world: World):
    world.tick += 1

    # spawn new stations occasionally
    if world.tick % 420 == 0:
        station_id = f"S{len(world.stations) + 1}"
        spawn_station(world, station_id)

    # spawn passengers frequently
    if world.tick % 60 == 0:
        passenger_id = f"P{len(world.passengers) + 1}"
        spawn_passenger(world, passenger_id)

    # TODO: simulate passenger movement on lines

