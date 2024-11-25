
from datetime import timedelta
from typing import Literal

# Cache behaviors
# TODO consider an enum
ALWAYS, CHECK, NEVER = 1, 2, 3
CacheFlag = Literal[ALWAYS, CHECK, NEVER]

# Cache expiration time
CACHE_EXPIRATION = timedelta(minutes=2)

# What container name is considered the "main" container, if present
MAIN_CONTAINERS = ["main", "notebook", "app"]

# Fake namespace if "--all-namespaces" option is used
ALL_NAMESPACE = "__all"