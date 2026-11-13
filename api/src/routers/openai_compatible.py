"""OpenAI-compatible router for text-to-speech"""

import asyncio
import io
import json
import os
import re
import tempfile
import time
import uuid
from typing import AsyncGenerator, Dict, List, Tuple, Union
from urllib import response

import aiofiles
import numpy as np
import torch
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger

from ..core.config import settings
from ..inference.base import AudioChunk
from ..services.audio import AudioService
from ..services.streaming_audio_writer import StreamingAudioWriter
from ..services.tts_service import TTSService
from ..structures import OpenAISpeechRequest
from ..structures.schemas import CaptionedSpeechRequest


# Load OpenAI mappings
def load_openai_mappings() -> Dict:
    """Load OpenAI voice and model mappings from JSON"""
    api_dir = os.path.dirname(os.path.dirname(__file__))
    mapping_path = os.path.join(api_dir, "core", "openai_mappings.json")
    try:
        with open(mapping_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load OpenAI mappings: {e}")
        return {"models": {}, "voices": {}}


# Global mappings
_openai_mappings = load_openai_mappings()


def _elapsed_ms(start: float) -> int:
    """Milliseconds elapsed since a time.perf_counter() start value"""
    return int((time.perf_counter() - start) * 1000)


router = APIRouter(
    tags=["OpenAI Compatible TTS"],
    responses={404: {"description": "Not found"}},
)

# Global TTSService instance with lock
_tts_service = None
_init_lock = None


async def get_tts_service() -> TTSService:
    """Get global TTSService instance"""
    global _tts_service, _init_lock

    # Create lock if needed
    if _init_lock is None:
        import asyncio

        _init_lock = asyncio.Lock()

    # Initialize service if needed
    if _tts_service is None:
        async with _init_lock:
            # Double check pattern
            if _tts_service is None:
                start = time.perf_counter()
                _tts_service = await TTSService.create()
                logger.info(
                    f"Created global TTSService instance in {_elapsed_ms(start)}ms"
                )

    return _tts_service


def get_model_name(model: str) -> str:
    """Get internal model name from OpenAI model name"""
    base_name = _openai_mappings["models"].get(model)
    if not base_name:
        raise ValueError(f"Unsupported model: {model}")
    return base_name + ".pth"


async def process_and_validate_voices(
    voice_input: Union[str, List[str]], tts_service: TTSService
) -> str:
    """Process voice input, handling both string and list formats

    Returns:
        Voice name to use (with weights if specified)
    """
    voices = []
    # Convert input to list of voices
    if isinstance(voice_input, str):
        voice_input = voice_input.replace(" ", "").strip()

        if voice_input[-1] in "+-" or voice_input[0] in "+-":
            raise ValueError(f"Voice combination contains empty combine items")

        if re.search(r"[+-]{2,}", voice_input) is not None:
            raise ValueError(f"Voice combination contains empty combine items")
        voices = re.split(r"([-+])", voice_input)
    else:
        voices = [[item, "+"] for item in voice_input][:-1]

    available_voices = await tts_service.list_voices()

    for voice_index in range(0, len(voices), 2):
        mapped_voice = voices[voice_index].split("(")
        mapped_voice = list(map(str.strip, mapped_voice))

        if len(mapped_voice) > 2:
            raise ValueError(
                f"Voice '{voices[voice_index]}' contains too many weight items"
            )

        if mapped_voice.count(")") > 1:
            raise ValueError(
                f"Voice '{voices[voice_index]}' contains too many weight items"
            )

        mapped_voice[0] = _openai_mappings["voices"].get(
            mapped_voice[0], mapped_voice[0]
        )

        if mapped_voice[0] not in available_voices:
            raise ValueError(
                f"Voice '{mapped_voice[0]}' not found. Available voices: {', '.join(sorted(available_voices))}"
            )

        voices[voice_index] = "(".join(mapped_voice)

    return "".join(voices)


async def stream_audio_chunks(
    tts_service: TTSService,
    request: Union[OpenAISpeechRequest, CaptionedSpeechRequest],
    client_request: Request,
    writer: StreamingAudioWriter,
    request_id: str = "-",
) -> AsyncGenerator[AudioChunk, None]:
    """Stream audio chunks as they're generated with client disconnect handling"""
    start = time.perf_counter()
    chunk_count = 0
    voice_name = await process_and_validate_voices(request.voice, tts_service)
    unique_properties = {"return_timestamps": False}
    if hasattr(request, "return_timestamps"):
        unique_properties["return_timestamps"] = request.return_timestamps

    try:
        async for chunk_data in tts_service.generate_audio_stream(
            text=request.input,
            voice=voice_name,
            writer=writer,
            speed=request.speed,
            output_format=request.response_format,
            lang_code=request.lang_code,
            volume_multiplier=request.volume_multiplier,
            normalization_options=request.normalization_options,
            return_timestamps=unique_properties["return_timestamps"],
        ):
            chunk_count += 1
            if chunk_count == 1:
                logger.debug(
                    f"[{request_id}] First audio chunk generated in "
                    f"{_elapsed_ms(start)}ms"
                )

            # Check if client is still connected
            is_disconnected = client_request.is_disconnected
            if callable(is_disconnected):
                is_disconnected = await is_disconnected()
            if is_disconnected:
                logger.info(
                    f"[{request_id}] Client disconnected after {chunk_count} "
                    f"chunks ({_elapsed_ms(start)}ms), stopping audio generation"
                )
                break

            yield chunk_data
        else:
            logger.debug(
                f"[{request_id}] Audio generation finished: {chunk_count} "
                f"chunks in {_elapsed_ms(start)}ms"
            )
    except asyncio.CancelledError:
        logger.warning(
            f"[{request_id}] Audio generation cancelled after {chunk_count} "
            f"chunks ({_elapsed_ms(start)}ms)"
        )
        raise
    except Exception as e:
        logger.exception(
            f"[{request_id}] Error in audio streaming after {chunk_count} "
            f"chunks ({_elapsed_ms(start)}ms): {e}"
        )
        # Let the exception propagate to trigger cleanup
        raise


@router.post("/audio/speech")
async def create_speech(
    request: OpenAISpeechRequest,
    client_request: Request,
    x_raw_response: str = Header(None, alias="x-raw-response"),
):
    """OpenAI-compatible endpoint for text-to-speech"""
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    client_host = client_request.client.host if client_request.client else "-"
    logger.info(
        f"[{request_id}] Speech request from {client_host}: "
        f"model={request.model} voice={request.voice} "
        f"format={request.response_format} stream={request.stream} "
        f"input_chars={len(request.input)} speed={request.speed} "
        f"lang_code={request.lang_code} "
        f"download_link={request.return_download_link} "
        f"product={request.product} article_id={request.article_id}"
    )

    # Validate model before processing request
    if request.model not in _openai_mappings["models"]:
        logger.warning(f"[{request_id}] Unsupported model: {request.model}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_model",
                "message": f"Unsupported model: {request.model}",
                "type": "invalid_request_error",
            },
        )

    try:
        # model_name = get_model_name(request.model)
        tts_service = await get_tts_service()
        voice_name = await process_and_validate_voices(
            request.voice, tts_service
        )

        # Set content type based on format
        content_type = {
            "mp3": "audio/mpeg",
            "opus": "audio/opus",
            "aac": "audio/aac",
            "flac": "audio/flac",
            "wav": "audio/wav",
            "pcm": "audio/pcm",
        }.get(request.response_format, f"audio/{request.response_format}")

        writer = StreamingAudioWriter(
            request.response_format, sample_rate=24000
        )

        # Check if streaming is requested (default for OpenAI client)
        if request.stream:
            # Create generator but don't start it yet
            generator = stream_audio_chunks(
                tts_service, request, client_request, writer, request_id
            )

            # If download link requested, wrap generator with temp file writer
            if request.return_download_link:
                from ..services.temp_manager import TempFileWriter

                # Use download_format if specified, otherwise use response_format
                output_format = (
                    request.download_format or request.response_format
                )
                temp_writer = TempFileWriter(
                    output_format, request.product, request.article_id
                )
                await temp_writer.__aenter__()  # Initialize temp file

                # Get download path immediately after temp file creation
                download_path = temp_writer.download_path

                # Create response headers with download path
                headers = {
                    "Content-Disposition": f"attachment; filename=speech.{output_format}",
                    "X-Accel-Buffering": "no",
                    "Cache-Control": "no-cache",
                    "Transfer-Encoding": "chunked",
                    "X-Download-Path": download_path,
                }

                # Add header to indicate if temp file writing is available
                if temp_writer._write_error:
                    logger.warning(
                        f"[{request_id}] Temp file writing unavailable for "
                        f"{download_path}"
                    )
                    headers["X-Download-Status"] = "unavailable"

                # Create async generator for streaming
                async def dual_output():
                    bytes_sent = 0
                    completed = False
                    try:
                        # Write chunks to temp file and stream
                        async for chunk_data in generator:
                            if chunk_data.output:  # Skip empty chunks
                                await temp_writer.write(chunk_data.output)
                                if bytes_sent == 0:
                                    logger.debug(
                                        f"[{request_id}] First audio bytes sent "
                                        f"{_elapsed_ms(start)}ms after request"
                                    )
                                bytes_sent += len(chunk_data.output)
                                # if return_json:
                                #    yield chunk, chunk_data
                                # else:
                                yield chunk_data.output

                        # Finalize the temp file
                        await temp_writer.finalize()
                        completed = True
                        logger.info(
                            f"[{request_id}] Streamed {bytes_sent} bytes in "
                            f"{_elapsed_ms(start)}ms, download file "
                            f"{download_path}"
                        )
                    except Exception as e:
                        logger.error(
                            f"[{request_id}] Error in dual output streaming: {e}"
                        )
                        await temp_writer.__aexit__(
                            type(e), e, e.__traceback__
                        )
                        raise
                    finally:
                        if not completed:
                            logger.warning(
                                f"[{request_id}] Stream ended early after "
                                f"{bytes_sent} bytes ({_elapsed_ms(start)}ms)"
                            )
                        # Ensure temp writer is closed
                        if not temp_writer._finalized:
                            await temp_writer.__aexit__(None, None, None)
                        writer.close()

                # Stream with temp file writing
                return StreamingResponse(
                    dual_output(), media_type=content_type, headers=headers
                )

            async def single_output():
                bytes_sent = 0
                completed = False
                try:
                    # Stream chunks
                    async for chunk_data in generator:
                        if chunk_data.output:  # Skip empty chunks
                            if bytes_sent == 0:
                                logger.debug(
                                    f"[{request_id}] First audio bytes sent "
                                    f"{_elapsed_ms(start)}ms after request"
                                )
                            bytes_sent += len(chunk_data.output)
                            yield chunk_data.output
                    completed = True
                    logger.info(
                        f"[{request_id}] Streamed {bytes_sent} bytes in "
                        f"{_elapsed_ms(start)}ms"
                    )
                except Exception as e:
                    logger.error(
                        f"[{request_id}] Error in single output streaming: {e}"
                    )
                    writer.close()
                    raise
                finally:
                    if not completed:
                        logger.warning(
                            f"[{request_id}] Stream ended early after "
                            f"{bytes_sent} bytes ({_elapsed_ms(start)}ms)"
                        )

            # Standard streaming without download link
            return StreamingResponse(
                single_output(),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"attachment; filename=speech.{request.response_format}",
                    "X-Accel-Buffering": "no",
                    "Cache-Control": "no-cache",
                    "Transfer-Encoding": "chunked",
                },
            )
        else:
            headers = {
                "Content-Disposition": f"attachment; filename=speech.{request.response_format}",
                "Cache-Control": "no-cache",  # Prevent caching
            }

            # Generate complete audio using public interface
            generation_start = time.perf_counter()
            audio_data = await tts_service.generate_audio(
                text=request.input,
                voice=voice_name,
                writer=writer,
                speed=request.speed,
                volume_multiplier=request.volume_multiplier,
                normalization_options=request.normalization_options,
                lang_code=request.lang_code,
            )
            logger.debug(
                f"[{request_id}] Audio generated in "
                f"{_elapsed_ms(generation_start)}ms"
            )

            conversion_start = time.perf_counter()
            audio_data = await AudioService.convert_audio(
                audio_data,
                request.response_format,
                writer,
                is_last_chunk=False,
                trim_audio=False,
            )

            # Convert to requested format with proper finalization
            final = await AudioService.convert_audio(
                AudioChunk(np.array([], dtype=np.int16)),
                request.response_format,
                writer,
                is_last_chunk=True,
            )
            output = audio_data.output + final.output
            logger.debug(
                f"[{request_id}] Audio converted to {request.response_format} "
                f"in {_elapsed_ms(conversion_start)}ms"
            )

            if request.return_download_link:
                from ..services.temp_manager import TempFileWriter

                # Use download_format if specified, otherwise use response_format
                output_format = (
                    request.download_format or request.response_format
                )
                temp_writer = TempFileWriter(output_format)
                await temp_writer.__aenter__()  # Initialize temp file

                # Get download path immediately after temp file creation
                download_path = temp_writer.download_path
                headers["X-Download-Path"] = download_path

                try:
                    # Write chunks to temp file
                    logger.info(
                        f"[{request_id}] Writing audio to temporary file "
                        f"{download_path} for download"
                    )
                    await temp_writer.write(output)
                    # Finalize the temp file
                    await temp_writer.finalize()

                except Exception as e:
                    logger.error(f"[{request_id}] Error in dual output: {e}")
                    await temp_writer.__aexit__(type(e), e, e.__traceback__)
                    raise
                finally:
                    # Ensure temp writer is closed
                    if not temp_writer._finalized:
                        await temp_writer.__aexit__(None, None, None)
                    writer.close()

            logger.info(
                f"[{request_id}] Returned {len(output)} bytes in "
                f"{_elapsed_ms(start)}ms"
            )
            return Response(
                content=output,
                media_type=content_type,
                headers=headers,
            )

    except ValueError as e:
        # Handle validation errors
        logger.warning(
            f"[{request_id}] Invalid request ({_elapsed_ms(start)}ms): {e}"
        )

        try:
            writer.close()
        except:
            pass

        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": str(e),
                "type": "invalid_request_error",
            },
        )
    except RuntimeError as e:
        # Handle runtime/processing errors
        logger.exception(
            f"[{request_id}] Processing error ({_elapsed_ms(start)}ms): {e}"
        )

        try:
            writer.close()
        except:
            pass

        raise HTTPException(
            status_code=500,
            detail={
                "error": "processing_error",
                "message": str(e),
                "type": "server_error",
            },
        )
    except Exception as e:
        # Handle unexpected errors
        logger.exception(
            f"[{request_id}] Unexpected error in speech generation "
            f"({_elapsed_ms(start)}ms): {e}"
        )

        try:
            writer.close()
        except:
            pass

        raise HTTPException(
            status_code=500,
            detail={
                "error": "processing_error",
                "message": str(e),
                "type": "server_error",
            },
        )


@router.get("/download/{filename}")
async def download_audio_file(filename: str, product: str = "bgmp"):
    """Download a generated audio file from temp storage"""
    try:
        from ..core.paths import _find_file, get_content_type

        # Search for file in temp directory
        file_path = await _find_file(
            filename=filename,
            search_paths=[f"{settings.temp_file_dir}/{product}"],
        )

        # Get content type from path helper
        content_type = await get_content_type(file_path)

        return FileResponse(
            file_path,
            media_type=content_type,
            filename=filename,
            headers={
                "Cache-Control": "no-cache",
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )

    except Exception as e:
        logger.exception(
            f"Error serving download file {filename} (product={product}): {e}"
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "server_error",
                "message": "Failed to serve audio file",
                "type": "server_error",
            },
        )


@router.get("/models")
async def list_models():
    """List all available models"""
    try:
        # Create standard model list
        models = [
            {
                "id": "tts-1",
                "object": "model",
                "created": 1686935002,
                "owned_by": "kokoro",
            },
            {
                "id": "tts-1-hd",
                "object": "model",
                "created": 1686935002,
                "owned_by": "kokoro",
            },
            {
                "id": "kokoro",
                "object": "model",
                "created": 1686935002,
                "owned_by": "kokoro",
            },
            {
                "id": "gpt-4o-mini-tts",
                "object": "model",
                "created": 1686935002,
                "owned_by": "kokoro",
            },
        ]

        return {"object": "list", "data": models}
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "server_error",
                "message": "Failed to retrieve model list",
                "type": "server_error",
            },
        )


@router.get("/models/{model}")
async def retrieve_model(model: str):
    """Retrieve a specific model"""
    try:
        # Define available models
        models = {
            "tts-1": {
                "id": "tts-1",
                "object": "model",
                "created": 1686935002,
                "owned_by": "kokoro",
            },
            "tts-1-hd": {
                "id": "tts-1-hd",
                "object": "model",
                "created": 1686935002,
                "owned_by": "kokoro",
            },
            "kokoro": {
                "id": "kokoro",
                "object": "model",
                "created": 1686935002,
                "owned_by": "kokoro",
            },
        }

        # Check if requested model exists
        if model not in models:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "model_not_found",
                    "message": f"Model '{model}' not found",
                    "type": "invalid_request_error",
                },
            )

        # Return the specific model
        return models[model]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving model {model}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "server_error",
                "message": "Failed to retrieve model information",
                "type": "server_error",
            },
        )


@router.get("/audio/voices")
async def list_voices(legacy: bool = False):
    """List all available voices for text-to-speech.

    Returns `[{"id": ..., "name": ...}, ...]` by default so OpenAI-compatible
    clients (Open WebUI in particular, which does `voice['id']` directly and
    silently falls back to a hardcoded 6-voice list otherwise) can render the
    full voice list. Pass `?legacy=true` for the pre-0.3.x plain-string shape.
    """
    try:
        tts_service = await get_tts_service()
        voices = await tts_service.list_voices()
        if legacy:
            return {"voices": voices}
        return {"voices": [{"id": v, "name": v} for v in voices]}
    except Exception as e:
        logger.exception(f"Error listing voices: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "server_error",
                "message": "Failed to retrieve voice list",
                "type": "server_error",
            },
        )


@router.post("/audio/voices/combine")
async def combine_voices(request: Union[str, List[str]]):
    """Combine multiple voices into a new voice and return the .pt file.

    Args:
        request: Either a string with voices separated by + (e.g. "voice1+voice2")
                or a list of voice names to combine

    Returns:
        FileResponse with the combined voice .pt file

    Raises:
        HTTPException:
            - 400: Invalid request (wrong number of voices, voice not found)
            - 500: Server error (file system issues, combination failed)
    """
    # Check if local voice saving is allowed
    if not settings.allow_local_voice_saving:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "permission_denied",
                "message": "Local voice saving is disabled",
                "type": "permission_error",
            },
        )

    try:
        # Convert input to list of voices
        if isinstance(request, str):
            # Check if it's an OpenAI voice name
            mapped_voice = _openai_mappings["voices"].get(request)
            if mapped_voice:
                request = mapped_voice
            voices = [v.strip() for v in request.split("+") if v.strip()]
        else:
            # For list input, map each voice if it's an OpenAI voice name
            voices = [_openai_mappings["voices"].get(v, v) for v in request]
            voices = [v.strip() for v in voices if v.strip()]

        if not voices:
            raise ValueError("No voices provided")

        # For multiple voices, validate base voices exist
        tts_service = await get_tts_service()
        available_voices = await tts_service.list_voices()
        for voice in voices:
            if voice not in available_voices:
                raise ValueError(
                    f"Base voice '{voice}' not found. Available voices: {', '.join(sorted(available_voices))}"
                )

        # Combine voices
        combined_tensor = await tts_service.combine_voices(voices=voices)
        combined_name = "+".join(voices)

        # Save to temp file
        temp_dir = tempfile.gettempdir()
        voice_path = os.path.join(temp_dir, f"{combined_name}.pt")
        buffer = io.BytesIO()
        torch.save(combined_tensor, buffer)
        async with aiofiles.open(voice_path, "wb") as f:
            await f.write(buffer.getvalue())

        return FileResponse(
            voice_path,
            media_type="application/octet-stream",
            filename=f"{combined_name}.pt",
            headers={
                "Content-Disposition": f"attachment; filename={combined_name}.pt",
                "Cache-Control": "no-cache",
            },
        )

    except ValueError as e:
        logger.warning(f"Invalid voice combination request: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": str(e),
                "type": "invalid_request_error",
            },
        )
    except RuntimeError as e:
        logger.exception(f"Voice combination processing error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "processing_error",
                "message": "Failed to process voice combination request",
                "type": "server_error",
            },
        )
    except Exception as e:
        logger.exception(f"Unexpected error in voice combination: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "server_error",
                "message": "An unexpected error occurred",
                "type": "server_error",
            },
        )
