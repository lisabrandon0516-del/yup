"""Inbox desk: read the floor's notes, and write the people who matter."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from open_late.mail import MailContact, contacts, send_letter, topics_for
from open_late.text import weekday_name

INK = "#E8EEF8"
MUTED = "#8BA0C0"
LINE = "#1A2E55"
GREEN = "#1E7A3A"


class MailDesk(QWidget):
    def __init__(self, host, parent=None):
        super().__init__(parent)
        self._host = host
        self._state = None
        self._selected = "folder:inbox"
        self._contacts: list[MailContact] = []
        self.setObjectName("mailDesk")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(420)
        self.setStyleSheet(
            "QWidget#mailDesk { background: #09152D; color: #E8EEF8; }"
            "QTreeWidget, QListWidget, QPlainTextEdit, QComboBox, QLineEdit {"
            " background: #0E1C3A; color: #E8EEF8; border: 1px solid #1A2E55; border-radius: 4px; }"
            "QTreeWidget::item { padding: 3px 2px; }"
            "QTreeWidget::item:selected, QListWidget::item:selected {"
            " background: #17376D; color: #FFFFFF; }"
        )
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        root.addWidget(self._people_pane())
        root.addWidget(self._letter_pane(), stretch=1)

    def load(self, state) -> None:
        self._state = state
        self._contacts = contacts(state) if state is not None else []
        self._fill_people()
        self._show_selected()

    def _people_pane(self) -> QFrame:
        frame = QFrame()
        frame.setFixedWidth(248)
        frame.setStyleSheet(f"QFrame {{ background: #0E1C3A; color: #E8EEF8; border-right: 1px solid {LINE}; }}")
        column = QVBoxLayout(frame)
        column.setContentsMargins(8, 8, 8, 8)
        column.setSpacing(6)
        find = QLineEdit()
        find.setObjectName("mailFind")
        find.setPlaceholderText("Find a person")
        find.textChanged.connect(self._fill_people)
        self._find = find
        column.addWidget(find)
        tree = QTreeWidget()
        tree.setObjectName("mailPeople")
        tree.setHeaderHidden(True)
        tree.setIndentation(14)
        tree.itemSelectionChanged.connect(self._on_pick)
        self._tree = tree
        column.addWidget(tree, stretch=1)
        return frame

    def _letter_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("mailLetter")
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pane.setStyleSheet(
            "QWidget#mailLetter { background: #0E1C3A; color: #E8EEF8; border: 1px solid #1A2E55; border-radius: 4px; }"
        )
        column = QVBoxLayout(pane)
        column.setContentsMargins(12, 8, 12, 8)
        column.setSpacing(6)
        head = QLabel("Inbox")
        head.setObjectName("mailHead")
        head.setWordWrap(True)
        head.setStyleSheet(f"color: {INK}; font-weight: 700; background: transparent;")
        self._head = head
        column.addWidget(head)
        letters = QListWidget()
        letters.setObjectName("letterList")
        letters.currentRowChanged.connect(self._show_row)
        self._letters = letters
        column.addWidget(letters, stretch=1)
        reading = QLabel("")
        reading.setObjectName("letterReading")
        reading.setWordWrap(True)
        reading.setAlignment(Qt.AlignmentFlag.AlignTop)
        reading.setStyleSheet(f"color: {INK}; background: #102343; border: 1px solid {LINE}; padding: 8px;")
        reading.setMinimumHeight(96)
        self._reading = reading
        column.addWidget(reading)
        self._choices = QHBoxLayout()
        column.addLayout(self._choices)
        self._topic = QComboBox()
        self._topic.setObjectName("mailTopic")
        column.addWidget(self._topic)
        body = QPlainTextEdit()
        body.setObjectName("mailBody")
        body.setPlaceholderText("Write the letter. They answer from the books.")
        body.setFixedHeight(72)
        self._body = body
        column.addWidget(body)
        row = QHBoxLayout()
        hint = QLabel("A store manager can set the hours, written like 8 to 21. A vendor can send the truck. A price and a wage stay put.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED}; background: transparent;")
        row.addWidget(hint, stretch=1)
        send = QPushButton("Send")
        send.setObjectName("sendMail")
        send.setMinimumHeight(32)
        send.setMinimumWidth(96)
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(
            "QPushButton#sendMail { background: #16803C; color: white; border: none; "
            "border-radius: 4px; padding: 6px 16px; font-weight: 700; }"
            "QPushButton#sendMail:hover { background: #0E5C32; }"
        )
        send.clicked.connect(self._send)
        row.addWidget(send)
        self._send_button = send
        column.addLayout(row)
        return pane

    def _fill_people(self) -> None:
        query = self._find.text().strip().lower()
        tree = self._tree
        tree.blockSignals(True)
        tree.clear()
        folders = (
            ("folder:inbox", "Inbox"),
            ("folder:sent", "Sent"),
            ("folder:journal", "Closed days"),
        )
        chosen = None
        for key, label in folders:
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            tree.addTopLevelItem(item)
            if key == self._selected:
                chosen = item
        groups: dict[str, list[MailContact]] = {}
        for person in self._contacts:
            hay = f"{person.name} {person.title} {person.detail}".lower()
            if query and query not in hay:
                continue
            groups.setdefault(person.group, []).append(person)
        for name in ("Managers", "Vendors", "The house"):
            people = groups.get(name) or []
            if query and not people:
                continue
            parent = QTreeWidgetItem([f"{name}  {len(people)}"])
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
            tree.addTopLevelItem(parent)
            for person in people:
                child = QTreeWidgetItem([person.name])
                child.setToolTip(0, f"{person.title}. {person.detail}")
                child.setData(0, Qt.ItemDataRole.UserRole, person.id)
                parent.addChild(child)
                if person.id == self._selected:
                    chosen = child
            parent.setExpanded(True)
        tree.blockSignals(False)
        if chosen is not None:
            tree.setCurrentItem(chosen)
        elif tree.topLevelItemCount():
            tree.setCurrentItem(tree.topLevelItem(0))

    def _on_pick(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            return
        self._selected = str(key)
        self._show_selected()

    def _contact(self) -> MailContact | None:
        return next((person for person in self._contacts if person.id == self._selected), None)

    def _show_selected(self) -> None:
        self._clear_choices()
        person = self._contact()
        writing = person is not None
        self._topic.setVisible(writing)
        self._body.setVisible(writing)
        self._send_button.setVisible(writing)
        state = self._state
        if person is not None:
            self._head.setText(f"{person.name}  ·  {person.title}\n{person.detail}")
            self._fill_topics(person)
            self._fill_thread(person)
            return
        if self._selected == "folder:sent":
            self._head.setText("Sent")
            self._fill_sent()
            return
        if self._selected == "folder:journal":
            self._head.setText("Closed days")
            self._fill_journal()
            return
        waiting = 0 if state is None else sum(1 for message in state.inbox if not message.resolved)
        self._head.setText(f"Inbox  ·  {waiting} open")
        self._fill_inbox()

    def _fill_topics(self, person: MailContact) -> None:
        self._topic.blockSignals(True)
        self._topic.clear()
        for topic in topics_for(person):
            self._topic.addItem(topic.label, topic.id)
        self._topic.blockSignals(False)

    def _set_rows(self, rows: list) -> None:
        self._letter_rows = rows
        self._letters.blockSignals(True)
        self._letters.clear()
        for title, _payload in rows:
            self._letters.addItem(QListWidgetItem(title))
        self._letters.blockSignals(False)
        if rows:
            self._letters.setCurrentRow(0)
        else:
            self._reading.setText(self._empty_text())

    def _empty_text(self) -> str:
        if self._contact() is not None:
            return "No letter to them yet. Pick a subject and send."
        if self._selected == "folder:sent":
            return "Nothing sent yet."
        if self._selected == "folder:journal":
            return "The journal starts when you close a day."
        return "Nothing is waiting. Pick a person and write them."

    def _fill_inbox(self) -> None:
        state = self._state
        rows = []
        if state is not None:
            pending = [message for message in state.inbox if not message.resolved]
            pending.sort(key=lambda message: (not message.urgent, -message.day))
            for message in pending:
                when = f"{weekday_name(message.day)} · Day {message.day}"
                mark = "Urgent  ·  " if message.urgent else ""
                rows.append((f"{mark}{message.title}    {when}", message))
        self._set_rows(rows)

    def _fill_sent(self) -> None:
        state = self._state
        rows = []
        if state is not None:
            for letter in reversed(state.sent_mail):
                when = f"Day {letter.day}"
                rows.append((f"To {letter.to_name}  ·  {letter.subject}    {when}", letter))
        self._set_rows(rows)

    def _fill_thread(self, person: MailContact) -> None:
        state = self._state
        rows = []
        if state is not None:
            for letter in reversed(state.sent_mail):
                if letter.to_id != person.id:
                    continue
                rows.append((f"Day {letter.day}  ·  {letter.subject}", letter))
        self._set_rows(rows)

    def _fill_journal(self) -> None:
        state = self._state
        rows = []
        if state is not None:
            for entry in reversed(state.journal[-12:]):
                rows.append((entry.split("\n", 1)[0][:80], entry))
        self._set_rows(rows)

    def _show_row(self, row: int) -> None:
        self._clear_choices()
        rows = getattr(self, "_letter_rows", [])
        if row < 0 or row >= len(rows):
            return
        payload = rows[row][1]
        if isinstance(payload, str):
            self._reading.setText(payload)
            return
        subject = getattr(payload, "subject", "")
        if subject:
            yours = payload.body or "(No note written.)"
            self._reading.setText(
                f"To {payload.to_name}\n{payload.subject}\n\n{yours}\n\n{payload.reply_from} wrote back:\n{payload.reply}"
            )
            return
        self._reading.setText(f"{payload.title}\n\n{payload.body}")
        for choice in payload.choices:
            button = QPushButton(choice.label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if choice is payload.choices[0]:
                button.setStyleSheet(
                    f"QPushButton {{ background: {GREEN}; color: white; border: none; "
                    "border-radius: 2px; padding: 6px 12px; font-weight: 700; }"
                )
            button.clicked.connect(
                lambda _=False, mid=payload.id, cid=choice.id: self._choose(mid, cid)
            )
            self._choices.addWidget(button)
        self._choices.addStretch(1)

    def _clear_choices(self) -> None:
        while self._choices.count():
            item = self._choices.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _choose(self, message_id: str, choice_id: str) -> None:
        host = self._host
        if host is not None and hasattr(host, "_choose"):
            host._choose(message_id, choice_id)

    def _send(self) -> None:
        state = self._state
        person = self._contact()
        host = self._host
        if state is None or person is None:
            return
        topic_id = self._topic.currentData()
        ok, text = send_letter(state, person.id, str(topic_id or ""), self._body.toPlainText())
        if host is not None and hasattr(host, "_say"):
            host._say(text.split("\n", 1)[0][:180])
        if not ok:
            self._reading.setText(text)
            return
        self._body.clear()
        if host is not None and hasattr(host, "_save"):
            host._save()
        self._selected = person.id
        self.load(state)
