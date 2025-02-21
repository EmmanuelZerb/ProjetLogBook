import asyncio
import base64
import json
import pyaudio
import websockets
from websockets.server import serve
import requests
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import wave
import io
import time
from urllib.parse import parse_qs, urlparse

# Charger les variables d'environnement
load_dotenv()

# Configuration Supabase
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

# Configuration des paramètres audio
AUDIO_CONFIG = {
    'channels': 1,
    'format': pyaudio.paInt16,
    'frames_per_buffer': 3200,
    'sample_rate': 16_000
}

# Configuration Gladia
GLADIA_API_URL = "https://api.gladia.io"
GLADIA_API_KEY = os.getenv("GLADIA_API_KEY")

def init_gladia_session():
    """
    Initialiser une session de transcription en temps réel avec Gladia.
    
    Returns:
        dict: Informations de session de Gladia
    """
    config = {
        "encoding": "wav/pcm",
        "sample_rate": AUDIO_CONFIG['sample_rate'],
        "bit_depth": 16,
        "channels": AUDIO_CONFIG['channels'],
        "language_config": {
            "languages": [],
            "code_switching": True,
        }
    }
    
    try:
        response = requests.post(
            f"{GLADIA_API_URL}/v2/live",
            headers={"X-Gladia-Key": GLADIA_API_KEY},
            json=config,
            timeout=3,
        )
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Échec de l'initialisation de la session Gladia : {e}")

async def verify_user(user_id, token):
    """
    Vérifier l'authentification de l'utilisateur via Supabase.
    
    Args:
        user_id (str): Identifiant de l'utilisateur
        token (str): Token d'authentification
    
    Returns:
        bool: True si l'authentification est réussie, False sinon
    """
    try:
        # Vérifier le token côté serveur
        user_response = supabase.auth.get_user(token)
        
        # Vérifier que l'ID utilisateur correspond
        return user_response and user_response.user and user_response.user.id == user_id
    except Exception as e:
        print(f"Erreur de vérification : {e}")
        return False

async def handle_websocket(websocket):
    """
    Gérer la connexion WebSocket pour l'enregistrement et la transcription audio.
    
    Args:
        websocket (websockets.WebSocketServerProtocol): Connexion WebSocket entrante
    """
    # Extraire les paramètres de l'URL
    query = urlparse(websocket.path).query
    params = parse_qs(query)
    user_id = params.get('userId', [None])[0]
    token = params.get('token', [None])[0]

    # Vérifier les paramètres d'authentification
    if not user_id or not token:
        await websocket.close(1008, "User ID et token requis")
        return

    # Vérifier l'authentification
    if not await verify_user(user_id, token):
        await websocket.close(1008, "Authentification échouée")
        return

    # Initialiser la session Gladia
    gladia_session = init_gladia_session()

    # Ouvrir la connexion WebSocket avec Gladia
    async with websockets.connect(gladia_session["url"]) as gladia_ws:
        # Préparer le flux audio
        p = pyaudio.PyAudio()
        stream = p.open(
            format=AUDIO_CONFIG['format'],
            channels=AUDIO_CONFIG['channels'],
            rate=AUDIO_CONFIG['sample_rate'],
            input=True,
            frames_per_buffer=AUDIO_CONFIG['frames_per_buffer'],
        )
        
        try:
            audio_chunks = []  # Stocker les chunks audio
            transcription_text = ""

            async def send_audio():
                """Envoyer les chunks audio à Gladia"""
                while True:
                    data = stream.read(AUDIO_CONFIG['frames_per_buffer'])
                    audio_chunks.append(data)  # Stocker chaque chunk
                    audio_b64 = base64.b64encode(data).decode("utf-8")
                    await gladia_ws.send(json.dumps({
                        "type": "audio_chunk",
                        "data": {"chunk": audio_b64}
                    }))
                    await asyncio.sleep(0.1)
            
            async def receive_transcripts():
                """Recevoir et traiter les transcriptions de Gladia"""
                nonlocal transcription_text
                while True:
                    msg = await gladia_ws.recv()
                    msg_data = json.loads(msg)
                    if msg_data["type"] == "transcript" and msg_data["data"]["is_final"]:
                        transcription_text += msg_data["data"]["utterance"]["text"].strip() + " "
                    await websocket.send(msg)
            
            # Exécuter l'envoi audio et la réception de transcriptions
            await asyncio.gather(send_audio(), receive_transcripts())
        
        except websockets.exceptions.ConnectionClosed:
            # Sauvegarder l'audio et la transcription lors de la fermeture de la connexion
            timestamp = int(time.time())
            
            # Créer un fichier WAV en mémoire
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(AUDIO_CONFIG['channels'])
                wav_file.setsampwidth(p.get_sample_size(AUDIO_CONFIG['format']))
                wav_file.setframerate(AUDIO_CONFIG['sample_rate'])
                wav_file.writeframes(b''.join(audio_chunks))
            
            # Chemins pour l'upload Supabase
            audio_path = f"audio/{user_id}/recording_{timestamp}.wav"
            text_path = f"text/{user_id}/transcript_{timestamp}.txt"
            
            try:
                # Upload du fichier audio
                supabase.storage.from_("recordings").upload(
                    path=audio_path,
                    file=wav_buffer.getvalue(),
                    file_options={"content-type": "audio/wav"}
                )
                
                # Upload de la transcription
                supabase.storage.from_("recordings").upload(
                    path=text_path,
                    file=transcription_text.encode(),
                    file_options={"content-type": "text/plain"}
                )
            
            except Exception as e:
                print(f"Erreur lors de l'upload : {e}")
            
        finally:
            # Fermer le flux audio
            stream.stop_stream()
            stream.close()
            p.terminate()

async def main():
    """
    Démarrer le serveur WebSocket.
    
    Lance un serveur qui écoute les connexions pour l'enregistrement 
    et la transcription audio.
    """
    print("Démarrage du serveur WebSocket sur ws://localhost:8765")
    async with serve(handle_websocket, "localhost", 8765):
        print("Serveur prêt")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServeur arrêté")