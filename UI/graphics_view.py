import copy
import typing

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGraphicsView, QGraphicsItem


class CopyItem(QGraphicsItem):
    def __init__(self, item: QGraphicsItem):
        super().__init__()
        self.item = item

    def paint(self, painter: QtGui.QPainter, option: 'QtWidgets.QStyleOptionGraphicsItem', widget: typing.Optional[QtWidgets.QWidget] = ...) -> None:
        self.item.paint(painter, option, widget)

    def boundingRect(self) -> QtCore.QRectF:
        return self.item.boundingRect()

    def shape(self) -> QtGui.QPainterPath:
        return self.item.shape()

    def type(self) -> int:
        return self.item.type()


class CustomGraphicsView(QGraphicsView):
    mouse_pos_signal = QtCore.pyqtSignal(object)
    draw_line_signal = QtCore.pyqtSignal(object)
    draw_rect_signal = QtCore.pyqtSignal(object)
    draw_circle_signal = QtCore.pyqtSignal(object)
    draw_text_signal = QtCore.pyqtSignal(object)
    draw_curve_signal = QtCore.pyqtSignal(object)
    draw_polyline_signal = QtCore.pyqtSignal(object)
    toggle_temp_drawing = QtCore.pyqtSignal(bool)
    change_cursor_signal = QtCore.pyqtSignal(object)
    item_pasted_signal = QtCore.pyqtSignal(object)
    draw_selected_item_rect = QtCore.pyqtSignal(object)
    clear_selection_rect = QtCore.pyqtSignal()
    show_status_bar_message_signal = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._copied_item_center = None
        self.move_start_pos = None
        self._item_for_move: typing.Union[None, QGraphicsItem] = None
        self._curve_points = []
        self._copied_item = None
        self._move_start_pos = None
        self._to_enter_text = ""
        self._wait_for_mouse_click = False
        self.drag_start_pos = None
        self.current_item: typing.Union[None, QGraphicsItem] = None
        # self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)
        self.grid_on = False
        self.grid_size = 10
        self.is_first_line = True
        self.last_point = 0
        self.control_key = False

        # add keyboard shortcuts
        # right key shortcut
        QtWidgets.QShortcut(QtGui.QKeySequence(Qt.Key_Right), self, lambda: self.rotate_item(True))
        # left key shortcut
        QtWidgets.QShortcut(QtGui.QKeySequence(Qt.Key_Left), self, lambda: self.rotate_item(False))
        # copy key shortcut
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, lambda: self.copy_item_to_clipboard())
        # paste key shortcut
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+V"), self, lambda: self.paste_item_from_clipboard())

    def copy_item_to_clipboard(self):
        if self._item_for_move:
            self._copied_item = CopyItem(self._item_for_move)
            self._copied_item_center = self._item_for_move.sceneBoundingRect().center()
            print(f"{self._copied_item_center=}")
            self.show_status_bar_message_signal.emit("Item copied to clipboard")

    def paste_item_from_clipboard(self):
        if self._copied_item:
            # locate point at center of item
            cursor_pos = QtGui.QCursor.pos()
            pos = self.mapToScene(self.mapFromGlobal(cursor_pos))
            # print(f"  {pos=}\n")
            self._copied_item: QGraphicsItem
            self.scene().addItem(self._copied_item)
            diff_point = pos - self._copied_item_center
            # print(f"{diff_point=}\n")
            self._copied_item.setPos(pos)
            self._copied_item.setPos(diff_point)  # this only works when copied from original item

            self.item_pasted_signal.emit(self._copied_item)  # to add new item to drawing list

            self._copied_item = None
            self._copied_item_center = None
            self.show_status_bar_message_signal.emit("Item pasted from clipboard")

    def rotate_item(self, is_right=True):
        multiplier = -1
        if is_right:
            multiplier = 1
        if self._item_for_move:
            center_prev = self._item_for_move.sceneBoundingRect().center()

            self._item_for_move.setTransformOriginPoint(center_prev)
            transform = self._item_for_move.transform()
            transform.rotate(5 * multiplier)
            self._item_for_move.setTransform(transform)

            center_now = self._item_for_move.sceneBoundingRect().center()

            # move to the new center
            self._item_for_move.moveBy(center_prev.x() - center_now.x(), center_prev.y() - center_now.y())

    def is_grid_on(self, is_on):
        if is_on:
            self.grid_on = False
            print(self.grid_on)
        else:
            self.grid_on = True
            print(self.grid_on)
        return

    def set_current_item(self, item: str):
        self.current_item = item

    def cancel_wait_for_mouse_click(self):
        self._wait_for_mouse_click = False
        self._to_enter_text = ""

    def wait_for_mouse_click(self, text):
        self._wait_for_mouse_click = True
        self._to_enter_text = text

    @staticmethod
    def draw_line_grid_on(pos, grid_size):
        if (pos % grid_size) < grid_size / 2:
            counted_pos = (pos // grid_size) * grid_size
        else:
            counted_pos = (pos // grid_size) * grid_size + grid_size
        return counted_pos

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._wait_for_mouse_click:
                self.draw_text_signal.emit((self._to_enter_text, self.mapToScene(event.pos())))
                self._wait_for_mouse_click = False
                self._to_enter_text = ""
            else:
                self.drag_start_pos = event.pos()
                if self.current_item == 'curve' and len(self._curve_points) < 3:
                    self._curve_points.append(self.mapToScene(event.pos()))
                self.toggle_temp_drawing.emit(True)

        elif event.button() == Qt.RightButton:
            self._move_start_pos = event.pos()
            _point = self.mapToScene(self._move_start_pos)
            self._item_for_move = self.scene().itemAt(_point, self.transform())
            if self._item_for_move:
                self._move_start_pos = event.pos()
                rect_f = self._item_for_move.sceneBoundingRect()
                self.draw_selected_item_rect.emit((rect_f, self._item_for_move))
            else:
                self._move_start_pos = None

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.drag_start_pos:
                drag_end_pos = self.mapToScene(event.pos())
                drag_start_pos = self.mapToScene(self.drag_start_pos)
                self.toggle_temp_drawing.emit(False)  # clear temporary drawing objects
                if self.current_item == 'line':
                    self.draw_line_signal.emit((drag_start_pos, drag_end_pos))
                elif self.current_item == 'rectangle':
                    self.draw_rect_signal.emit((drag_start_pos, drag_end_pos))
                elif self.current_item == 'circle':
                    self.draw_circle_signal.emit((drag_start_pos, drag_end_pos))
                elif self.current_item == "curve":
                    if len(self._curve_points) == 3:
                        self._curve_points[2] = drag_end_pos
                        _3_points = tuple(self._curve_points)
                        self.draw_curve_signal.emit(_3_points)
                        self._curve_points.clear()
                    else:
                        self.draw_curve_signal.emit(self._curve_points)
                elif self.current_item == "polyline":
                    if self.is_first_line:
                        self.draw_polyline_signal.emit((drag_start_pos, drag_end_pos))
                        self.last_point = drag_end_pos
                    else:
                        drag_start_pos = self.last_point
                        self.draw_polyline_signal.emit((drag_start_pos, drag_end_pos))
                        self.last_point = drag_end_pos

            self.drag_start_pos = None
        elif event.button() == Qt.RightButton:
            if self.grid_on:
                if self._item_for_move:
                    _move_end_pos = event.pos()
                    start_pos_x = self.draw_line_grid_on(self._move_start_pos.x(), self.grid_size)
                    start_pos_y = self.draw_line_grid_on(self._move_start_pos.y(), self.grid_size)
                    end_pos_x = self.draw_line_grid_on(_move_end_pos.x(), self.grid_size)
                    end_pos_y = self.draw_line_grid_on(_move_end_pos.y(), self.grid_size)
                    diff = (self.mapToScene(end_pos_x, end_pos_y) - self.mapToScene(start_pos_x, start_pos_y))
                    dx = diff.x()
                    dy = diff.y()
                    self._item_for_move.moveBy(dx, dy)
                    self._item_for_move = None
                    self._move_start_pos = None
                    self.clear_selection_rect.emit()
                else:
                    self.clear_selection_rect.emit()
            else:
                if self._item_for_move:
                    _move_end_pos = event.pos()
                    diff = (self.mapToScene(_move_end_pos) - self.mapToScene(self._move_start_pos))
                    dx = diff.x()
                    dy = diff.y()
                    self._item_for_move.moveBy(dx, dy)
                    self._item_for_move = None
                    self._move_start_pos = None
                    self.clear_selection_rect.emit()
                else:
                    self.clear_selection_rect.emit()
            if not self.is_first_line:
                self.is_first_line = True
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_start_pos:
            temp_drag_end_pos = self.mapToScene(event.pos())
            temp_drag_start_pos = self.mapToScene(self.drag_start_pos)
            if self.current_item == 'line':
                self.draw_line_signal.emit((temp_drag_start_pos, temp_drag_end_pos))
            elif self.current_item == 'rectangle':
                self.draw_rect_signal.emit((temp_drag_start_pos, temp_drag_end_pos))
            elif self.current_item == 'circle':
                self.draw_circle_signal.emit((temp_drag_start_pos, temp_drag_end_pos))
            elif self.current_item == "curve":
                if len(self._curve_points) == 3:
                    self._curve_points[2] = temp_drag_end_pos
                    _3_points = tuple(self._curve_points)
                    self.draw_curve_signal.emit(_3_points)
            elif self.current_item == "polyline":
                if self.is_first_line:
                    self.draw_polyline_signal.emit((temp_drag_start_pos, temp_drag_end_pos))
                    self.last_point = temp_drag_end_pos
                else:
                    temp_drag_start_pos = self.last_point
                    self.draw_polyline_signal.emit((temp_drag_start_pos, temp_drag_end_pos))
                    # self.last_point = temp_drag_end_pos

        if self._item_for_move and self._move_start_pos:
            _move_end_pos = event.pos()
            if self.grid_on:
                start_pos_x = self.draw_line_grid_on(self._move_start_pos.x(), self.grid_size)
                start_pos_y = self.draw_line_grid_on(self._move_start_pos.y(), self.grid_size)
                end_pos_x = self.draw_line_grid_on(_move_end_pos.x(), self.grid_size)
                end_pos_y = self.draw_line_grid_on(_move_end_pos.y(), self.grid_size)
                diff = (self.mapToScene(end_pos_x, end_pos_y) - self.mapToScene(start_pos_x, start_pos_y))
                dx = diff.x()
                dy = diff.y()
                self._item_for_move.moveBy(dx, dy)
                self._move_start_pos = _move_end_pos
                self.clear_selection_rect.emit()
                self.draw_selected_item_rect.emit((self._item_for_move.sceneBoundingRect(), self._item_for_move))
            else:
                diff = (self.mapToScene(_move_end_pos) - self.mapToScene(self._move_start_pos))
                dx = diff.x()
                dy = diff.y()
                self._item_for_move.moveBy(dx, dy)
                self._move_start_pos = _move_end_pos
                self.clear_selection_rect.emit()
                self.draw_selected_item_rect.emit((self._item_for_move.sceneBoundingRect(), self._item_for_move))

        item_under_mouse = self.scene().itemAt(self.mapToScene(event.pos()), self.transform())
        self.mouse_pos_signal.emit(self.mapToScene(event.pos()).toPoint())
        self.change_cursor_signal.emit(Qt.PointingHandCursor if item_under_mouse else Qt.CrossCursor)
        super().mouseMoveEvent(event)
