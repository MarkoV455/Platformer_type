from operator import le
import sys
import pygame
from enum import Enum
import json
import os

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
        self.out_of_bounds = False
        self.dead = False
        self.death_timer = 0

    def draw(self, surface, camera):
        pygame.draw.rect(surface, (255, 0, 0), camera.apply(self.player_rect))

    def die(self):
        if self.dead:
            return
        self.dead = True
        self.vel_x = 0
        self.death_timer = 0
        self.vel_x = 0
        self.vel_y = -650  # Bounce up on death
        
    def update(self, keys, solid_tiles, dt, on_platform=False):
        if self.dead:
            self.death_timer += dt
            self.vel_y += 1800 * dt
            self.player_rect.y += int(self.vel_y * dt)
            if self.death_timer > 2:
                self.out_of_bounds = True
            return

        GRAVITY = 1800

        # HORIZONTAL INPUT
        self.vel_x = 0
        if keys[pygame.K_LEFT]:
            self.vel_x = -250
        elif keys[pygame.K_RIGHT]:
            self.vel_x = 250

        # IMPORTANT: if we're riding a platform, force grounded BEFORE jump check
        if on_platform:
            self.on_ground = True
            if self.vel_y > 0:
                self.vel_y = 0

        # JUMP
        jump = keys[pygame.K_SPACE]
        just_pressed = jump and not self.prev_jump
        self.prev_jump = jump

        jumped = False
        if just_pressed and self.on_ground:
            self.vel_y = -700
            jumped = True

        # Apply movement X + collisions
        self.player_rect.x += int(self.vel_x * dt)
        for tile in solid_tiles:
            if self.player_rect.colliderect(tile):
                if self.vel_x > 0:
                    self.player_rect.right = tile.left
                elif self.vel_x < 0:
                    self.player_rect.left = tile.right
                self.vel_x = 0

        # GRAVITY (turn off while riding)
        if not on_platform:
            self.vel_y += GRAVITY * dt
        else:
            # keep stable while platform moves down/up
            if self.vel_y > 0:
                self.vel_y = 0

        # Apply movement Y + collisions
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

        # Ground probe (only if NOT on platform)
        if not on_platform:
            feet_probe = self.player_rect.move(0, 1)
            self.on_ground = any(feet_probe.colliderect(t) for t in solid_tiles)
            if self.on_ground and self.vel_y > 0:
                self.vel_y = 0

        if self.player_rect.top > 600:
            self.out_of_bounds = True

        return jumped

class Enemy:
    def __init__(self, x, y, width, height):
        self.enemy_rect = pygame.Rect(x, y, width, height)
        self.vel_x = 250
        self.alive = True

    def draw(self, surface, camera):
        if not self.alive:
            return
        pygame.draw.rect(surface, (0, 0, 255), camera.apply(self.enemy_rect)) # Color blue for enemies

    def update(self, dt, solid_tiles): # Simple horizontal patrol logic
        self.enemy_rect.x += int(self.vel_x * dt)

        # Check for collisions with solid tiles to reverse direction
        for tile in solid_tiles:
            if self.enemy_rect.colliderect(tile):
                if self.vel_x > 0:
                    self.enemy_rect.right = tile.left
                else:
                    self.enemy_rect.left = tile.right
                self.vel_x *= -1
        
class PlatformEnemy(Enemy):
    def __init__(self, x, y, width, height):
        super().__init__(x, y, width, height)
    
    def draw(self, surface, camera):
        if not self.alive:
            return
        pygame.draw.rect(surface, (0, 0, 255), camera.apply(self.enemy_rect)) # Color blue for enemies
    
    def update(self, dt, solid_tiles):
        super().update(dt, solid_tiles)
        # Ensure enemy stays within platform bounds
        probe_rect = self.enemy_rect.move(0, 1)  # Check 1px below enemy center
        on_platform = any(probe_rect.colliderect(t) for t in solid_tiles)
        if not on_platform:
            self.vel_x *= -1  # Reverse direction if about to walk off platform

import pygame

class MovingPlatform:
    def __init__(self, x, y, width, height, path_length, axis="horizontal", vel=250):
        self.platform_rect = pygame.Rect(x, y, width, height)
        self.start_x = x
        self.start_y = y
        self.path_length = path_length
        self.axis = axis

        # speed (pixels/sec)
        self.vel_x = vel
        self.vel_y = vel

        # per-frame delta (computed in update)
        self.dx = 0
        self.dy = 0

    def draw(self, surface, camera):
        pygame.draw.rect(surface, (100, 100, 255), camera.apply(self.platform_rect))

    def update(self, dt):
        old_x, old_y = self.platform_rect.x, self.platform_rect.y

        if self.axis == "horizontal":
            self.platform_rect.x += int(self.vel_x * dt)
            if abs(self.platform_rect.x - self.start_x) > self.path_length:
                # clamp to edge to avoid jitter at the boundary
                if self.platform_rect.x > self.start_x:
                    self.platform_rect.x = self.start_x + self.path_length
                else:
                    self.platform_rect.x = self.start_x - self.path_length
                self.vel_x *= -1

        elif self.axis == "vertical":
            # positive vel_y means moving DOWN (simpler mentally)
            self.platform_rect.y += int(self.vel_y * dt)
            if abs(self.platform_rect.y - self.start_y) > self.path_length:
                if self.platform_rect.y > self.start_y:
                    self.platform_rect.y = self.start_y + self.path_length
                else:
                    self.platform_rect.y = self.start_y - self.path_length
                self.vel_y *= -1

        self.dx = self.platform_rect.x - old_x
        self.dy = self.platform_rect.y - old_y

class Coin:
    def __init__(self, x, y, size, worth=10):
        COIN_SIZE = size // 2
        self.coin_rect = pygame.Rect(x + size // 4, y + size // 4, COIN_SIZE, COIN_SIZE)
        self.worth = worth

    def draw(self, surface, camera):
        pygame.draw.rect(surface, (255, 215, 0), camera.apply(self.coin_rect))

class Spikes:
    def __init__(self, x, y, width, height):
        self.spike_rect = pygame.Rect(
            x + width // 4, 
            y + height // 2, 
            width * 0.5, 
            height * 0.6
        )
        
        self.visual_rect = pygame.Rect(x, y, width, height)

    def draw(self, surface, camera):
        r = camera.apply(self.visual_rect)

        p1 = (r.left, r.bottom)
        p2 = (r.centerx, r.top)
        p3 = (r.right, r.bottom)

        pygame.draw.polygon(surface, (200, 50, 50), [p1, p2, p3])
        

TILE_SIZE = 40

# G = Ground, P = Player Spawn, C = Coin, S = Spike, E = Enemy, M = Moving Platform, V = Vertical Moving Platform
LEVEL_MAP_2 = [
"G                                                                                                               G",
"G                                                                                                               G",
"G                                                          GGGGGGGGGGGGG       GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
"G                                                          G                                                    G",
"G                                      CE                  G        C    S  G                 E      C          G",
"G                                    GGGGG                 G      GGG G GG    G GG GG   G GG GGGGG GG G  G      G",
"G                                          G               G  G                                             G   G",
"G               C                          C               G        C         C        C           C            G",
"G               GGG                      GGGGG             G GG GG GG GG GG GG GG GG GG GG GG GG GG GG        G G", 
"G                                                                                                         G     G",
"G                                                  M                                                           G",
"G          V                                G   C                 C                C                         G  G",
"G                                      S  S     S   S  S S  S   S   S S  S   S  S S  S  S  S   S   S      G     G",
"G   P     E        G    E    G   E   GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG    E  G",
"GGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
]

LEVEL_MAP = [
"GGGGGGGGGGGGGG                                                                   GGGGGGGGGGGGGGGGGGGG",
"G                                                                                                   G",
"G                                                                                        C          G",
"G                                        C                                             GGGGG        G",
"G                                     GGGGG                                V      M                 G",
"G                                              GGGGG                                                G",
"G                C       M      V                             C   SS      E                         G",
"G              GGGGG                                      GGGGG   GG     GGGGG                      G",
"G       GGG                                           V                        V                    G",
"G   C                                EC                           G                                 G",
"G  GGG                             GGGGG      M               G   G             C                   G",
"G         E                                                       G            M                    G",
"G       GGGGG                        GGGG                                 G           GGGG          G",
"G  P                                                              G                           E    CG",
"GGGGGGG   SSSSSSSSSS   GGGGGGG   SGGSSSSSSSG   GGGGGGGSSSGGGGGSSSGGGGGGGG   SSSSSSSSSS   GGGGGGGGGGGG"
]

# The Gauntlet Level - A long, challenging level designed to test all the player's skills, 
# with a focus on precision and timing. It features a mix of tight platforming sections, 
# enemy gauntlets, and moving platforms that require careful navigation. 
# The level is structured as a long horizontal stretch with various obstacles and enemies placed strategically to create a sense of escalating difficulty.
#  The player must maintain focus and control throughout the level to succeed, making it a true test of their mastery of the game mechanics.

class Level:
    def __init__(self, level_map):
        self.map_data = level_map
        self.rows = len(self.map_data)
        self.cols = max(len(r) for r in self.map_data)
        self.level_width = self.cols * TILE_SIZE

        self.solid_tiles = []
        self.coins = []
        self.spikes = []
        self.enemies = []
        self.moving_platforms = []

        ENEMY_SIZE = TILE_SIZE - 10
        self.player_spawn = (40, 40)  # fallback

        for row_index, row in enumerate(self.map_data):
            for col_index, char in enumerate(row):
                x = col_index * TILE_SIZE
                y = row_index * TILE_SIZE

                if char == "G":
                    rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
                    self.solid_tiles.append(rect)

                elif char == "P":
                    self.player_spawn = (x, y)

                elif char == "C":
                    self.coins.append(Coin(x, y, TILE_SIZE))

                elif char == "S":
                    self.spikes.append(Spikes(x, y, TILE_SIZE, TILE_SIZE))

                elif char == "E":
                    enemy = PlatformEnemy(x, y - 10, ENEMY_SIZE, ENEMY_SIZE + 20)
                    self.enemies.append(enemy)

                elif char == "M":
                    platform = MovingPlatform(x, y, TILE_SIZE * 2, TILE_SIZE // 2, path_length=200)
                    self.moving_platforms.append(platform)
                    self.solid_tiles.append(platform.platform_rect)

                elif char == "V":
                    platform = MovingPlatform(x, y, TILE_SIZE * 2, TILE_SIZE // 2, path_length=100, axis="vertical")
                    self.moving_platforms.append(platform)
                    self.solid_tiles.append(platform.platform_rect)

    def draw(self, surface, camera):
        for tile in self.solid_tiles:
            pygame.draw.rect(surface, (0, 200, 0), camera.apply(tile))
        for spike in self.spikes:
            spike.draw(surface, camera)
        for coin in self.coins:
            coin.draw(surface, camera)
        for enemy in self.enemies:
            enemy.draw(surface, camera)
        for platform in self.moving_platforms:
            platform.draw(surface, camera)

class GameState(Enum):
    MENU = 0
    ACTIVE = 1
    DEATH_ANIM = 2
    DEATH = 3
    WON = 4


# GAME CLASS, klasata gi poseduva site metodi za iscrtuvanje, updejtiranje kako fizikata na samata igra
class Game:
    def __init__(self, win_width, win_height, state = GameState.MENU):
        # Initialize Pygame and set up the window
        pygame.init()
        pygame.mixer.init()
        pygame.display.set_caption("Mario Game")
        self.height = win_height
        self.width = win_width
        self.screen = pygame.display.set_mode((win_width, win_height))
        self.clock = pygame.time.Clock()
        self.fps = 60
        self.running = True

        # BUTTON TRACKING (for menu and end screens, if you want them)
        self.end_buttons = []  # list of (rect, action_string)
        # ---- Highscores ----
        self.score_file = "highscores.json"
        self.highscores = self.load_scores()   # dict

        # Initialize level, player, and camera and state
        self.levels = [LEVEL_MAP, LEVEL_MAP_2]
        self.level_index = 0
        self.level = Level(self.levels[self.level_index])
        spawn_x, spawn_y = self.level.player_spawn
        self.player = Player(spawn_x, spawn_y, 30, 30)
        self.camera = Camera(self.width, self.level.level_width)
        self.state = state


        # ---- MENU selection ----
        self.selected_level = 0
        self.menu_buttons = []  # list of (rect, index)
        # Score tracking
        self.score = 0
        self.coins_collected = 0
        self.max_coins = len(self.level.coins)
        self.font = pygame.font.SysFont("Arial", 36)
        self.font_small = pygame.font.SysFont("Comic Sans", 24)
        self.won = False
        self.restart = False

        # Tracking time elapsed during play for potential time-based scoring
        self.level_start_ticks = None # WHEN ACTIVE BEGINS
        self.time_elapsed = 0.0 # current time (seconds)
        self.final_time = None # time at moment of win, for scoring purposes

        # LOADING SOUNDS
        self.sounds = {
            "jump": pygame.mixer.Sound("Sounds/jump.ogg"),
            "coin": pygame.mixer.Sound("Sounds/coin.ogg"),
            "death": pygame.mixer.Sound("Sounds/death.ogg"),
            "win": pygame.mixer.Sound("Sounds/win.ogg"),
            "stomp": pygame.mixer.Sound("Sounds/stomp.ogg")
        }
        # Volume control
        self.sounds["jump"].set_volume(0.4)
        self.sounds["coin"].set_volume(0.5)
        self.sounds["death"].set_volume(0.6)
        self.sounds["win"].set_volume(0.5)
        self.sounds["stomp"].set_volume(0.7)

        # LOAD MUSIC
        pygame.mixer.music.load("Sounds/music.ogg")
        pygame.mixer.music.set_volume(0.1)
        pygame.mixer.music.play(-1)  # Loop indefinitely
    
    def load_scores(self):
        if not os.path.exists(self.score_file):
            return {}
        try:
            with open(self.score_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_scores(self):
        try:
            with open(self.score_file, "w", encoding="utf-8") as f:
                json.dump(self.highscores, f, indent=2)
        except Exception:
            pass

    def update_highscore_for_level(self):
        """Call this when the player wins. Saves best points and best time for this level."""
        lvl = str(self.level_index)
        current_points = int(self.score)
        current_time = float(self.final_time if self.final_time is not None else self.time_elapsed)

        entry = self.highscores.get(lvl, {"best_points": 0, "best_time": None})

        # Best points: higher is better
        if current_points > entry.get("best_points", 0):
            entry["best_points"] = current_points

        # Best time: lower is better (store None if not existing yet)
        best_time = entry.get("best_time", None)
        if (best_time is None) or (current_time < best_time):
            entry["best_time"] = round(current_time, 2)

        self.highscores[lvl] = entry
        self.save_scores()

    def get_highscore_text(self, level_idx):
        lvl = str(level_idx)
        entry = self.highscores.get(lvl)
        if not entry:
            return "Best: -- pts | -- s"
        bp = entry.get("best_points", 0)
        bt = entry.get("best_time", None)
        bt_text = f"{bt:.1f}s" if isinstance(bt, (int, float)) else "-- s"
        return f"Best: {bp} pts | {bt_text}"
    
    def start_level(self, index):
        self.level_index = index
        self.level = Level(self.levels[self.level_index])

        spawn_x, spawn_y = self.level.player_spawn
        self.player = Player(spawn_x, spawn_y, 30, 30)
        self.camera = Camera(self.width, self.level.level_width)

        # reset scoring/timer for the level
        self.score = 0
        self.coins_collected = 0
        self.max_coins = len(self.level.coins)
        self.won = False
        self.player.out_of_bounds = False

        self.level_start_ticks = None
        self.time_elapsed = 0.0
        self.final_time = None
        self.state = GameState.ACTIVE
    
    def restart_current_level(self):
        self.start_level(self.level_index)

    def go_to_menu(self):
        self.state = GameState.MENU
        self.selected_level = self.level_index  # highlight last played level (optional)

    def run(self):
        while self.running:
            dt = self.clock.tick(self.fps) / 1000
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()
        sys.exit()

    def update_menu(self, dt):
        keys = pygame.key.get_pressed()

        # quick start with Enter if you want:
        if keys[pygame.K_RETURN]:
            self.start_level(self.selected_level)
    
    def update_death(self, dt):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_r]:
            self.restart_current_level()
        if keys[pygame.K_m]:
            self.go_to_menu()

    def update_death_anim(self, dt):
        keys = pygame.key.get_pressed()
        self.player.update(keys, self.level.solid_tiles, dt, on_platform=False)
        self.camera.update(self.player.player_rect)

        if self.player.out_of_bounds:
            self.state = GameState.DEATH

    def update_won(self, dt):
        keys = pygame.key.get_pressed()

        # R = restart same level
        if keys[pygame.K_r]:
            self.restart_current_level()

        # M = back to menu
        if keys[pygame.K_m]:
            self.go_to_menu()

    def update_active(self, dt):
        # ---- timer (keep yours if you want) ----
        if self.level_start_ticks is None:
            self.level_start_ticks = pygame.time.get_ticks()
            self.final_time = None
        now = pygame.time.get_ticks()
        self.time_elapsed = (now - self.level_start_ticks) / 1000.0

        # ---- state checks ----
        if self.won:
            self.state = GameState.WON
            return
        if self.player.dead:
            self.sounds["death"].play()
            self.state = GameState.DEATH_ANIM
            return

        # ---- 1) update moving platforms FIRST ----
        # update platforms first
        for platform in self.level.moving_platforms:
            platform.update(dt)

        # detect riding
        riding = None
        feet_probe = self.player.player_rect.move(0, 2)
        for platform in self.level.moving_platforms:
            if feet_probe.colliderect(platform.platform_rect):
                riding = platform
                break

        on_platform = riding is not None

        if riding is not None:
            self.player.player_rect.bottom = riding.platform_rect.top
            self.player.player_rect.x += riding.dx
            self.player.player_rect.y += riding.dy

        # ---- 3) normal player physics & collisions ----
        keys = pygame.key.get_pressed()
        jumped = self.player.update(keys, self.level.solid_tiles, dt, on_platform=on_platform)

        if jumped:
            self.sounds["jump"].play()

        # ---- 4) camera after movement ----
        self.camera.update(self.player.player_rect)

        # ---- coins ----
        for coin in self.level.coins[:]:
            if self.player.player_rect.colliderect(coin.coin_rect):
                self.sounds["coin"].play()
                self.score += coin.worth
                self.coins_collected += 1
                self.level.coins.remove(coin)

        # ---- spikes ----
        for spike in self.level.spikes:
            if self.player.player_rect.colliderect(spike.spike_rect):
                self.player.die()

        # ---- win ----
        if not self.level.coins and not self.won:
            self.state = GameState.WON
            self.won = True
            self.sounds["win"].play()
            self.final_time = self.time_elapsed
            self.update_highscore_for_level()
            return

        # ---- out of bounds ----
        if self.player.out_of_bounds:
            self.player.die()

        # ---- enemies ----
        for enemy in self.level.enemies:
            enemy.update(dt, self.level.solid_tiles)
            if enemy.alive and self.player.player_rect.colliderect(enemy.enemy_rect):
                player = self.player.player_rect
                enemy_rect = enemy.enemy_rect
                stomp = (self.player.vel_y > 0) and (player.bottom <= enemy_rect.centery)

                if stomp:
                    self.sounds["stomp"].play()
                    enemy.alive = False
                    self.score += 20
                    self.player.vel_y = -300
                else:
                    self.player.die()
                
    
    def update(self, dt):
        if self.state == GameState.MENU:
            self.update_menu(dt)
        elif self.state == GameState.ACTIVE:
            self.update_active(dt)
        elif self.state == GameState.DEATH_ANIM:
            self.update_death_anim(dt)
        elif self.state == GameState.DEATH:
            self.update_death(dt)
        elif self.state == GameState.WON:
            self.update_won(dt)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # ---- MENU controls ----
            if self.state == GameState.MENU:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        self.selected_level = (self.selected_level + 1) % len(self.levels)
                    elif event.key == pygame.K_UP:
                        self.selected_level = (self.selected_level - 1) % len(self.levels)
                    elif event.key == pygame.K_RETURN:
                        self.start_level(self.selected_level)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    for rect, idx in self.menu_buttons:
                        if rect.collidepoint(mx, my):
                            self.start_level(idx)
                            break
            # ---- DEATH/WON clickable buttons ----
           
            if self.state in (GameState.DEATH, GameState.WON):
                if self.state == GameState.DEATH:
                    # block clicks/keys until animation ends
                    if not self.player.out_of_bounds:
                        continue
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.restart_current_level()
                    elif event.key == pygame.K_m:
                        self.go_to_menu()

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    for rect, action in self.end_buttons:
                        if rect.collidepoint(mx, my):
                            if action == "restart":
                                self.restart_current_level()
                            elif action == "menu":
                                self.go_to_menu()
                            break
            
    def draw_button(self, text, center, hovered):
        font = self.font_small
        label = font.render(text, True, (255, 255, 255))
        rect = pygame.Rect(0, 0, 260, 48)
        rect.center = center

        bg = (70, 90, 220) if hovered else (35, 35, 55)
        pygame.draw.rect(self.screen, bg, rect, border_radius=10)
        pygame.draw.rect(self.screen, (220, 220, 220), rect, 2, border_radius=10)

        self.screen.blit(label, (rect.centerx - label.get_width() // 2,
                                rect.centery - label.get_height() // 2))
        return rect

    def restart_current_level(self):
        self.start_level(self.level_index)

    def go_to_menu(self):
        self.state = GameState.MENU
        self.selected_level = self.level_index          

    def draw(self):
        if self.state == GameState.MENU:
            self.screen.fill((15, 15, 25))

            title = self.font.render("LEVEL SELECT", True, (255, 255, 255))
            self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 80))

            subtitle = self.font_small.render("Click a level or use UP/DOWN and Enter", True, (180, 180, 180))
            self.screen.blit(subtitle, (self.width // 2 - subtitle.get_width() // 2, 130))

            # build buttons
            self.menu_buttons = []
            mx, my = pygame.mouse.get_pos()

            start_y = 220
            button_w, button_h = 400, 70
            gap = 18

            for i in range(len(self.levels)):
                rect = pygame.Rect(0, 0, button_w, button_h)
                rect.center = (self.width // 2, start_y + i * (button_h + gap))

                hovered = rect.collidepoint(mx, my)
                selected = (i == self.selected_level)

                # background
                if selected:
                    pygame.draw.rect(self.screen, (70, 90, 220), rect, border_radius=10)
                elif hovered:
                    pygame.draw.rect(self.screen, (45, 45, 70), rect, border_radius=10)
                else:
                    pygame.draw.rect(self.screen, (30, 30, 45), rect, border_radius=10)

                # border
                pygame.draw.rect(self.screen, (200, 200, 200), rect, 2, border_radius=10)

                # label + small preview
                preview_level = Level(self.levels[i])  # only for showing coin count
                coins_in_level = len(preview_level.coins)

                text_main = self.font_small.render(f"Level {i+1}", True, (255, 255, 255))
                text_sub = self.font_small.render(f"Coins: {coins_in_level}", True, (200, 200, 200))
                hs_line = self.get_highscore_text(i)
                text_hs = self.font_small.render(hs_line, True, (180, 180, 180))
                self.screen.blit(text_hs, (rect.x + 160, rect.y + 28))

                self.screen.blit(text_main, (rect.x + 18, rect.y + 8))
                self.screen.blit(text_sub, (rect.x + 18, rect.y + 28))

                # little arrow indicator
                if selected:
                    arrow = self.font_small.render("▶", True, (255, 255, 255))
                    self.screen.blit(arrow, (rect.right - 40, rect.y + 14))

                self.menu_buttons.append((rect, i))
            return
            
        else:
            self.screen.fill((0, 0, 0))
            self.level.draw(self.screen, self.camera)
            self.player.draw(self.screen, self.camera)

            # Draw score
            score_text = self.font_small.render(f"Coins: {self.coins_collected}  / {self.max_coins} | Points: {self.score}", True, (255, 255, 255))
            timer_text = self.font_small.render(f"Time: {self.time_elapsed:.1f}s", True, (255, 255, 255))
            self.screen.blit(timer_text, (5, 5))
            self.screen.blit(score_text, (self.width // 2 - score_text.get_width() // 2, 5))

            # Draw win message if all coins are collected
            if self.state == GameState.WON:
                self.screen.fill((10, 10, 20))

                title = self.font.render("YOU WIN!", True, (255, 255, 0))
                self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 120))

                t = self.final_time if self.final_time is not None else self.time_elapsed
                stats = self.font_small.render(
                    f"Points: {self.score} | Time: {t:.1f}s", True, (255, 255, 255)
                )
                self.screen.blit(stats, (self.width // 2 - stats.get_width() // 2, 190))

                best = self.get_highscore_text(self.level_index)
                best_text = self.font_small.render(best, True, (200, 200, 200))
                self.screen.blit(best_text, (self.width // 2 - best_text.get_width() // 2, 225))

                mx, my = pygame.mouse.get_pos()
                self.end_buttons = []

                r1 = self.draw_button("Restart Level (R)", (self.width // 2, 310), False)
                r2 = self.draw_button("Back to Menu (M)", (self.width // 2, 370), False)

                self.end_buttons = [(r1, "restart"), (r2, "menu")]
                for rect, action in self.end_buttons:
                    hovered = rect.collidepoint(mx, my)
                    if action == "restart":
                        self.draw_button("Restart Level (R)", rect.center, hovered)
                    else:
                        self.draw_button("Back to Menu (M)", rect.center, hovered)

                return
            if self.state == GameState.DEATH:
                self.screen.fill((10, 10, 20))

                title = self.font.render("You Died!", True, (255, 60, 60))
                self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 140))

                info = self.font_small.render(f"Level {self.level_index + 1}", True, (200, 200, 200))
                self.screen.blit(info, (self.width // 2 - info.get_width() // 2, 200))

                mx, my = pygame.mouse.get_pos()
                self.end_buttons = []

                r1 = self.draw_button("Restart Level (R)", (self.width // 2, 300), False)
                r2 = self.draw_button("Back to Menu (M)", (self.width // 2, 360), False)

                # hover re-draw (simple way)
                self.end_buttons = [(r1, "restart"), (r2, "menu")]
                for rect, action in self.end_buttons:
                    hovered = rect.collidepoint(mx, my)
                    # redraw hovered state
                    if action == "restart":
                        self.draw_button("Restart Level (R)", rect.center, hovered)
                    else:
                        self.draw_button("Back to Menu (M)", rect.center, hovered)

                return
            if self.state == GameState.DEATH_ANIM:
                self.screen.fill((0, 0, 0))
                self.level.draw(self.screen, self.camera)
                self.player.draw(self.screen, self.camera)
                return
        

game = Game(800, 600)
game.run()

