from qgis.PyQt.QtGui import QIcon
from pathlib import Path

cwd = Path(__file__).parent
IconGeomorphEye = QIcon(str(cwd / "geomorpheye.svg"))
