import keyboard
import asyncio
import sounddevice as sd
from mistralai.client import Mistral
from mistralai.client.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)

SAMPLE_RATE = 16000
CHUNK_MS = 100 
client = Mistral(api_key="mstrl_CGZ1BzrDG2cnmZsNyh5937Hvxikgn8IA_2ABWBD")


async def mic_chunks():
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
        while not keyboard.is_pressed("esc"):
            yield await queue.get()


async def main():
    input("Appuyez sur Entrée pour parler")
    texte_final = "" 
    
    async for event in client.audio.realtime.transcribe_stream(
        mic_chunks(),
        model="voxtral-mini-transcribe-realtime-3",
        audio_format=AudioFormat(encoding="pcm_s16le", sample_rate=SAMPLE_RATE),
    ):
        if isinstance(event, TranscriptionStreamTextDelta):
            print(event.text, end="", flush=True)
            texte_final += event.text
        elif isinstance(event, TranscriptionStreamDone):
            print(f"\n\nFinal transcript: {event.text}")
        elif isinstance(event, RealtimeTranscriptionError):
            print(f"\nError: {event.error.message}")


asyncio.run(main()) 

