
from datetime import timedelta
from pathlib import Path

# Config file and cache folder locations
CONFIG = Path.home() / ".kubeqlrc"
CACHE = Path.home() / ".kubeql"

# Cache behaviors
ALWAYS, CHECK, NEVER = 1, 2, 3

# Cache expiration time
CACHE_EXPIRATION = timedelta(minutes=10)

# What kinds of Kubernetes resources we know about
RESOURCE_KINDS = ["pods", "nodes", "jobs", "workflows"]

# What container name is considered the "main" container, if present
MAIN_CONTAINERS = ["main", "notebook", "app"]