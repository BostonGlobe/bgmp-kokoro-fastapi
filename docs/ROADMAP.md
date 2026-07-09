# Roadmap

## Future Features

### Audio file versioning
Currently since we store files under the article ID, if we try to regenerate the audio for an article, it will overwrite the previous file. If we have a need to maintain both audio files, we'll need to implement some versioning logic.

### Streaming response for download endpoint
The GET /v1/download/{filename} endpoint returns the audio file as one chunk of bytes. It may be beneficial to add an option for streaming responses in the case of large audio files.

### Overwrite protection
Similar to versioning, there currently are not overwrite protections in the API, so if two requests for the same article ID are sent, the earlier request would be overwritten.