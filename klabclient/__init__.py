import os
import sys

# Make the bundled deps/ directory importable before anything else loads.
_deps = os.path.join(os.path.dirname(__file__), "deps")
if _deps not in sys.path:
    sys.path.insert(0, _deps)

from .plugin import KlabClientPlugin  # noqa: E402


def classFactory(iface):
    return KlabClientPlugin(iface)
