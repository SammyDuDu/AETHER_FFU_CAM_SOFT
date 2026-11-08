"""
eMMC cleanup: free eMMC space by deleting recordings that are safely on the SD card.

When eMMC usage passes THRESHOLD_PERCENT, delete the oldest finished
camera{N}[_k].h264 files from the eMMC streams dir, but ONLY if the SD card has
a file with the same name and the same size (i.e. a complete copy).

Never touched:
- the newest file of each camera (the one the pipeline may still be writing;
  deleting an open file would not free space anyway)
- files with no identical copy on the SD card
"""

import logging
import os
import re
import shutil

logger = logging.getLogger(__name__)

THRESHOLD_PERCENT = 75
_NAME = re.compile(r"camera(\d+)(?:_(\d+))?\.h264$")


def _candidates(emmc_dir):
    """Finished eMMC recordings, oldest first (the newest per camera is excluded)."""
    by_cam = {}
    for entry in os.listdir(emmc_dir):
        m = _NAME.match(entry)
        if m:
            by_cam.setdefault(m.group(1), []).append((int(m.group(2) or 0), entry))
    out = []
    for files in by_cam.values():
        files.sort()
        out += [name for _, name in files[:-1]]
    return sorted(out, key=lambda n: os.path.getmtime(os.path.join(emmc_dir, n)))


def cleanup_emmc(emmc_dir, sd_dir, threshold=THRESHOLD_PERCENT):
    """Delete SD-verified eMMC recordings until usage < threshold. Returns bytes freed."""
    freed = 0
    try:
        for name in _candidates(emmc_dir):
            u = shutil.disk_usage(emmc_dir)
            if u.used * 100 / u.total < threshold:
                break
            src, dup = os.path.join(emmc_dir, name), os.path.join(sd_dir, name)
            if not os.path.isfile(dup) or os.path.getsize(dup) != os.path.getsize(src):
                continue
            size = os.path.getsize(src)
            os.remove(src)
            freed += size
            logger.warning(f"eMMC over {threshold}%: deleted {name} ({size} bytes, copy on SD)")
    except OSError as e:
        logger.error(f"eMMC cleanup failed: {e}")
    return freed
