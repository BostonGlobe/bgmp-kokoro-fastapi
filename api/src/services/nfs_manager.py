"""Temporary file writer for audio downloads"""

import os
import tempfile

import aiofiles
from loguru import logger

from ..core.config import settings


class NfsFileWriter:
    """Handles writing audio chunks to an NFS-mounted file"""

    def __init__(self, format: str):
        """Initialize NFS file writer

        Args:
            format: Audio format extension (mp3, wav, etc)
        """
        self.format = format
        self.nfs_file = None
        self._finalized = False
        self._write_error = False  # Flag to track if we've had a write error

    async def __aenter__(self):
        """Async context manager entry"""
        try:

            # Create NFS file with proper extension
            await aiofiles.os.makedirs(settings.nfs_mount_dir, exist_ok=True)
            temp = tempfile.NamedTemporaryFile(
                dir=settings.nfs_mount_dir,
                delete=False,
                suffix=f".{self.format}",
                mode="wb",
            )
            self.nfs_file = await aiofiles.open(temp.name, mode="wb")
            self.temp_path = temp.name
            temp.close()  # Close sync file, we'll use async version

            # Generate download path immediately
            self.download_path = f"/download/{os.path.basename(self.temp_path)}"
        except Exception as e:
            # Handle permission issues or other errors gracefully
            logger.error(f"Failed to create temp file: {e}")
            self._write_error = True
            # Set a placeholder path so the API can still function
            self.temp_path = f"unavailable_{self.format}"
            self.download_path = f"/download/{self.temp_path}"

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        try:
            if self.nfs_file and not self._finalized:
                await self.nfs_file.close()
                self._finalized = True
        except Exception as e:
            logger.error(f"Error closing temp file: {e}")
            self._write_error = True

    async def write(self, chunk: bytes) -> None:
        """Write a chunk of audio data

        Args:
            chunk: Audio data bytes to write
        """
        if self._finalized:
            raise RuntimeError("Cannot write to finalized temp file")

        # Skip writing if we've already encountered an error
        if self._write_error or not self.nfs_file:
            return

        try:
            await self.nfs_file.write(chunk)
            await self.nfs_file.flush()
        except Exception as e:
            # Handle permission issues or other errors gracefully
            logger.error(f"Failed to write to temp file: {e}")
            self._write_error = True

    async def finalize(self) -> str:
        """Close temp file and return download path

        Returns:
            Path to use for downloading the temp file
        """
        if self._finalized:
            raise RuntimeError("Temp file already finalized")

        # Skip finalizing if we've already encountered an error
        if self._write_error or not self.nfs_file:
            self._finalized = True
            return self.download_path

        try:
            await self.nfs_file.close()
            self._finalized = True
        except Exception as e:
            # Handle permission issues or other errors gracefully
            logger.error(f"Failed to finalize temp file: {e}")
            self._write_error = True
            self._finalized = True

        return self.download_path
