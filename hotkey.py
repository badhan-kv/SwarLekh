"""Tap-to-toggle vs hold-to-talk hotkey state machine.

Pure logic, no pynput here — see tray.py for the actual global key listener that
drives on_key_down()/on_key_up().
"""

import time

STATE_IDLE = "idle"
STATE_PRESSED = "pressed"  # key down, first press, duration not yet decided
STATE_TOGGLE_RECORDING = "toggle_recording"  # tap released; recording continues
STATE_TOGGLE_STOPPING = "toggle_stopping"  # second press down, waiting for release to stop

DEFAULT_HOLD_THRESHOLD_SECONDS = 0.35


class HotkeyStateMachine:
    """Quick tap toggles recording on/off; press-and-hold is push-to-talk.

    `on_start_recording()` fires the moment the key is first pressed (so no
    audio is missed while we wait to find out if this is a tap or a hold).
    `on_stop_recording()` fires once we know recording should end — either on
    release of a hold, or on the second press+release that ends a toggle.
    """

    def __init__(
        self,
        on_start_recording,
        on_stop_recording,
        on_cancel_recording=None,
        hold_threshold_seconds: float = DEFAULT_HOLD_THRESHOLD_SECONDS,
        now_fn=None,
    ):
        self._on_start_recording = on_start_recording
        self._on_stop_recording = on_stop_recording
        self._on_cancel_recording = on_cancel_recording or (lambda: None)
        self._hold_threshold = hold_threshold_seconds
        self._now_fn = now_fn or time.monotonic
        self._state = STATE_IDLE
        self._pressed_at = None

    @property
    def state(self) -> str:
        return self._state

    def on_key_down(self) -> None:
        if self._state == STATE_IDLE:
            self._pressed_at = self._now_fn()
            self._on_start_recording()
            self._state = STATE_PRESSED
        elif self._state == STATE_TOGGLE_RECORDING:
            self._state = STATE_TOGGLE_STOPPING
        # STATE_PRESSED / STATE_TOGGLE_STOPPING: ignore key-repeat down events.

    def on_key_up(self) -> None:
        if self._state == STATE_PRESSED:
            elapsed = self._now_fn() - self._pressed_at
            if elapsed >= self._hold_threshold:
                self._on_stop_recording()
                self._state = STATE_IDLE
            else:
                self._state = STATE_TOGGLE_RECORDING
        elif self._state == STATE_TOGGLE_STOPPING:
            self._on_stop_recording()
            self._state = STATE_IDLE
        # STATE_IDLE / STATE_TOGGLE_RECORDING: ignore stray key-up.

    def cancel(self) -> None:
        """Call when a non-combo key joins mid-press — this wasn't our hotkey
        after all (e.g. the user was actually pressing Ctrl+Shift+N).

        If we'd already started recording for a fresh press, discard it. If we
        were about to end a toggle-recording, that attempt didn't count —
        recording just keeps going.
        """
        if self._state == STATE_PRESSED:
            self._on_cancel_recording()
            self._state = STATE_IDLE
        elif self._state == STATE_TOGGLE_STOPPING:
            self._state = STATE_TOGGLE_RECORDING
        # STATE_IDLE / STATE_TOGGLE_RECORDING: nothing engaged, nothing to cancel.
