from qgis.PyQt.QtGui import QIcon
from pathlib import Path

cwd = Path(__file__).parent
IconKlabClient = QIcon(str(cwd / "klabclient.svg"))
