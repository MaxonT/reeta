"""OCI Speech client using the Whisper model. STUB, not wired yet.

TODO(oci):
  1. pip install oci; auth with OCI_CONFIG_FILE / OCI_PROFILE (or instance principal)
  2. Upload audio to Object Storage (OCI_SPEECH_NAMESPACE / OCI_SPEECH_BUCKET)
  3. oci.ai_speech.AIServiceSpeechClient.create_transcription_job(
         model_details=TranscriptionModelDetails(model_type="WHISPER_MEDIUM", language_code="en"),
         input_location=ObjectListInlineInputLocation(...),
         output_location=OutputLocation(...))
  4. Poll the job, read the JSON result from the bucket
  5. Map result tokens/segments to [{text, start_ms, end_ms}] and call
     segments_to_sentences() so the output matches OpenAIWhisperClient exactly.
"""
from pathlib import Path

from .base import SpeechClient


class OCISpeechClient(SpeechClient):
    def transcribe(self, audio_path: Path) -> list[dict]:
        raise NotImplementedError("OCISpeechClient is a stub. See TODO in speech/oci_speech.py")
