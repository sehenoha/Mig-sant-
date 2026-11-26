#$env:SSL_CERT_FILE = ""

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

FREQUENCE = 16000


async def _ecouter_en_direct(nom_fichier, frequence=FREQUENCE):
    """Diffuse le micro en direct vers Voxtral realtime.
    Affiche la transcription au fil de l'eau, s'arrête quand on appuie sur Entrée,
    et renvoie (texte_final, langue_detectee)."""
    loop = asyncio.get_running_loop()
    file_audio = asyncio.Queue()
    audio_data = []

    # Callback appelé par sounddevice dans un autre thread : on transfère
    # les blocs vers la boucle asyncio de façon thread-safe.
    def callback(indata, frames, time, status):
        audio_data.append(indata.copy())
        loop.call_soon_threadsafe(file_audio.put_nowait, indata.tobytes())

    async def flux_micro():
        while True:
            bloc = await file_audio.get()
            if bloc is None:  # fin de l'enregistrement
                return
            yield bloc

    async def attendre_entree():
        await loop.run_in_executor(None, input)
        loop.call_soon_threadsafe(file_audio.put_nowait, None)

    texte_partiel = []
    texte_final, langue = None, None

    with sd.InputStream(samplerate=frequence, channels=1, dtype="int16",
                        blocksize=frequence // 10, callback=callback):
        print("🎙️  Parlez... (Entrée pour arrêter)")
        arret = asyncio.create_task(attendre_entree())
        try:
            async for event in client.audio.realtime.transcribe_stream(
                audio_stream=flux_micro(),
                model="voxtral-mini-transcribe-realtime-3",
                audio_format=AudioFormat(encoding="pcm_s16le", sample_rate=frequence),
            ):
                if isinstance(event, TranscriptionStreamTextDelta):
                    texte_partiel.append(event.text)
                    print(event.text, end="", flush=True)
                elif isinstance(event, TranscriptionStreamDone):
                    texte_final, langue = event.text, event.language
                elif isinstance(event, RealtimeTranscriptionError):
                    print(f"\nErreur realtime : {event.error.message}")
        finally:
            if not arret.done():
                # le flux s'est terminé avant Entrée : on attend quand même l'appui
                await arret
    print()

    if audio_data:
        write(nom_fichier, frequence, np.concatenate(audio_data, axis=0))

    if not texte_final:
        texte_final = "".join(texte_partiel)
    return texte_final.strip(), langue


def enregistrer_micro(nom_fichier, frequence=FREQUENCE):
    input("Appuyez sur Entrée pour commencer à parler...")
    return asyncio.run(_ecouter_en_direct(nom_fichier, frequence))



while True:

    #Speech to text victime
    texte_victime_src, langue_detectee = enregistrer_micro("victime.wav")
    if not texte_victime_src:
        print("(rien entendu, on recommence)")
        continue
    print("Victime :", texte_victime_src)

    #Traduction LLM

    trad_fr = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": "Tu es un traducteur. Traduis en français sans commentaire."},
            {"role": "user", "content": texte_victime_src}
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
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.call([opener, "pour_med.mp3"])
    
    #Speech to text med (en direct)

    texte_med, _ = enregistrer_micro("med.wav")
    if not texte_med:
        print("(rien entendu, on recommence)")
        continue
    print("Médecin :", texte_med)

    #Traduction LLM

    detect_langue = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": "Réponds uniquement par le code de la langue du texte (ex: en, fr, de, ). Un seul mot, sans ponctuation."},
            {"role": "user", "content": texte_victime_src}
        ]
    )
    langue_victime = detect_langue.choices[0].message.content.strip()
    trad_pour_inconnu = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "user", "content": texte_med},{
                "role": "system",
                "content": f"Tu es un traducteur. Traduis le texte de l'utilisateur en la langue dont le code est {langue_victime}. Ne renvoie que la traduction, sans commentaire."
            },
        ]
    )
    texte_victime = trad_pour_inconnu.choices[0].message.content
    print("Traduction (victime) :", texte_victime)

    #Text to speech med

    # Voix adaptée à la langue de la victime (voice_3150 par défaut)
    id_v = "voice_3150"
    try:
        page = client.audio.voices.search(language=[langue_victime])
        if page.result.data:
            id_v = page.result.data[0].id
    except Exception as e:
        print("Recherche de voix impossible :", e)

    audio_etranger = client.audio.speech.complete(
        model="voxtral-mini-tts-3",
        input=texte_victime,
        voice_id=id_v,
        response_format="mp3",
        stream=False,
    )
    
    
    with open("pour_victime.mp3", "wb") as f:
        f.write(base64.b64decode(audio_etranger.audio_data))
    
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.call([opener, "pour_victime.mp3"])



