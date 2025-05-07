from qgis.PyQt.QtGui import QIcon
from pathlib import Path

cwd = Path(__file__).parent
IconRasterLoader = QIcon(str(cwd / "add_raster.svg"))
