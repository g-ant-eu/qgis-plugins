from .plugin import FeatureNavigatorPlugin

def classFactory(iface):
    """QGIS Plugin entry point."""
    return FeatureNavigatorPlugin(iface)
