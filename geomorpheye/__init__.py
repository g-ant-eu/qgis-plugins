from .plugin import GeomorphEyePlugin

def classFactory(iface):
    """QGIS Plugin entry point."""
    return GeomorphEyePlugin(iface)
