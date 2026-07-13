import pulsectl
import subprocess

class AudioHandler:

    def __init__(self, state, renderer):

        self.state = state
        self.renderer = renderer
        self.audio_queue = state.audio_queue
        self.control = pulsectl.Pulse("streamdeck-control")
        self.available_apps = []
        self.init_dials({
                            0: "Master_out",
                            1: "Master_in",
                            2: None,
                            3: None,    # Used for spotify control
                        })
        self.bind_idx = 0
        self.SPOT_ID = None


    def run(self):
        # Connection dedicated to events
        event_pulse = pulsectl.Pulse("streamdeck-events")

        self.update(self.control)
        event_pulse.event_mask_set("sink", "source", "sink_input",)

        def callback(event):
            self.update(self.control)
        event_pulse.event_callback_set(callback)

        while True:
            self.process_commands()
            event_pulse.event_listen(timeout=0.05)


    ####################################################
    # Runtime Audio Updates
    ####################################################

    def update(self, pulse):

        if self.state.DEBUG: print("\n AUDIO RUNTIME:")
        self.update_sink(pulse)
        self.update_source(pulse)
        self.update_inputs(pulse)
        self.state.render_queue.put("audio_touchbar")

    def update_sink(self, pulse):

        try:
            sink = pulse.get_sink_by_name(pulse.server_info().default_sink_name)

        except Exception as e:
            print("Failed to get default sink:",e)
            return

        self.state.audio["sink"] = {
            "name":     sink.description,
            "volume":   int(sink.volume.value_flat * 100),
            "mute":     sink.mute,
            "index":    sink.index,
        }

        for idx in range(4):
            d_idx = f"d{idx}"
            if self.state.audio[d_idx]["assignment"] == "Master_out":
                self.state.audio[d_idx]["vol"] = self.state.audio["sink"]["volume"]
                self.state.audio[d_idx]["mute"] = self.state.audio["sink"]["mute"]
                if self.state.audio[d_idx]["vol"] != 0:
                        self.state.audio[d_idx]["nonzero_vol"] = self.state.audio[d_idx]["vol"]

        if self.state.DEBUG: print(f"{self.state.audio["sink"]["name"]} --- VOL = {self.state.audio["sink"]["volume"]}  (muted={self.state.audio["sink"]["mute"]})")

    def update_source(self, pulse):

        try:
            source = pulse.get_source_by_name(pulse.server_info().default_source_name)

        except Exception as e:
            print("Failed to get default source:", e)
            return

        self.state.audio["source"] = {
            "name":     source.description,
            "volume":   int(source.volume.value_flat * 100),
            "mute":     source.mute,
            "index":    source.index,
        }

        for idx in range(4):
            d_idx = f"d{idx}"
            if self.state.audio[d_idx]["assignment"] == "Master_in":
                self.state.audio[d_idx]["vol"] = self.state.audio["source"]["volume"]
                self.state.audio[d_idx]["mute"] = self.state.audio["source"]["mute"]
                if self.state.audio[d_idx]["vol"] != 0:
                        self.state.audio[d_idx]["nonzero_vol"] = self.state.audio[d_idx]["vol"]       
                else:
                    self.state.audio[d_idx]["mute"] = True           

        if self.state.DEBUG: print(f'{self.state.audio["source"]["name"]} --- 'f'VOL = {self.state.audio["source"]["volume"]} 'f'(muted={self.state.audio["source"]["mute"]})')

    def update_inputs(self, pulse):
        self.available_apps = []

        inputs = {}
        for item in pulse.sink_input_list():
            name = item.proplist.get("application.name","Unknown",)
            id = item.index
            self.available_apps.append(id)
            inputs[id] = {
                "app_name": name,
                "media_name" : item.name,
                "name" : id,
                "volume":   int(item.volume.value_flat * 100),
                "mute":     item.mute,
                "index":    item.index,
            }

            for idx in range(4):
                d_idx = f"d{idx}"
                # TODO: this creases problems when there are multiple instances of the same name :/
                if self.state.audio[d_idx]["assignment"] == id:
                    if self.state.DEBUG: print(f"            Dial {idx} match with id {id}")
                    self.state.audio[d_idx]["vol"] = int(item.volume.value_flat * 100)
                    self.state.audio[d_idx]["mute"] = (self.state.audio[d_idx]["vol"] == 0)
                    self.state.audio[d_idx]["app_name"] = name
                    self.state.audio[d_idx]["media_name"] = item.name
                    self.state.audio[d_idx]["name"] = id
                    if self.state.audio[d_idx]["vol"] != 0:
                        self.state.audio[d_idx]["nonzero_vol"] = self.state.audio[d_idx]["vol"]
                if self.SPOT_ID is None:
                    if name == "Spotify": self._update_spotify_id()

            if self.state.DEBUG: print(f"{name}: {item.name} --- VOL = {inputs[id]["volume"]}  (muted={inputs[id]["mute"]})")

        # check if dial binding still valid
        self.validate_dial_bind(2)   # dial 2 is bindable - none others are

        self.state.audio["inputs"] = inputs


    ####################################################
    # Runtime Audio Commands
    ####################################################

    def sink_update(self, type, val):
        if type == "toggle_mute":
            print('mute')
        elif type == "volume":
            print('vol')
        else:
            print("UNKNOWN AUDIO SINK COMMAND")

    def source_update(self, type, val):    
        if type == "toggle_mute":
            source = self.control.get_source_by_name(self.control.server_info().default_source_name)
            self.control.mute(source, not source.mute)
        elif type == "volume":
            source = self.control.get_source_by_name(self.control.server_info().default_source_name)
            if source.mute:
                # Bug where increasing volume doesn't modify mute state of source
                self.control.mute(source, not source.mute)
            current = int(round(source.volume.value_flat * 100))
            new = max(0, min(100, current + val))
            self.control.volume_set_all_chans(source, new / 100.0)
        else:
            print("UNKNOWN AUDIO SOURCE COMMAND")

    def spotify_update(self, type, val):
        d_idx = None
        for idx in range(4):
            d_idx = f"d{idx}"
            if self.state.audio[d_idx]["assignment"] == self.SPOT_ID:
                break
        if d_idx is None:
            print("NO SPOTIFY DIAL FOUND")
            return
        
        step = abs(val * 0.02)
        nonzero_vol = self.state.audio[d_idx]["nonzero_vol"] * 0.01

        if type == "toggle_mute":
            match(self.state.audio[d_idx]["mute"]):
                case False:
                    subprocess.run(["playerctl", "--player=spotify", "volume", "0"])
                case True:
                    if(self.state.audio[d_idx]["nonzero_vol"] < 10): subprocess.run(["playerctl", "--player=spotify", "volume", f"{0.1}"])
                    else:                                            subprocess.run(["playerctl", "--player=spotify", "volume", f"{nonzero_vol}"])
        elif type == "volume":
            if val > 0:
                if self.state.audio[d_idx]["mute"] == True:
                    if(self.state.audio[d_idx]["nonzero_vol"] < 10): subprocess.run(["playerctl", "--player=spotify", "volume", f"{0.1}"])
                    else:                                            subprocess.run(["playerctl", "--player=spotify", "volume", f"{nonzero_vol}"])
                else:
                    subprocess.run(["playerctl", "--player=spotify", "volume", f"{step}+"])
            else:
                subprocess.run(["playerctl", "--player=spotify", "volume", f"{step}-"])
        else:
            print("UNKNOWN AUDIO SPOTIFY COMMAND")

    def app_update(self, type, val, app_name):
        if (app_name == "Spotify") or (app_name == self.SPOT_ID):
            self.spotify_update(type, val)
        elif app_name == None:
            print("DIAL APP NOT BOUND")
        else:
            #print("UPDATE APP ", app_name, "val = ", val)
            for item in self.control.sink_input_list():
                id = item.index
                if id == app_name:
                    current = int(item.volume.value_flat * 100)
                    new_volume = max(0, min(100, current + val))
                    self.control.volume_set_all_chans(item, new_volume / 100.0)
                    return
            print(f"DIAL APP ID {app_name} NOT FOUND")

    def _update_spotify_id(self):
        # find spotify pid
        self.SPOT_ID = None
        for item in self.control.sink_input_list():
            name = item.proplist.get("application.name","Unknown",)
            id = item.index
            if name == "Spotify":
                self.SPOT_ID = id
                if self.state.DEBUG: print(f"SPOTIFY ID: {self.SPOT_ID}")
                # TODO: hardcoded to dial 3 for now
                self.state.audio["d3"] = {
                    "assignment": id,
                    "vol": 50,
                    "nonzero_vol": 50,
                    "mute": 0,
                }
                self.update_inputs(self.control)
                self.state.render_queue.put("audio_touchbar")
                return
        if self.state.DEBUG: print(f"SPOTIFY ID COULD NOT BE FOUND")

    def process_commands(self):
        while not self.audio_queue.empty():
            command, type, value, app_name = self.audio_queue.get()
            if command == "sink_update":
                self.sink_update(type, value)
            elif command == "source_update":
                self.source_update(type, value)
            elif command == "app_update":
                self.app_update(type, value, app_name)
            elif command == "dial_bind":
                self.rotate_dial_bind(value)
            elif command == "update_spotify_id":
                self._update_spotify_id()
            else:
                print("UNKNOWN AUDIO COMMAND: ", command)


    ####################################################
    # Streamdeck Util
    ####################################################
    def validate_dial_bind(self, dial):
        d_idx = f"d{dial}"
        #print("validating ", d_idx)
        binded_app = self.state.audio[d_idx]["assignment"]

        if binded_app is None: return
        
        for app in self.available_apps:
            if binded_app == app:
                #print(f"APP {app} still valid")
                return
                
        # Debind since invalid
        if self.state.DEBUG:
            print(f"DIAL {d_idx} binding to app {binded_app} has been broken")
            self.state.audio[d_idx]["assignment"] = None
            self.state.audio_queue.put(("dial_bind", None, 2, None))

    def rotate_dial_bind(self, dial):
        d_idx = f"d{dial}"
        self.bind_idx += 1

        if len(self.available_apps) == 0:
            if self.state.DEBUG: print("NO AVAILABLE APPS TO BIND TO")
            self.state.audio[d_idx]["assignment"] = None
            if self.state.DEBUG: print("\n AUDIO RUNTIME:")
            self.update_inputs(self.control)
            self.state.render_queue.put("audio_touchbar")
            return

        if self.bind_idx >= len(self.available_apps):
            self.bind_idx = 0   # loop back to start of list
        self.state.audio[d_idx]["assignment"] = self.available_apps[self.bind_idx]
        if self.state.DEBUG: print(f"DIAL {dial} has been rotated to ID ",self.state.audio[d_idx]["assignment"])
        if self.state.DEBUG: print("\n AUDIO RUNTIME:")
        self.update_inputs(self.control)
        self.state.render_queue.put("audio_touchbar")

    def init_dials(self, assigns=None):
        if assigns is None:
            assigns = {}
        for idx in range(4):
            d_idx = f"d{idx}"
            self.state.audio[d_idx] = {
                "assignment": assigns.get(idx),
                "vol": 50,
                "nonzero_vol": 50,
                "mute": 0,
                "app_name": None,
                "media_name": None,
            }
        if self.state.DEBUG: print(self.state.audio)