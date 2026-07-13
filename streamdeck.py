import threading
from queue import Queue

from StreamDeck.DeviceManager import DeviceManager

from audio_handler import AudioHandler
from spotify_handler import SpotifyHandler
from clock_handler import ClockHandler
from input_handler import InputHandler
from renderer import Renderer


class AppState:
    def __init__(self):
        self.lock = threading.Lock()
        self.render_queue = Queue()
        self.audio_queue = Queue()
        self.audio = {}
        self.spotify = {
            "title": "",
            "artist": "",
            "album": "",
            "art_url": "",
            "cover": None,
            "status": "",
        }
        self.DEBUG = True


def main():

    decks = DeviceManager().enumerate()
    print("Found {} Stream Deck(s).\n".format(len(decks)))

    if not decks:
        print("No StreamDeck found")
        return

    deck = decks[0]

    if deck.DECK_TYPE != 'Stream Deck +':
        print(deck.DECK_TYPE)
        print("Sorry, this example only works with Stream Deck +")
    
    deck.open()
    deck.set_brightness(100)
    deck.reset()

    state = AppState()
    renderer = Renderer(deck, state)

    audio = AudioHandler(state, renderer)
    spotify = SpotifyHandler(state, renderer)
    clock = ClockHandler(state)
    controller = InputHandler(deck, state, renderer)

    threading.Thread(target=audio.run, daemon=True).start()
    threading.Thread(target=spotify.run, daemon=True).start()
    threading.Thread(target=clock.run, daemon=True).start()
    threading.Thread(target=controller.run, daemon=True).start()

    try:
        while True:
            request = state.render_queue.get()
            if request == "spotify_cover":
                renderer.draw_spot_cover()
            elif request == "clear_spotify_cover":
                renderer.clear_spot_cover()
            elif request == "audio_touchbar":
                renderer.render_audio()
            elif request == "rend_touch_bck":
                renderer.render()
            # BUTTONS
            elif request == "clock":
                renderer.draw_button_3()
            elif request == "button_2":
                renderer.draw_button_2()
            elif request == "button_6":
                renderer.draw_button_6()
            elif request == "button_7":
                renderer.draw_button_7()
            else:
                renderer.render()

    except KeyboardInterrupt:
        print("Shutting down...")
        pass

    deck.reset()
    deck.set_brightness(0)
    deck.close()



if __name__ == "__main__":
    main()