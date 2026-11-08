from __future__ import annotations
import os
import re
import shutil
import subprocess
import time
from pathlib import Path


def _flags():
    return getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def find_ffmpeg() -> str | None:
    """Resolve an FFmpeg executable without requiring a system-wide install."""
    env = os.environ.get('FFMPEG_EXE')
    if env and Path(env).exists():
        return env
    system = shutil.which('ffmpeg')
    if system:
        return system
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    return None


def capture_png(path: Path) -> bool:
    """Capture the primary Windows screen using PowerShell/.NET."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = str(path).replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "$bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height); "
        "$g=[System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size); "
        f"$bmp.Save('{safe}',[System.Drawing.Imaging.ImageFormat]::Png); "
        "$g.Dispose(); $bmp.Dispose();"
    )
    try:
        r = subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=_flags(), timeout=15
        )
        return r.returncode == 0 and path.exists() and path.stat().st_size > 0
    except Exception:
        return False


def _duration_seconds(ffmpeg: str, path: Path) -> float | None:
    """Read duration from FFmpeg's container probe output (ffprobe not required)."""
    try:
        p = subprocess.run(
            [ffmpeg, '-hide_banner', '-i', str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=_flags(), timeout=20
        )
        txt = p.stdout.decode(errors='ignore') if isinstance(p.stdout, (bytes, bytearray)) else str(p.stdout or '')
        m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', txt)
        if not m:
            return None
        h, mnt, sec = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h * 3600 + mnt * 60 + sec
    except Exception:
        return None


def validate_video(path: Path, ffmpeg: str | None = None, *, min_duration: float = 1.0, min_size: int = 50_000) -> dict:
    """Validate that a recorded MP4 exists, has duration, and can be decoded by FFmpeg."""
    path = Path(path)
    ffmpeg = ffmpeg or find_ffmpeg()
    result = {
        'ok': False,
        'path': str(path),
        'exists': path.exists(),
        'size_bytes': path.stat().st_size if path.exists() else 0,
        'duration_seconds': None,
        'decode_ok': False,
        'reason': '',
    }
    if not path.exists():
        result['reason'] = 'video file was not created'
        return result
    if result['size_bytes'] < min_size:
        result['reason'] = f"video file is unexpectedly small ({result['size_bytes']} bytes)"
        return result
    if not ffmpeg:
        result['reason'] = 'FFmpeg is unavailable for validation'
        return result

    duration = _duration_seconds(ffmpeg, path)
    result['duration_seconds'] = duration
    if duration is None:
        result['reason'] = 'video duration could not be read'
        return result
    if duration < min_duration:
        result['reason'] = f'video duration is too short ({duration:.2f}s)'
        return result

    try:
        p = subprocess.run(
            [ffmpeg, '-v', 'error', '-i', str(path), '-map', '0:v:0', '-f', 'null', '-'],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=_flags(), timeout=max(30, int(duration * 2 + 15))
        )
        result['decode_ok'] = p.returncode == 0
        if p.returncode != 0:
            err = (p.stderr or b'').decode(errors='ignore').strip().replace('\n', ' ')[:500]
            result['reason'] = 'FFmpeg could not decode the final video' + (f': {err}' if err else '')
            return result
    except Exception as exc:
        result['reason'] = f'video decode validation failed: {exc}'
        return result

    result['ok'] = True
    result['reason'] = 'ok'
    return result


class DesktopRecorder:
    """Windows desktop recorder using FFmpeg gdigrab + H.264 MP4.

    v1.7 treats recording as a first-class deliverable: startup failure raises,
    FFmpeg diagnostics are persisted, and the caller validates the final MP4.
    """
    def __init__(self, output: Path, fps: int = 20, log_path: Path | None = None):
        self.output = Path(output)
        self.fps = fps
        self._proc: subprocess.Popen | None = None
        self._stderr_handle = None
        self.ffmpeg = find_ffmpeg()
        self.log_path = Path(log_path) if log_path else self.output.parent / '.ffmpeg-capture.log'

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg)

    def start(self):
        if os.name != 'nt':
            raise RuntimeError('Desktop recording requires Windows 10/11.')
        if not self.ffmpeg:
            raise RuntimeError('FFmpeg is not available. Recording cannot start.')
        self.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.output.unlink()
        except FileNotFoundError:
            pass
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._stderr_handle = self.log_path.open('wb')

        cmd = [
            self.ffmpeg, '-y', '-hide_banner', '-loglevel', 'warning',
            '-f', 'gdigrab', '-framerate', str(self.fps), '-draw_mouse', '1',
            '-rtbufsize', '512M', '-i', 'desktop',
            '-an',
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
            str(self.output)
        ]
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=self._stderr_handle, creationflags=_flags()
        )
        # Give gdigrab enough time to initialize and write its first frames.
        time.sleep(1.8)
        if self._proc.poll() is not None:
            rc = self._proc.returncode
            self._close_log()
            tail = self._log_tail()
            raise RuntimeError(f'FFmpeg desktop capture exited during startup (code {rc}). {tail}'.strip())
        return True

    def screenshot(self, path: Path):
        return capture_png(path)

    def _close_log(self):
        if self._stderr_handle:
            try:
                self._stderr_handle.flush()
                self._stderr_handle.close()
            except Exception:
                pass
            self._stderr_handle = None

    def _log_tail(self) -> str:
        try:
            txt = self.log_path.read_text(encoding='utf-8', errors='ignore').strip()
            return txt[-1200:].replace('\n', ' ')
        except Exception:
            return ''

    def stop(self):
        if not self._proc:
            self._close_log()
            return 0
        proc = self._proc
        rc = proc.poll()
        if rc is None:
            try:
                if proc.stdin:
                    proc.stdin.write(b'q\n')
                    proc.stdin.flush()
                proc.wait(timeout=15)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=6)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            rc = proc.poll()
        self._proc = None
        self._close_log()
        return 0 if rc is None else rc


class ScreenshotOnlyRecorder:
    """Explicit screenshot-only mode; never used silently by RUN_ALL.bat in v1.7."""
    available = False
    def __init__(self, *args, **kwargs): pass
    def start(self): return None
    def screenshot(self, path: Path): return capture_png(path)
    def stop(self): return 0
