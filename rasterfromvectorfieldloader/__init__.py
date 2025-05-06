from .plugin import RasterLoaderPlugin

def classFactory(iface):
    """QGIS Plugin entry point."""
    return RasterLoaderPlugin(iface)
