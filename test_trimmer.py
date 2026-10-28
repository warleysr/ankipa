import os
import wave
import struct
import tempfile
import unittest

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter, QMouseEvent
from PyQt6.QtCore import Qt, QPointF, QEvent

# Set offscreen Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from trimmer import (
    read_wav_peaks,
    detect_silence_bounds,
    trim_wav_file,
    AudioWaveformWidget,
    AudioTrimDialog,
)


class TestAudioTrimmer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

        # Create sample WAV files
        cls.test_dir = tempfile.mkdtemp(prefix="ankipa_test_")

        # 1. Standard speech wav: 3.0 seconds, silence 0.6s, speech 1.5s, silence 0.9s
        cls.speech_wav = os.path.join(cls.test_dir, "speech.wav")
        with wave.open(cls.speech_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            # 0.6s silence (9600 frames)
            d = [0] * 9600
            # 1.5s speech (24000 frames)
            d += [12000 if (i % 30 < 15) else -12000 for i in range(24000)]
            # 0.9s silence (14400 frames)
            d += [0] * 14400
            wf.writeframes(struct.pack("<" + "h" * len(d), *d))

        # 2. Pure silence wav: 2.0s
        cls.silence_wav = os.path.join(cls.test_dir, "silence.wav")
        with wave.open(cls.silence_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(struct.pack("<" + "h" * 32000, *([0] * 32000)))

        # 3. Stereo 16-bit wav: 1.0s
        cls.stereo_wav = os.path.join(cls.test_dir, "stereo.wav")
        with wave.open(cls.stereo_wav, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            st_data = []
            for i in range(16000):
                st_data.extend([8000, -8000])
            wf.writeframes(struct.pack("<" + "h" * len(st_data), *st_data))

    def test_read_wav_peaks(self):
        dur, peaks, amps = read_wav_peaks(self.speech_wav, num_buckets=300)
        self.assertAlmostEqual(dur, 3.0, places=2)
        self.assertEqual(len(peaks), 300)
        self.assertEqual(len(amps), 300)
        self.assertGreater(max(amps), 0.3)

        # Test non-existent file
        dur0, peaks0, amps0 = read_wav_peaks("non_existent_file.wav")
        self.assertEqual(dur0, 0.0)

        # Test stereo file
        dur_st, peaks_st, amps_st = read_wav_peaks(self.stereo_wav, num_buckets=200)
        self.assertAlmostEqual(dur_st, 1.0, places=2)
        self.assertEqual(len(peaks_st), 200)

    def test_detect_silence_bounds(self):
        dur, peaks, amps = read_wav_peaks(self.speech_wav, num_buckets=400)
        s, e = detect_silence_bounds(amps, dur)
        # Speech was 0.6s to 2.1s; with 0.15 margin it should be around 0.45s to 2.25s
        self.assertGreaterEqual(s, 0.4)
        self.assertLessEqual(s, 0.65)
        self.assertGreaterEqual(e, 2.05)
        self.assertLessEqual(e, 2.3)

        # Pure silence
        dur_sil, _, amps_sil = read_wav_peaks(self.silence_wav, num_buckets=200)
        s_sil, e_sil = detect_silence_bounds(amps_sil, dur_sil)
        self.assertEqual(s_sil, 0.0)
        self.assertEqual(e_sil, dur_sil)

    def test_trim_wav_file(self):
        target = os.path.join(self.test_dir, "trimmed.wav")
        dur = trim_wav_file(self.speech_wav, target, 0.5, 2.0)
        self.assertAlmostEqual(dur, 1.5, places=2)
        self.assertTrue(os.path.exists(target))

        with wave.open(target, "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 16000)
            self.assertEqual(wf.getnframes(), int(1.5 * 16000))

    def test_waveform_widget_ui_and_mouse(self):
        widget = AudioWaveformWidget(self.speech_wav)
        widget.resize(600, 160)

        # Test initial range
        self.assertAlmostEqual(widget.start_time, 0.0)
        self.assertAlmostEqual(widget.end_time, 3.0, places=1)

        # Test rendering without crash
        img = QImage(600, 160, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        widget.render(p)
        p.end()

        # Test set_range clamping
        widget.set_range(1.0, 2.5)
        self.assertEqual(widget.start_time, 1.0)
        self.assertEqual(widget.end_time, 2.5)

        # Test auto trim
        widget.auto_trim_silence()
        self.assertGreater(widget.start_time, 0.0)
        self.assertLess(widget.end_time, 3.0)

        # Test reset
        widget.reset_selection()
        self.assertEqual(widget.start_time, 0.0)
        self.assertAlmostEqual(widget.end_time, 3.0, places=1)

        # Test mouse interaction on start handle
        x_start = widget._x_for_time(widget.start_time)
        press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(x_start, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.mousePressEvent(press)
        self.assertEqual(widget.drag_mode, "start")

        move = QMouseEvent(QEvent.Type.MouseMove, QPointF(x_start + 60, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.mouseMoveEvent(move)
        self.assertGreater(widget.start_time, 0.0)

        release = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(x_start + 60, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        widget.mouseReleaseEvent(release)
        self.assertIsNone(widget.drag_mode)

    def test_dialog_interactions_and_confirm(self):
        dlg = AudioTrimDialog(self.speech_wav, reference_text="Good morning")
        self.assertIn("Good morning", dlg.reference_text)

        # Test spinbox synchronization
        dlg.start_spin.setValue(0.8)
        dlg.end_spin.setValue(2.2)
        self.assertEqual(dlg.waveform.start_time, 0.8)
        self.assertEqual(dlg.waveform.end_time, 2.2)
        self.assertIn("1.40s", dlg.duration_label.text())

        # Test playback toggle
        dlg._toggle_play_snippet()
        self.assertTrue(dlg.is_playing)
        self.assertEqual(dlg.play_snippet_btn.text(), "⏹ Stop")

        dlg._stop_playback()
        self.assertFalse(dlg.is_playing)
        self.assertEqual(dlg.play_snippet_btn.text(), "▶ Play Snippet")

        # Test confirm
        dlg._on_confirm()
        trimmed_file = dlg.get_trimmed_file()
        self.assertTrue(os.path.exists(trimmed_file))
        self.assertAlmostEqual(dlg.get_trimmed_duration(), 1.4, places=2)

        with wave.open(trimmed_file, "rb") as wf:
            self.assertEqual(wf.getnframes(), int(1.4 * 16000))


if __name__ == "__main__":
    unittest.main()
