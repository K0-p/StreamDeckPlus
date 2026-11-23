import threading
import subprocess

from StreamDeck.Devices.StreamDeck import DialEventType, TouchscreenEventType
from evdev import UInput, ecodes
ui = UInput()

DOUBLE_CLICK_TIME = 0.3  # seconds
TOUCHBAR_WIDTH    = 800
TOUCHBAR_SECTORS  = 4

class InputHandler:

    def __init__(self, deck, state, renderer):

        self.deck = deck
        self.state = state
        self.renderer = renderer

        self._click_lock = threading.Lock()
        self._click_timers = {}

    def run(self):

        self.deck.set_key_callback(self.key_callback)
        self.deck.set_dial_callback(self.dial_callback)
        self.deck.set_touchscreen_callback(self.touch_callback)
        threading.Event().wait()


    ####################################################
    # Buttons
    ####################################################

    def handle_button_click(self, button, pressed, single_cb, double_cb):
        if not pressed:
            return
        with self._click_lock:
            timer = self._click_timers.get(button)
            if timer is None:
                timer = threading.Timer(
                    DOUBLE_CLICK_TIME,
                    self._single_click_timeout,
                    args=(button, single_cb),
                )
                self._click_timers[button] = timer
                timer.start()
            else:
                timer.cancel()
                del self._click_timers[button]
                double_cb()

    def _single_click_timeout(self, button, callback):
        with self._click_lock:
            self._click_timers.pop(button, None)
        callback()

    # -----------------------------
    # BUTTON PRESS EVENTS
    # -----------------------------
    def _button_0(self, val):
        if val is True:
            print('BUTTON 0 ACTION')

    def _button_1(self, val):
        if val is True:
            print('BUTTON 1 ACTION')

    def _button_2_single(self):
        brightness = self.state.brightness
        new = max(10, min(100, brightness + 10))
        if new != brightness:
            self.state.brightness = new
            self.state.render_queue.put("brightness")

    def _button_2_double(self):
        brightness = self.state.brightness
        new = 100
        if new != brightness:
            self.state.brightness = new
            self.state.render_queue.put("brightness")

    def _button_3_single(self):
        self.state.hr24 = not self.state.hr24
        self.state.render_queue.put("clock")

    def _button_3_double(self):
        print('BUTTON 3 DOUBLE ACTION')

    def _button_4(self, val):
        if val is True:
            print('BUTTON 4 ACTION')

    def _button_5(self, val):
        if val is True:
            print('BUTTON 5 ACTION')

    def _button_6_single(self):
        brightness = self.state.brightness
        new = max(10, min(100, brightness - 10))
        if new != brightness:
            self.state.brightness = new
            self.state.render_queue.put("brightness")

    def _button_6_double(self):
        brightness = self.state.brightness
        new = 10
        if new != brightness:
            self.state.brightness = new
            self.state.render_queue.put("brightness")

    def _button_7_single(self):
        subprocess.run(["playerctl", "--player=spotify", "play-pause"])

    def _button_7_double(self):
        subprocess.run(["playerctl", "--player=spotify", "next"])

    # -----------------------------
    # DIAL MAIN HANDLER
    # -----------------------------
    def key_callback(self, deck, key, state,):

        #print(f"Button {key} {'pressed' if state else 'released'}")
        match key:
            case 0: self._button_0(state)
            case 1: self._button_1(state)
            case 2: self.handle_button_click(key, state, self._button_2_single, self._button_2_double)
            case 3:
                if state is True: self._button_3_single()
            case 4: self._button_4(state)
            case 5: self._button_5(state)
            case 6: self.handle_button_click(key, state, self._button_6_single, self._button_6_double)
            case 7: self.handle_button_click(key, state, self._button_7_single, self._button_7_double)


    ####################################################
    # Dials
    ####################################################

    # -----------------------------
    # DIAL TURN EVENTS
    # -----------------------------
    def dial0_turn(self, val):
        val_abs = abs(val)
        if val > 0:
            for idx in range(val_abs):
                ui.write(ecodes.EV_KEY, ecodes.KEY_VOLUMEUP, 1)
                ui.write(ecodes.EV_KEY, ecodes.KEY_VOLUMEUP, 0)
                ui.syn()
        elif val < 0:
            for idx in range(val_abs):
                ui.write(ecodes.EV_KEY, ecodes.KEY_VOLUMEDOWN, 1)
                ui.write(ecodes.EV_KEY, ecodes.KEY_VOLUMEDOWN, 0)
                ui.syn()

    def dial1_turn(self, val):
        scaled_val = val*2
        self.state.audio_queue.put(("source_update", "volume", scaled_val, None))

    def dial2_turn(self, val):
        self.state.audio_queue.put(("app_update", "volume", (val * 2), self.state.audio["d2"]["assignment"]))

    def dial3_turn(self, val):
        self.state.audio_queue.put(("app_update", "volume", val, "Spotify"))

    # -----------------------------
    # DIAL PRESS EVENTS
    # -----------------------------
    def dial0_press(self, val):
        if val is True:
            ui.write(ecodes.EV_KEY, ecodes.KEY_MUTE, 1)
            ui.write(ecodes.EV_KEY, ecodes.KEY_MUTE, 0)
            ui.syn()

    def dial1_press(self, val):
        if val is True:
            self.state.audio_queue.put(("source_update", "toggle_mute", val, None))

    def dial2_press(self, val):
        if val is True:
            self.state.audio_queue.put(("app_update", "toggle_mute", val, self.state.audio["d2"]["assignment"]))

    def dial3_press(self, val):
        if val is True:
            self.state.audio_queue.put(("app_update", "toggle_mute", val, "Spotify"))

    # -----------------------------
    # DIAL MAIN HANDLER
    # -----------------------------
    def dial_callback(self,deck,dial,event_type,value,):

        #print(dial,event_type,value,)
        if event_type == DialEventType.PUSH:
            #print(f"dial pushed: {dial} state: {value}")
            match dial:
                case 0: self.dial0_press(value)
                case 1: self.dial1_press(value)
                case 2: self.dial2_press(value)
                case 3: self.dial3_press(value)
        elif event_type == DialEventType.TURN:
            #print(f"dial {dial} turned: {value}")
            match dial:
                case 0: self.dial0_turn(value)
                case 1: self.dial1_turn(value)
                case 2: self.dial2_turn(value)
                case 3: self.dial3_turn(value)


    ####################################################
    # Touchscreen
    ####################################################

    def get_touch_sector(self, x):
        sector_width = TOUCHBAR_WIDTH / TOUCHBAR_SECTORS
        sector = int(x // sector_width)
        return max(0, min(TOUCHBAR_SECTORS - 1, sector))

    # -----------------------------
    # TOUCHBAR EVENTS
    # -----------------------------
    def touch_0(self, mode, val):
        match mode:
            case 0:
                if self.state.DEBUG: print(f"Short touch in sector 0:" f"@ {val['x']},{val['y']}")
            case 1:
                if self.state.DEBUG: print(f"Long touch in sector 0:" f"@ {val['x']},{val['y']}")
            case 2:
                if self.state.DEBUG: print(f"Drag in sector 0: "f"{val['x']},{val['y']} -> "f"{val['x_out']},{val['y_out']}")

    def touch_1(self, mode, val):
        match mode:
            case 0:
                if self.state.DEBUG: print(f"Short touch in sector 1:" f"@ {val['x']},{val['y']}")
            case 1:
                if self.state.DEBUG: print(f"Long touch in sector 1:" f"@ {val['x']},{val['y']}")
            case 2:
                if self.state.DEBUG: print(f"Drag in sector 1: "f"{val['x']},{val['y']} -> "f"{val['x_out']},{val['y_out']}")

    def touch_2(self, mode, val):
        match mode:
            case 0:
                if self.state.DEBUG: print(f"Short touch in sector 2:" f"@ {val['x']},{val['y']}")
                self.state.audio_queue.put(("dial_bind", None, 2, None))
            case 1:
                if self.state.DEBUG: print(f"Long touch in sector 2:" f"@ {val['x']},{val['y']}")
                self.state.audio_queue.put(("dial_unbind", None, 2, None))
            case 2:
                if self.state.DEBUG: print(f"Drag in sector 2: "f"{val['x']},{val['y']} -> "f"{val['x_out']},{val['y_out']}")

    def touch_3(self, mode, val):
        match mode:
            case 0:
                if self.state.DEBUG: print(f"Short touch in sector 3:" f"@ {val['x']},{val['y']}")
            case 1:
                if self.state.DEBUG: print(f"Long touch in sector 3:" f"@ {val['x']},{val['y']}")
            case 2:
                if self.state.DEBUG: print(f"Drag in sector 3: "f"{val['x']},{val['y']} -> "f"{val['x_out']},{val['y_out']}")

    # -----------------------------
    # TOUCHBAR MAIN HANDLER
    # -----------------------------
    def touch_callback(self, deck, event_type, value):
        mode = 0

        if event_type == TouchscreenEventType.SHORT:
            sector = self.get_touch_sector(value['x'])

        elif event_type == TouchscreenEventType.LONG:
            sector = self.get_touch_sector(value['x'])
            mode = 1

        elif event_type == TouchscreenEventType.DRAG:
            start_sector = self.get_touch_sector(value['x'])
            end_sector   = self.get_touch_sector(value['x_out'])
            # Only accept drags that remain inside one sector
            if start_sector != end_sector:
                return
            sector = start_sector
            mode = 2

        match sector:
            case 0: self.touch_0(mode, value)
            case 1: self.touch_1(mode, value)
            case 2: self.touch_2(mode, value)
            case 3: self.touch_3(mode, value)