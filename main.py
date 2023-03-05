from functools import partial
import json
import math
import os.path
import sys
import typing
from collections import namedtuple
from svgelements import SVG

from PyQt5 import QtCore, QtGui, QtWidgets, QtSvg
from PyQt5.QtCore import Qt
from typing import Tuple

from UI import home, graphics_view, helpDialog

pos = namedtuple("mouse_coor", ("x", "y"))
BASE = os.path.dirname(os.path.abspath(__file__))
config_file = os.path.join(BASE, "config.json")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.current_shape = None
        self.ui = home.Ui_MainWindow()
        self.ui.setupUi(self)

        # -------- class attributes --------
        self.temp_drawing_item: typing.Union[None, QtWidgets.QGraphicsItem] = None
        self.temp_drawing_activated = False
        self.grid_image = os.path.join(BASE, "UI", "images", "grid2.png")
        # temp drawing pen with red color and dotted line

        self.selection_rect_pen = QtGui.QPen(QtGui.QColor("#2073e8"), 3, Qt.DashLine)
        self.drawing_items_list = []  # max length 10
        self.selected_item: typing.Union[None, QtWidgets.QGraphicsItem] = None
        self.selected_rect_item: typing.Union[None, QtWidgets.QGraphicsItem] = None

        # ------------------ widget customizations ------------------
        self.ui.comboBox_LineStyle.addItems(["Solid", "Dash", "DashDot", "Dot"])
        self.ui.label_show_pen_color.setStyleSheet(
            """
            border: 5px solid black;
            border-radius: 5px;
            background-color: black;
            """
        )
        # self.ui.label_show_pen_color.setText("Current Pen Color")
        self.ui.label_show_pen_color.setAlignment(Qt.AlignCenter)
        self.graphics_colorize_effect = QtWidgets.QGraphicsColorizeEffect(self)
        self.graphics_colorize_effect.setColor(Qt.black)  # default pen color
        self.ui.label_show_pen_color.setGraphicsEffect(self.graphics_colorize_effect)

        self.graphicsView_canvas = graphics_view.CustomGraphicsView(parent=self.ui.frame_left)
        self.graphicsView_canvas.mouse_pos_signal.connect(self.show_mouse_pos)
        self.graphicsView_canvas.change_cursor_signal.connect(self.change_cursor)
        self.graphicsView_canvas.draw_line_signal.connect(self.draw_line)
        self.graphicsView_canvas.draw_circle_signal.connect(self.draw_circle)
        self.graphicsView_canvas.draw_rect_signal.connect(self.draw_rectangle)
        self.graphicsView_canvas.draw_curve_signal.connect(self.draw_curve)
        self.graphicsView_canvas.draw_text_signal.connect(self.draw_text)
        self.graphicsView_canvas.draw_polyline_signal.connect(self.draw_polyline)
        self.graphicsView_canvas.toggle_temp_drawing.connect(self.toggle_temp_drawing)
        self.graphicsView_canvas.draw_selected_item_rect.connect(self.draw_selected_item_rect)
        self.graphicsView_canvas.item_pasted_signal.connect(self.add_item_to_drawing_list)
        self.graphicsView_canvas.clear_selection_rect.connect(self.clear_selection_rect)
        self.graphicsView_canvas.show_status_bar_message_signal.connect(self.show_status_bar_message)

        self.ui.frame_left.layout().addWidget(self.graphicsView_canvas)

        center_ = self.mapToGlobal(self.graphicsView_canvas.frameGeometry().center())
        x_ = center_.x()
        y_ = center_.y()
        self.current_mouse_pos = pos(x_, y_)

        # ====================== drawing defaults ======================
        self.select_line()
        self.ui.radioButton_line.setChecked(True)  # default shape (Line)
        self.point_size = 3  # default pen size
        self.line_style = Qt.SolidLine  # default line style
        self.current_pen_color = Qt.black  # default pen color
        self.current_font = QtGui.QFont(self.ui.fontComboBox_text.currentFont().family(), 12)  # current font for text
        self.change_pen_size(self.point_size)
        self.change_font_size(self.current_font.pointSize())
        self.ui.horizontalSlider_penSize.setValue(self.point_size)
        self.ui.horizontalSlider_fontSize.setValue(self.current_font.pointSize())
        self.temp_drawing_pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)
        # ====================== actions ======================
        self.ui.actionLoad_Image.triggered.connect(self.load_image)
        self.ui.actionLoad_SVG.triggered.connect(self.load_svg)

        self.ui.actionReset.triggered.connect(self.reset)
        self.ui.actionNew.triggered.connect(self.new_action_triggered)
        self.ui.actionExit.triggered.connect(self.exit_action_triggered)
        self.ui.actionSave.triggered.connect(self.save_image)
        # Ctrl+Z shortcut
        self.ui.actionUndo.setShortcut("Ctrl+Z")
        self.ui.actionUndo.triggered.connect(self.undo_item)

        # action full screen
        self.actionFull_Screen = QtWidgets.QAction(self)
        self.actionFull_Screen.setShortcut("F11")
        self.actionFull_Screen.setText("Full Screen")
        self.actionFull_Screen.triggered.connect(self.full_screen)
        self.ui.menuFile.addAction(self.actionFull_Screen)

        # action auto-configure
        self.actionAuto_Configure = QtWidgets.QAction(self)
        self.actionAuto_Configure.setShortcut("Ctrl+A")
        self.actionAuto_Configure.setText("Auto-Configure Canvas Size")
        self.actionAuto_Configure.triggered.connect(partial(self.autoconfigure_canvas_size, True))
        self.ui.menuFile.addAction(self.actionAuto_Configure)

        # Help menu
        self.ui.actionAbout.triggered.connect(self.show_about_dialog)

        # action show/hide grid
        self.actionShow_Grid = QtWidgets.QAction(self)
        self.actionShow_Grid.setText("Show Grid")
        self.actionShow_Grid.setCheckable(True)
        self.actionShow_Grid.triggered.connect(self.toggle_grid)
        self.ui.menuImage.addAction(self.actionShow_Grid)
        self.grid_size = 10

        # ====================== button signals ======================
        self.ui.radioButton_line.clicked.connect(self.select_line)
        self.ui.radioButton_circle.clicked.connect(self.select_circle)
        self.ui.radioButton_square.clicked.connect(self.select_rectangle)
        self.ui.radioButton_curve.clicked.connect(self.select_curve)
        self.ui.radioButton_polyline.clicked.connect(self.select_polyline)

        self.ui.pushButton_text_inp_pos.clicked.connect(self.set_text_input_pos)
        self.ui.fontComboBox_text.currentFontChanged.connect(self.font_changed)
        self.ui.comboBox_LineStyle.currentIndexChanged.connect(self.line_changed)

        self.ui.pushButton_pickColor.clicked.connect(self.pick_color)
        self.ui.horizontalSlider_penSize.valueChanged[int].connect(self.change_pen_size)
        self.ui.horizontalSlider_fontSize.valueChanged[int].connect(self.change_font_size)

        # ====================== graphics scene ======================
        self._scene = QtWidgets.QGraphicsScene(self.graphicsView_canvas)
        self.graphicsView_canvas.setScene(self._scene)
        self.lines = []
        self.circles = []
        self.rects = []
        self.texts = []
        self.curves = []
        self.points_grid = []
        self.autoconfigure_canvas_size()
        self.activate_mouse_check_timer()

    # ====================== menu actions ======================
    def autoconfigure_canvas_size(self, manual_trigger=False):
        # load autoconfiguration if available
        config = self.load_config()
        if config and not manual_trigger:
            max_viewport_size = config["max_viewport_size"]
            self._scene.setSceneRect(QtCore.QRectF(0, 0, max_viewport_size[0], max_viewport_size[1]))
        elif manual_trigger:
            # get view port size
            view_port_size = self.graphicsView_canvas.viewport().size()
            # get scene size
            self._scene.setSceneRect(QtCore.QRectF(self.graphicsView_canvas.viewport().rect()))
            print(f"view port size & scene size: {view_port_size}")
            self.save_config({"max_viewport_size": [view_port_size.width(), view_port_size.height()]})
        self.graphicsView_canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.graphicsView_canvas.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def full_screen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def toggle_grid(self):
        if self.actionShow_Grid.isChecked():
            # _bg_brush = QtGui.QBrush(QtGui.QPixmap(self.grid_image))
            _bg_brush = QtGui.QBrush()
            _bg_brush.setColor(QtGui.QColor('#999'))
            _bg_brush.setStyle(Qt.CrossPattern)
            self._scene.setBackgroundBrush(_bg_brush)
            self.graphicsView_canvas.is_grid_on(False)

        else:
            self._scene.setBackgroundBrush(Qt.white)
            self.graphicsView_canvas.is_grid_on(True)
        self._scene.update()

    def load_image(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.png *.jpg *.bmp)")
        if file_name:
            self._scene.addPixmap(QtGui.QPixmap(file_name))
        self._scene.update()

    def save_image(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Image", "",
                                                             "Image Files (*.png *.jpg *.jpeg *.bmp *.svg)")

        if file_name:
            ext = os.path.splitext(file_name)[1]
            if ext == "":
                file_name += ".png"  # default extension (when user doesn't specify extension)
            if ext.lower() == ".svg":
                svg_generator = QtSvg.QSvgGenerator()
                svg_generator.setFileName(file_name)
                _canvas_size = self.graphicsView_canvas.viewport().size()
                svg_generator.setSize(_canvas_size)

                painter = QtGui.QPainter()
                painter.begin(svg_generator)
                self._scene.render(painter)
                painter.end()
                return
            print(file_name)
            self.graphicsView_canvas.grab().save(file_name)

    def reset(self):
        self._scene.clear()
        self._scene.update()

    def toggle_temp_drawing(self, action: bool):
        self.temp_drawing_activated = action
        if not action and self.temp_drawing_item:
            self.remove_item_from_scene(self.temp_drawing_item)

    def new_action_triggered(self):
        self.reset()
        self.current_pen_color = Qt.black
        self.graphics_colorize_effect.setColor(self.current_pen_color)
        self.graphicsView_canvas.cancel_wait_for_mouse_click()
        self.ui.lineEdit_input_text.clear()
        self.ui.radioButton_line.setChecked(True)
        self.select_line()

    def exit_action_triggered(self):
        self.close()

    def font_changed(self, font: QtGui.QFont):
        self.current_font = font

    def line_changed(self, line):
        if line == 0:
            self.line_style = Qt.SolidLine
        elif line == 1:
            self.line_style = Qt.DashLine
        elif line == 2:
            self.line_style = Qt.DashDotLine
        elif line == 3:
            self.line_style = Qt.DotLine

    @QtCore.pyqtSlot(str)
    def show_status_bar_message(self, message: str):
        self.ui.statusbar.showMessage(message, 3000)  # show status bar message for 3 seconds

    @QtCore.pyqtSlot(int)
    def change_font_size(self, size: int):
        self.current_font.setPointSize(size)
        self.ui.label_font_size.setText(f"Select font size <b>(current {size}pt)</b>")

    @QtCore.pyqtSlot(int)
    def change_pen_size(self, size: int):
        self.point_size = size
        self.ui.label_show_pen_size.setText(f"Pen Size: {size}")

    # ------------------ drawing ------------------
    def pick_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.current_pen_color = color
            self.graphics_colorize_effect.setColor(self.current_pen_color)

    def select_circle(self):
        self.current_shape = "circle"
        self.graphicsView_canvas.set_current_item(self.current_shape)

    def select_line(self):
        self.current_shape = "line"
        self.graphicsView_canvas.set_current_item(self.current_shape)

    def select_rectangle(self):
        self.current_shape = "rectangle"
        self.graphicsView_canvas.set_current_item(self.current_shape)

    def select_curve(self):
        self.current_shape = "curve"
        self.graphicsView_canvas.set_current_item(self.current_shape)

    def select_polyline(self):
        self.current_shape = "polyline"
        self.graphicsView_canvas.set_current_item(self.current_shape)

    def add_item_to_drawing_list(self, item: QtWidgets.QGraphicsItem):
        """
        gets used when a new item is pasted in the scene
        :param item:
        :return:
        """
        self.drawing_items_list.append(item)

    @staticmethod
    def remove_item_from_scene(item: QtWidgets.QGraphicsItem):
        _scene = item.scene()
        if _scene:
            _scene.removeItem(item)

    @QtCore.pyqtSlot()
    def undo_item(self):  # action on Ctrl+Z
        if self.drawing_items_list:
            self.remove_item_from_scene(self.drawing_items_list[-1])
            self.drawing_items_list.pop()

    def select_delete(self):
        if self.selected_item:
            self.remove_item_from_scene(self.selected_item)
            if self.selected_item in self.drawing_items_list:
                self.drawing_items_list.remove(self.selected_item)
            self.selected_item = None
            self.remove_item_from_scene(self.selected_rect_item)
            self.selected_item = None
            self.selected_rect_item = None

    @staticmethod
    def draw_when_grid_on(grid_size, act_pos1):
        if (act_pos1 % grid_size) < grid_size / 2:
            counted_pos = (act_pos1 // grid_size) * grid_size
        else:
            counted_pos = (act_pos1 // grid_size) * grid_size + grid_size
        return counted_pos

    def draw_line(self, args):
        start_pos, end_pos = args
        if self.actionShow_Grid.isChecked():
            start_pos_x = self.draw_when_grid_on(self.grid_size, start_pos.x())
            start_pos_y = self.draw_when_grid_on(self.grid_size, start_pos.y())
            end_pos_x = self.draw_when_grid_on(self.grid_size, end_pos.x())
            end_pos_y = self.draw_when_grid_on(self.grid_size, end_pos.y())
            _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
            if self.temp_drawing_activated and self.temp_drawing_item:
                self.remove_item_from_scene(self.temp_drawing_item)
                _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)

            graphics_item = self._scene.addLine(start_pos_x, start_pos_y, end_pos_x, end_pos_y,
                                                pen=_pen)

            if self.temp_drawing_activated:
                self.temp_drawing_item = graphics_item
            else:
                self.drawing_items_list.append(graphics_item)

            self._scene.update()
        else:
            _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
            if self.temp_drawing_activated and self.temp_drawing_item:
                self.remove_item_from_scene(self.temp_drawing_item)
                _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)

            graphics_item = self._scene.addLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y(),
                                                pen=_pen)
            if self.temp_drawing_activated:
                self.temp_drawing_item = graphics_item
            else:
                self.drawing_items_list.append(graphics_item)
            self._scene.update()

    def draw_polyline(self, args):
        start_pos, end_pos = args
        if self.actionShow_Grid.isChecked():
            start_pos_x = self.draw_when_grid_on(self.grid_size, start_pos.x())
            start_pos_y = self.draw_when_grid_on(self.grid_size, start_pos.y())
            end_pos_x = self.draw_when_grid_on(self.grid_size, end_pos.x())
            end_pos_y = self.draw_when_grid_on(self.grid_size, end_pos.y())
            if self.graphicsView_canvas.is_first_line:
                _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
                if self.temp_drawing_activated and self.temp_drawing_item:
                    self.remove_item_from_scene(self.temp_drawing_item)
                    _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)
                graphics_item = self._scene.addLine(start_pos_x, start_pos_y, end_pos_x, end_pos_y,
                                                    pen=_pen)
                if self.temp_drawing_activated:
                    self.temp_drawing_item = graphics_item
                else:
                    self.drawing_items_list.append(graphics_item)
                    self.graphicsView_canvas.is_first_line = False
            else:
                _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
                if self.temp_drawing_activated and self.temp_drawing_item:
                    self.remove_item_from_scene(self.temp_drawing_item)
                    _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)

                graphics_item = self._scene.addLine(start_pos_x, start_pos_y, end_pos_x, end_pos_y,
                                                    pen=_pen)
                if self.temp_drawing_activated:
                    self.temp_drawing_item = graphics_item
                else:
                    self.drawing_items_list.append(graphics_item)
                    self.graphicsView_canvas.is_first_line = False
        else:
            if self.graphicsView_canvas.is_first_line:
                _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
                if self.temp_drawing_activated and self.temp_drawing_item:
                    self.remove_item_from_scene(self.temp_drawing_item)
                    _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)
                graphics_item = self._scene.addLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y(),
                                                    pen=_pen)
                if self.temp_drawing_activated:
                    self.temp_drawing_item = graphics_item
                else:
                    self.drawing_items_list.append(graphics_item)
                    self.graphicsView_canvas.is_first_line = False
            else:
                _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
                if self.temp_drawing_activated and self.temp_drawing_item:
                    self.remove_item_from_scene(self.temp_drawing_item)
                    _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)

                graphics_item = self._scene.addLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y(),
                                                    pen=_pen)
                if self.temp_drawing_activated:
                    self.temp_drawing_item = graphics_item
                else:
                    self.drawing_items_list.append(graphics_item)
                    self.graphicsView_canvas.is_first_line = False
        self._scene.update()

    def draw_circle(self, args):
        start_pos, end_pos = args
        start_pos: QtCore.QPoint
        end_pos: QtCore.QPoint
        if self.actionShow_Grid.isChecked():
            start_pos_x = self.draw_when_grid_on(self.grid_size, start_pos.x())
            start_pos_y = self.draw_when_grid_on(self.grid_size, start_pos.y())
            end_pos_x = self.draw_when_grid_on(self.grid_size, end_pos.x())
            end_pos_y = self.draw_when_grid_on(self.grid_size, end_pos.y())
            center_x = (start_pos_x + end_pos_x) / 2
            center_y = (start_pos_y + end_pos_y) / 2
            radius = self.distance_grid(start_pos_x, start_pos_y, end_pos_x, end_pos_y) / 2
            center_pos = QtCore.QPointF(center_x, center_y)
            inner_circle_radius = radius

            tl2 = QtCore.QPointF(center_pos.x() - inner_circle_radius, center_pos.y() - inner_circle_radius)
            br2 = QtCore.QPointF(center_pos.x() + inner_circle_radius, center_pos.y() + inner_circle_radius)

            _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
            _rect = QtCore.QRectF(tl2, br2)
            if self.temp_drawing_activated and self.temp_drawing_item:
                self.remove_item_from_scene(self.temp_drawing_item)
                _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)

            graphics_item = self._scene.addEllipse(_rect, _pen)
            if self.temp_drawing_activated:
                self.temp_drawing_item = graphics_item
            else:
                self.drawing_items_list.append(graphics_item)
            self._scene.update()
        else:
            center_x = (start_pos.x() + end_pos.x()) / 2
            center_y = (start_pos.y() + end_pos.y()) / 2
            radius = self.distance(start_pos, end_pos) / 2
            center_pos = QtCore.QPointF(center_x, center_y)
            inner_circle_radius = radius

            tl2 = QtCore.QPointF(center_pos.x() - inner_circle_radius, center_pos.y() - inner_circle_radius)
            br2 = QtCore.QPointF(center_pos.x() + inner_circle_radius, center_pos.y() + inner_circle_radius)

            _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
            _rect = QtCore.QRectF(tl2, br2)
            if self.temp_drawing_activated and self.temp_drawing_item:
                self.remove_item_from_scene(self.temp_drawing_item)
                _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)

            graphics_item = self._scene.addEllipse(_rect, _pen)
            if self.temp_drawing_activated:
                self.temp_drawing_item = graphics_item
            else:
                self.drawing_items_list.append(graphics_item)
            self._scene.update()

    def draw_selected_item_rect(self, args):
        rect_f: QtCore.QRectF = args[0]  # bounding rect
        rect_item = args[1]  # bounding rect for this item
        if self.selected_rect_item and rect_item == self.selected_rect_item:
            self.remove_item_from_scene(self.selected_rect_item)
            self.selected_item = None
            self.selected_rect_item = None
            return
        elif self.selected_rect_item:  # only 1 selection allowed at a time
            self.remove_item_from_scene(self.selected_rect_item)
        self.selected_rect_item = self._scene.addRect(rect_f, pen=self.selection_rect_pen)
        self.selected_item = rect_item

    def clear_selection_rect(self):
        if self.selected_rect_item:
            self.remove_item_from_scene(self.selected_rect_item)
            self.selected_rect_item = None
            self.selected_item = None

    def draw_rectangle(self, args):
        start_pos, end_pos = args
        if self.actionShow_Grid.isChecked():
            start_pos_x = self.draw_when_grid_on(self.grid_size, start_pos.x())
            start_pos_y = self.draw_when_grid_on(self.grid_size, start_pos.y())
            end_pos_x = self.draw_when_grid_on(self.grid_size, end_pos.x())
            end_pos_y = self.draw_when_grid_on(self.grid_size, end_pos.y())
            _rectF = QtCore.QRectF(start_pos_x, start_pos_y, end_pos_x - start_pos_x, end_pos_y - start_pos_y)
            _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
            if self.temp_drawing_activated and self.temp_drawing_item:
                self.remove_item_from_scene(self.temp_drawing_item)
                _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)

            graphics_item = self._scene.addRect(_rectF, pen=_pen)
            if self.temp_drawing_activated:
                self.temp_drawing_item = graphics_item
            else:
                self.drawing_items_list.append(graphics_item)
            self._scene.update()
        else:
            _rectF = QtCore.QRectF(start_pos, end_pos)
            _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
            if self.temp_drawing_activated and self.temp_drawing_item:
                self.remove_item_from_scene(self.temp_drawing_item)
                _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)

            graphics_item = self._scene.addRect(_rectF, pen=_pen)
            if self.temp_drawing_activated:
                self.temp_drawing_item = graphics_item
            else:
                self.drawing_items_list.append(graphics_item)
            self._scene.update()

    def draw_curve(self, args):
        curve_points: Tuple[QtCore.QPoint] = args
        if self.actionShow_Grid.isChecked():
            if len(curve_points) == 2:
                print(curve_points[0].x())
                self.points_grid.append(self.draw_when_grid_on(self.grid_size, curve_points[0].x()))
                self.points_grid.append(self.draw_when_grid_on(self.grid_size, curve_points[0].y()))
                self.points_grid.append(self.draw_when_grid_on(self.grid_size, curve_points[1].x()))
                self.points_grid.append(self.draw_when_grid_on(self.grid_size, curve_points[1].y()))
                _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)
                graphics_item = self._scene.addLine(self.points_grid[0], self.points_grid[1], self.points_grid[2],
                                                    self.points_grid[3], pen=_pen)
                self.temp_drawing_item = graphics_item
                self._scene.update()

            elif len(curve_points) == 3:
                self.points_grid.insert(4, self.draw_when_grid_on(self.grid_size, curve_points[2].x()))
                self.points_grid.insert(5, self.draw_when_grid_on(self.grid_size, curve_points[2].y()))
                print("1. ", len(self.points_grid))
                if len(self.points_grid) > 6:
                    print("2. ", len(self.points_grid))
                    print(self.points_grid)
                    del self.points_grid[6:]
                self.remove_item_from_scene(self.temp_drawing_item)
                _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
                if self.temp_drawing_activated and self.temp_drawing_item:
                    self.remove_item_from_scene(self.temp_drawing_item)
                    _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)
                graphics_item = self._scene.addPath(self.create_curve_grid(self.points_grid), _pen)
                if self.temp_drawing_activated:
                    self.temp_drawing_item = graphics_item
                else:
                    self.drawing_items_list.append(graphics_item)
                    self.points_grid.clear()
                    print(self.points_grid)
        else:
            if len(curve_points) == 2:
                _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)
                graphics_item = self._scene.addLine(curve_points[0].x(), curve_points[0].y(), curve_points[1].x(),
                                                    curve_points[1].y(), pen=_pen)
                self.temp_drawing_item = graphics_item
                self._scene.update()

            elif len(curve_points) == 3:
                self.remove_item_from_scene(self.temp_drawing_item)
                _pen = QtGui.QPen(self.current_pen_color, self.point_size, self.line_style)
                if self.temp_drawing_activated and self.temp_drawing_item:
                    self.remove_item_from_scene(self.temp_drawing_item)
                    _pen = QtGui.QPen(QtGui.QColor("#ea353e"), self.point_size, Qt.DotLine)
                graphics_item = self._scene.addPath(self.create_curve(*curve_points), _pen)
                if self.temp_drawing_activated:
                    self.temp_drawing_item = graphics_item
                else:
                    self.drawing_items_list.append(graphics_item)
                    self.points_grid.clear()
                    print(self.points_grid)
        self._scene.update()

    @staticmethod
    def create_curve(*points):
        path = QtGui.QPainterPath()
        path.moveTo(points[0])
        path.cubicTo(points[0], points[2], points[1])
        print(*points)
        return path

    def create_curve_grid(self, points):
        path = QtGui.QPainterPath()
        path.moveTo(points[0], points[1])
        path.cubicTo(points[0], points[1], points[4], points[5], points[2], points[3])
        print(*points)
        return path

    def draw_text(self, args):
        text, text_pos = args
        text_item = self._scene.addText(text, self.current_font)
        text_item.setPos(text_pos.x(), text_pos.y())
        text_item.setDefaultTextColor(self.current_pen_color)
        self.ui.pushButton_text_inp_pos.setChecked(False)

    def set_text_input_pos(self):
        text = self.ui.lineEdit_input_text.text()
        self.graphicsView_canvas.wait_for_mouse_click(text)

    # ====================== events ======================
    def show_about_dialog(self):
        self.about_dialog = helpDialog.AboutDialog(self)
        self.about_dialog.exec()

    def show_mouse_pos(self, mouse_pos: QtCore.QPoint):
        self.current_mouse_pos = mouse_pos
        self.ui.label_pointer.setText(f"x: {mouse_pos.x()}, y: {mouse_pos.y()}")

    def change_cursor(self, cursor_type: QtCore.Qt.CursorShape):
        self.setCursor(QtGui.QCursor(cursor_type))
        self.graphicsView_canvas.setCursor(QtGui.QCursor(cursor_type))

    def custom_mouse_pos_check(self) -> None:
        if self.graphicsView_canvas.underMouse():
            pass
        else:
            self.change_cursor(QtCore.Qt.ArrowCursor)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == QtCore.Qt.Key_Delete:
            self.select_delete()
        super(MainWindow, self).keyPressEvent(event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        # if scene has fixed size, handling resizeEvent is not required for accurate scaling
        # self._scene.setSceneRect(0, 0, self.graphicsView_canvas.viewport().width(),
        #                          self.graphicsView_canvas.viewport().height())
        # self.graphicsView_canvas.fitInView(self._scene.sceneRect(), QtCore.Qt.KeepAspectRatioByExpanding)
        super(MainWindow, self).resizeEvent(event)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        super(MainWindow, self).showEvent(event)

        # ------ set the scene rect, after the windows is displayed completely --------
        _view_port_rectF = QtCore.QRectF(self.graphicsView_canvas.viewport().rect())
        self._scene.setSceneRect(_view_port_rectF)
        _rectF = self._scene.sceneRect()
        self.graphicsView_canvas.fitInView(_rectF, QtCore.Qt.IgnoreAspectRatio)

    # ====================== utility ======================
    @staticmethod
    def distance(p1: QtCore.QPoint, p2: QtCore.QPoint):
        squared_distance = math.sqrt(abs(p1.x() - p2.x()) ** 2 + abs(p1.y() - p2.y()) ** 2)
        return squared_distance

    @staticmethod
    def distance_grid(x1, y1, x2, y2):
        squared_distance = math.sqrt(abs(x1 - x2) ** 2 + abs(y1 - y2) ** 2)
        return squared_distance

    @staticmethod
    def load_config():
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = json.load(f)
            return config
        else:
            return None

    @staticmethod
    def save_config(config):
        if config is None:
            config = {}
        with open(config_file, "w") as f:
            json.dump(config, f)

    def load_svg(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Image", "", "Image Files (*.svg)")
        if file_name:
            svg = SVG.parse(file_name)
            print(list(svg.elements()))  # the whole list of svg elements
            print(svg[2])  # list of elements we need
            used_elements = svg[2]
            used_elements_len = len(used_elements)
            print(used_elements_len)

            for i in range(0, used_elements_len):  # starting from 3, because the first rect is useless
                fn = used_elements[i]
                if fn:  # if it is not empty

                    # using list comprehension
                    listToStr = ' '.join([str(elem) for elem in fn])

                    print(listToStr)
                    separator = listToStr.find("(")
                    element = listToStr[:separator]
                    separator = listToStr.find(" ")
                    is_path = listToStr[:separator]
                    if element == 'Polyline':
                        start_x = fn[0].points[0].x
                        start_y = fn[0].points[0].y
                        end_x = fn[0].points[1].x
                        end_y = fn[0].points[1].y
                        color = fn.values['stroke']
                        pen_size = int(round(float(fn.values['stroke-width'])))
                        self.lines.append([start_x, start_y, end_x, end_y, color, pen_size])
                    elif element == 'Circle' or element == 'Ellipse':
                        cx = fn[0].cx
                        cy = fn[0].cy
                        r = fn[0].implicit_r
                        color = fn.values['stroke']
                        pen_size = int(round(float(fn.values['stroke-width'])))
                        self.circles.append([cx, cy, r, color, pen_size])
                    elif element == 'Rect':
                        separator1 = listToStr.find("fill='") + 6
                        separator2 = listToStr.find("f'") - 1
                        separator3 = listToStr.find("x=")
                        # print(separator3)
                        error = listToStr[separator1:separator2]
                        # print(error)
                        if separator3 == -1:
                            print("grid")
                            pass
                        else:
                            x = fn[0].x
                            y = fn[0].y
                            width = fn[0].width
                            height = fn[0].height
                            color = fn.values['stroke']
                            pen_size = int(round(float(fn.values['stroke-width'])))
                            self.rects.append([x, y, width, height, color, pen_size])

                    elif element == 'Text':
                        x = fn[0].transform.e
                        y = fn[0].transform.f
                        text = fn[0].text
                        font_family = fn[0].font_family
                        color = fn.values['stroke']
                        font_size = int(fn[0].font_size)
                        self.texts.append([text, x, y, font_family, font_size, color])

                    if is_path == "M":
                        points = fn[0]._segments[1]
                        start_x = points.start.x
                        start_y = points.start.y
                        middle_x = points.control2.x
                        middle_y = points.control2.y
                        end_x = points.end.x
                        end_y = points.end.y
                        color = fn.values['stroke']
                        pen_size = int(round(float(fn.values['stroke-width'])))
                        self.curves.append([start_x, start_y, middle_x, middle_y, end_x, end_y, color, pen_size])
                else:
                    print("empty")
        self.draw_svg(self.lines, self.circles, self.rects, self.texts, self.curves)

    def draw_svg(self, lines, circles, rects, texts, curves):
        for i in range(len(self.lines)):
            line = lines[i]
            print(line)
            _pen = QtGui.QPen(QtGui.QColor(line[4]), (line[5]))
            self._scene.addLine(line[0], line[1], line[2], line[3], pen=_pen)
            print("line added")

        for i in range(len(self.circles)):
            circle = circles[i]
            print(circle)
            _pen = QtGui.QPen(QtGui.QColor(circle[3]), (circle[4]))
            self._scene.addEllipse(circle[0] - circle[2], circle[1] - circle[2], circle[2] * 2, circle[2] * 2, pen=_pen)
            print("circle added")

        for i in range(len(self.rects)):
            rect = rects[i]
            print(rect)
            _pen = QtGui.QPen(QtGui.QColor(rect[4]), (rect[5]))
            self._scene.addRect(rect[0], rect[1], rect[2], rect[3], pen=_pen)
            print("rect added")
        for i in range(len(self.texts)):
            text = texts[i]
            font = QtGui.QFont(text[3], text[4])
            text_item = self._scene.addText(text[0], font)
            text_item.setPos(text[1], text[2])
        for i in range(len(self.curves)):
            curve = curves[i]
            path = QtGui.QPainterPath()
            path.moveTo(curve[0], curve[1])
            path.cubicTo(curve[0], curve[1], curve[2], curve[3], curve[4], curve[5])
            _pen = QtGui.QPen(QtGui.QColor(curve[6]), (curve[7]))
            self._scene.addPath(path, pen=_pen)

        self.lines.clear()
        self.circles.clear()
        self.rects.clear()
        self.texts.clear()
        self.curves.clear()
        self._scene.update()

    def activate_mouse_check_timer(self):
        """
        activate mouse check timer
        """
        self.mouse_check_timer = QtCore.QTimer()
        self.mouse_check_timer.timeout.connect(self.custom_mouse_pos_check)
        self.mouse_check_timer.start(100)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
