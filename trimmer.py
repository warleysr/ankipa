import os
import wave
import time
import array
import struct
import tempfile

from aqt.qt import (
    Qt,
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QDoubleSpinBox,
    QDialogButtonBox,
    QTimer,
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QRectF,
    QPointF,
    QPolygonF,
    QShortcut,
    QKeySequence,
    pyqtSignal,
)

try:
    from aqt.sound import play, av_player
except ImportError:
    play = None
    av_player = None


def get_temp_ankipa_dir() -> str:
    temp_dir = os.path.join(tempfile.gettempdir(), "ankipa")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def read_wav_peaks(file_path: str, num_buckets: int = 400):
    """
    Reads a WAV file and returns (duration, peaks, amps).
    peaks: list of (min_val, max_val) normalized to [-1.0, 1.0]
    amps: list of max absolute amplitudes normalized to [0.0, 1.0]
    """
    if not os.path.exists(file_path):
        return 0.0, [(0.0, 0.0)] * num_buckets, [0.0] * num_buckets

    try:
        with wave.open(file_path, "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            if nframes == 0 or framerate == 0:
                return 0.0, [(0.0, 0.0)] * num_buckets, [0.0] * num_buckets

            duration = nframes / float(framerate)
            raw_bytes = wf.readframes(nframes)
    except Exception:
        return 0.0, [(0.0, 0.0)] * num_buckets, [0.0] * num_buckets

    peaks = []
    amps = []

    if sampwidth == 2:
        samples = array.array("h")
        samples.frombytes(raw_bytes)
        total_samples = len(samples)
        if total_samples == 0:
            return duration, [(0.0, 0.0)] * num_buckets, [0.0] * num_buckets

        bucket_size = max(1, total_samples // num_buckets)
        for b in range(num_buckets):
            start_i = b * bucket_size
            end_i = min(total_samples, (b + 1) * bucket_size)
            chunk = samples[start_i:end_i]
            if chunk:
                min_v = min(chunk) / 32768.0
                max_v = max(chunk) / 32768.0
                peaks.append((min_v, max_v))
                amps.append(max(abs(min_v), abs(max_v)))
            else:
                peaks.append((0.0, 0.0))
                amps.append(0.0)
    elif sampwidth == 1:
        unsigned = array.array("B")
        unsigned.frombytes(raw_bytes)
        total_samples = len(unsigned)
        if total_samples == 0:
            return duration, [(0.0, 0.0)] * num_buckets, [0.0] * num_buckets

        bucket_size = max(1, total_samples // num_buckets)
        for b in range(num_buckets):
            start_i = b * bucket_size
            end_i = min(total_samples, (b + 1) * bucket_size)
            chunk = unsigned[start_i:end_i]
            if chunk:
                min_v = (min(chunk) - 128) / 128.0
                max_v = (max(chunk) - 128) / 128.0
                peaks.append((min_v, max_v))
                amps.append(max(abs(min_v), abs(max_v)))
            else:
                peaks.append((0.0, 0.0))
                amps.append(0.0)
    else:
        # Fallback for 24-bit or 32-bit
        peaks = [( -0.5, 0.5 )] * num_buckets
        amps = [0.5] * num_buckets

    return duration, peaks, amps


def detect_silence_bounds(amps, duration, margin: float = 0.15):
    """
    Detect speech start and end boundaries, stripping leading and trailing silence.
    Adds a safety margin around speech.
    """
    if not amps or duration <= 0:
        return 0.0, duration

    max_amp = max(amps)
    if max_amp < 0.05:
        # Audio is essentially pure silence or too quiet to distinguish
        return 0.0, duration

    threshold = max(0.035, max_amp * 0.12)

    start_idx = 0
    while start_idx < len(amps) and amps[start_idx] < threshold:
        start_idx += 1

    end_idx = len(amps) - 1
    while end_idx >= 0 and amps[end_idx] < threshold:
        end_idx -= 1

    if start_idx > end_idx:
        return 0.0, duration

    start_t = max(0.0, (start_idx / len(amps)) * duration - margin)
    end_t = min(duration, ((end_idx + 1) / len(amps)) * duration + margin)

    start_t = round(start_t, 2)
    end_t = round(end_t, 2)

    if end_t - start_t < 0.2:
        return 0.0, duration

    return start_t, end_t


def trim_wav_file(source_path: str, target_path: str, start_time: float, end_time: float) -> float:
    """
    Cuts a segment of a WAV file from start_time to end_time and saves to target_path.
    Returns the duration in seconds of the trimmed segment.
    """
    with wave.open(source_path, "rb") as in_wf:
        nchannels = in_wf.getnchannels()
        sampwidth = in_wf.getsampwidth()
        framerate = in_wf.getframerate()
        nframes = in_wf.getnframes()

        start_frame = max(0, min(int(start_time * framerate), nframes))
        end_frame = max(start_frame, min(int(end_time * framerate), nframes))
        num_frames = end_frame - start_frame

        in_wf.setpos(start_frame)
        frames = in_wf.readframes(num_frames)

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with wave.open(target_path, "wb") as out_wf:
        out_wf.setnchannels(nchannels)
        out_wf.setsampwidth(sampwidth)
        out_wf.setframerate(framerate)
        out_wf.writeframes(frames)

    actual_duration = num_frames / float(framerate) if framerate > 0 else 0.0
    return round(actual_duration, 2)


class AudioWaveformWidget(QWidget):
    rangeChanged = pyqtSignal(float, float)

    def __init__(self, audio_path: str, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(140)
        self.setMinimumWidth(500)

        self.audio_path = audio_path
        self.duration, self.peaks, self.amps = read_wav_peaks(audio_path)

        self.start_time = 0.0
        self.end_time = max(0.1, self.duration)
        self.playhead_time = None
        self.min_duration = 0.1

        self.drag_mode = None
        self.drag_anchor_x = 0
        self.drag_orig_start = 0.0
        self.drag_orig_end = 0.0

        # Margins for rendering
        self.margin_left = 14
        self.margin_right = 14
        self.margin_top = 10
        self.margin_bottom = 22

    def set_range(self, start_t: float, end_t: float, emit_signal: bool = False):
        start_t = max(0.0, min(start_t, self.duration - self.min_duration))
        end_t = max(start_t + self.min_duration, min(end_t, self.duration))

        if abs(self.start_time - start_t) > 0.001 or abs(self.end_time - end_t) > 0.001:
            self.start_time = round(start_t, 2)
            self.end_time = round(end_t, 2)
            self.update()
            if emit_signal:
                self.rangeChanged.emit(self.start_time, self.end_time)

    def set_playhead(self, playhead_t):
        self.playhead_time = playhead_t
        self.update()

    def auto_trim_silence(self):
        s, e = detect_silence_bounds(self.amps, self.duration)
        self.set_range(s, e, emit_signal=True)

    def reset_selection(self):
        self.set_range(0.0, self.duration, emit_signal=True)

    def _usable_width(self) -> float:
        return max(1.0, self.width() - self.margin_left - self.margin_right)

    def _usable_height(self) -> float:
        return max(1.0, self.height() - self.margin_top - self.margin_bottom)

    def _x_for_time(self, t: float) -> float:
        if self.duration <= 0:
            return float(self.margin_left)
        ratio = max(0.0, min(1.0, t / self.duration))
        return self.margin_left + ratio * self._usable_width()

    def _time_for_x(self, x: float) -> float:
        if self.duration <= 0:
            return 0.0
        ratio = max(0.0, min(1.0, (x - self.margin_left) / self._usable_width()))
        return ratio * self.duration

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        usable_w = self._usable_width()
        usable_h = self._usable_height()
        top_y = self.margin_top
        center_y = top_y + usable_h / 2.0

        # Background
        bg_rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        painter.setPen(QPen(QColor(60, 65, 75), 1))
        painter.setBrush(QBrush(QColor(24, 26, 32)))
        painter.drawRoundedRect(bg_rect, 6, 6)

        # Center line
        painter.setPen(QPen(QColor(45, 55, 72), 1))
        painter.drawLine(
            QPointF(self.margin_left, center_y),
            QPointF(self.margin_left + usable_w, center_y),
        )

        # Time grid markers
        if self.duration > 0:
            grid_step = 1.0
            if self.duration <= 3.0:
                grid_step = 0.5
            elif self.duration > 15.0:
                grid_step = 2.0

            font = QFont()
            font.setPointSize(8)
            painter.setFont(font)

            curr_t = grid_step
            while curr_t < self.duration:
                tx = self._x_for_time(curr_t)
                painter.setPen(QPen(QColor(55, 65, 80), 1, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(tx, top_y), QPointF(tx, top_y + usable_h))
                painter.setPen(QColor(130, 140, 155))
                painter.drawText(
                    QRectF(tx - 25, top_y + usable_h + 2, 50, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{curr_t:.1f}s",
                )
                curr_t += grid_step

        # X positions for handles
        x_start = self._x_for_time(self.start_time)
        x_end = self._x_for_time(self.end_time)

        # Draw waveform bars
        num_peaks = len(self.peaks)
        if num_peaks > 0:
            step_px = usable_w / float(num_peaks)
            bar_w = max(1.0, step_px * 0.85)

            for i, (min_v, max_v) in enumerate(self.peaks):
                bx = self.margin_left + i * step_px
                y1 = center_y + min_v * (usable_h * 0.45)
                y2 = center_y + max_v * (usable_h * 0.45)
                if abs(y2 - y1) < 2.0:
                    y1 = center_y - 1.0
                    y2 = center_y + 1.0

                is_selected = (x_start - 0.5) <= bx <= (x_end + 0.5)
                if is_selected:
                    painter.setPen(QPen(QColor(14, 165, 233), bar_w))
                else:
                    painter.setPen(QPen(QColor(75, 85, 99, 160), bar_w))

                painter.drawLine(QPointF(bx, y1), QPointF(bx, y2))

        # Selection overlay
        sel_rect = QRectF(x_start, top_y, max(0.0, x_end - x_start), usable_h)
        painter.fillRect(sel_rect, QColor(14, 165, 233, 35))

        # Boundary handles
        handle_color = QColor(2, 132, 199)
        grip_bg = QColor(3, 105, 161)
        grip_dot = QColor(255, 255, 255)

        # Start Handle
        painter.setPen(QPen(handle_color, 2))
        painter.drawLine(QPointF(x_start, top_y), QPointF(x_start, top_y + usable_h))
        # Top badge
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grip_bg))
        painter.drawRoundedRect(QRectF(x_start - 5, top_y - 2, 10, 14), 3, 3)
        painter.setBrush(QBrush(grip_dot))
        painter.drawEllipse(QPointF(x_start, top_y + 3), 1.5, 1.5)
        painter.drawEllipse(QPointF(x_start, top_y + 7), 1.5, 1.5)

        # End Handle
        painter.setPen(QPen(handle_color, 2))
        painter.drawLine(QPointF(x_end, top_y), QPointF(x_end, top_y + usable_h))
        # Top badge
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grip_bg))
        painter.drawRoundedRect(QRectF(x_end - 5, top_y - 2, 10, 14), 3, 3)
        painter.setBrush(QBrush(grip_dot))
        painter.drawEllipse(QPointF(x_end, top_y + 3), 1.5, 1.5)
        painter.drawEllipse(QPointF(x_end, top_y + 7), 1.5, 1.5)

        # Playhead
        if self.playhead_time is not None:
            ph_x = self._x_for_time(self.playhead_time)
            ph_color = QColor(244, 63, 94)
            painter.setPen(QPen(ph_color, 2))
            painter.drawLine(QPointF(ph_x, top_y), QPointF(ph_x, top_y + usable_h))

            # Triangle at top
            painter.setBrush(QBrush(ph_color))
            painter.setPen(Qt.PenStyle.NoPen)
            poly = QPolygonF([
                QPointF(ph_x - 5, top_y - 3),
                QPointF(ph_x + 5, top_y - 3),
                QPointF(ph_x, top_y + 5),
            ])
            painter.drawPolygon(poly)

    def mousePressEvent(self, event):
        x = event.position().x() if hasattr(event, "position") else event.x()
        x_start = self._x_for_time(self.start_time)
        x_end = self._x_for_time(self.end_time)

        if abs(x - x_start) <= 9:
            self.drag_mode = "start"
        elif abs(x - x_end) <= 9:
            self.drag_mode = "end"
        elif x_start < x < x_end:
            self.drag_mode = "selection"
            self.drag_anchor_x = x
            self.drag_orig_start = self.start_time
            self.drag_orig_end = self.end_time
        else:
            self.drag_mode = "new"
            click_t = self._time_for_x(x)
            self.drag_anchor_x = x
            self.drag_orig_start = click_t
            self.drag_orig_end = click_t
            self.set_range(click_t, click_t + self.min_duration, emit_signal=True)

    def mouseMoveEvent(self, event):
        x = event.position().x() if hasattr(event, "position") else event.x()
        x_start = self._x_for_time(self.start_time)
        x_end = self._x_for_time(self.end_time)

        if self.drag_mode is None:
            if abs(x - x_start) <= 9 or abs(x - x_end) <= 9:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif x_start < x < x_end:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
            return

        if self.drag_mode == "start":
            new_t = self._time_for_x(x)
            new_start = min(new_t, self.end_time - self.min_duration)
            self.set_range(new_start, self.end_time, emit_signal=True)
        elif self.drag_mode == "end":
            new_t = self._time_for_x(x)
            new_end = max(new_t, self.start_time + self.min_duration)
            self.set_range(self.start_time, new_end, emit_signal=True)
        elif self.drag_mode == "selection":
            dt = ((x - self.drag_anchor_x) / self._usable_width()) * self.duration
            sel_len = self.drag_orig_end - self.drag_orig_start
            new_start = self.drag_orig_start + dt
            new_end = self.drag_orig_end + dt
            if new_start < 0:
                new_start = 0.0
                new_end = sel_len
            if new_end > self.duration:
                new_end = self.duration
                new_start = self.duration - sel_len
            self.set_range(new_start, new_end, emit_signal=True)
        elif self.drag_mode == "new":
            curr_t = self._time_for_x(x)
            s = min(self.drag_orig_start, curr_t)
            e = max(self.drag_orig_start, curr_t)
            if e - s < self.min_duration:
                e = s + self.min_duration
            self.set_range(s, e, emit_signal=True)

    def mouseReleaseEvent(self, event):
        self.drag_mode = None
        self.rangeChanged.emit(self.start_time, self.end_time)

    def mouseDoubleClickEvent(self, event):
        self.reset_selection()


class AudioTrimDialog(QDialog):
    def __init__(self, audio_path: str, parent=None, reference_text: str = None):
        super().__init__(parent)
        self.setWindowTitle("Trim Audio - AnkiPA")
        self.setMinimumWidth(680)

        self.audio_path = audio_path
        self.reference_text = reference_text
        self.trimmed_file = audio_path
        self.trimmed_duration = 0.0

        self.playback_timer = QTimer(self)
        self.playback_timer.setInterval(25)
        self.playback_timer.timeout.connect(self._on_playback_tick)

        self.playback_start_wall = 0.0
        self.playback_segment_duration = 0.0
        self.playback_offset_time = 0.0
        self.is_playing = False

        self._init_ui()

    def _init_ui(self):
        vbox = QVBoxLayout()
        vbox.setSpacing(12)

        # Header instructions
        title_label = QLabel("<b>Trim audio before sending to Azure</b>")
        title_label.setStyleSheet("font-size: 14px;")
        vbox.addWidget(title_label)

        sub_label = QLabel(
            "Select the audio segment you want to evaluate. Only the selected snippet "
            "will be sent to Azure Speech API."
        )
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet("color: #a0aec0;")
        vbox.addWidget(sub_label)

        if self.reference_text:
            ref_label = QLabel(f"<b>Reference text:</b> <i>{self.reference_text}</i>")
            ref_label.setWordWrap(True)
            ref_label.setStyleSheet(
                "background-color: rgba(255, 255, 255, 0.05); padding: 8px; border-radius: 4px;"
            )
            vbox.addWidget(ref_label)

        # Waveform visualizer
        self.waveform = AudioWaveformWidget(self.audio_path, self)
        self.waveform.rangeChanged.connect(self._on_waveform_range_changed)
        vbox.addWidget(self.waveform)

        # Range adjustment controls & duration display
        range_layout = QHBoxLayout()

        start_label = QLabel("Start:")
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setRange(0.0, max(0.1, self.waveform.duration))
        self.start_spin.setSingleStep(0.05)
        self.start_spin.setDecimals(2)
        self.start_spin.setSuffix(" s")
        self.start_spin.setValue(self.waveform.start_time)
        self.start_spin.valueChanged.connect(self._on_spin_changed)

        end_label = QLabel("End:")
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setRange(0.0, max(0.1, self.waveform.duration))
        self.end_spin.setSingleStep(0.05)
        self.end_spin.setDecimals(2)
        self.end_spin.setSuffix(" s")
        self.end_spin.setValue(self.waveform.end_time)
        self.end_spin.valueChanged.connect(self._on_spin_changed)

        self.duration_label = QLabel()
        self.duration_label.setStyleSheet("font-weight: bold; color: #38bdf8;")
        self._update_duration_label()

        range_layout.addWidget(start_label)
        range_layout.addWidget(self.start_spin)
        range_layout.addSpacing(10)
        range_layout.addWidget(end_label)
        range_layout.addWidget(self.end_spin)
        range_layout.addSpacing(15)
        range_layout.addWidget(self.duration_label)
        range_layout.addStretch()

        vbox.addLayout(range_layout)

        # Action bar: Auto-trim silence + Reset
        tools_layout = QHBoxLayout()
        self.auto_trim_btn = QPushButton("⚡ Auto-Trim Silence")
        self.auto_trim_btn.setToolTip("Detects speech and removes silence at start and end")
        self.auto_trim_btn.clicked.connect(self.waveform.auto_trim_silence)

        self.reset_btn = QPushButton("↺ Select All")
        self.reset_btn.setToolTip("Resets selection to the full audio duration")
        self.reset_btn.clicked.connect(self.waveform.reset_selection)

        tools_layout.addWidget(self.auto_trim_btn)
        tools_layout.addWidget(self.reset_btn)
        tools_layout.addStretch()

        # Playback buttons
        self.play_snippet_btn = QPushButton("▶ Play Snippet")
        self.play_snippet_btn.setStyleSheet(
            "font-weight: bold; padding: 6px 14px; background-color: #0284c7; color: white;"
        )
        self.play_snippet_btn.clicked.connect(self._toggle_play_snippet)

        self.play_full_btn = QPushButton("Play Full Audio")
        self.play_full_btn.clicked.connect(self._toggle_play_full)

        tools_layout.addWidget(self.play_snippet_btn)
        tools_layout.addWidget(self.play_full_btn)

        vbox.addLayout(tools_layout)

        # Space shortcut to toggle playback
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.space_shortcut.activated.connect(self._toggle_play_snippet)

        # Dialog buttons (Confirm & Cancel)
        self.button_box = QDialogButtonBox()
        self.confirm_btn = QPushButton("Confirm and Send")
        self.confirm_btn.setDefault(True)
        self.confirm_btn.setStyleSheet("font-weight: bold; padding: 6px 16px;")
        self.cancel_btn = QPushButton("Cancel")

        self.button_box.addButton(self.confirm_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_box.addButton(self.cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self.button_box.accepted.connect(self._on_confirm)
        self.button_box.rejected.connect(self._on_cancel)

        vbox.addSpacing(8)
        vbox.addWidget(self.button_box)

        self.setLayout(vbox)

    def _update_duration_label(self):
        sel_dur = max(0.0, self.waveform.end_time - self.waveform.start_time)
        tot_dur = self.waveform.duration
        self.duration_label.setText(f"Duration: {sel_dur:.2f}s  (Total: {tot_dur:.2f}s)")

    def _on_waveform_range_changed(self, s: float, e: float):
        self.start_spin.blockSignals(True)
        self.end_spin.blockSignals(True)
        self.start_spin.setValue(s)
        self.end_spin.setValue(e)
        self.start_spin.blockSignals(False)
        self.end_spin.blockSignals(False)
        self._update_duration_label()

    def _on_spin_changed(self):
        s = self.start_spin.value()
        e = self.end_spin.value()
        self.waveform.set_range(s, e, emit_signal=False)
        self._update_duration_label()

    def _stop_playback(self):
        self.playback_timer.stop()
        self.is_playing = False
        self.waveform.set_playhead(None)
        self.play_snippet_btn.setText("▶ Play Snippet")
        self.play_full_btn.setText("Play Full Audio")
        if av_player:
            try:
                av_player.stop_and_clear_queue()
            except Exception:
                pass

    def _toggle_play_snippet(self):
        if self.is_playing:
            self._stop_playback()
            return

        s = self.waveform.start_time
        e = self.waveform.end_time
        dur = max(0.05, e - s)

        # Generate temporary preview WAV
        temp_dir = get_temp_ankipa_dir()
        preview_file = os.path.join(temp_dir, f"preview_{int(time.time() * 1000)}.wav")
        trim_wav_file(self.audio_path, preview_file, s, e)

        self._start_playback(preview_file, s, dur, is_snippet=True)

    def _toggle_play_full(self):
        if self.is_playing:
            self._stop_playback()
            return

        self._start_playback(self.audio_path, 0.0, self.waveform.duration, is_snippet=False)

    def _start_playback(self, file_path: str, offset: float, duration: float, is_snippet: bool):
        self._stop_playback()

        if play:
            try:
                play(file_path)
            except Exception:
                pass
        elif av_player and hasattr(av_player, "play_file"):
            try:
                av_player.play_file(file_path)
            except Exception:
                pass

        self.is_playing = True
        self.playback_offset_time = offset
        self.playback_segment_duration = duration
        self.playback_start_wall = time.time()

        if is_snippet:
            self.play_snippet_btn.setText("⏹ Stop")
        else:
            self.play_full_btn.setText("⏹ Stop")

        self.waveform.set_playhead(offset)
        self.playback_timer.start()

    def _on_playback_tick(self):
        elapsed = time.time() - self.playback_start_wall
        if elapsed >= self.playback_segment_duration:
            self._stop_playback()
        else:
            current_pos = self.playback_offset_time + elapsed
            self.waveform.set_playhead(current_pos)

    def _on_confirm(self):
        self._stop_playback()

        s = self.waveform.start_time
        e = self.waveform.end_time

        # Create trimmed audio file
        temp_dir = get_temp_ankipa_dir()
        trimmed_path = os.path.join(temp_dir, f"trimmed_{int(time.time() * 1000)}.wav")
        self.trimmed_duration = trim_wav_file(self.audio_path, trimmed_path, s, e)
        self.trimmed_file = trimmed_path

        self.accept()

    def _on_cancel(self):
        self._stop_playback()
        self.reject()

    def closeEvent(self, event):
        self._stop_playback()
        super().closeEvent(event)

    def get_trimmed_file(self) -> str:
        return self.trimmed_file

    def get_trimmed_duration(self) -> float:
        return self.trimmed_duration
