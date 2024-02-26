from pathlib import Path

# Config file and cache folder locations
CONFIG = Path.home() / ".kubeqlrc"
CACHE = Path.home() / ".kubeql"

# Cache behaviors
ALWAYS, CHECK, NEVER = 1, 2, 3

# What kinds of Kubernetes resources we know about
RESOURCE_KINDS = ["pods", "nodes", "jobs", "workflows"]