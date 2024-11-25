
from datetime import timedelta

# Cache behaviors
ALWAYS, CHECK, NEVER = 1, 2, 3

# Cache expiration time
CACHE_EXPIRATION = timedelta(minutes=2)

# What container name is considered the "main" container, if present
MAIN_CONTAINERS = ["main", "notebook", "app"]