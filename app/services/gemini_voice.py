import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def create_gemini_live_session():
    # Use the live preview model designed for real-time bidirectional voice
    model_id = "gemini-2.5-flash"
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part.from_text(
                "You are the elite autonomous AI receptionist for GFI Dental OS. "
                "Your job is to answer patient calls, triage emergency dental pain, check chair availability, "
                "and securely book appointments in English, Hindi, or Telugu with ultra-low latency."
            )]
        ),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        )
    )
    
    return client.aio.live.connect(model=model_id, config=config)