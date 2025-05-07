from qgis.PyQt.QtGui import QIcon
from pathlib import Path

cwd = Path(__file__).parent
IconfeatureNavigation = QIcon(str(cwd / "feature_nav.svg"))
