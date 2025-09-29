import binascii
import hashlib
import json
import time

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes


class XPFFHeaderGenerator:
    def __init__(self, base_key: str = None, user_agent: str = None):
        if base_key is None:
            base_key = "0e6be1f1e21ffc33590b888fd4dc81b19713e570e805d4e5df80a493c9571a05"
        if user_agent is None:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        self.base_key = base_key
        self.user_agent = user_agent

    def _derive_xpff_key(self, guest_id: str) -> bytes:
        combined = self.base_key + guest_id
        return hashlib.sha256(combined.encode()).digest()

    def generate_xpff(self, plaintext: str, guest_id: str) -> str:
        key = self._derive_xpff_key(guest_id)
        nonce = get_random_bytes(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())
        return binascii.hexlify(nonce + ciphertext + tag).decode()

    def decode_xpff(self, hex_string: str, guest_id: str) -> str:
        key = self._derive_xpff_key(guest_id)
        raw = binascii.unhexlify(hex_string)
        nonce = raw[:12]
        ciphertext = raw[12:-16]
        tag = raw[-16:]
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode()

    def gen(self, guest_id: str) -> str:
        xpff_plain = {"navigator_properties":
                          {"hasBeenActive": "true",
                           "userAgent": self.user_agent,
                           "webdriver": "false"}, "created_at": int(time.time() * 1000)
                      }
        xpff_plain = json.dumps(xpff_plain, ensure_ascii=False, separators=(',', ':'))
        return self.generate_xpff(xpff_plain, guest_id)


if __name__ == '__main__':
    xpff = XPFFHeaderGenerator()
    guest_id = "v1%3A175609135281804827"
    encrypted = xpff.gen(guest_id)
    print("Encrypted:", encrypted)

    # encrypted = 'a2e0452fc76227e05279535183552c7ccde9fa676a8c256d7e6fe42e8f3280656886a8b74e94a59f5a09909849baeecfecf4a9ade46fa2a5223b4e4ba4c53f7a5060d0b0f31af51bae8eebd8d07efb937117274cce02f217b4b15a9febd77de278ac023ed7a99e834de4bc6ac7bca3c3ac5dfda41fe3e3be72e5ff090cc5dd73b7d9ba942da0af7462d074fa800380f88ac3d332f41d7aecc4b2355ee0c5bd87d560c447f66b143430edc58e26afab0c6bd1a7db71a7d6d01aa4959891dc28041b639fd7613b499526f41ea1bdefc1c748fc7a04c2a6b5900553d2ed3a69743ef52c5365f0ceee98efea5d4d3b62a7aadf156d322d295d7e9ed7c419118b6ebf8e'

    # decrypted = xpff_gen.decode_xpff(encrypted, guest_id)
    # print("Decrypted:", decrypted)
