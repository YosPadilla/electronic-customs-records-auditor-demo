from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
OUT.mkdir(exist_ok=True)
LOG = OUT / 'RUN_ALL_LOG.txt'
STATE = OUT / '.recording_setup.json'
PREFLIGHT = OUT / '.recording-preflight.mp4'


def log(msg: str):
    print(msg, flush=True)
    with LOG.open('a', encoding='utf-8') as fh:
        fh.write(msg + '\n')


def can_import_tk() -> bool:
    try:
        import tkinter  # noqa
        return True
    except Exception as exc:
        log(f'[ERROR] Tkinter is unavailable: {exc}')
        return False


def imageio_ffmpeg_path() -> str | None:
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and Path(p).exists():
            return p
    except Exception:
        pass
    return None


def candidate_ffmpegs() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    env = os.environ.get('FFMPEG_EXE')
    if env and Path(env).exists():
        out.append((env, 'FFMPEG_EXE'))
    path = shutil.which('ffmpeg')
    if path and all(Path(x[0]).resolve() != Path(path).resolve() for x in out):
        out.append((path, 'PATH'))
    img = imageio_ffmpeg_path()
    if img and all(Path(x[0]).resolve() != Path(img).resolve() for x in out):
        out.append((img, 'imageio-ffmpeg'))
    return out


def run(cmd):
    log('> ' + ' '.join(map(str, cmd)))
    p = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.stdout:
        with LOG.open('a', encoding='utf-8') as fh:
            fh.write(p.stdout + '\n')
        print(p.stdout, end='')
    return p.returncode


def ensure_imageio_ffmpeg() -> str | None:
    current = imageio_ffmpeg_path()
    if current:
        return current
    log('[INFO] Installing the self-contained imageio-ffmpeg package for this user...')
    if run([sys.executable, '-m', 'pip', '--version']) != 0:
        log('[INFO] pip not available; attempting ensurepip...')
        run([sys.executable, '-m', 'ensurepip', '--upgrade'])
    attempts = [
        [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--user', '--upgrade', 'imageio-ffmpeg'],
        [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade', 'imageio-ffmpeg'],
    ]
    for cmd in attempts:
        if run(cmd) == 0:
            current = imageio_ffmpeg_path()
            if current:
                return current
    return None


def smoke_test(ffmpeg: str, fps: int = 15) -> tuple[bool, str, dict]:
    """Record ~2.5 seconds of the desktop and validate the resulting MP4."""
    try:
        PREFLIGHT.unlink()
    except FileNotFoundError:
        pass
    old = os.environ.get('FFMPEG_EXE')
    os.environ['FFMPEG_EXE'] = ffmpeg
    try:
        from desktop.desktop_recorder import DesktopRecorder, validate_video
        rec = DesktopRecorder(PREFLIGHT, fps=fps, log_path=OUT / '.ffmpeg-preflight.log')
        rec.start()
        time.sleep(2.6)
        rc = rec.stop()
        if rc not in (0, None):
            return False, f'FFmpeg exited with code {rc}', {}
        check = validate_video(PREFLIGHT, ffmpeg=ffmpeg, min_duration=1.5, min_size=30_000)
        if not check.get('ok'):
            return False, check.get('reason', 'unknown validation failure'), check
        return True, 'ok', check
    except Exception as exc:
        return False, str(exc), {}
    finally:
        if old is None:
            os.environ.pop('FFMPEG_EXE', None)
        else:
            os.environ['FFMPEG_EXE'] = old
        try:
            PREFLIGHT.unlink()
        except Exception:
            pass


def write_state(payload: dict):
    STATE.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--screenshots-only', action='store_true', help='Explicitly skip video capture.')
    args = ap.parse_args()

    LOG.write_text('Electronic Customs Records Auditor v1.7 - RUN_ALL diagnostic log\n', encoding='utf-8')
    log(f'Python: {sys.executable}')
    log(f'Python version: {sys.version.split()[0]}')

    if os.name != 'nt':
        log('[ERROR] Natural desktop capture requires Windows 10/11.')
        write_state({'recording': False, 'fatal': True, 'reason': 'not_windows'})
        return 2
    if not can_import_tk():
        write_state({'recording': False, 'fatal': True, 'reason': 'tkinter_missing'})
        return 3

    if args.screenshots_only:
        log('[OK] Explicit screenshot-only mode selected. MP4 validation is intentionally skipped.')
        write_state({'recording': False, 'fatal': False, 'explicit_screenshots_only': True})
        return 0

    candidates = candidate_ffmpegs()
    if not candidates:
        img = ensure_imageio_ffmpeg()
        if img:
            candidates = [(img, 'imageio-ffmpeg')]

    # Smoke-test every available candidate because a generic FFmpeg build may not include gdigrab.
    tested = set()
    for ffmpeg, source in candidates:
        key = str(Path(ffmpeg).resolve()).lower()
        if key in tested:
            continue
        tested.add(key)
        log(f'[INFO] Testing desktop capture via {source}: {ffmpeg}')
        ok, reason, check = smoke_test(ffmpeg, fps=15)
        if ok:
            log(f"[OK] Recording preflight passed · {check.get('duration_seconds', 0):.2f}s · {check.get('size_bytes', 0)} bytes")
            write_state({
                'recording': True,
                'validated': True,
                'ffmpeg': ffmpeg,
                'source': source,
                'fps': 20,
                'preflight': check,
            })
            return 0
        log(f'[WARNING] Capture preflight failed via {source}: {reason}')

    # If system FFmpeg failed, install/try imageio-ffmpeg as a controlled fallback.
    img = ensure_imageio_ffmpeg()
    if img:
        key = str(Path(img).resolve()).lower()
        if key not in tested:
            log(f'[INFO] Retesting with imageio-ffmpeg: {img}')
            ok, reason, check = smoke_test(img, fps=15)
            if ok:
                log(f"[OK] Recording preflight passed · {check.get('duration_seconds', 0):.2f}s · {check.get('size_bytes', 0)} bytes")
                write_state({
                    'recording': True,
                    'validated': True,
                    'ffmpeg': img,
                    'source': 'imageio-ffmpeg',
                    'fps': 20,
                    'preflight': check,
                })
                return 0
            log(f'[WARNING] imageio-ffmpeg capture preflight failed: {reason}')

    log('[ERROR] MP4 recording could not be prepared or verified.')
    log('[ERROR] v1.7 RUN_ALL requires a working video recorder; the portfolio sequence will NOT start without one.')
    log('[INFO] You can still run RUN_SCREENSHOTS_ONLY.bat if you only need milestone images.')
    write_state({'recording': False, 'fatal': True, 'reason': 'desktop_capture_preflight_failed'})
    return 4


if __name__ == '__main__':
    raise SystemExit(main())
