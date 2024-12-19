
from datetime import timedelta
from pathlib import Path
import re
from typing import Literal

# Cache behaviors
# TODO consider an enum
ALWAYS_UPDATE, CHECK, NEVER_UPDATE = 1, 2, 3
CacheFlag = Literal[ALWAYS_UPDATE, CHECK, NEVER_UPDATE]

# What container name is considered the "main" container, if present
MAIN_CONTAINERS = ["main", "notebook", "app"]

# Fake namespace if "--all-namespaces" option is used
# TODO: move into Kubernetes resource domain
ALL_NAMESPACE = "__all"

WHITESPACE = re.compile(r"\s+")

# For use with simulated clock
UNIT_TEST_TIMEBASE = 1733798942