import asyncio
import io
import threading
from queue import Queue
import urllib.request

from PIL import Image
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType

SPOTIFY_SERVICE = "org.mpris.MediaPlayer2.spotify"
SPOTIFY_PATH = "/org/mpris/MediaPlayer2"

PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"

class SpotifyHandler:

    def __init__(self, state, renderer):
        self.state = state
        self.renderer = renderer

        self.bus = None
        self.spotify_props = None
        self.connected = False

    ####################################################################
    # Public entry point
    ####################################################################

    def run(self):
        asyncio.run(self._main())

    async def _main(self):

        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        await self._watch_name_changes()
        await self._try_connect()
        # Stay alive forever waiting for DBus callbacks.
        await asyncio.Future()

    ####################################################################
    # Watch Spotify appearing/disappearing
    ####################################################################

    async def _watch_name_changes(self):

        intro = await self.bus.introspect("org.freedesktop.DBus","/org/freedesktop/DBus",)
        obj = self.bus.get_proxy_object("org.freedesktop.DBus","/org/freedesktop/DBus",intro,)
        dbus = obj.get_interface("org.freedesktop.DBus")
        dbus.on_name_owner_changed(self._name_owner_changed)

    def _name_owner_changed(self,name,old_owner,new_owner,):

        if name != SPOTIFY_SERVICE:
            return

        if new_owner:
            print("Spotify started")
            asyncio.create_task(self._try_connect())

        else:
            print("Spotify closed")
            self.connected = False
            self.spotify_props = None
            self.state.spotify = {}
            self.state.render_queue.put("button_7")
            self.state.render_queue.put("clear_spotify_cover")

    ####################################################################
    # Connect to Spotify
    ####################################################################

    async def _try_connect(self):

        if self.connected:
            return

        try:
            intro = await self.bus.introspect(SPOTIFY_SERVICE,SPOTIFY_PATH,)
        except Exception:
            return

        obj = self.bus.get_proxy_object(SPOTIFY_SERVICE,SPOTIFY_PATH,intro,)
        self.spotify_props = obj.get_interface(PROPERTIES_INTERFACE)
        self.spotify_props.on_properties_changed(self._properties_changed)
        self.connected = True

        print("Connected to Spotify")
        await self._read_initial_state()

    ####################################################################
    # Read current values once after connecting
    ####################################################################

    async def _read_initial_state(self):

        metadata = await self.spotify_props.call_get(PLAYER_INTERFACE,"Metadata",)
        playback = await self.spotify_props.call_get(PLAYER_INTERFACE,"PlaybackStatus",)
        self._update_state(metadata.value,playback.value,)

    ####################################################################
    # DBus callback
    ####################################################################

    def _properties_changed(self,interface_name,changed,invalidated,):

        if interface_name != PLAYER_INTERFACE:
            return

        metadata = None
        playback = None

        if "Metadata" in changed:
            metadata = changed["Metadata"].value

        if "PlaybackStatus" in changed:
            playback = changed["PlaybackStatus"].value

        self._update_state(metadata,playback,)

    ####################################################################
    # Helpers
    ####################################################################

    def _metadata_value(self,metadata,key,default=None,):
        """
        MPRIS metadata is:
            Variant(a{sv})
                -> dict[str, Variant]

        This unwraps the inner Variant.
        """

        value = metadata.get(key)

        if value is None:
            return default

        return value.value

    ####################################################################
    # Cover image handler
    ####################################################################

    def _download_cover(self, url):
        
        #print("DOWNLOADING COVER:", url)

        if not url:
            return None

        try:
            with urllib.request.urlopen(url,timeout=5) as response:
                data = response.read()
            image = Image.open(io.BytesIO(data))
            #image.show()
            return image.convert("RGB")

        except Exception as e:
            print(f"Cover download failed: {e}")
            return None

    ####################################################################
    # Shared state update
    ####################################################################

    def _update_state(self, metadata=None, playback=None,):

        spotify = self.state.spotify

        if metadata is not None:
            spotify["title"] = self._metadata_value(metadata, "xesam:title", "",)
            spotify["artist"] = ", ".join(self._metadata_value(metadata,"xesam:artist",[],))
            spotify["album"] = self._metadata_value(metadata,"xesam:album","",)
            spotify["length"] = self._metadata_value(metadata,"mpris:length",0,)
            old_art_url = spotify.get("art_url")
            art_url = self._metadata_value(metadata,"mpris:artUrl","",)
            if art_url != old_art_url:
                spotify["art_url"] = art_url
                spotify["cover"] = (self._download_cover(art_url))

        if playback is not None:
            spotify["status"] = playback
            self.state.render_queue.put("button_7")

        if metadata is not None:
            print(f"SPOTIFY: New Track - {spotify["title"]} --- {spotify["artist"]}")
            self.state.render_queue.put("spotify_cover")
             #TODO: lock?