"""Annotation Dialog - Add narrative annotations to events."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QTextEdit,
    QComboBox,
    QLineEdit,
)
from PySide6.QtCore import Qt

from timeos.core.annotations import Annotation, AnnotationType


class AnnotationDialog(QDialog):
    """Dialog for creating or editing event annotations."""

    def __init__(self, event_id: str, existing: Annotation | None = None, parent=None):
        super().__init__(parent)

        self._event_id = event_id
        self._existing = existing
        self._annotation: Annotation | None = None

        self._setup_ui()
        self._connect_signals()

        if existing:
            self._populate_from_existing()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Add Annotation" if not self._existing else "Edit Annotation")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Event reference
        event_label = QLabel(f"Event: {self._event_id[:16]}...")
        event_label.setStyleSheet("color: #808080; font-family: monospace;")
        layout.addWidget(event_label)

        # Annotation type
        type_layout = QHBoxLayout()
        type_label = QLabel("Type:")
        type_label.setStyleSheet("color: #808080;")
        type_label.setFixedWidth(60)
        type_layout.addWidget(type_label)

        self._type_combo = QComboBox()
        for atype in AnnotationType:
            # Get icon for type
            icons = {
                AnnotationType.NOTE: "📝 Note",
                AnnotationType.HYPOTHESIS: "🔬 Hypothesis",
                AnnotationType.OBSERVATION: "👁 Observation",
                AnnotationType.WARNING: "⚠️ Warning",
                AnnotationType.TODO: "☐ TODO",
                AnnotationType.QUESTION: "❓ Question",
                AnnotationType.NARRATIVE: "📖 Narrative",
            }
            self._type_combo.addItem(icons.get(atype, atype.value), atype.value)
        type_layout.addWidget(self._type_combo)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # Tags
        tags_layout = QHBoxLayout()
        tags_label = QLabel("Tags:")
        tags_label.setStyleSheet("color: #808080;")
        tags_label.setFixedWidth(60)
        tags_layout.addWidget(tags_label)

        self._tags_input = QLineEdit()
        self._tags_input.setPlaceholderText("comma-separated tags (optional)")
        self._tags_input.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a1a;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
                padding: 4px 8px;
            }
        """)
        tags_layout.addWidget(self._tags_input)
        layout.addLayout(tags_layout)

        # Content
        content_group = QGroupBox("Content (Markdown supported)")
        content_layout = QVBoxLayout(content_group)

        self._content_edit = QTextEdit()
        self._content_edit.setPlaceholderText(
            "Enter your annotation here...\n\n"
            "Markdown formatting is supported:\n"
            "- **bold** and *italic*\n"
            "- `code` and ```code blocks```\n"
            "- [links](url)\n"
            "- Lists and headers"
        )
        self._content_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d0d;
                border: 1px solid #3a3a3a;
                font-family: monospace;
                color: #e0e0e0;
                padding: 8px;
            }
        """)
        content_layout.addWidget(self._content_edit)

        layout.addWidget(content_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._save_btn = QPushButton("Save")
        self._save_btn.setProperty("primary", True)
        self._save_btn.setMinimumSize(80, 32)
        button_layout.addWidget(self._save_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setMinimumSize(80, 32)
        button_layout.addWidget(self._cancel_btn)

        layout.addLayout(button_layout)

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(self.reject)

    def _populate_from_existing(self) -> None:
        """Populate dialog from existing annotation."""
        if not self._existing:
            return

        # Set type
        for i in range(self._type_combo.count()):
            if self._type_combo.itemData(i) == self._existing.annotation_type.value:
                self._type_combo.setCurrentIndex(i)
                break

        # Set tags
        self._tags_input.setText(", ".join(self._existing.tags))

        # Set content
        self._content_edit.setPlainText(self._existing.content)

    def _on_save(self) -> None:
        """Handle save button."""
        content = self._content_edit.toPlainText().strip()

        if not content:
            return  # Don't save empty annotations

        # Parse tags
        tags_text = self._tags_input.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []

        # Get type
        annotation_type = AnnotationType(self._type_combo.currentData())

        # Create or update annotation
        if self._existing:
            self._annotation = Annotation(
                annotation_id=self._existing.annotation_id,
                event_id=self._event_id,
                content=content,
                annotation_type=annotation_type,
                author=self._existing.author,
                created_at=self._existing.created_at,
                tags=tags,
            )
        else:
            self._annotation = Annotation.create(
                event_id=self._event_id,
                content=content,
                annotation_type=annotation_type,
                tags=tags,
            )

        self.accept()

    def get_annotation(self) -> Annotation | None:
        """Get the created/edited annotation."""
        return self._annotation
