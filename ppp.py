import keyboard
import os
import base64
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from mistralai.client import Mistral
from mistralai.client.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)

import subprocess, sys
import asyncio
import wave

client = Mistral(api_key="mstrl_CGZ1BzrDG2cnmZsNyh5937Hvxikgn8IA_2ABWBD")
SAMPLE_RATE = 16000
CHUNK_MS = 100

async def mic_chunks(stop_event):
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes] = asyncio.Queue()

    def callback(indata, frames, time_info, status):
        loop.call_soon_threadsafe(queue.put_nowait, indata.tobytes())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=int(SAMPLE_RATE * CHUNK_MS / 1000),
        callback=callback,
    ):
        while not stop_event.is_set():
            try:
                yield await asyncio.wait_for(queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue


async def main(qui_parle):
    input(f"\nAppuyez sur Entrée pour parler ({qui_parle})")
    
    # Crée un signal d'arrêt déclenché par la prochaine touche Entrée
    stop_event = asyncio.Event()
    async def attendre_arret():
        await asyncio.to_thread(input)
        stop_event.set()

    asyncio.create_task(attendre_arret())
    print(f"{qui_parle} (Entrée pour arrêter) : ", end="", flush=True)

    texte_final = ""
    async for event in client.audio.realtime.transcribe_stream(
        mic_chunks(stop_event),
        model="voxtral-mini-transcribe-realtime-3",
        audio_format=AudioFormat(encoding="pcm_s16le", sample_rate=SAMPLE_RATE),
    ):
        if isinstance(event, TranscriptionStreamTextDelta):
            print(event.text, end="", flush=True)
            texte_final += event.text
        elif isinstance(event, RealtimeTranscriptionError):
            print(f"\nError: {event.error.message}")

    print()  # Saut de ligne propre à la fin
    return texte_final.strip()


def enregistrement(qui_parle):
    return asyncio.run(main(qui_parle))

while True :

    #Speech to text victime

    text_victime_original = enregistrement("victime")

    #Traduction LLM

    trad_fr = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": "Tu es un traducteur. Traduis en français sans commentaire."},
            {"role": "user", "content": text_victime_original}
        ]
    )
    texte_fr = trad_fr.choices[0].message.content
    print("Traduction :", texte_fr)

    #Text to speech victime

    audio_fr = client.audio.speech.complete(
        model="voxtral-mini-tts-3",
        input=texte_fr,
        voice_id="voice_3137",
        response_format="mp3",
        stream=False,
    )
    with open("pour_med.mp3", "wb") as f:
        f.write(base64.b64decode(audio_fr.audio_data))
    os.startfile("pour_med.mp3")
    
    #Speech to text med

    text_med = enregistrement("medecin")

    #Traduction LLM

    detect_langue = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": "Réponds uniquement par le code de la langue du texte (ex: en, fr, de, ). Un seul mot, sans ponctuation."},
            {"role": "user", "content": text_med}
        ]
    )
    langue_victime = detect_langue.choices[0].message.content.strip()
    trad_pour_inconnu = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "user", "content": text_med},
            {"role": "system","content": f"Tu es un traducteur. Traduis le texte de l'utilisateur en la langue dont le code est {langue_victime}. Ne renvoie que la traduction, sans commentaire."}
        ]
    )
    texte_victime = trad_pour_inconnu.choices[0].message.content
    print("Traduction (victime) :", texte_victime)

    #Text to speech med

    audio_etranger = client.audio.speech.complete(
        model="voxtral-mini-tts-3",
        input=texte_victime,
        voice_id="voice_3150",
        response_format="mp3",
        stream=False,
    )

    # Filter by language and gender
    page = client.audio.voices.search(
        language=[langue_victime],
        )
    id_v=(page.result.data[0]).id
    
    audio_etranger = client.audio.speech.complete(
        model="voxtral-mini-tts-3",
        input=texte_victime,
        voice_id=id_v,
        response_format="mp3",
        stream=False,
    )
    
    
    with open("pour_victime.mp3", "wb") as f:
        f.write(base64.b64decode(audio_etranger.audio_data))
    os.startfile("pour_victime.mp3")
