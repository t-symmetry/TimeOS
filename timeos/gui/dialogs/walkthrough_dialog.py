"""Walkthrough Dialog - Step-by-step guided scenario exploration."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QTextBrowser,
    QProgressBar,
    QFrame,
    QComboBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from timeos.paradoxes.walkthrough import (
    Walkthrough,
    WalkthroughStep,
    StepType,
    get_walkthrough,
    list_walkthroughs,
)


class WalkthroughDialog(QDialog):
    """Dialog for step-by-step walkthrough of scenarios."""

    load_scenario_requested = Signal(str)  # Emits scenario name
    highlight_events_requested = Signal(list)  # Emits event names to highlight

    def __init__(self, walkthrough: Walkthrough | None = None, parent=None):
        super().__init__(parent)

        self._walkthrough = walkthrough
        self._current_step = 0

        self._setup_ui()
        self._connect_signals()

        if walkthrough:
            self._load_walkthrough(walkthrough)

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Walkthrough")
        self.setMinimumSize(700, 550)
        self.setModal(False)  # Allow interaction with main window

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header with walkthrough selector
        header_layout = QHBoxLayout()

        header_label = QLabel("Walkthrough:")
        header_label.setStyleSheet("color: #808080;")
        header_layout.addWidget(header_label)

        self._walkthrough_combo = QComboBox()
        self._walkthrough_combo.setMinimumWidth(250)
        for w in list_walkthroughs():
            difficulty_icon = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}.get(w.difficulty, "⚪")
            self._walkthrough_combo.addItem(f"{difficulty_icon} {w.title}", w.scenario_name)
        header_layout.addWidget(self._walkthrough_combo)

        header_layout.addStretch()

        # Load scenario button
        self._load_btn = QPushButton("Load Scenario")
        self._load_btn.setToolTip("Load the scenario for this walkthrough")
        header_layout.addWidget(self._load_btn)

        layout.addLayout(header_layout)

        # Progress bar
        progress_layout = QHBoxLayout()

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("Step %v of %m")
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                background-color: #1a1a1a;
                text-align: center;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #2d5016;
            }
        """)
        progress_layout.addWidget(self._progress_bar)

        self._time_label = QLabel()
        self._time_label.setStyleSheet("color: #606060; font-size: 10px;")
        progress_layout.addWidget(self._time_label)

        layout.addLayout(progress_layout)

        # Step type indicator
        self._step_type_label = QLabel()
        self._step_type_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border-radius: 4px;
                padding: 4px 12px;
                color: #88ccff;
                font-weight: bold;
            }
        """)
        layout.addWidget(self._step_type_label)

        # Main content area
        content_group = QGroupBox()
        content_layout = QVBoxLayout(content_group)

        # Step title
        self._title_label = QLabel()
        self._title_label.setStyleSheet("""
            QLabel {
                color: #00ff88;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        content_layout.addWidget(self._title_label)

        # Step content (markdown)
        self._content_browser = QTextBrowser()
        self._content_browser.setOpenExternalLinks(True)
        self._content_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #0d0d0d;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
                padding: 12px;
                font-size: 13px;
            }
        """)
        content_layout.addWidget(self._content_browser)

        layout.addWidget(content_group)

        # Navigation buttons
        nav_layout = QHBoxLayout()

        self._prev_btn = QPushButton("< Previous")
        self._prev_btn.setMinimumSize(100, 32)
        nav_layout.addWidget(self._prev_btn)

        nav_layout.addStretch()

        self._step_indicator = QLabel()
        self._step_indicator.setStyleSheet("color: #808080;")
        nav_layout.addWidget(self._step_indicator)

        nav_layout.addStretch()

        self._next_btn = QPushButton("Next >")
        self._next_btn.setProperty("primary", True)
        self._next_btn.setMinimumSize(100, 32)
        nav_layout.addWidget(self._next_btn)

        layout.addLayout(nav_layout)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.setMinimumSize(80, 32)
        close_layout.addWidget(self._close_btn)

        layout.addLayout(close_layout)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._walkthrough_combo.currentIndexChanged.connect(self._on_walkthrough_changed)
        self._load_btn.clicked.connect(self._on_load_scenario)
        self._prev_btn.clicked.connect(self._on_previous)
        self._next_btn.clicked.connect(self._on_next)
        self._close_btn.clicked.connect(self.accept)

    def _load_walkthrough(self, walkthrough: Walkthrough) -> None:
        """Load a walkthrough."""
        self._walkthrough = walkthrough
        self._current_step = 0

        # Update progress bar
        self._progress_bar.setMaximum(len(walkthrough))
        self._progress_bar.setValue(1)

        # Update time estimate
        self._time_label.setText(f"~{walkthrough.estimated_time}")

        # Update title
        self.setWindowTitle(f"Walkthrough: {walkthrough.title}")

        # Show first step
        self._show_step(0)

    def _show_step(self, index: int) -> None:
        """Show a specific step."""
        if not self._walkthrough or index < 0 or index >= len(self._walkthrough):
            return

        step = self._walkthrough.steps[index]
        self._current_step = index

        # Update step type label
        type_icons = {
            StepType.INTRO: "📖 Introduction",
            StepType.CONCEPT: "💡 Concept",
            StepType.ACTION: "⚡ Action",
            StepType.OBSERVATION: "👁 Observation",
            StepType.QUESTION: "❓ Question",
            StepType.CONSTRAINT: "🔒 Constraint",
            StepType.RESULT: "✅ Result",
            StepType.QUIZ: "📝 Quiz",
        }
        self._step_type_label.setText(type_icons.get(step.step_type, step.step_type.value))

        # Update title
        self._title_label.setText(step.title)

        # Update content (convert markdown-ish to HTML)
        html_content = self._markdown_to_html(step.content)
        self._content_browser.setHtml(html_content)

        # Update navigation
        self._progress_bar.setValue(index + 1)
        self._step_indicator.setText(f"Step {index + 1} of {len(self._walkthrough)}")

        self._prev_btn.setEnabled(index > 0)
        self._next_btn.setEnabled(index < len(self._walkthrough) - 1)

        if index == len(self._walkthrough) - 1:
            self._next_btn.setText("Finish")
        else:
            self._next_btn.setText("Next >")

        # Emit highlight request if step has events to highlight
        if step.highlight_events:
            self.highlight_events_requested.emit(step.highlight_events)

    def _markdown_to_html(self, text: str) -> str:
        """Convert simple markdown to HTML."""
        import re

        # Remove leading/trailing whitespace from text
        text = text.strip()

        lines = text.split('\n')
        html_lines = []

        in_code_block = False
        in_list = False

        for line in lines:
            # Code blocks
            if line.strip().startswith('```'):
                if in_code_block:
                    html_lines.append('</pre>')
                    in_code_block = False
                else:
                    html_lines.append('<pre style="background-color: #1a1a1a; padding: 8px; border-radius: 4px; color: #a0ffa0; font-family: monospace;">')
                    in_code_block = True
                continue

            if in_code_block:
                html_lines.append(line)
                continue

            # Headers
            if line.startswith('# '):
                html_lines.append(f'<h2 style="color: #00ff88; margin-top: 16px;">{line[2:]}</h2>')
                continue
            if line.startswith('## '):
                html_lines.append(f'<h3 style="color: #88ccff;">{line[3:]}</h3>')
                continue

            # Lists
            if line.strip().startswith('- ') or line.strip().startswith('* '):
                if not in_list:
                    html_lines.append('<ul style="margin-left: 20px;">')
                    in_list = True
                item = line.strip()[2:]
                item = self._inline_formatting(item)
                html_lines.append(f'<li>{item}</li>')
                continue
            elif in_list and line.strip() == '':
                html_lines.append('</ul>')
                in_list = False

            # Tables (simple)
            if '|' in line and line.strip().startswith('|'):
                # Skip separator lines
                if set(line.replace('|', '').replace('-', '').strip()) == set():
                    continue
                cells = [c.strip() for c in line.split('|')[1:-1]]
                row = ''.join(f'<td style="padding: 4px 8px; border: 1px solid #3a3a3a;">{c}</td>' for c in cells)
                html_lines.append(f'<tr>{row}</tr>')
                continue

            # Blockquotes
            if line.strip().startswith('>'):
                quote = line.strip()[1:].strip()
                quote = self._inline_formatting(quote)
                html_lines.append(f'<blockquote style="border-left: 3px solid #4a4a4a; padding-left: 12px; color: #a0a0a0; font-style: italic;">{quote}</blockquote>')
                continue

            # Regular paragraphs
            if line.strip():
                line = self._inline_formatting(line)
                html_lines.append(f'<p>{line}</p>')
            else:
                html_lines.append('<br/>')

        if in_list:
            html_lines.append('</ul>')
        if in_code_block:
            html_lines.append('</pre>')

        return '\n'.join(html_lines)

    def _inline_formatting(self, text: str) -> str:
        """Apply inline markdown formatting."""
        import re

        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        # Code
        text = re.sub(r'`(.+?)`', r'<code style="background-color: #2a2a2a; padding: 2px 4px; border-radius: 3px; color: #ffcc88;">\1</code>', text)

        return text

    def _on_walkthrough_changed(self, index: int) -> None:
        """Handle walkthrough selection change."""
        scenario_name = self._walkthrough_combo.currentData()
        walkthrough = get_walkthrough(scenario_name)
        if walkthrough:
            self._load_walkthrough(walkthrough)

    def _on_load_scenario(self) -> None:
        """Handle load scenario button."""
        if self._walkthrough:
            self.load_scenario_requested.emit(self._walkthrough.scenario_name)

    def _on_previous(self) -> None:
        """Go to previous step."""
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _on_next(self) -> None:
        """Go to next step."""
        if self._walkthrough and self._current_step < len(self._walkthrough) - 1:
            self._show_step(self._current_step + 1)
        elif self._walkthrough and self._current_step == len(self._walkthrough) - 1:
            # Last step - close dialog
            self.accept()

    def set_walkthrough(self, scenario_name: str) -> bool:
        """Set walkthrough by scenario name.

        Returns True if walkthrough was found and loaded.
        """
        walkthrough = get_walkthrough(scenario_name)
        if walkthrough:
            # Update combo box
            for i in range(self._walkthrough_combo.count()):
                if self._walkthrough_combo.itemData(i) == scenario_name:
                    self._walkthrough_combo.setCurrentIndex(i)
                    break
            self._load_walkthrough(walkthrough)
            return True
        return False
