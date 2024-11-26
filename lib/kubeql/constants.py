
from datetime import timedelta
import re
from typing import Literal

# Cache behaviors
# TODO consider an enum
ALWAYS_UPDATE, CHECK, NEVER_UPDATE = 1, 2, 3
CacheFlag = Literal[ALWAYS_UPDATE, CHECK, NEVER_UPDATE]

# Cache expiration time
CACHE_EXPIRATION = int(timedelta(minutes=2).total_seconds())

# What container name is considered the "main" container, if present
MAIN_CONTAINERS = ["main", "notebook", "app"]

# Fake namespace if "--all-namespaces" option is used
ALL_NAMESPACE = "__all"

WHITESPACE = re.compile(r"\s+")
