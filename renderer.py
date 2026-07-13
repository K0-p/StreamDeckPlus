from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import io

from StreamDeck.ImageHelpers import PILHelper

SPOTIFY_BUTTONS = [0,1,4,5]
TOUCH_IMG_PATH = "assets/touchbar_img.jpg"
BUTTS_IMG_PATH = "assets/buttons_bck.jpg"
TOUCH_BCK_IMG  = Image.open(TOUCH_IMG_PATH).convert("RGB").resize((800, 100))
BUTTS_BCK_IMG  = Image.open(BUTTS_IMG_PATH).convert("RGB")
BUTTON_IMG_ARRAY = []

PLAY_IMG    = Image.open("assets/play.png").convert("RGB").resize((80,80))
PAUSE_IMG   = Image.open("assets/pause.png").convert("RGB").resize((80,80))
NOPLAY_IMG  = Image.open("assets/spotify_disconnect.png").convert("RGB").resize((100,100))

D0_UNMUTE_IMG = Image.open("assets/volume_true.png").convert("RGBA").resize((80,80))
D1_UNMUTE_IMG = Image.open("assets/input_on.png").convert("RGBA").resize((80,80))
D2_UNMUTE_IMG = Image.open("assets/app_vol_true.png").convert("RGBA").resize((50,50))
D3_UNMUTE_IMG = Image.open("assets/music_true.png").convert("RGBA").resize((90,90))

D0_MUTE_IMG   = Image.open("assets/volume_false.png").convert("RGBA").resize((80,80))
D1_MUTE_IMG   = Image.open("assets/input_off.png").convert("RGBA").resize((80,80))
D2_MUTE_IMG   = Image.open("assets/app_vol_false.png").convert("RGBA").resize((50,50))
D3_MUTE_IMG   = Image.open("assets/music_false.png").convert("RGBA").resize((90,90))

TOUCH_MUTE_ICOS      = [D0_MUTE_IMG, D1_MUTE_IMG, D2_MUTE_IMG, D3_MUTE_IMG]
TOUCH_MUTE_ICOS_XY   = [[15, 10], [215, 10], [425, 37], [615, 5]]
TOUCH_UNMUTE_ICOS    = [D0_UNMUTE_IMG, D1_UNMUTE_IMG, D2_UNMUTE_IMG, D3_UNMUTE_IMG]
TOUCH_UNMUTE_ICOS_XY = [[15, 10], [215, 10], [425, 37], [615, 7]]

FONT_PATH = "/usr/share/fonts/methanerse-font/MethanerseFreeTrial-eZX7x.ttf"

class Renderer:

    def __init__(self, deck, state):
        global BUTTON_IMG_ARRAY

        self.deck = deck
        self.state = state
        self.font = ImageFont.truetype(FONT_PATH, 32)

        # Init Buttons Backgrounds for Later Use
        image = BUTTS_BCK_IMG.copy()
        w, h = image.size
        tile_w = w // 4
        tile_h = h // 2
        tiles = []
        for row in range(2):
            for col in range(4):
                left = col * tile_w
                upper = row * tile_h
                right = left + tile_w
                lower = upper + tile_h
                tile = image.crop((left, upper, right, lower))
                tiles.append(tile)
        for i, tile in enumerate(tiles):
            BUTTON_IMG_ARRAY.append(tile)

        self.rend_touch_bck()
        self.rend_buttons_bck()

    def draw_touch_bounds_box(self, draw):
        for i in range(4):
            x0 = i * 200
            x1 = x0 + 199  # stay within the image bounds
            draw.rectangle(
                [(x0, 0), (x1, 99)],
                outline="white",
                width=2
            )

    def draw_touch_test_lines(self, draw):
        for y in range(0, 100, 10):
            draw.line(
                [(0, y), (800, y)],
                fill="white",
                width=1
            )

    def rend_touch_bck(self):
        img  = TOUCH_BCK_IMG.copy()
        draw = ImageDraw.Draw(img)

        #self.draw_touch_test_lines(draw)
        #self.draw_touch_bounds_box(draw)

        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=95)
        self.deck.set_touchscreen_image(buf.getvalue(), 0, 0, 800, 100)

    def render_audio(self):
        img  = TOUCH_BCK_IMG.copy()
        draw = ImageDraw.Draw(img)

        #self.draw_touch_test_lines(draw)
        self.draw_touch_bounds_box(draw)
        for idx in range(4):
            d_idx = f"d{idx}"
            match self.state.audio[d_idx]["mute"]:
                case 0:
                    draw.text((((idx*200) + 175), 30), str(self.state.audio[d_idx]["vol"]), fill="white", font=self.font, anchor="ra")
                    icon = TOUCH_UNMUTE_ICOS[idx].copy()
                    img.paste(icon, (TOUCH_UNMUTE_ICOS_XY[idx][0], TOUCH_UNMUTE_ICOS_XY[idx][1]), icon)
                case _:
                    draw.text((((idx*200) + 175), 30), str(self.state.audio[d_idx]["vol"]), fill="red", font=self.font, anchor="ra")
                    icon = TOUCH_MUTE_ICOS[idx].copy()
                    img.paste(icon, (TOUCH_MUTE_ICOS_XY[idx][0], TOUCH_MUTE_ICOS_XY[idx][1]), icon)
            if idx == 2:
                text = self.state.audio[d_idx]["assignment"]
                if text is not None:
                    if draw.textbbox((0, 0), text + "...", font=ImageFont.truetype(FONT_PATH, 20))[2] > 170:
                        while draw.textbbox((0, 0), text + "...", font=ImageFont.truetype(FONT_PATH, 20))[2] > 170:
                            text = text[:-1]
                        text = text + "..."
                    draw.text(((420), 3), text, fill="white", font = ImageFont.truetype(FONT_PATH, 20), anchor="la")

        #print(dial_audio)

        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=95)
        self.deck.set_touchscreen_image(buf.getvalue(), 0, 0, 800, 100)
    
    def draw_spot_cover(self):
        global SPOTIFY_BUTTONS

        cover = self.state.spotify.get("cover")
        if cover is None:
            return self.draw_button("Spotify")

        image = cover.copy()
        w, h = image.size
        half_w, half_h = w // 2, h // 2
        quads = [
            image.crop((0, 0, half_w, half_h)),          # top-left
            image.crop((half_w, 0, w, half_h)),          # top-right
            image.crop((0, half_h, half_w, h)),          # bottom-left
            image.crop((half_w, half_h, w, h)),          # bottom-right
        ]
        for i, quad in enumerate(quads):
            key_img = PILHelper.to_native_format(self.deck, quad)
            self.deck.set_key_image(SPOTIFY_BUTTONS[i], key_img)

    def clear_spot_cover(self):
        for button in SPOTIFY_BUTTONS:
            butt = BUTTON_IMG_ARRAY[button]
            img = butt.copy()
            native = PILHelper.to_native_format(self.deck, PILHelper.create_scaled_image(self.deck, img))
            self.deck.set_key_image(button, native)

    def rend_buttons_bck(self):
        for b_idx, butt in enumerate(BUTTON_IMG_ARRAY):
            img = butt.copy()
            native = PILHelper.to_native_format(self.deck, PILHelper.create_scaled_image(self.deck, img))
            self.deck.set_key_image(b_idx, native)

    def draw_button_7(self):
        img = BUTTON_IMG_ARRAY[7].copy()

        playback = self.state.spotify.get("status")
        if playback == "Paused":
            overlay = PLAY_IMG.copy()
        elif playback == "Playing":
            overlay = PAUSE_IMG.copy()
        else:
            overlay = NOPLAY_IMG.copy()
        
        x = (img.width - overlay.width) // 2
        y = (img.height - overlay.height) // 2
        img.paste(overlay, (x, y))
        
        native = PILHelper.to_native_format(self.deck, PILHelper.create_scaled_image(self.deck, img))
        self.deck.set_key_image(7, native)

    def render(self):
        print('test render function - hi :)')