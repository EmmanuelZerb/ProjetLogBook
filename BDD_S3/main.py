import asyncio
import base64
import json
import pyaudio
import websockets
from websockets.server import serve
import requests
import os
from dotenv import load_dotenv
from supabase import create_client
import wave
import io
import time
from urllib.parse import parse_qs, urlparse

# Chargement des variables d'environnement
load_dotenv()

# Configuration Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# Configuration Audio
CHANNELS = 1
FORMAT = pyaudio.paInt16
FRAMES_PER_BUFFER = 3200
SAMPLE_RATE = 16_000
P = pyaudio.PyAudio()

# Configuration Gladia
GLADIA_API_URL = "https://api.gladia.io"
GLADIA_API_KEY = os.getenv("GLADIA_API_KEY")

# Variable globale pour stocker les chunks audio
audio_chunks = []

def init_gladia_session():
    config = {
        "encoding": "wav/pcm",
        "sample_rate": SAMPLE_RATE,
        "bit_depth": 16,
        "channels": CHANNELS,
        "language_config": {
            "languages": [],
            "code_switching": True,
        }
    }
    
    response = requests.post(
        f"{GLADIA_API_URL}/v2/live",
        headers={"X-Gladia-Key": GLADIA_API_KEY},
        json=config,
        timeout=3,
    )
    return response.json()

async def verify_user(user_id, token):
    """Vérifier l'authentification de l'utilisateur via Supabase"""
    try:
        # Vérifier le token côté serveur
        user_response = supabase.auth.get_user(token)
        
        # Vérifier que l'ID utilisateur correspond
        if user_response and hasattr(user_response, 'user') and user_response.user.id == user_id:
            return True
        return False
    except Exception as e:
        print(f"Erreur de vérification : {e}")
        return False

async def handle_websocket(websocket):
    # Récupérer l'ID utilisateur et le token de l'URL
    query = urlparse(websocket.path).query
    params = parse_qs(query)
    user_id = params.get('userId', [None])[0]
    token = params.get('token', [None])[0]

    if not user_id or not token:
        await websocket.close(1008, "User ID et token requis")
        return

    # Vérifier l'authentification
    is_authenticated = await verify_user(user_id, token)
    if not is_authenticated:
        await websocket.close(1008, "Authentification échouée")
        return

    print(f"Nouvelle connexion client établie pour l'utilisateur {user_id}")
    
    gladia_session = init_gladia_session()
    print("Session Gladia initialisée")
    
    async with websockets.connect(gladia_session["url"]) as gladia_ws:
        stream = P.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=FRAMES_PER_BUFFER,
        )
        print("Flux audio ouvert")
        
        try:
            global audio_chunks
            audio_chunks = []  # Réinitialiser pour chaque nouvelle session
            transcription_text = ""

            async def send_audio():
                while True:
                    data = stream.read(FRAMES_PER_BUFFER)
                    audio_chunks.append(data)  # Stocker chaque chunk
                    audio_b64 = base64.b64encode(data).decode("utf-8")                   
                    await gladia_ws.send(json.dumps({
                        "type": "audio_chunk",
                        "data": {"chunk": audio_b64}
                    }))
                    await asyncio.sleep(0.1)
            
            async def receive_transcripts():
                nonlocal transcription_text
                while True:
                    msg = await gladia_ws.recv()
                    msg_data = json.loads(msg)
                    if msg_data["type"] == "transcript" and msg_data["data"]["is_final"]:
                        transcription_text += msg_data["data"]["utterance"]["text"].strip() + " "
                    await websocket.send(msg)
            
            try:
                await asyncio.gather(send_audio(), receive_transcripts())
            except websockets.exceptions.ConnectionClosed:
                # Sauvegarder l'audio et la transcription
                timestamp = int(time.time())
                
                # Sauvegarde du fichier WAV
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wav_file:
                    wav_file.setnchannels(CHANNELS)
                    wav_file.setsampwidth(P.get_sample_size(FORMAT))
                    wav_file.setframerate(SAMPLE_RATE)
                    wav_file.writeframes(b''.join(audio_chunks))
                
                # Upload vers Supabase avec l'ID utilisateur dans le chemin
                audio_path = f"audio/{user_id}/recording_{timestamp}.wav"
                text_path = f"text/{user_id}/transcript_{timestamp}.txt"
                
                try:
                    # Upload audio
                    print("Tentative d'upload audio...")
                    result_audio = supabase.storage.from_("recordings").upload(
                        path=audio_path,
                        file=wav_buffer.getvalue(),
                        file_options={"content-type": "audio/wav"}
                    )
                    print("Résultat upload audio:", result_audio)
                    
                    # Upload transcription
                    print("Tentative d'upload texte...")
                    result_text = supabase.storage.from_("recordings").upload(
                        path=text_path,
                        file=transcription_text.encode(),
                        file_options={"content-type": "text/plain"}
                    )
                    print("Résultat upload texte:", result_text)
                    
                except Exception as e:
                    print("Erreur lors de l'upload:", str(e))
                
                print(f"Fichiers sauvegardés : {audio_path}, {text_path}")
                
        finally:
            stream.stop_stream()
            stream.close()
            print("Flux audio fermé")

async def main():
    print("Démarrage du serveur WebSocket sur ws://localhost:8765")
    async with serve(handle_websocket, "localhost", 8765):
        print("Serveur prêt")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServeur arrêté")
    finally:
        P.terminate()