import threading
import subprocess
import pulsectl

from StreamDeck.Devices.StreamDeck import DialEventType, TouchscreenEventType
from evdev import UInput, ecodes
ui = UInput()

DOUBLE_CLICK_TIME = 0.3  # seconds

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
    def button_0(self, val):
        if val is True:
            print('BUTTON 0 ACTION')

    def button_1(self, val):
        if val is True:
            print('BUTTON 1 ACTION')

    def button_2_single(self):
        print('BUTTON 2 SINGLE ACTION')

    def button_2_double(self):
        print('BUTTON 2 DOUBLE ACTION')

    def button_3_single(self):
        print('BUTTON 3 SINGLE ACTION')

    def button_3_double(self):
        print('BUTTON 3 DOUBLE ACTION')

    def button_4(self, val):
        if val is True:
            print('BUTTON 4 ACTION')

    def button_5(self, val):
        if val is True:
            print('BUTTON 5 ACTION')

    def button_6_single(self):
        print('BUTTON 6 SINGLE ACTION')

    def button_6_double(self):
        print('BUTTON 6 DOUBLE ACTION')

    def button_7_single(self):
        subprocess.run(["playerctl", "--player=spotify", "play-pause"])

    def button_7_double(self):
        subprocess.run(["playerctl", "--player=spotify", "next"])

    # -----------------------------
    # DIAL MAIN HANDLER
    # -----------------------------
    def key_callback(self, deck, key, state,):

        #print(f"Button {key} {'pressed' if state else 'released'}")
        match key:
            case 0: self.button_0(state)
            case 1: self.button_1(state)
            case 2: self.handle_button_click(key, state, self.button_2_single, self.button_2_double)
            case 3: self.handle_button_click(key, state, self.button_3_single, self.button_3_double)
            case 4: self.button_4(state)
            case 5: self.button_5(state)
            case 6: self.handle_button_click(key, state, self.button_6_single, self.button_6_double)
            case 7: self.handle_button_click(key, state, self.button_7_single, self.button_7_double)


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
            self.state.audio_queue.put(("dial_bind", None, 2, None))

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

    def touch_callback(self,deck,event_type,value,):

        #print(event_type,value,)
        if event_type == TouchscreenEventType.SHORT:
            print("Short touch @ " + str(value['x']) + "," + str(value['y']))

        elif event_type == TouchscreenEventType.LONG:
            print("Long touch @ " + str(value['x']) + "," + str(value['y']))

        elif event_type == TouchscreenEventType.DRAG:
            print("Drag started @ " + str(value['x']) + "," + str(value['y']) + " ended @ " + str(value['x_out']) + "," + str(value['y_out']))