from __future__ import annotations
import sys
from core.models import World
from core import simulation

def run_game():
    try:
        import pygame
    except Exception:
        print("pygame not installed. Install with: pip install pygame")
        return

    pygame.init()
    W, H = 800, 600
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()

    world = World()
    simulation.spawn_station(world, "S1")
    simulation.spawn_station(world, "S2")

    running = True
    while running:
        dt = clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        simulation.tick(world)

        screen.fill((20, 20, 28))
        # draw stations
        for s in world.stations.values():
            pygame.draw.circle(screen, (200,200,200), (int(s.x), int(s.y)), 12)
        # draw passengers as small dots at origin
        for p in world.passengers.values():
            if p.onboard is None:
                s = world.stations[p.origin]
                pygame.draw.circle(screen, (255,200,100), (int(s.x)+random.randint(-6,6), int(s.y)+random.randint(-6,6)), 3)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)
