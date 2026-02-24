# Copyright (C) 2020  Davis Remmel
# Copyright 2021 Robert Schroll
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import gc
import io
import json
import logging

from reportlab.graphics import renderPDF
from reportlab.lib.utils import ImageReader
from svglib.svglib import svg2rlg

from . import lines, pens
from .constants import DISPLAY, PDFHEIGHT, PDFWIDTH, PTPERPX, TEMPLATE_PATH


log = logging.getLogger(__name__)

class DocumentPage:
    # A single page in a document
    def __init__(self, source, pid, pagenum):
        # Page 0 is the first page!
        self.source = source
        self.num = pagenum

        # On disk, these files are named by a UUID
        self.rmpath = f'{{ID}}/{pid}.rm'
        if not source.exists(self.rmpath):
            # From the API, these files are just numbered
            pid = str(pagenum)
            self.rmpath = f'{{ID}}/{pid}.rm'

        # Try to load page metadata
        self.metadict = None
        metafilepath = f'{{ID}}/{pid}-metadata.json'
        if source.exists(metafilepath):
            with source.open(metafilepath, 'r') as f:
                self.metadict = json.load(f)

        # Try to load template
        self.template = None
        templatefilepath = f'{{ID}}.pagedata'
        if source.exists(templatefilepath):
            with source.open(templatefilepath, 'r') as f:
                templatenames = f.read().splitlines()
            if pagenum < len(templatenames):
                templatename = templatenames[pagenum]
                templatefile = TEMPLATE_PATH / (templatename + '.svg')
                if templatefile.exists():
                    self.template = str(templatefile)

        # Load page
        self.layers = []
        if not source.exists(self.rmpath):
            return

        with source.open(self.rmpath, 'rb') as f:
            page_version, layerdata = lines.readLines(f)

        for i, layerstrokes in enumerate(layerdata):
            name = 'Layer ' + str(i + 1)

            try:
                name = self.metadict['layers'][i]['name']
            except:
                pass

            layer = DocumentPageLayer(self, name=name)
            layer.strokes = layerstrokes
            self.layers.append(layer)

    def render_to_painter(self, canvas, vector, template_alpha):
        # Render template layer
        if self.template:
            if template_alpha > 0:
                background = svg2rlg(self.template)
                background.scale(PDFWIDTH / background.width, PDFWIDTH / background.width)
                renderPDF.draw(background, canvas, 0, 0)
                if template_alpha < 1:
                    canvas.saveState()
                    canvas.setFillColorRGB(1., 1., 1.)
                    canvas.setFillAlpha(1 - template_alpha)
                    canvas.rect(0, 0, PDFWIDTH, PDFHEIGHT, fill=True, stroke=False)
                    canvas.restoreState()

        if vector:
            # Vector mode: apply coordinate transform and render directly
            canvas.translate(0, PDFHEIGHT)
            canvas.scale(PTPERPX, -PTPERPX)
            for layer in self.layers:
                layer.render_to_painter(canvas, vector)
        else:
            # Raster mode: render all layers to a QImage, then embed
            # in the PDF as a PNG image. This enables texture brushes.
            self._render_raster_layers(canvas)

        canvas.showPage()

    def _render_raster_layers(self, pdf_canvas):
        """Render all layers to a QImage and embed in PDF."""
        from PyQt5.QtCore import Qt, QBuffer, QIODevice
        from PyQt5.QtGui import QImage, QPainter
        from .qpainter_canvas import QPainterCanvas

        scale = 4  # 4x device resolution — good detail when zoomed in
                   # (higher = better zoom quality, more memory/file size)
        img_w = DISPLAY['screenwidth'] * scale
        img_h = DISPLAY['screenheight'] * scale

        # Pre-allocate buffer to avoid QImage memory corruption
        bytespp = 4
        buf = bytearray(img_w * img_h * bytespp)
        qimage = QImage(buf, img_w, img_h, img_w * bytespp,
                        QImage.Format_ARGB32)
        qimage.fill(Qt.white)

        imgpainter = QPainter(qimage)
        imgpainter.setRenderHint(QPainter.Antialiasing)
        imgpainter.scale(scale, scale)

        # Use the adapter so pen classes work with QPainter
        adapter = QPainterCanvas(imgpainter)
        for layer in self.layers:
            layer.paint_strokes(adapter, vector=False)
        imgpainter.end()

        # Convert QImage to PNG bytes
        qbuffer = QBuffer()
        qbuffer.open(QIODevice.WriteOnly)
        qimage.save(qbuffer, 'PNG')
        qbuffer.close()
        png_buf = io.BytesIO(bytes(qbuffer.data()))

        # Draw into PDF at full page size (no transform needed —
        # we're in the original PDF coordinate space)
        img_reader = ImageReader(png_buf)
        pdf_canvas.drawImage(img_reader,
                             0, 0,
                             PDFWIDTH, PDFHEIGHT,
                             preserveAspectRatio=False)

        del imgpainter
        del qimage
        del buf
        gc.collect()

    def get_grouped_annotations(self):
        annots = []
        for layer in self.layers:
            annots.append(layer.get_grouped_annotations())
        return annots


class DocumentPageLayer:
    pen_widths = []

    def __init__(self, page, name=None):
        self.page = page
        self.name = name

        self.colors = [
            (0, 0, 0),
            (0.5, 0.5, 0.5),
            (1, 1, 1)
        ]

        # Set this from the calling func
        self.strokes = None

        # Store PDF annotations with the layer, in case actual
        # PDF layers are ever implemented.
        self.annot_paths = []

    def get_grouped_annotations(self):
        # return: (LayerName, [(AnnotType, minX, minY, maxX, maxY)])

        # Compare all the annot_paths to each other. If any overlap,
        # they will be grouped together. This is done recursively.
        def grouping_func(pathset):
            newset = []

            for p in pathset:
                annotype = p[0]
                path = p[1]
                did_fit = False
                for i, g in enumerate(newset):
                    gannotype = g[0]
                    group = g[1]
                    # Only compare annotations of the same type
                    if gannotype != annotype:
                        continue
                    if path.intersects(group):
                        did_fit = True
                        newset[i] = (annotype, group.united(path))
                        break
                if did_fit:
                    continue
                # Didn't fit, so place into a new group
                newset.append(p)

            if len(newset) != len(pathset):
                # Might have stuff left to group
                return grouping_func(newset)
            else:
                # Nothing was grouped, so done
                return newset

        grouped = grouping_func(self.annot_paths)

        # Get the bounding rect of each group, which sets the PDF
        # annotation geometry.
        annot_rects = []
        for p in grouped:
            annotype = p[0]
            path = p[1]
            rect = path.boundingRect()
            annot = (annotype,
                     float(rect.x()),
                     float(rect.y()),
                     float(rect.x() + rect.width()),
                     float(rect.y() + rect.height()))
            annot_rects.append(annot)

        return (self.name, annot_rects)

    def paint_strokes(self, canvas, vector):
        for stroke in self.strokes:
            pen, color, unk1, width, unk2, segments = stroke

            penclass = pens.PEN_MAPPING.get(pen)
            if penclass is None:
                log.error("Unknown pen code %d" % pen)
                penclass = pens.GenericPen

            qpen = penclass(vector=vector,
                            layer=self,
                            color=self.colors[color])

            # Do the needful
            qpen.paint_stroke(canvas, stroke)

    def render_to_painter(self, painter, vector):
        self.paint_strokes(painter, vector=vector)

