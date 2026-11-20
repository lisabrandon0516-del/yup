from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog,QDialogButtonBox,QFormLayout,QLabel,QVBoxLayout
from open_late.ui.components import Section,label

class ForecastDialog(QDialog):
    confirmed=Signal()
    def __init__(self,forecast,parent=None):
        super().__init__(parent); self.setWindowTitle(forecast.headline); self.setMinimumWidth(460)
        box=QVBoxLayout(self); box.addWidget(label('Expected outcome',13,True)); box.addWidget(label(forecast.expected,12,wrap=True))
        box.addWidget(label('Downside risk',13,True)); box.addWidget(label(forecast.downside,12,wrap=True))
        box.addWidget(label(f'Confidence: {forecast.confidence}',12,True)); box.addWidget(label('Affected: '+', '.join(forecast.affected),11,wrap=True))
        self.buttons=QDialogButtonBox(QDialogButtonBox.Cancel|QDialogButtonBox.Ok); self.buttons.button(QDialogButtonBox.Ok).setText('Approve decision')
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject); box.addWidget(self.buttons)
