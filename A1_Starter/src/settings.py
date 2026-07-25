# Window size in pixels
WIDTH, HEIGHT = 1080, 720

# Target frames per second for the game loop
FPS = 60

# Colors as RGB tuples used for UI and entities
BG    = (28, 33, 38)     # background color
WHITE = (240, 240, 240)  # text and highlights
GREEN = (90, 220, 120)   # frog color
BLUE  = (120, 180, 250)  # bubble color
YELLOW= (250, 225, 120)  # fly color when flocking or idle
PURPLE= (185, 120, 250)  # fly color when fleeing
RED   = (232, 88, 88)    # health hearts
MUTED = (180, 188, 196)  # hint text

# Frog configuration
FROG_RADIUS = 16          # draw size and collision radius for the frog
FROG_SPEED  = 200.0       # max movement speed in pixels per second
HURT_INVULN = 1.0         # seconds of temporary invulnerability after taking damage

# Bubble configuration
BUBBLE_RADIUS   = 8       # visual and collision radius
BUBBLE_SPEED    = 380.0   # projectile velocity
BUBBLE_LIFETIME = 2.0     # lifetime in seconds before popping

# Fly configuration
NUM_FLIES = 18            # initial fly count
FLY_RADIUS = 8            # fly collision radius
FLY_SPEED  = 120.0        # fly top movement speed

# Flocking weights and perception radii
NEIGHBOR_RADIUS = 120.0   # perception radius for neighbor detection
SEP_RADIUS      = 50.0    # separation threshold distance
SEP_WEIGHT      = 1.9     # separation weight during flocking
FLEE_SEP_WEIGHT = 0.5     # separation weight during fleeing
COH_WEIGHT      = 0.9     # cohesion weight
ALI_WEIGHT      = 0.8     # alignment weight
ANCHOR_WEIGHT   = 0.6     # arena center attraction force weight

# Arrive behavior tuning
ARRIVE_SLOW_RADIUS = 120.0
ARRIVE_STOP_RADIUS = 8.0

# Snake configuration
NUM_SNAKES  = 3
SNAKE_RADIUS = 18
SNAKE_SPEED  = 160.0

# Snake state transition ranges
AGGRO_RANGE   = 260.0     # chase range threshold
DEAGGRO_RANGE = 360.0     # de-aggro distance threshold

# Obstacle avoidance parameters
AVOID_LOOKAHEAD       = 260.0   # forward raycast distance
AVOID_ANGLE_INCREMENT = 12      # angular increment per corridor probe
AVOID_MAX_ANGLE       = 84      # maximum scan angle deviation

# Gap corridor navigation parameters
GAP_MAX_WIDTH       = 120        # max gap width between obstacle pairs
GAP_MIN_WIDTH       = 42         # min gap width to navigate through
GAP_APPROACH_RADIUS = 60.0       # approach threshold before committing through gap

# Gameplay rules
START_HEALTH = 3                 # initial player health
FLIES_TO_WIN = 10                # objective target count
