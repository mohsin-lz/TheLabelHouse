import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QMainWindow,
    QToolBar,
)


class DraggableText(QGraphicsTextItem):
    def __init__(self, text="New Text"):
        super().__init__(text)

        # Allow moving
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsMovable, True)

        # Allow selecting
        self.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIsSelectable, True)

        # Allow editing by double click
        self.setTextInteractionFlags(Qt.TextEditorInteraction)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simple Label Designer")
        self.resize(900, 600)

        # Canvas
        self.scene = QGraphicsScene()

        # Label size (500 x 300 pixels)
        self.scene.setSceneRect(0, 0, 500, 300)

        # Draw label border
        self.scene.addRect(self.scene.sceneRect())

        self.view = QGraphicsView(self.scene)
        self.setCentralWidget(self.view)

        # Toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        add_text_action = QAction("Add Text", self)
        add_text_action.triggered.connect(self.add_text)
        toolbar.addAction(add_text_action)

        print_action = QAction("Print", self)
        print_action.triggered.connect(self.print_label)
        toolbar.addAction(print_action)

    def add_text(self):
        text = DraggableText("Double-click to edit")
        text.setPos(20, 20)
        self.scene.addItem(text)

    def print_label(self):
        printer = QPrinter()

        dialog = QPrintDialog(printer, self)

        if dialog.exec():

            painter = QPainter(printer)

            # Print exactly what is inside the label rectangle
            self.scene.render(painter)

            painter.end()


app = QApplication(sys.argv)

window = MainWindow()
window.show()

sys.exit(app.exec())