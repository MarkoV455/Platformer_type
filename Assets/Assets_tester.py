import os
import sys
import pygame

# ----------------------------
# CONFIG (tweak these if slicing is a bit off)
# ----------------------------
FRAME_W, FRAME_H = 192, 221  # looks like your character size

SHEETS = {
    "dead": {
        "path": "Player_dead.png",
        "grid": (1, 1),          # cols, rows
        "margin": (0, 0),
        "spacing": (0, 0),
        "fps": 1,
    },
    "idle": {
        "path": "Idle_animation.png",
        "grid": (4, 2),
        "margin": (10, 8),       # try (16,10) if needed
        "spacing": (10, 8),      # try (16,10) if needed
        "fps": 6,
    },
    "jump": {
        "path": "Jump_animation.png",
        "grid": (4, 2),
        "margin": (16, 10),
        "spacing": (16, 10),
        "fps": 8,
    },
    "walk": {
        "path": "Charachter_walk_animation.png",
        "grid": (3, 3),
        "margin": (16, 10),
        "spacing": (16, 10),
        "fps": 10,
    },
}

SCALE = 2  # make it bigger on screen


def slice_sheet(sheet_surf, cols, rows, frame_w, frame_h, margin=(0, 0), spacing=(0, 0)):
    """Slice a spritesheet by grid + frame size + margin/spacing."""
    mx, my = margin
    sx, sy = spacing
    frames = []

    for r in range(rows):
        for c in range(cols):
            x = mx + c * (frame_w + sx)
            y = my + r * (frame_h + sy)
            rect = pygame.Rect(x, y, frame_w, frame_h)

            # guard: don't crash if config is slightly off
            if rect.right <= sheet_surf.get_width() and rect.bottom <= sheet_surf.get_height():
                frame = sheet_surf.subsurface(rect).copy()
                frames.append(frame)

    return frames


class Animation:
    def __init__(self, frames, fps=8, loop=True):
        self.frames = frames
        self.fps = fps
        self.loop = loop
        self.i = 0
        self.t = 0.0

    def reset(self):
        self.i = 0
        self.t = 0.0

    def update(self, dt):
        if len(self.frames) <= 1:
            return

        self.t += dt
        frame_time = 1.0 / max(1, self.fps)
        while self.t >= frame_time:
            self.t -= frame_time
            self.i += 1
            if self.i >= len(self.frames):
                if self.loop:
                    self.i = 0
                else:
                    self.i = len(self.frames) - 1

    def get_frame(self):
        return self.frames[self.i]


def load_animations():
    anims = {}

    # folder where Assets_tester.py lives
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    for name, cfg in SHEETS.items():
        # build full path like: .../Assets/Player_dead.png
        full_path = os.path.join(BASE_DIR, cfg["path"])

        if not os.path.exists(full_path):
            print(f"[ERROR] Missing file: {full_path}")
            sys.exit(1)

        surf = pygame.image.load(full_path).convert_alpha()

        cols, rows = cfg["grid"]
        frames = slice_sheet(
            surf,
            cols=cols,
            rows=rows,
            frame_w=FRAME_W,
            frame_h=FRAME_H,
            margin=cfg["margin"],
            spacing=cfg["spacing"],
        )

        if SCALE != 1:
            frames = [
                pygame.transform.scale(f, (f.get_width() * SCALE, f.get_height() * SCALE))
                for f in frames
            ]

        anims[name] = Animation(frames, fps=cfg["fps"], loop=(name != "jump"))

    return anims


def main():
    pygame.init()
    pygame.display.set_caption("Sprite Sheet Tester")
    screen = pygame.display.set_mode((1000, 700))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 26)

    anims = load_animations()
    current = "idle"
    x, y = 450, 250
    vel = 300
    flip = False

    debug_show_bbox = True

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    current = "idle"
                    anims[current].reset()
                if event.key == pygame.K_2:
                    current = "walk"
                    anims[current].reset()
                if event.key == pygame.K_3:
                    current = "jump"
                    anims[current].reset()
                if event.key == pygame.K_4:
                    current = "dead"
                    anims[current].reset()
                if event.key == pygame.K_b:
                    debug_show_bbox = not debug_show_bbox

        keys = pygame.key.get_pressed()
        moving = False

        if keys[pygame.K_LEFT]:
            x -= vel * dt
            flip = True
            moving = True
        if keys[pygame.K_RIGHT]:
            x += vel * dt
            flip = False
            moving = True

        # auto-switch to walk/idle if you're not forcing jump/dead
        if current not in ("jump", "dead"):
            current = "walk" if moving else "idle"

        anims[current].update(dt)

        # draw
        screen.fill((25, 25, 25))
        pygame.draw.rect(screen, (60, 60, 60), pygame.Rect(0, 520, 1000, 180))  # ground

        frame = anims[current].get_frame()
        if flip:
            frame = pygame.transform.flip(frame, True, False)

        screen.blit(frame, (x, y))

        # debug bbox
        if debug_show_bbox:
            w, h = frame.get_width(), frame.get_height()
            pygame.draw.rect(screen, (255, 255, 0), pygame.Rect(x, y, w, h), 2)

        info = f"[1] idle  [2] walk  [3] jump  [4] dead   Arrows move   [B] bbox   current={current} frames={len(anims[current].frames)}"
        screen.blit(font.render(info, True, (230, 230, 230)), (20, 20))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()