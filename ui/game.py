from __future__ import annotations

import math
import random
import sys

from core import simulation
from core.models import Station, World

LINE_COLORS = [
    (239, 71, 111),
    (17, 138, 178),
    (6, 214, 160),
    (255, 209, 102),
    (17, 45, 78),
    (149, 125, 173),
]

LINE_WIDTH = 6
STATION_DRAW_RADIUS = 12
HOVER_RING_RADIUS = 18
STATION_SELECT_RADIUS = 20
END_HANDLE_STEM_LENGTH = 18
END_HANDLE_CAP_HALF_WIDTH = 10
END_HANDLE_HIT_RADIUS = 14
SEGMENT_HANDLE_RADIUS = 6
SEGMENT_HANDLE_HIT_RADIUS = 12
EDGE_OFFSET_DISTANCE = 8
HOVER_COLOR = (255, 255, 255)
DEFAULT_STATION_COLOR = (200, 200, 200)
CONNECTED_STATION_COLOR = (0, 0, 0)


def lighten_color(color, factor: float = 0.6):
    """Return a lightened version of the given RGB color."""
    return tuple(min(255, int(c + (255 - c) * factor)) for c in color)


def draw_station_panel(surface, station, font):
    import pygame

    lines = [
        f"Station {station.name}",
        f"Type: {station.type}",
        f"Passengers: {station.waiting}/{station.capacity}",
    ]
    padding = 12
    line_height = font.get_linesize()
    width = max(font.size(line)[0] for line in lines) + padding * 2
    height = line_height * len(lines) + padding * 2
    panel_rect = pygame.Rect(16, surface.get_height() - height - 16, width, height)

    pygame.draw.rect(surface, (28, 30, 44), panel_rect)
    pygame.draw.rect(surface, (90, 120, 200), panel_rect, 2)

    y = panel_rect.top + padding
    for line in lines:
        text_surf = font.render(line, True, (235, 235, 245))
        surface.blit(text_surf, (panel_rect.left + padding, y))
        y += line_height


def station_at_position(world: World, pos: tuple[int, int], radius: int = STATION_SELECT_RADIUS) -> Station | None:
    px, py = pos
    radius_sq = radius * radius
    for station in world.stations.values():
        dx = station.x - px
        dy = station.y - py
        if dx * dx + dy * dy <= radius_sq:
            return station
    return None


def build_end_handle(line_id: str, origin: Station, neighbor: Station, color, *, is_start: bool, offset: float = 0.0):
    dx = origin.x - neighbor.x
    dy = origin.y - neighbor.y
    distance = math.hypot(dx, dy)
    if distance == 0:
        return None

    dir_x = dx / distance
    dir_y = dy / distance

    perp_x, perp_y = -dir_y, dir_x

    offset_x = perp_x * offset
    offset_y = perp_y * offset

    stem_inner = (
        origin.x + dir_x * STATION_DRAW_RADIUS + offset_x,
        origin.y + dir_y * STATION_DRAW_RADIUS + offset_y,
    )
    stem_outer = (
        origin.x + dir_x * (STATION_DRAW_RADIUS + END_HANDLE_STEM_LENGTH) + offset_x,
        origin.y + dir_y * (STATION_DRAW_RADIUS + END_HANDLE_STEM_LENGTH) + offset_y,
    )

    cap_start = (
        stem_outer[0] + perp_x * END_HANDLE_CAP_HALF_WIDTH,
        stem_outer[1] + perp_y * END_HANDLE_CAP_HALF_WIDTH,
    )
    cap_end = (
        stem_outer[0] - perp_x * END_HANDLE_CAP_HALF_WIDTH,
        stem_outer[1] - perp_y * END_HANDLE_CAP_HALF_WIDTH,
    )

    return {
        "kind": "end",
        "line_id": line_id,
        "station_id": origin.id,
        "is_start": is_start,
        "pos": stem_outer,
        "stem_inner": stem_inner,
        "stem_outer": stem_outer,
        "cap_start": cap_start,
        "cap_end": cap_end,
        "color": color,
        "hit_radius": END_HANDLE_HIT_RADIUS,
    }


def build_segment_handle(line_id: str, left: Station, right: Station, color, index: int, offset: float = 0.0):
    midpoint = ((left.x + right.x) * 0.5, (left.y + right.y) * 0.5)
    dx = right.x - left.x
    dy = right.y - left.y
    length = math.hypot(dx, dy)
    if length != 0 and offset != 0:
        perp_x = -dy / length
        perp_y = dx / length
        midpoint = (midpoint[0] + perp_x * offset, midpoint[1] + perp_y * offset)
    return {
        "kind": "segment",
        "line_id": line_id,
        "index": index,
        "pos": midpoint,
        "left_station_id": left.id,
        "right_station_id": right.id,
        "color": color,
        "hit_radius": SEGMENT_HANDLE_HIT_RADIUS,
    }


def build_line_handles(world: World, edge_usage: dict[tuple[str, str], list[str]] | None = None):
    if edge_usage is None:
        edge_usage = compute_edge_usage(world)

    handles = []
    for line in world.lines.values():
        station_objs = [world.stations[sid] for sid in line.stations if sid in world.stations]
        if len(station_objs) < 2:
            continue

        first_edge = tuple(sorted((line.stations[0], line.stations[1])))
        first_siblings = edge_usage.get(first_edge, [line.id])
        first_offset = lane_offset(first_siblings.index(line.id)) if len(first_siblings) > 1 else 0.0
        start_handle = build_end_handle(line.id, station_objs[0], station_objs[1], line.color, is_start=True, offset=first_offset)

        last_edge = tuple(sorted((line.stations[-2], line.stations[-1])))
        last_siblings = edge_usage.get(last_edge, [line.id])
        last_offset = lane_offset(last_siblings.index(line.id)) if len(last_siblings) > 1 else 0.0
        end_handle = build_end_handle(line.id, station_objs[-1], station_objs[-2], line.color, is_start=False, offset=last_offset)

        if start_handle:
            handles.append(start_handle)
        if end_handle:
            handles.append(end_handle)

        for index in range(len(station_objs) - 1):
            edge_key = tuple(sorted((line.stations[index], line.stations[index + 1])))
            siblings = edge_usage.get(edge_key, [line.id])
            offset_amount = lane_offset(siblings.index(line.id)) if len(siblings) > 1 else 0.0
            segment_handle = build_segment_handle(line.id, station_objs[index], station_objs[index + 1], line.color, index, offset=offset_amount)
            handles.append(segment_handle)
    return handles


def handle_at_position(handles, pos: tuple[int, int], default_radius: int = END_HANDLE_HIT_RADIUS):
    px, py = pos
    for handle in handles:
        hx, hy = handle["pos"]
        radius = handle.get("hit_radius", default_radius)
        dx = hx - px
        dy = hy - py
        if dx * dx + dy * dy <= radius * radius:
            return handle
    return None


def draw_handle(surface, handle, highlight: bool = False):
    import pygame

    color = HOVER_COLOR if highlight else handle["color"]
    if handle["kind"] == "end":
        stem_inner = (int(handle["stem_inner"][0]), int(handle["stem_inner"][1]))
        stem_outer = (int(handle["stem_outer"][0]), int(handle["stem_outer"][1]))
        cap_start = (int(handle["cap_start"][0]), int(handle["cap_start"][1]))
        cap_end = (int(handle["cap_end"][0]), int(handle["cap_end"][1]))
        pygame.draw.line(surface, color, stem_inner, stem_outer, LINE_WIDTH)
        pygame.draw.line(surface, color, cap_start, cap_end, LINE_WIDTH)
    else:
        center = (int(handle["pos"][0]), int(handle["pos"][1]))
        radius = SEGMENT_HANDLE_RADIUS + (2 if highlight else 0)
        pygame.draw.circle(surface, handle["color"], center, SEGMENT_HANDLE_RADIUS)
        if highlight:
            pygame.draw.circle(surface, color, center, radius, 2)


def gather_station_points(world: World, station_ids):
    points = []
    for station_id in station_ids:
        station = world.stations.get(station_id)
        if station:
            points.append((int(station.x), int(station.y)))
    return points


def compute_edge_usage(world: World) -> dict[tuple[str, str], list[str]]:
    usage: dict[tuple[str, str], list[str]] = {}
    for line_id, line in world.lines.items():
        stations = line.stations
        for idx in range(len(stations) - 1):
            key = tuple(sorted((stations[idx], stations[idx + 1])))
            usage.setdefault(key, []).append(line_id)
    return usage


def lane_offset(index: int) -> float:
    if index == 0:
        return 0.0
    steps = (index + 1) // 2
    direction = 1 if index % 2 == 1 else -1
    return steps * EDGE_OFFSET_DISTANCE * direction


def offset_segment(start: tuple[float, float], end: tuple[float, float], offset: float) -> tuple[tuple[int, int], tuple[int, int]]:
    if offset == 0:
        return (
            (int(round(start[0])), int(round(start[1]))),
            (int(round(end[0])), int(round(end[1]))),
        )
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return (
            (int(round(start[0])), int(round(start[1]))),
            (int(round(end[0])), int(round(end[1]))),
        )
    perp_x = -dy / length
    perp_y = dx / length
    ox = perp_x * offset
    oy = perp_y * offset
    return (
        (int(round(start[0] + ox)), int(round(start[1] + oy))),
        (int(round(end[0] + ox)), int(round(end[1] + oy))),
    )

def run_game():
    try:
        import pygame
    except Exception:
        print("pygame not installed. Install with: pip install pygame")
        return

    pygame.init()
    width, height = 800, 600
    screen = pygame.display.set_mode((width, height))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("arial", 16)

    world = World()
    simulation.spawn_station(world, "S1")
    simulation.spawn_station(world, "S2")

    color_index = 0
    cursor_pos = (0, 0)

    dragging = False
    drag_mode: str | None = None  # "new", "extend", "insert"

    active_line_stations: list[str] = []

    extend_line_id: str | None = None
    extend_from_start = False
    extend_anchor_station: str | None = None
    extend_new_stations: list[str] = []

    insert_line_id: str | None = None
    insert_segment_index: int | None = None
    insert_anchor_left: str | None = None
    insert_anchor_right: str | None = None
    insert_target_station: str | None = None

    hover_station_id: str | None = None
    hover_handle = None
    selected_station_id: str | None = None

    running = True
    while running:
        dt = clock.tick(60)
        handles_for_events = build_line_handles(world)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEMOTION:
                cursor_pos = event.pos
                station = station_at_position(world, event.pos)
                if drag_mode == "new":
                    if station and station.id not in active_line_stations:
                        active_line_stations.append(station.id)
                elif drag_mode == "extend" and extend_line_id:
                    line = world.lines.get(extend_line_id)
                    if station and station.id != extend_anchor_station:
                        if line and station.id not in line.stations and station.id not in extend_new_stations:
                            extend_new_stations.append(station.id)
                elif drag_mode == "insert" and insert_line_id is not None and insert_segment_index is not None:
                    line = world.lines.get(insert_line_id)
                    if station and line:
                        if station.id not in (insert_anchor_left, insert_anchor_right) and station.id not in line.stations:
                            insert_target_station = station.id
                        else:
                            insert_target_station = None
                    else:
                        insert_target_station = None
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    cursor_pos = event.pos
                    handle = handle_at_position(handles_for_events, event.pos)
                    station = station_at_position(world, event.pos)
                    if station:
                        selected_station_id = station.id
                    elif not handle:
                        selected_station_id = None
                    if handle:
                        dragging = True
                        if handle["kind"] == "end":
                            drag_mode = "extend"
                            extend_line_id = handle["line_id"]
                            extend_from_start = handle["is_start"]
                            extend_anchor_station = handle["station_id"]
                            extend_new_stations = []
                            active_line_stations = []
                            insert_line_id = None
                            insert_segment_index = None
                            insert_anchor_left = None
                            insert_anchor_right = None
                            insert_target_station = None
                        elif handle["kind"] == "segment":
                            drag_mode = "insert"
                            insert_line_id = handle["line_id"]
                            insert_segment_index = handle["index"]
                            insert_anchor_left = handle["left_station_id"]
                            insert_anchor_right = handle["right_station_id"]
                            insert_target_station = None
                            active_line_stations = []
                            extend_line_id = None
                            extend_new_stations = []
                            extend_anchor_station = None
                            extend_from_start = False
                    elif station:
                        dragging = True
                        drag_mode = "new"
                        active_line_stations = [station.id]
                        extend_line_id = None
                        extend_new_stations = []
                        extend_anchor_station = None
                        extend_from_start = False
                        insert_line_id = None
                        insert_segment_index = None
                        insert_anchor_left = None
                        insert_anchor_right = None
                        insert_target_station = None
                elif event.button == 3:
                    dragging = False
                    drag_mode = None
                    active_line_stations = []
                    extend_line_id = None
                    extend_new_stations = []
                    extend_anchor_station = None
                    extend_from_start = False
                    insert_line_id = None
                    insert_segment_index = None
                    insert_anchor_left = None
                    insert_anchor_right = None
                    insert_target_station = None
                    selected_station_id = None
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and dragging:
                    if drag_mode == "new":
                        if len(active_line_stations) >= 2:
                            color = LINE_COLORS[color_index]
                            try:
                                simulation.create_line(world, active_line_stations, color)
                                color_index = (color_index + 1) % len(LINE_COLORS)
                            except ValueError as exc:
                                print(f"Could not create line: {exc}")
                        active_line_stations = []
                    elif drag_mode == "extend" and extend_line_id:
                        additions = list(extend_new_stations)
                        if extend_from_start:
                            additions = list(reversed(additions))
                        if additions:
                            try:
                                simulation.extend_line(world, extend_line_id, additions, at_start=extend_from_start)
                            except ValueError as exc:
                                print(f"Could not extend line: {exc}")
                        extend_line_id = None
                        extend_new_stations = []
                        extend_anchor_station = None
                        extend_from_start = False
                    elif drag_mode == "insert" and insert_line_id is not None and insert_segment_index is not None:
                        if insert_target_station:
                            try:
                                simulation.insert_stations(world, insert_line_id, [insert_target_station], after_index=insert_segment_index)
                            except ValueError as exc:
                                print(f"Could not insert station: {exc}")
                        insert_line_id = None
                        insert_segment_index = None
                        insert_anchor_left = None
                        insert_anchor_right = None
                        insert_target_station = None
                    dragging = False
                    drag_mode = None
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    dragging = False
                    drag_mode = None
                    active_line_stations = []
                    extend_line_id = None
                    extend_new_stations = []
                    extend_anchor_station = None
                    extend_from_start = False
                    insert_line_id = None
                    insert_segment_index = None
                    insert_anchor_left = None
                    insert_anchor_right = None
                    insert_target_station = None

        simulation.tick(world)

        current_station = station_at_position(world, cursor_pos)
        hover_station_id = current_station.id if current_station else None

        screen.fill((20, 20, 28))

        edge_usage = compute_edge_usage(world)

        for line_id, line in world.lines.items():
            station_ids = [sid for sid in line.stations if sid in world.stations]
            if len(station_ids) < 2:
                continue
            draw_color = line.color
            if drag_mode == "insert" and insert_line_id == line.id:
                draw_color = lighten_color(line.color)
            for idx in range(len(station_ids) - 1):
                start_station = world.stations[station_ids[idx]]
                end_station = world.stations[station_ids[idx + 1]]
                edge_key = tuple(sorted((station_ids[idx], station_ids[idx + 1])))
                siblings = edge_usage.get(edge_key, [line.id])
                if len(siblings) > 1:
                    offset_index = siblings.index(line.id)
                    offset_amount = lane_offset(offset_index)
                else:
                    offset_amount = 0.0
                offset_start, offset_end = offset_segment(
                    (start_station.x, start_station.y),
                    (end_station.x, end_station.y),
                    offset_amount,
                )
                pygame.draw.line(screen, draw_color, offset_start, offset_end, LINE_WIDTH)

        handles_for_draw = build_line_handles(world)
        if not dragging:
            hover_handle = handle_at_position(handles_for_draw, cursor_pos)
        else:
            hover_handle = None

        # previews for new lines
        if drag_mode == "new" and active_line_stations:
            preview_points = gather_station_points(world, active_line_stations)
            if len(preview_points) >= 2:
                pygame.draw.lines(screen, LINE_COLORS[color_index], False, preview_points, LINE_WIDTH)
            if preview_points:
                pygame.draw.line(screen, LINE_COLORS[color_index], preview_points[-1], cursor_pos, LINE_WIDTH)

        # previews for line extensions
        if drag_mode == "extend" and extend_line_id and extend_anchor_station:
            line = world.lines.get(extend_line_id)
            anchor_station = world.stations.get(extend_anchor_station)
            if line and anchor_station:
                if extend_from_start:
                    preview_ids = list(reversed(extend_new_stations)) + [extend_anchor_station]
                else:
                    preview_ids = [extend_anchor_station] + list(extend_new_stations)
                preview_points = gather_station_points(world, preview_ids)
                if len(preview_points) >= 2:
                    pygame.draw.lines(screen, line.color, False, preview_points, LINE_WIDTH)
                if preview_points:
                    if extend_from_start:
                        free_point = preview_points[0]
                    else:
                        free_point = preview_points[-1]
                else:
                    free_point = (int(anchor_station.x), int(anchor_station.y))
                pygame.draw.line(screen, line.color, free_point, cursor_pos, LINE_WIDTH)

        # previews for inserting stations mid-line
        if drag_mode == "insert" and insert_line_id and insert_segment_index is not None:
            line = world.lines.get(insert_line_id)
            if line and 0 <= insert_segment_index < len(line.stations) - 1:
                left_station = world.stations.get(line.stations[insert_segment_index])
                right_station = world.stations.get(line.stations[insert_segment_index + 1])
                if left_station and right_station:
                    left_pos = (int(left_station.x), int(left_station.y))
                    right_pos = (int(right_station.x), int(right_station.y))
                    if insert_target_station and insert_target_station in world.stations:
                        target_station = world.stations[insert_target_station]
                        target_pos = (int(target_station.x), int(target_station.y))
                    else:
                        target_pos = (int(cursor_pos[0]), int(cursor_pos[1]))
                    pygame.draw.lines(screen, line.color, False, [left_pos, target_pos, right_pos], LINE_WIDTH)

        for handle in handles_for_draw:
            if drag_mode == "extend" and extend_line_id and handle["kind"] == "end":
                if handle["line_id"] == extend_line_id and handle["is_start"] == extend_from_start:
                    continue
            if drag_mode == "insert" and insert_line_id and handle["kind"] == "segment":
                if handle["line_id"] == insert_line_id and handle["index"] == insert_segment_index:
                    continue
            highlight = handle is hover_handle
            draw_handle(screen, handle, highlight)

        for station in world.stations.values():
            pos = (int(station.x), int(station.y))
            fill_color = CONNECTED_STATION_COLOR if station.connected else DEFAULT_STATION_COLOR
            pygame.draw.circle(screen, fill_color, pos, STATION_DRAW_RADIUS)

            highlight = False
            if hover_station_id == station.id:
                highlight = True
            if selected_station_id == station.id:
                highlight = True
            if drag_mode == "new" and station.id in active_line_stations:
                highlight = True
            if drag_mode == "extend":
                if station.id == extend_anchor_station or station.id in extend_new_stations:
                    highlight = True
            if drag_mode == "insert":
                if station.id in (insert_anchor_left, insert_anchor_right, insert_target_station):
                    highlight = True
            if highlight:
                pygame.draw.circle(screen, HOVER_COLOR, pos, HOVER_RING_RADIUS, 2)

        for passenger in world.passengers.values():
            if passenger.onboard is None:
                origin = world.stations.get(passenger.origin)
                if origin:
                    jittered = (
                        int(origin.x) + random.randint(-6, 6),
                        int(origin.y) + random.randint(-6, 6),
                    )
                    pygame.draw.circle(screen, (255, 200, 100), jittered, 3)

        if selected_station_id:
            station = world.stations.get(selected_station_id)
            if station:
                draw_station_panel(screen, station, font)
            else:
                selected_station_id = None

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)











