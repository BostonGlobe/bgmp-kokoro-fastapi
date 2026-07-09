import base64
import json

import pydub
import requests


def generate_audio_from_phonemes(phonemes: str, voice: str = "af_bella"):
    """Generate audio from phonemes"""
    response = requests.post(
        "http://localhost:8880/dev/generate_from_phonemes",
        json={"phonemes": phonemes, "voice": voice},
        headers={"Accept": "audio/wav"},
    )
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None
    return response.content


with open(f"outputnostreammoney.wav", "wb") as f:
    f.write(
        generate_audio_from_phonemes(
            r"mɪsəki ɪz ɐn ɪkspˌɛɹəmˈɛntᵊl ʤˈitəpˈi ˈɛnʤən dəzˈInd tə pˈWəɹ fjˈuʧəɹ vˈɜɹʒənz ʌv kəkˈɔɹO mˈɑdᵊlz."
        )
    )
