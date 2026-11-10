"""Desktop playback lab. Run: python main.py."""
import asyncio
import logging
import math
import re
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QCheckBox, QPushButton, QHBoxLayout, QLabel,
    QPlainTextEdit, QMessageBox)

from app.core.runner import Runner
from app.utils.validators import video_id
from PySide6.QtWidgets import QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from app.config import ROOT

class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('YouTube Playback Lab')
        self.resize(850, 650)
        self.runner = None
        self.last_config = None
        self.closing = False
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText('https://www.youtube.com/watch?v=... atau /shorts/...')
        form.addRow('Link YouTube', self.url)
        self.browser = QComboBox()
        self.browser.addItem('Chromium bawaan Playwright', 'chromium')
        self.browser.addItem('Google Chrome terpasang (uji kompatibilitas)', 'chrome')
        form.addRow('Browser', self.browser)
        self.inputs = []
        for label, default, maximum in [('Target sesi', 1, 10000), ('Maksimal jendela Chromium', 1, 20), ('Durasi tonton (detik)', 30, 86400)]:
            box = QSpinBox()
            box.setRange(1, maximum)
            box.setValue(default)
            form.addRow(label, box)
            self.inputs.append(box)
        layout.addLayout(form)
        self.monitor = QCheckBox('Pantau views melalui halaman setiap 120 detik')
        self.simulation = QCheckBox('Mode simulasi — tanpa membuka browser')
        self.simulation.setChecked(True)
        layout.addWidget(self.monitor)
        layout.addWidget(self.simulation)
        layout.addWidget(QLabel('Link Shorts dibuka pada tampilan Shorts. Monitor views memakai halaman watch terpisah.'))
        layout.addWidget(QLabel('Data browser sementara dibersihkan setiap sesi. Sesi selesai tidak menjamin view diterima.'))
        buttons = QHBoxLayout()
        self.start = QPushButton('Run')
        self.stop = QPushButton('Stop')
        self.check = QPushButton('Cek Views Sekarang')
        self.logs_button = QPushButton('Buka folder log')
        self.logs_button.clicked.connect(self.open_logs)
        self.stop.setEnabled(False)
        self.check.setEnabled(False)
        for b in (self.start, self.stop, self.check, self.logs_button):
            buttons.addWidget(b)
        layout.addLayout(buttons)
        self.status = QLabel('Siap — mode simulasi aktif')
        self.views = QLabel('Views: belum diperiksa')
        self.views.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(self.views)
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Sesi', 'Kondisi', 'Detail / Pembersihan'])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMaximumHeight(220)
        layout.addWidget(self.table)
        self.rows = {}
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        layout.addWidget(self.log)
        self.start.clicked.connect(self.launch)
        self.stop.clicked.connect(self.stop_run)
        self.check.clicked.connect(lambda: self.launch(True))

    def launch(self, manual=False):
        try:
            if manual:
                config = dict(self.last_config, manual=True, simulation=False,
                              baseline=self.runner.baseline, last_snapshot=self.runner.last_snapshot)
            else:
                ident = video_id(self.url.text()) if not self.simulation.isChecked() else 'simulation'
                config = dict(id=ident, url=f'https://www.youtube.com/watch?v={ident}',
                    browser=self.browser.currentData(),
                    shorts=urlparse(self.url.text().strip()).path.startswith('/shorts/'),
                    total=self.inputs[0].value(), windows=self.inputs[1].value(),
                    duration=self.inputs[2].value(), monitor=self.monitor.isChecked(),
                    simulation=self.simulation.isChecked())
                self.last_config = config.copy()
                self.views.setText('Views: belum diperiksa')
                self.table.setRowCount(0)
                self.rows.clear()
                self.progress_bar.setValue(0)
        except ValueError as exc:
            QMessageBox.warning(self, 'Input tidak valid', str(exc))
            return
        if self.runner is not None:
            self.runner.deleteLater()
        self.runner = Runner(config)
        self.runner.setParent(self)
        self.runner.line.connect(self.log.appendPlainText)
        self.runner.progress.connect(self.status.setText)
        self.runner.stats.connect(self.views.setText)
        self.runner.counts_changed.connect(self.update_counts)
        self.runner.worker_changed.connect(self.update_worker)
        self.runner.outcome.connect(self.set_outcome)
        self.runner.finished.connect(self.finished)
        self.busy(True)
        self.status.setText('Berjalan')
        self.runner.start()

    def open_logs(self):
        folder = ROOT / 'log'
        try:
            folder.mkdir(exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        except OSError as exc:
            QMessageBox.warning(self, 'Folder log', str(exc))

    def set_outcome(self, message):
        self.result_message = message

    def update_counts(self, counts):
        terminal = counts['completed'] + counts['failed'] + counts['cancelled']
        self.progress_bar.setRange(0, counts['total'])
        self.progress_bar.setValue(terminal)
        remaining = counts['total'] - terminal - counts['active']
        self.progress_bar.setFormat(f'{terminal}/{counts["total"]} diproses; {remaining} menunggu')

    def update_worker(self, number, status, detail):
        if number not in self.rows:
            # Keep the table bounded independently of the complete disk log.
            if self.table.rowCount() >= 250:
                self.table.removeRow(0)
                self.rows = {key: row - 1 for key, row in self.rows.items() if row > 0}
            self.rows[number] = self.table.rowCount()
            self.table.insertRow(self.table.rowCount())
        row = self.rows[number]
        for column, value in enumerate(('Monitor' if number == 0 else str(number), status, detail)):
            self.table.setItem(row, column, QTableWidgetItem(value))

    def busy(self, state):
        for widget in [self.url, self.browser, *self.inputs, self.monitor, self.simulation, self.start]:
            widget.setEnabled(not state)
        self.stop.setEnabled(state)
        self.check.setEnabled(not state and bool(self.last_config) and not self.last_config['simulation'])

    def stop_run(self):
        if self.runner:
            self.runner.stop()
            self.status.setText('Menghentikan dan membersihkan browser...')
            self.stop.setEnabled(False)

    def finished(self):
        self.runner.wait()
        self.busy(False)
        self.status.setText(getattr(self, 'result_message', 'Selesai') + ' | ' + self.status.text())
        if self.closing:
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event):
        if self.runner and self.runner.isRunning():
            self.closing = True
            self.stop_run()
            event.ignore()
        else:
            event.accept()
