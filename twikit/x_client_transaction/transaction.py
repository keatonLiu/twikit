import asyncio
import base64
import hashlib
import math
import random
import re
import time
from functools import reduce, lru_cache

from .cubic_curve import Cubic
from .interpolate import interpolate
from .rotation import convert_rotation_to_matrix
from .utils import float_to_hex, is_odd, base64_encode, handle_x_migration

ON_DEMAND_FILE_REGEX: re.Pattern = re.compile(
    r""",(\d+):["']ondemand\.s["']""", flags=(re.VERBOSE | re.MULTILINE))

INDICES_REGEX = re.compile(
    r"""(\(\w\[(\d{1,2})],\s*16\))+""", flags=(re.VERBOSE | re.MULTILINE))
ON_DEMAND_FILE_URL: str = "https://abs.twimg.com/responsive-web/client-web/ondemand.s.{filename}a.js"


class ClientTransaction:
    ADDITIONAL_RANDOM_NUMBER = 3
    DEFAULT_KEYWORD = "obfiowerehiring"
    DEFAULT_ROW_INDEX = None
    DEFAULT_KEY_BYTES_INDICES = None

    def __init__(self):
        self.home_page_response = None
        self.__inited = False
        self.init_lock = asyncio.Lock()
        self.session = None
        self.headers = {}
        self._key_bytes_cache = None
        self._animation_key_cache = None

    async def is_inited(self):
        async with self.init_lock:
            return self.__inited

    async def init(self, session, headers):
        self.session = session
        self.headers = headers
        self.home_page_response = await handle_x_migration(session, headers)
        self.DEFAULT_ROW_INDEX, self.DEFAULT_KEY_BYTES_INDICES = await self.get_indices()
        self.__inited = True

    async def get_indices(self):
        key_byte_indices = []
        on_demand_file_index = ON_DEMAND_FILE_REGEX.search(str(self.home_page_response)).group(1)
        regex = re.compile(
            rf',{on_demand_file_index}:\"(?!.*ondemand\.s)(.*?)\"'
        )
        filename = regex.search(str(self.home_page_response)).group(1)
        file_url = ON_DEMAND_FILE_URL.format(filename=filename)
        on_demand_file_response = await self.session.request(method="GET", url=file_url, headers=self.headers)
        on_demand_file_response_text = on_demand_file_response.text
        key_byte_indices_match = INDICES_REGEX.finditer(
            str(on_demand_file_response.text))
        for item in key_byte_indices_match:
            key_byte_indices.append(item.group(2))
        if not key_byte_indices:
            raise Exception(f"Couldn't get KEY_BYTE indices: {on_demand_file_response_text}")
        key_byte_indices = list(map(int, key_byte_indices))
        return key_byte_indices[0], key_byte_indices[1:]

    @property
    @lru_cache()
    def key(self):
        # <meta name="twitter-site-verification" content="mentU...+1yPz..../IcNS+......./RaF...R+b"/>
        element = self.home_page_response.select_one("[name='twitter-site-verification']")
        if not element:
            raise Exception("Couldn't get key from the page source")
        return element.get("content")

    @property
    def key_bytes(self):
        if self._key_bytes_cache is not None:
            return self._key_bytes_cache
        return list(base64.b64decode(bytes(self.key, 'utf-8')))

    @property
    @lru_cache()
    def frames(self):
        # loading-x-anim-0...loading-x-anim-3
        return self.home_page_response.select("[id^='loading-x-anim']")

    @property
    @lru_cache()
    def _2d_array(self):
        # return list(list(frames[key[5] % 4].children)[0].children)[1].get("d")[9:].split("C")
        return [[int(x) for x in re.sub(r"[^\d]+", " ", item).strip().split()] for item in
                list(list(self.frames[self.key_bytes[5] % 4].children)[0].children)[1].get("d")[9:].split("C")]

    def solve(self, value, min_val, max_val, rounding: bool):
        result = value * (max_val - min_val) / 255 + min_val
        return math.floor(result) if rounding else round(result, 2)

    def animate(self, frames, target_time):
        # from_color = f"#{''.join(['{:x}'.format(digit) for digit in frames[:3]])}"
        # to_color = f"#{''.join(['{:x}'.format(digit) for digit in frames[3:6]])}"
        # from_rotation = "rotate(0deg)"
        # to_rotation = f"rotate({solve(frames[6], 60, 360, True)}deg)"
        # easing_values = [solve(value, -1 if count % 2 else 0, 1, False)
        #                  for count, value in enumerate(frames[7:])]
        # easing = f"cubic-bezier({','.join([str(value) for value in easing_values])})"
        # current_time = round(target_time / 10) * 10

        from_color = [float(item) for item in [*frames[:3], 1]]
        to_color = [float(item) for item in [*frames[3:6], 1]]
        from_rotation = [0.0]
        to_rotation = [self.solve(float(frames[6]), 60.0, 360.0, True)]
        frames = frames[7:]
        curves = [self.solve(float(item), is_odd(counter), 1.0, False)
                  for counter, item in enumerate(frames)]
        cubic = Cubic(curves)
        val = cubic.get_value(target_time)
        color = interpolate(from_color, to_color, val)
        color = [value if value > 0 else 0 for value in color]
        rotation = interpolate(from_rotation, to_rotation, val)
        matrix = convert_rotation_to_matrix(rotation[0])
        # str_arr = [format(int(round(color[i])), '02x') for i in range(len(color) - 1)]
        # str_arr = [format(int(round(color[i])), 'x') for i in range(len(color) - 1)]
        str_arr = [format(round(value), 'x') for value in color[:-1]]
        for value in matrix:
            rounded = round(value, 2)
            if rounded < 0:
                rounded = -rounded
            hex_value = float_to_hex(rounded)
            str_arr.append(f"0{hex_value}".lower() if hex_value.startswith(
                ".") else hex_value if hex_value else '0')
        str_arr.extend(["0", "0"])
        animation_key = re.sub(r"[.-]", "", "".join(str_arr))
        return animation_key

    @property
    def animation_key(self):
        if self._animation_key_cache is not None:
            return self._animation_key_cache
        total_time = 4096
        # row_index, frame_time = [key_bytes[2] % 16, key_bytes[12] % 16 * (key_bytes[14] % 16) * (key_bytes[7] % 16)]
        # row_index, frame_time = [key_bytes[2] % 16, key_bytes[2] % 16 * (key_bytes[42] % 16) * (key_bytes[45] % 16)]

        row_index = self.key_bytes[self.DEFAULT_ROW_INDEX] % 16
        frame_time = reduce(lambda num1, num2: num1 * num2,
                            [self.key_bytes[index] % 16 for index in self.DEFAULT_KEY_BYTES_INDICES])
        frame_time = round(frame_time / 10) * 10
        frame_row = self._2d_array[row_index]

        target_time = float(frame_time) / total_time
        animation_key = self.animate(frame_row, target_time)
        return animation_key

    def to_dict(self) -> dict:
        return {
            "key_bytes": self.key_bytes,
            "animation_key": self.animation_key,
        }

    def from_dict(self, data: dict):
        self._key_bytes_cache = data["key_bytes"]
        self._animation_key_cache = data["animation_key"]
        self.__inited = True

    def generate_transaction_id(self, method: str, path: str, time_now=None):
        time_now = time_now or math.floor(
            (time.time() * 1000 - 1682924400 * 1000) / 1000)
        time_now_bytes = [(time_now >> (i * 8)) & 0xFF for i in range(4)]
        # hash_val = hashlib.sha256(f"{method}!{path}!{time_now}bird{animation_key}".encode()).digest()
        hash_val = hashlib.sha256(
            f"{method}!{path}!{time_now}{self.DEFAULT_KEYWORD}{self.animation_key}".encode()).digest()
        # hash_bytes = [int(hash_val[i]) for i in range(len(hash_val))]
        hash_bytes = list(hash_val)
        random_num = random.randint(0, 255)
        bytes_arr = [*self.key_bytes, *time_now_bytes, *
        hash_bytes[:16], self.ADDITIONAL_RANDOM_NUMBER]
        out = bytearray(
            [random_num, *[item ^ random_num for item in bytes_arr]])
        return base64_encode(out).strip("=")
