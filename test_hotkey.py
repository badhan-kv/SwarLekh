from unittest.mock import MagicMock

from hotkey import (
    HotkeyStateMachine,
    STATE_IDLE,
    STATE_PRESSED,
    STATE_TOGGLE_RECORDING,
    STATE_TOGGLE_STOPPING,
)


class _FakeClock:
    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def _make(threshold=0.35, clock=None):
    clock = clock or _FakeClock()
    start_cb = MagicMock()
    stop_cb = MagicMock()
    cancel_cb = MagicMock()
    sm = HotkeyStateMachine(
        start_cb, stop_cb, cancel_cb, hold_threshold_seconds=threshold, now_fn=clock
    )
    return sm, start_cb, stop_cb, cancel_cb, clock


def test_key_down_starts_recording_immediately():
    sm, start_cb, stop_cb, cancel_cb, clock = _make()
    sm.on_key_down()
    start_cb.assert_called_once()
    stop_cb.assert_not_called()
    assert sm.state == STATE_PRESSED


def test_quick_tap_enters_toggle_recording_without_stopping():
    sm, start_cb, stop_cb, cancel_cb, clock = _make(threshold=0.35)
    sm.on_key_down()
    clock.advance(0.1)  # well under threshold
    sm.on_key_up()
    start_cb.assert_called_once()
    stop_cb.assert_not_called()
    assert sm.state == STATE_TOGGLE_RECORDING


def test_hold_past_threshold_stops_on_release():
    sm, start_cb, stop_cb, cancel_cb, clock = _make(threshold=0.35)
    sm.on_key_down()
    clock.advance(1.0)  # held well past threshold
    sm.on_key_up()
    start_cb.assert_called_once()
    stop_cb.assert_called_once()
    assert sm.state == STATE_IDLE


def test_second_press_and_release_ends_toggle_recording():
    sm, start_cb, stop_cb, cancel_cb, clock = _make(threshold=0.35)
    sm.on_key_down()
    clock.advance(0.05)
    sm.on_key_up()  # tap -> toggle recording starts
    assert sm.state == STATE_TOGGLE_RECORDING

    sm.on_key_down()  # second press, any duration
    clock.advance(2.0)  # even a long hold on the second press just stops it
    sm.on_key_up()

    assert start_cb.call_count == 1  # recording only started once
    stop_cb.assert_called_once()
    assert sm.state == STATE_IDLE


def test_stray_key_up_in_idle_is_ignored():
    sm, start_cb, stop_cb, cancel_cb, clock = _make()
    sm.on_key_up()
    start_cb.assert_not_called()
    stop_cb.assert_not_called()
    assert sm.state == STATE_IDLE


def test_key_repeat_down_events_while_pressed_are_ignored():
    sm, start_cb, stop_cb, cancel_cb, clock = _make()
    sm.on_key_down()
    sm.on_key_down()  # OS key-repeat while still held
    sm.on_key_down()
    start_cb.assert_called_once()
    assert sm.state == STATE_PRESSED


def test_exactly_at_threshold_counts_as_hold():
    sm, start_cb, stop_cb, cancel_cb, clock = _make(threshold=0.35)
    sm.on_key_down()
    clock.advance(0.35)
    sm.on_key_up()
    stop_cb.assert_called_once()
    assert sm.state == STATE_IDLE


def test_cancel_while_pressed_discards_without_stopping():
    # e.g. Ctrl+Shift+N: our combo landed, then a foreign key joined mid-press.
    sm, start_cb, stop_cb, cancel_cb, clock = _make()
    sm.on_key_down()
    sm.cancel()
    start_cb.assert_called_once()
    stop_cb.assert_not_called()
    cancel_cb.assert_called_once()
    assert sm.state == STATE_IDLE


def test_cancel_while_toggle_stopping_keeps_recording_going():
    sm, start_cb, stop_cb, cancel_cb, clock = _make()
    sm.on_key_down()
    clock.advance(0.05)
    sm.on_key_up()  # tap -> toggle recording
    assert sm.state == STATE_TOGGLE_RECORDING

    sm.on_key_down()  # second press begins, arms for stop
    assert sm.state == STATE_TOGGLE_STOPPING
    sm.cancel()  # a foreign key joined -> this wasn't the stop tap after all

    stop_cb.assert_not_called()  # recording must keep going, not be discarded
    cancel_cb.assert_not_called()  # nothing was discarded either
    assert sm.state == STATE_TOGGLE_RECORDING


def test_cancel_in_idle_or_toggle_recording_is_a_no_op():
    sm, start_cb, stop_cb, cancel_cb, clock = _make()
    sm.cancel()  # idle
    cancel_cb.assert_not_called()
    assert sm.state == STATE_IDLE

    sm.on_key_down()
    clock.advance(0.05)
    sm.on_key_up()  # now toggle_recording
    sm.cancel()
    cancel_cb.assert_not_called()
    stop_cb.assert_not_called()
    assert sm.state == STATE_TOGGLE_RECORDING
