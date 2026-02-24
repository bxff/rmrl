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

from .generic import GenericPen, pairs
from .textures import PENCIL_TEXTURES

class PencilPen(GenericPen):

    def set_segment_properties(self, canvas, segment, nextsegment):
        basewidth = segment.width
        deltamax = 0.42 * basewidth
        delta = -deltamax
        prim_width = basewidth + delta
        canvas.setLineWidth(prim_width)

        stroke_color = [1 - (1 - c) * segment.pressure for c in self.color]
        canvas.setStrokeColor(stroke_color)

    def set_segment_properties_raster(self, canvas, segment, nextsegment):
        """Raster mode: use texture brush instead of color blending."""
        basewidth = segment.width
        deltamax = 0.42 * basewidth
        delta = -deltamax
        prim_width = basewidth + delta
        canvas.setLineWidth(prim_width)

        texture = PENCIL_TEXTURES.get_log(segment.pressure)
        canvas.setTextureBrush(texture)

    def paint_stroke(self, canvas, stroke):
        """Override to add spatter pass in raster mode."""
        canvas.saveState()
        canvas.setLineCap(1)  # Rounded
        canvas.setLineJoin(1)  # Round join
        canvas.setStrokeColor(self.color)

        use_raster = PENCIL_TEXTURES is not None and hasattr(canvas, 'setTextureBrush')

        for p1, p2 in pairs(stroke.segments):
            if use_raster:
                # Primary stroke with texture
                self.set_segment_properties_raster(canvas, p1, p2)
                canvas.line(p1.x, p1.y, p2.x, p2.y)

                # Spatter stroke (wider, lighter texture)
                basewidth = p1.width
                deltamax = 0.42 * basewidth
                prim_width = basewidth - deltamax
                spat_width = prim_width * 1.25
                canvas.setLineWidth(spat_width)
                texture = PENCIL_TEXTURES.get_log(p1.pressure * 0.7)
                canvas.setTextureBrush(texture)
                canvas.line(p1.x, p1.y, p2.x, p2.y)
            else:
                self.set_segment_properties(canvas, p1, p2)
                canvas.line(p1.x, p1.y, p2.x, p2.y)

        canvas.restoreState()
