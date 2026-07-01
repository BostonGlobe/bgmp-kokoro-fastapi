# Quickstart: `/audio/speech`

This guide shows how to generate speech from a client application using the OpenAI-compatible `POST /v1/audio/speech` endpoint.

## What the endpoint does

`/v1/audio/speech` converts text into an audio file.

- Method: `POST`
- Path: `/v1/audio/speech`
- Request body: JSON
- Response: binary audio data
- Default behavior: streaming audio chunks as they are generated

The endpoint accepts the same general pattern as OpenAI’s speech API, while using this project’s model and voice names.

## Basic request

Send a JSON body with at least:

- `input`: the text to speak
- `voice`: the voice to use
- `model`: a supported model name

Example:

```json
{
  "model": "kokoro",
  "input": "Hello world!",
  "voice": "af_heart",
  "response_format": "mp3"
}
```

## Supported models

The endpoint validates `model` against the server’s model list.

Supported values are:

- `kokoro`

If you send a model that is not enabled on the server, the API returns `400` with an `invalid_model` error.

## Supported voices

Voice names are validated against the server’s available voices.

- You can use a single voice, such as `af_heart`
- You can also combine voices, for example `af_bella+af_sky`
- Weighted combinations are also supported, for example `af_bella(2)+af_sky(1)`

If a voice is not recognized, the API returns a `400` validation error.

## Request schema

`POST /v1/audio/speech` accepts the `OpenAISpeechRequest` body.

```json
{
  "model": "kokoro",
  "input": "string",
  "voice": "af_heart",
  "response_format": "mp3",
  "download_format": "mp3",
  "speed": 1.0,
  "stream": true,
  "return_download_link": false,
  "lang_code": null,
  "volume_multiplier": 1.0,
  "normalization_options": {
    "normalize": true,
    "unit_normalization": false,
    "url_normalization": true,
    "email_normalization": true,
    "optional_pluralization_normalization": true,
    "phone_normalization": true,
    "replace_remaining_symbols": true,
    "html_normalization": true,
    "comma_pacing_normalization": true,
    "month_abbreviation_normalization": true,
    "score_normalization": true,
    "number_abbreviation_normalization": true,
    "pronunciation_normalization": false,
    "pronunciation_dictionary": {}
  }
}
```

## Field reference

### Required fields

| Field | Type | Description |
| --- | --- | --- |
| `model` | string | Model name to use. Must match a supported server model. Currently the only supported value is `kokoro`. |
| `input` | string | Text to convert to speech. |
| `voice` | string | Voice name or voice combination. Default: `af_heart`. |

### Audio output fields

| Field | Type | Description |
| --- | --- | --- |
| `response_format` | string | Audio format returned by the endpoint. Supported values: `mp3`, `opus`, `aac`, `flac`, `wav`, `pcm`. Default: `mp3`. The code currently flags AAC as not fully supported, so validate that format in your environment before relying on it. |
| `download_format` | string or null | Optional separate format for the downloadable file when `return_download_link` is enabled. If omitted, the endpoint uses `response_format`. |

### Playback and generation fields

| Field | Type | Description |
| --- | --- | --- |
| `speed` | number | Speech speed multiplier. Range: `0.25` to `4.0`. Default: `1.0`. |
| `stream` | boolean | Whether to stream audio as it is generated. Default: `true`. |
| `lang_code` | string or null | Optional language code used during text processing. If omitted, the server falls back to the first letter of the voice name. |
| `volume_multiplier` | number or null | Multiplies the output volume. Default: `1.0`. |

### Download fields

| Field | Type | Description |
| --- | --- | --- |
| `return_download_link` | boolean | When `true`, the endpoint returns an `X-Download-Path` header that points to a downloadable file route under the same API base, such as `/v1/download/<filename>`. Default: `false`. |

### Normalization fields

`normalization_options` is an object that controls how the input text is preprocessed before synthesis.

| Field | Type | Description |
| --- | --- | --- |
| `normalize` | boolean | Master switch for text normalization. Default: `true`. |
| `unit_normalization` | boolean | Expands units such as `10KB` into spoken form. Default: `false`. |
| `url_normalization` | boolean | Improves pronunciation of URLs. Default: `true`. |
| `email_normalization` | boolean | Improves pronunciation of email addresses. Default: `true`. |
| `optional_pluralization_normalization` | boolean | Rewrites forms like `(s)` for clearer pronunciation. Default: `true`. |
| `phone_normalization` | boolean | Improves pronunciation of phone numbers. Default: `true`. |
| `replace_remaining_symbols` | boolean | Replaces remaining symbols with words. Default: `true`. |
| `html_normalization` | boolean | Removes HTML tags before synthesis. Default: `true`. |
| `comma_pacing_normalization` | boolean | Replaces commas with a pacing pattern to improve flow. Default: `true`. |
| `month_abbreviation_normalization` | boolean | Expands month abbreviations. Default: `true`. |
| `score_abbreviation` | boolean | Expands instances of 'number-number' to 'number - number' for better parsing. Model will say 'minus' in the first example, and just pause in the second example. Default: `true`. |
| `number_abbreviation_normalization` | boolean | Expands instance of 'No. #' abbreviations to 'Number #'. Default: `true`. |
| `pronunciation_normalization` | boolean | Applies pronunciation overrides. Default: `true`. |
| `pronunciation_dictionary` | object | Custom pronunciation map for specific words. Default: `{}`. |

## Response behavior

The endpoint returns audio bytes directly, not JSON.

- `Content-Type` matches the selected audio format
- `Content-Disposition` is set so browsers and download handlers treat the response as a file
- If `stream=true`, the server sends the audio incrementally
- If `return_download_link=true`, the response may include an `X-Download-Path` header with a relative download route

If something goes wrong, the API returns JSON error responses with HTTP status codes such as:

- `400` for validation issues
- `500` for processing errors

## Example requests

### JavaScript `fetch`

```js
const response = await fetch("http://localhost:8880/v1/audio/speech", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "kokoro",
    input: "Hello world!",
    voice: "af_heart",
    response_format: "mp3",
    stream: true,
  }),
});

if (!response.ok) {
  throw new Error(`Request failed: ${response.status}`);
}

const audioBlob = await response.blob();
const url = URL.createObjectURL(audioBlob);
const audio = new Audio(url);
await audio.play();
```

### PHP with cURL

```php
<?php

$payload = json_encode([
    "model" => "kokoro",
    "input" => "Hello world!",
    "voice" => "af_heart",
    "response_format" => "mp3",
    "stream" => true,
]);

$ch = curl_init("http://localhost:8880/v1/audio/speech");
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        "Content-Type: application/json",
    ],
    CURLOPT_POSTFIELDS => $payload,
    CURLOPT_RETURNTRANSFER => true,
]);

$audio = curl_exec($ch);

if ($audio === false) {
    throw new RuntimeException(curl_error($ch));
}

$status = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

if ($status >= 400) {
    throw new RuntimeException("Request failed with status {$status}");
}

file_put_contents(__DIR__ . "/output.mp3", $audio);
```

## Practical tips

- Use `stream: true` for the fastest first byte and the best OpenAI-compatible behavior.
- Use `stream: false` if your client prefers a single complete audio payload.
- If you need a separate downloadable file format, set `return_download_link: true` and optionally `download_format`.
- If your text contains URLs, email addresses, phone numbers, or HTML, keep the default normalization settings unless you have a reason to disable them.

## Example cURL request

```bash
curl -X POST "http://localhost:8880/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kokoro",
    "input": "Hello world!",
    "voice": "af_heart",
    "response_format": "mp3",
    "stream": true
  }' \
  --output output.mp3
```
