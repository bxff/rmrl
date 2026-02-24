# Lazy-loaded texture manager for rmrl raster pen rendering.
#
# Textures are loaded on first access, so vector-only mode
# doesn't require PyQt5.

from pathlib import Path


class PencilTextures:
    def __init__(self):
        self._textures_linear = None
        self._textures_log = None
        self._textures_log_paintbrush = None

    def _ensure_loaded(self):
        """Lazy-load textures on first access."""
        if self._textures_log is not None:
            return

        from PyQt5.QtGui import QImage

        self._textures_linear = []
        texpath = Path(__file__).parent / 'pencil_textures_linear'
        for p in sorted(texpath.glob('*.ppm')):
            img = QImage()
            img.load(str(p))
            self._textures_linear.append(img)

        self._textures_log = []
        texpath = Path(__file__).parent / 'pencil_textures_log'
        for p in sorted(texpath.glob('*.ppm')):
            img = QImage()
            img.load(str(p))
            self._textures_log.append(img)

        self._textures_log_paintbrush = []
        texpath = Path(__file__).parent / 'paintbrush_textures_log'
        for p in sorted(texpath.glob('*.ppm')):
            img = QImage()
            img.load(str(p))
            self._textures_log_paintbrush.append(img)

    def get_linear(self, val):
        self._ensure_loaded()
        scale = len(self._textures_linear)
        i = int(val * scale)
        if i < 0:
            i = 0
        if i >= scale:
            i = scale - 1
        return self._textures_linear[i]

    def get_log(self, val):
        self._ensure_loaded()
        scale = len(self._textures_log)
        # These values were reached by trial-and-error.
        if val < 0:
            val = 0
        i = int(0.25 * (val * scale)**1.21)
        if i < 0:
            i = 0
        if i >= scale:
            i = scale - 1
        return self._textures_log[i]

    def get_log_paintbrush(self, val):
        self._ensure_loaded()
        scale = len(self._textures_log_paintbrush)
        if val < 0:
            val = 0
        i = int(0.25 * (val * scale)**1.21)
        if i < 0:
            i = 0
        if i >= scale:
            i = scale - 1
        return self._textures_log_paintbrush[i]


# Singleton instance — textures are lazy-loaded on first use
PENCIL_TEXTURES = PencilTextures()
