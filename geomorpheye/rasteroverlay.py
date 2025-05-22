from qgis.gui import QgsMapCanvasItem, QgsMapCanvas
from qgis.core import QgsPointXY, QgsRasterLayer, QgsRectangle
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtCore import QRectF, Qt

class RasterOverlay(QgsMapCanvasItem):
    def __init__(self, canvas:QgsMapCanvas, rasterLayer:QgsRasterLayer, x_y_c_r_v_sink_dir_List,
                 readExtent:QgsRectangle, xRes:float, yRes:float,
                draw_flow, draw_pits, draw_values, draw_cells, draw_colors):
        super().__init__(canvas)
        self.canvas = canvas
        self.rasterLayer = rasterLayer
        self.x_y_c_r_v_sink_dir_List = x_y_c_r_v_sink_dir_List
        self.readExtent = readExtent
        self.xRes = xRes
        self.yRes = yRes
        self.draw_flow = draw_flow
        self.draw_pits = draw_pits
        self.draw_values = draw_values
        self.draw_cells = draw_cells
        self.draw_colors = draw_colors
        self.setZValue(1000)  # draw on top

    def boundingRect(self):
        top_left = self.toCanvasCoordinates(QgsPointXY(self.readExtent.xMinimum(), self.readExtent.yMaximum()))
        bottom_right = self.toCanvasCoordinates(QgsPointXY(self.readExtent.xMaximum(), self.readExtent.yMinimum()))
        return QRectF(top_left, bottom_right)

    def paint(self, painter, option, widget):
        painter.setPen(QPen(QColor(255, 149, 0, 255), 1))
        painter.setFont(QFont("Arial", 14))

        for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
            worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
            if self.draw_cells:
                upperLeft = self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY + self.yRes/2))
                lowerRight = self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY - self.yRes/2))
                rect = QRectF(upperLeft, lowerRight)
                painter.drawRect(rect)

            if self.draw_flow and not isSink:
                # draw a point at the center of the cell
                center = self.toCanvasCoordinates(QgsPointXY(worldX, worldY))
                painter.setPen(QPen(QColor(0, 255, 0, 255), 1))
                painter.drawPoint(center)
                # draw an line from the center to the corner or edge in the direction of steepest descent
                if steepestDir is not None:
                    if steepestDir == 1:
                        # draw line to the right edge
                        painter.drawLine(center, self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY)))
                    elif steepestDir == 2:
                        # draw line to the top right corner
                        painter.drawLine(center, self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY + self.yRes/2)))
                    elif steepestDir == 3:
                        # draw line to the top edge
                        painter.drawLine(center, self.toCanvasCoordinates(QgsPointXY(worldX, worldY + self.yRes/2)))
                    elif steepestDir == 4:
                        # draw line to the top left corner
                        painter.drawLine(center, self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY + self.yRes/2)))
                    elif steepestDir == 5:
                        # draw line to the left edge
                        painter.drawLine(center, self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY)))
                    elif steepestDir == 6:
                        # draw line to the bottom left corner
                        painter.drawLine(center, self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY - self.yRes/2)))
                    elif steepestDir == 7:
                        # draw line to the bottom edge
                        painter.drawLine(center, self.toCanvasCoordinates(QgsPointXY(worldX, worldY - self.yRes/2)))
                    elif steepestDir == 8:
                        # draw line to the bottom right corner
                        painter.drawLine(center, self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY - self.yRes/2)))
            
            if self.draw_pits and isSink:
                # draw a point at the center of the cell
                center = self.toCanvasCoordinates(QgsPointXY(worldX, worldY))
                painter.setPen(QPen(QColor(255, 0, 0, 255), 3))
                painter.drawPoint(center)

            if self.draw_values:
                if value is not None:
                    # write col, row and value below each other inside the cell
                    text = f"c: {origCol}\nr: {origRow}\nv: {value}"
                    painter.drawText(rect, Qt.AlignCenter, text)

            


                        
