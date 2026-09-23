"""Animation Recorder UI for Maya (PySide6).

Provides quick tools to:
  - Animate a selected object's translate/scale via manual recording.
  - Clean up keyframes (thin them out, change tangent interpolation).
  - Copy animation from one object onto one or more targets.

Rotate is intentionally not offered on the Animate tab — see the comment on
TRANSFORM_ATTRS below for why.

Visual style matches RigDiff's ui/styles.py (dark theme, teal accent,
severity-red danger actions) so the two tools sit together comfortably in a
reel or a toolshelf.
"""

import os
from functools import wraps

import maya.cmds as cmds
import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide6 import QtGui, QtWidgets
from shiboken6 import wrapInstance

WINDOW_OBJECT_NAME = "animationRecorderUI"
WINDOW_TITLE = "Animation Recorder"

# Ships in icons/ next to this file — see icons/README for shelf setup.
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "animation_recorder_icon_64.png")

# ---------------------------------------------------------------------------
# Theme — copied from RigDiff's ui/styles.py so companion tools look like one
# family instead of each reinventing its own palette.
# ---------------------------------------------------------------------------
ACCENT_COLOR = "#3fb8af"
ACCENT_COLOR_HOVER = "#4dd0c5"
ACCENT_COLOR_PRESSED = "#33978f"

SEVERITY_UI_COLORS = {
    "CRITICAL": "#e74c3c",
    "CRITICAL_HOVER": "#ec7263",
    "CRITICAL_PRESSED": "#c9432f",
    "HIGH": "#e67e22",
    "MEDIUM": "#f1c40f",
    "LOW": "#2ecc71",
    "GOOD": "#2ecc71",
    "NEUTRAL": "#6b6b6b",
}

WINDOW_STYLE = f"""
QDialog, QMainWindow {{
    background-color: #2b2b2b;
}}

QWidget {{
    background-color: #2b2b2b;
    color: #eeeeee;
    font-family: Segoe UI;
    font-size: 10pt;
}}

QGroupBox {{
    border: 1px solid #4a4a4a;
    border-radius: 6px;
    margin-top: 14px;
    font-weight: bold;
    padding: 8px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0px 6px;
    color: {ACCENT_COLOR};
}}

QPushButton {{
    background-color: #454545;
    border: 1px solid #5c5c5c;
    border-radius: 4px;
    padding: 6px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: #545454;
    border: 1px solid {ACCENT_COLOR};
}}

QPushButton:pressed {{
    background-color: #3a3a3a;
}}

QPushButton:disabled {{
    color: #808080;
    border: 1px solid #454545;
}}

QPushButton#primaryButton {{
    background-color: {ACCENT_COLOR};
    border: 1px solid {ACCENT_COLOR};
    color: #16211f;
    font-weight: bold;
}}

QPushButton#primaryButton:hover {{
    background-color: {ACCENT_COLOR_HOVER};
    border: 1px solid {ACCENT_COLOR_HOVER};
}}

QPushButton#primaryButton:pressed {{
    background-color: {ACCENT_COLOR_PRESSED};
}}

QPushButton#dangerButton {{
    background-color: {SEVERITY_UI_COLORS['CRITICAL']};
    border: 1px solid {SEVERITY_UI_COLORS['CRITICAL']};
    color: #2b0a06;
    font-weight: bold;
}}

QPushButton#dangerButton:hover {{
    background-color: {SEVERITY_UI_COLORS['CRITICAL_HOVER']};
    border: 1px solid {SEVERITY_UI_COLORS['CRITICAL_HOVER']};
}}

QPushButton#dangerButton:pressed {{
    background-color: {SEVERITY_UI_COLORS['CRITICAL_PRESSED']};
}}

QLineEdit {{
    background-color: #363636;
    border: 1px solid #5c5c5c;
    border-radius: 4px;
    padding: 4px;
}}

QLineEdit:focus {{
    border: 1px solid {ACCENT_COLOR};
}}

QRadioButton {{
    spacing: 6px;
}}

QLabel#sectionHint {{
    color: #9a9a9a;
    font-weight: normal;
}}

QLabel#statusLabel {{
    color: #9a9a9a;
    padding-top: 4px;
}}

QTabWidget::pane {{
    border: 1px solid #4a4a4a;
    border-radius: 6px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: #363636;
    border: 1px solid #4a4a4a;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 14px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: #2b2b2b;
    color: {ACCENT_COLOR};
    font-weight: bold;
}}

QTabBar::tab:hover {{
    background-color: #454545;
}}
"""

TRANSLATE_ATTRS = ["translateX", "translateY", "translateZ"]
SCALE_ATTRS = ["scaleX", "scaleY", "scaleZ"]
# Rotate is intentionally not offered here: recording it live via
# recordAttr + play(record=True) depends on Euler angles, which aren't a
# unique representation of an orientation, and in practice that made the
# manipulator feel "locked" / unusable for rotation. Translate and Scale are
# plain scalars with none of that ambiguity.
TRANSFORM_ATTRS = {0: TRANSLATE_ATTRS, 1: SCALE_ATTRS}
# Maya's built-in manipulator contexts for each transform type (same ones the
# W / R hotkeys switch to).
TOOL_CONTEXTS = {0: "moveSuperContext", 1: "scaleSuperContext"}
INTERPOLATION_TYPES = {0: "linear", 1: "step", 2: "spline"}


def _undoable(func):
    """Wrap a scene-editing method in a single undo chunk.

    Without this, a button that issues several Maya commands (e.g. cutKey
    per keyframe, or setKeyframe per attribute/object) needs several Ctrl+Z
    to undo. With it, one click of a button is one step in the undo queue.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        cmds.undoInfo(openChunk=True)
        try:
            return func(self, *args, **kwargs)
        finally:
            cmds.undoInfo(closeChunk=True)
    return wrapper


def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)


class AnimationRecorderUI(MayaQWidgetDockableMixin, QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(AnimationRecorderUI, self).__init__(parent or maya_main_window())
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle(WINDOW_TITLE)
        self.setStyleSheet(WINDOW_STYLE)
        self.resize(420, 380)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QtGui.QIcon(ICON_PATH))

        # Objects currently targeted by the Transfer Animation tab.
        self.source_object = None
        self.point_objects = []

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        self.tabs.addTab(self._build_animate_tab(), "Animate")
        self.tabs.addTab(self._build_clean_keys_tab(), "Clean Keys")
        self.tabs.addTab(self._build_transfer_tab(), "Transfer Animation")

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _get_selection(self, warning="No object selected."):
        """Return the current selection (long names), or None (with a warning)."""
        selected = cmds.ls(selection=True, long=True)
        if not selected:
            self._warn(warning)
            return None
        return selected

    def _warn(self, message):
        cmds.warning(message)
        self.status_label.setText(message)

    def _info(self, message):
        self.status_label.setText(message)

    @staticmethod
    def _get_key_interval(field):
        """Read a positive int from a QLineEdit, or None (with a warning)."""
        try:
            interval = int(field.text())
        except ValueError:
            cmds.warning("Key interval must be a whole number.")
            return None
        if interval < 1:
            cmds.warning("Key interval must be at least 1.")
            return None
        return interval

    # ------------------------------------------------------------------
    # Animate tab
    # ------------------------------------------------------------------
    def _build_animate_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        selection_group = QtWidgets.QGroupBox("Selection")
        selection_layout = QtWidgets.QVBoxLayout(selection_group)
        self.selected_object_label = QtWidgets.QLabel("Selected Object: None")
        selection_layout.addWidget(self.selected_object_label)
        update_button = QtWidgets.QPushButton("Update Selected Object")
        update_button.clicked.connect(self.update_selected_object)
        selection_layout.addWidget(update_button)
        layout.addWidget(selection_group)

        transform_group = QtWidgets.QGroupBox("Transformation")
        transform_layout = QtWidgets.QHBoxLayout(transform_group)
        self.transformation_group = QtWidgets.QButtonGroup(self)
        transform_layout.addStretch()
        for index, label in enumerate(["Translate", "Scale"]):
            radio = QtWidgets.QRadioButton(label)
            radio.setChecked(index == 0)
            self.transformation_group.addButton(radio, index)
            transform_layout.addWidget(radio)
        transform_layout.addStretch()
        layout.addWidget(transform_group)

        actions_layout = QtWidgets.QHBoxLayout()
        animate_button = QtWidgets.QPushButton("Animate")
        animate_button.setObjectName("primaryButton")
        animate_button.setToolTip(
            "Switches the viewport tool to match the chosen channels (Move/Scale),\n"
            "sets an initial key, then starts Play with Record.\n"
            "Fails if the channels are locked, connected or constrained."
        )
        animate_button.clicked.connect(self.run_animation)
        actions_layout.addWidget(animate_button)

        reset_button = QtWidgets.QPushButton("Reset")
        reset_button.clicked.connect(self.reset_animate_tab)
        actions_layout.addWidget(reset_button)
        layout.addLayout(actions_layout)

        delete_button = QtWidgets.QPushButton("Delete All Keys")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_all_keys)
        layout.addWidget(delete_button)

        layout.addStretch()
        return tab

    def update_selected_object(self):
        selected = self._get_selection()
        if not selected:
            return
        self.selected_object_label.setText("Selected Object: " + selected[0])

    @_undoable
    def delete_all_keys(self):
        selected = self._get_selection()
        if not selected:
            return
        cmds.cutKey(selected, clear=True)
        self._info("Deleted all keys on {0} object(s).".format(len(selected)))

    def reset_animate_tab(self):
        self.selected_object_label.setText("Selected Object: None")
        self.transformation_group.button(0).setChecked(True)

    @_undoable
    def run_animation(self):
        selected = self._get_selection()
        if not selected:
            return

        self.selected_object_label.setText("Selected Object: " + selected[0])

        transformation = self.transformation_group.checkedId()
        attributes = TRANSFORM_ATTRS[transformation]

        try:
            # Switch the viewport manipulator to match the chosen channels —
            # otherwise whatever tool (e.g. Move) was active before stays
            # active, and dragging it during recording changes nothing on
            # Scale, which looks like the object is "locked".
            cmds.setToolTo(TOOL_CONTEXTS[transformation])
            cmds.setKeyframe(selected, attribute=attributes)
            cmds.recordAttr(selected, attribute=attributes)
            cmds.play(record=True)
        except RuntimeError as error:
            self._warn("Could not start recording: {0}".format(error))

    # ------------------------------------------------------------------
    # Clean Keys tab
    # ------------------------------------------------------------------
    def _build_clean_keys_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        hint = QtWidgets.QLabel(
            "Set Interpolation and Delete Every N Keys act on the keyframes\n"
            "currently selected in the Graph Editor."
        )
        hint.setObjectName("sectionHint")
        layout.addWidget(hint)

        settings_group = QtWidgets.QGroupBox("Settings")
        settings_layout = QtWidgets.QFormLayout(settings_group)

        self.interval_field = QtWidgets.QLineEdit("1")
        self.interval_field.setToolTip("Every Nth selected key is deleted (1 = delete all selected keys).")
        settings_layout.addRow("Key Interval:", self.interval_field)

        interp_layout = QtWidgets.QHBoxLayout()
        self.interpolation_group = QtWidgets.QButtonGroup(self)
        for index, label in enumerate(["Linear", "Step", "Spline"]):
            radio = QtWidgets.QRadioButton(label)
            radio.setChecked(index == 0)
            self.interpolation_group.addButton(radio, index)
            interp_layout.addWidget(radio)
        settings_layout.addRow("Interpolation:", interp_layout)
        layout.addWidget(settings_group)

        actions_layout = QtWidgets.QHBoxLayout()
        set_interp_button = QtWidgets.QPushButton("Set Interpolation")
        set_interp_button.setObjectName("primaryButton")
        set_interp_button.setToolTip("Applies the chosen tangent type to the selected keyframes.")
        set_interp_button.clicked.connect(self.set_interpolation_type)
        actions_layout.addWidget(set_interp_button)

        delete_button = QtWidgets.QPushButton("Delete Every N Keys")
        delete_button.setObjectName("dangerButton")
        delete_button.setToolTip("Deletes every Nth key among the selected keyframes.")
        delete_button.clicked.connect(self.delete_every_n_keys)
        actions_layout.addWidget(delete_button)
        layout.addLayout(actions_layout)

        reset_button = QtWidgets.QPushButton("Reset")
        reset_button.clicked.connect(self.reset_clean_keys_tab)
        layout.addWidget(reset_button)

        graph_button = QtWidgets.QPushButton("Open Graph Editor")
        graph_button.clicked.connect(self.open_graph_editor)
        layout.addWidget(graph_button)

        layout.addStretch()
        return tab

    @_undoable
    def delete_every_n_keys(self):
        selected = self._get_selection()
        if not selected:
            return

        # Work per animation curve, not per object: cutKey on the object would
        # delete keys on every attribute at a given time, even ones that were
        # never selected in the Graph Editor.
        curves = cmds.keyframe(selected, query=True, selected=True, name=True)
        if not curves:
            self._warn("No keys selected. Select keyframes in the Graph Editor first.")
            return

        interval = self._get_key_interval(self.interval_field)
        if interval is None:
            return

        deleted = 0
        for curve in curves:
            times = cmds.keyframe(curve, query=True, selected=True) or []
            for time in times[::interval]:
                cmds.cutKey(curve, time=(time, time))
                deleted += 1

        self._info("Deleted {0} keyframe(s).".format(deleted))

    @_undoable
    def set_interpolation_type(self):
        selected = self._get_selection()
        if not selected:
            return

        curves = cmds.keyframe(selected, query=True, selected=True, name=True)
        if not curves:
            self._warn("No keys selected. Select keyframes in the Graph Editor first.")
            return

        interpolation = INTERPOLATION_TYPES[self.interpolation_group.checkedId()]

        for curve in curves:
            times = cmds.keyframe(curve, query=True, selected=True) or []
            for time in times:
                cmds.keyTangent(curve, time=(time, time), itt=interpolation, ott=interpolation)

        self._info("Set {0} interpolation on selected keys.".format(interpolation))

    def reset_clean_keys_tab(self):
        self.interval_field.setText("1")
        self.interpolation_group.button(0).setChecked(True)

    @staticmethod
    def open_graph_editor():
        cmds.GraphEditor()

    # ------------------------------------------------------------------
    # Transfer Animation tab
    # ------------------------------------------------------------------
    def _build_transfer_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        group = QtWidgets.QGroupBox("Transfer Animation")
        group_layout = QtWidgets.QVBoxLayout(group)

        self.source_label = QtWidgets.QLabel("Source Object: None")
        group_layout.addWidget(self.source_label)
        source_button = QtWidgets.QPushButton("Select Source Object")
        source_button.clicked.connect(self.select_source_object)
        group_layout.addWidget(source_button)

        self.point_label = QtWidgets.QLabel("Point Object(s): None")
        group_layout.addWidget(self.point_label)
        point_button = QtWidgets.QPushButton("Select Point Object(s)")
        point_button.setToolTip("You can select more than one target object.")
        point_button.clicked.connect(self.select_point_object)
        group_layout.addWidget(point_button)

        layout.addWidget(group)

        transfer_button = QtWidgets.QPushButton("Transfer Animation")
        transfer_button.setObjectName("primaryButton")
        transfer_button.clicked.connect(self.transfer_animation)
        layout.addWidget(transfer_button)

        layout.addStretch()
        return tab

    def select_source_object(self):
        selected = self._get_selection()
        if not selected:
            return
        self.source_object = selected[0]
        self.source_label.setText("Source Object: " + self.source_object)

    def select_point_object(self):
        selected = self._get_selection()
        if not selected:
            return
        self.point_objects = selected
        if len(self.point_objects) == 1:
            label = "Point Object(s): " + self.point_objects[0]
        else:
            label = "Point Object(s): {0} objects selected".format(len(self.point_objects))
        self.point_label.setText(label)

    @_undoable
    def transfer_animation(self):
        if not self.source_object or not self.point_objects:
            self._warn("Please select both a source object and at least one point object.")
            return

        source_attrs = set(cmds.listAttr(self.source_object, keyable=True) or [])
        transferred = 0

        for point_object in self.point_objects:
            if point_object == self.source_object:
                continue
            transferred += self._transfer_animation_to(point_object, source_attrs)

        self._info("Transferred animation to {0} object(s).".format(transferred))

    def _transfer_animation_to(self, point_object, source_attrs):
        point_attrs = set(cmds.listAttr(point_object, keyable=True) or [])
        common_attrs = source_attrs & point_attrs

        if not common_attrs:
            self._warn("{0}: no keyable attributes in common with the source object.".format(point_object))
            return 0

        copied_any = False
        for attr in common_attrs:
            source_plug = self.source_object + "." + attr
            point_plug = point_object + "." + attr

            if not cmds.keyframe(source_plug, query=True, keyframeCount=True):
                continue

            times = cmds.keyframe(source_plug, query=True, timeChange=True) or []
            values = cmds.keyframe(source_plug, query=True, valueChange=True) or []

            if cmds.keyframe(point_plug, query=True, keyframeCount=True):
                cmds.cutKey(point_plug, clear=True)

            for time, value in zip(times, values):
                cmds.setKeyframe(point_plug, time=time, value=value)
            copied_any = True

        return 1 if copied_any else 0


WORKSPACE_CONTROL_NAME = WINDOW_OBJECT_NAME + "WorkspaceControl"

_animation_recorder_ui = None


def show():
    global _animation_recorder_ui

    # The Python-side reference above only survives if this module stays
    # imported between runs. Re-running the script from the Script Editor (or
    # reloading the module) starts _animation_recorder_ui back at None, but
    # the native Maya workspaceControl from the previous run is still there
    # — hence "Object's name '...WorkspaceControl' is not unique." Deleting
    # it by name (rather than relying on the Python object) makes every run
    # start clean regardless of how the script got re-executed.
    if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, exists=True):
        cmds.deleteUI(WORKSPACE_CONTROL_NAME)

    if _animation_recorder_ui is not None:
        try:
            _animation_recorder_ui.close()
            _animation_recorder_ui.deleteLater()
        except RuntimeError:
            pass

    _animation_recorder_ui = AnimationRecorderUI()
    _animation_recorder_ui.show(dockable=True)
    return _animation_recorder_ui


if __name__ == "__main__":
    show()
