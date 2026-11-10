import time
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from app.gui.main_window import Window


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_finished(self, window):
        deadline = time.monotonic() + 8
        while window.runner.isRunning() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.app.processEvents()
        self.assertFalse(window.runner.isRunning())
        window.runner.wait()

    def dispose(self, window):
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def test_run_stop_run_and_disk_log(self):
        window = Window()
        try:
            window.inputs[0].setValue(4)
            window.inputs[1].setValue(2)
            window.inputs[2].setValue(1)
            window.launch()
            self.assertFalse(window.start.isEnabled())
            self.assertTrue(window.stop.isEnabled())
            window.stop_run()
            self.wait_finished(window)
            self.assertEqual(window.runner.counts['cancelled'], 4)
            window.inputs[0].setValue(1)
            window.launch()
            self.wait_finished(window)
            self.assertEqual(window.runner.counts['completed'], 1)
            self.assertEqual(window.progress_bar.value(), 1)
            self.assertGreater(window.table.rowCount(), 0)
            self.assertIn('Ringkasan', window.log.toPlainText())
            self.assertTrue(window.start.isEnabled())
            self.assertFalse(window.stop.isEnabled())
        finally:
            self.dispose(window)

    def test_close_stops_active_run(self):
        window = Window()
        window.show()
        window.inputs[2].setValue(5)
        window.launch()
        window.close()
        self.wait_finished(window)
        self.app.processEvents()
        self.assertTrue(window.closing)
        self.assertFalse(window.isVisible())
        self.dispose(window)
