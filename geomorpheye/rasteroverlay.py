from qgis.gui import QgsMapCanvasItem, QgsMapCanvas
from qgis.core import QgsPointXY, QgsRasterLayer, QgsRectangle
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtCore import QRectF, Qt

class RasterOverlay(QgsMapCanvasItem):
    def __init__(self, canvas:QgsMapCanvas, rasterLayer:QgsRasterLayer, x_y_c_r_v_sink_dir_List,
                 readExtent:QgsRectangle, xRes:float, yRes:float,
                 fontSize, borderColor, draw_pits, draw_flow, draw_values, draw_cells, draw_colors):
        super().__init__(canvas)
        self.canvas = canvas
        self.rasterLayer = rasterLayer
        self.x_y_c_r_v_sink_dir_List = x_y_c_r_v_sink_dir_List
        self.readExtent = readExtent
        self.xRes = xRes
        self.yRes = yRes
        self.fontSize = fontSize
        self.cellBorderColorHex = borderColor
        self.draw_pits = draw_pits
        self.draw_flow = draw_flow
        self.draw_values = draw_values
        self.draw_cells = draw_cells
        self.draw_colors = draw_colors
        self.setZValue(1000)  # draw on top

        self.radius = 3
        self.textColorHex = "#000000"
        self.flowLinesColorHex = "#1868C4"
        self.sinkColorHex = "#FF0000"
        self.haloColorHex = "#FFFFFF"

    def boundingRect(self):
        top_left = self.toCanvasCoordinates(QgsPointXY(self.readExtent.xMinimum(), self.readExtent.yMaximum()))
        bottom_right = self.toCanvasCoordinates(QgsPointXY(self.readExtent.xMaximum(), self.readExtent.yMinimum()))
        return QRectF(top_left, bottom_right)

    def paint(self, painter, option, widget):
        self.drawCells(painter)
        self.drawFlow(painter)
        value = self.drawSinks(painter)

        self.drawValues(painter, value)

    def drawValues(self, painter, value):
        if self.draw_values:
            painter.setFont(QFont("Arial", self.fontSize))
            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                if value is not None:
                    upperLeft = self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY + self.yRes/2))
                    lowerRight = self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY - self.yRes/2))
                    rect = QRectF(upperLeft, lowerRight)
                    # write col, row and value below each other inside the cell
                    text = f"c: {origCol}\nr: {origRow}\nv: {value}"


                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            offset_rect = QRectF(rect)
                            offset_rect.translate(dx, dy)
                            painter.setPen(QPen(QColor(self.haloColorHex), 1))
                            painter.drawText(offset_rect, Qt.AlignCenter, text)


                    painter.setPen(QPen(QColor(self.textColorHex), 1))
                    painter.drawText(rect, Qt.AlignCenter, text)

    def drawSinks(self, painter):
        if self.draw_pits:
            painter.setPen(QPen(QColor(self.sinkColorHex), 1))
            painter.setBrush(QColor(self.sinkColorHex))
            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                if isSink:
                    # draw a point at the center of the cell
                    center = self.toCanvasCoordinates(QgsPointXY(worldX, worldY))
                    painter.drawEllipse(center, self.radius, self.radius)
        return value

    def drawFlow(self, painter):
        if self.draw_flow:
            painter.setPen(QPen(QColor(self.flowLinesColorHex), 1))
            painter.setBrush(QColor(self.flowLinesColorHex))
            scale = 0.85 # to avoid touching the cell borders
            

            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                if isSink:
                    continue

                center = QgsPointXY(worldX, worldY)

                dx = dy = 0
                if steepestDir == 1:   dx =  self.xRes / 2
                elif steepestDir == 2: dx =  self.xRes / 2; dy =  self.yRes / 2
                elif steepestDir == 3: dy =  self.yRes / 2
                elif steepestDir == 4: dx = -self.xRes / 2; dy =  self.yRes / 2
                elif steepestDir == 5: dx = -self.xRes / 2
                elif steepestDir == 6: dx = -self.xRes / 2; dy = -self.yRes / 2
                elif steepestDir == 7: dy = -self.yRes / 2
                elif steepestDir == 8: dx =  self.xRes / 2; dy = -self.yRes / 2

                if steepestDir is not None:
                    end = QgsPointXY(worldX + dx * scale, worldY + dy * scale)
                    canvas_center = self.toCanvasCoordinates(center)
                    canvas_end = self.toCanvasCoordinates(end)
                    
                    painter.drawEllipse(canvas_center, self.radius, self.radius)
                    painter.drawLine(canvas_center, canvas_end)

    def drawCells(self, painter):
        if self.draw_cells:
            painter.setPen(QPen(QColor(self.cellBorderColorHex), 1))
            for x_y_c_r_v_sink_dir in self.x_y_c_r_v_sink_dir_List:
                worldX, worldY, origCol, origRow, value, isSink, steepestDir = x_y_c_r_v_sink_dir
                upperLeft = self.toCanvasCoordinates(QgsPointXY(worldX - self.xRes/2, worldY + self.yRes/2))
                lowerRight = self.toCanvasCoordinates(QgsPointXY(worldX + self.xRes/2, worldY - self.yRes/2))
                rect = QRectF(upperLeft, lowerRight)
                painter.drawRect(rect)

            


                        
