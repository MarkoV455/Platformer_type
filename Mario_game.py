import sys
import pygame

#------------------------ MARIO GAME ----------------------------------------------------
class Camera:
    def __init__(self, screen_width, level_width):
        self.offset_x = 0
        self.screen_width = screen_width
        self.level_width = level_width

    def update(self, target_rect):
        # Keep player centered
        target = target_rect.centerx - self.screen_width // 2

        # Clamp, kamera da ne izleze nadvor od levelot
        self.offset_x = max(0, min(target, self.level_width - self.screen_width))

    def apply(self, rect):
        # Convert world rect -> screen rect
        return rect.move(-self.offset_x, 0)

class Player:
    def __init__(self, x, y, width, height):
        self.width = width
        self.height = height
        self.player_rect = pygame.Rect(x, y, self.width, self.height)
        self.vel_x = 0
        self.vel_y = 0
        self.prev_jump = False
        self.on_ground = False

    def draw(self, surface, camera):
        pygame.draw.rect(surface, (255, 0, 0), camera.apply(self.player_rect))

    def update(self, keys, solid_tiles, dt):
        GRAVITY = 1800
        #HORIZONTAL INPUT
        self.vel_x = 0
        if keys[pygame.K_LEFT]:
            self.vel_x = -250
        elif keys[pygame.K_RIGHT]:
            self.vel_x = 250

        # JUMP
        jump = keys[pygame.K_SPACE]
        just_pressed = jump and not self.prev_jump
        self.prev_jump = jump

        if just_pressed and self.on_ground:
            self.vel_y = -600

        # Apply movement X
        self.player_rect.x += int(self.vel_x * dt)
        for tile in solid_tiles:
            if self.player_rect.colliderect(tile):
                if self.vel_x > 0:
                    self.player_rect.right = tile.left
                elif self.vel_x < 0:
                    self.player_rect.left = tile.right
                self.vel_x = 0


        # Apply movement Y
        self.vel_y += GRAVITY * dt
        self.player_rect.y += int(self.vel_y * dt)
        self.on_ground = False
        for tile in solid_tiles:
            if self.player_rect.colliderect(tile):
                if self.vel_y > 0:
                    self.player_rect.bottom = tile.top
                    self.vel_y = 0
                    self.on_ground = True
                elif self.vel_y < 0:
                    self.player_rect.top = tile.bottom
                    self.vel_y = 0

        # Reliable ground check (1px probe under feet)
        feet_probe = self.player_rect.move(0, 1)
        self.on_ground = any(feet_probe.colliderect(t) for t in solid_tiles)
        if self.on_ground and self.vel_y > 0:
            self.vel_y = 0


TILE_SIZE = 40

LEVEL_MAP = [
    "                                                                ",
    "                                                                ",
    "              P                                 GGG             ",
    "                                             GGG                ",
    "                      GGG              GGG                      ",
    "GGGGGGGGGGGGGGGGGGG         GGGGGGGGG                           ",
]

class Level:
    def __init__(self):
        self.cols = len(LEVEL_MAP[0])
        self.level_width = self.cols * TILE_SIZE
        self.solid_tiles = []
        self.player_spawn = None

        for row_index, row in enumerate(LEVEL_MAP):
            for col_index, char in enumerate(row):
                x = col_index * TILE_SIZE
                y = row_index * TILE_SIZE

                if char == "G":
                    rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
                    self.solid_tiles.append(rect)

                elif char == "P":
                    self.player_spawn = (x, y)

    def draw(self, surface, camera):
        for tile in self.solid_tiles:
            pygame.draw.rect(surface, (0, 200, 0), camera.apply(tile))



# GAME CLASS, klasata gi poseduva site metodi za iscrtuvanje, updejtiranje kako fizikata na samata igra
class Game:
    def __init__(self, win_width, win_height):
        pygame.init()
        pygame.display.set_caption("Mario Game")
        self.height = win_height
        self.width = win_width
        self.screen = pygame.display.set_mode((win_width, win_height))
        self.clock = pygame.time.Clock()
        self.fps = 60
        self.running = True
        self.level = Level()
        spawn_x, spawn_y = self.level.player_spawn
        self.player = Player(spawn_x, spawn_y, 30, 30)
        self.camera = Camera(self.width, self.level.level_width)

    def run(self):
        while self.running:
            dt = self.clock.tick(self.fps) / 1000
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit()

    def update(self, dt):
        keys = pygame.key.get_pressed()
        self.player.update(keys, self.level.solid_tiles, dt)
        self.camera.update(self.player.player_rect)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.level.draw(self.screen, self.camera)
        self.player.draw(self.screen, self.camera)


game = Game(800, 600)
game.run()

