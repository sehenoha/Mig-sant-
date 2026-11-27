import asyncio
import os

import sounddevice as sd
from mistralai.client import Mistral
from mistralai.client.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)

SAMPLE_RATE = 16000  # 16 kHz, standard pour la transcription
CHUNK_MS = 40
client = Mistral(api_key="mstrl_CGZ1BzrDG2cnmZsNyh5937Hvxikgn8IA_2ABWBD")

async def mic_chunks():
    queue: asyncio.Queue[bytes] = asyncio.Queue()

    def callback(indata, frames, time_info, status):
        # indata est un buffer numpy int16 (mono) -> on le convertit en bytes
        queue.put_nowait(indata.copy().tobytes())

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16",
        blocksize=int(SAMPLE_RATE * CHUNK_MS / 1000),
        callback=lambda indata, frames, t, status: queue.put_nowait(indata.copy().tobytes()),
    ):
        while True:
            yield await queue.get()

async def main():
    async for event in client.audio.realtime.transcribe_stream(
        mic_chunks(),
        model="voxtral-mini-transcribe-realtime-3",
        audio_format=AudioFormat(encoding="pcm_s16le", sample_rate=SAMPLE_RATE),
    ):
        if isinstance(event, TranscriptionStreamTextDelta):
            print(event.text, end="", flush=True)
        elif isinstance(event, TranscriptionStreamDone):
            print(f"\n\nFinal transcript: {event.text}")
        elif isinstance(event, RealtimeTranscriptionError):
            print(f"\nError: {event.error.message}")

asyncio.run(main())  # Ctrl+C pour arrêter