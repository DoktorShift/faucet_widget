# SPDX-License-Identifier: AGPL-3.0-or-later
"""QR-code generation for LNURL strings.

We render as an SVG path string and inline it in the JSON response. SVG is
sharper than PNG at any size and a few hundred bytes smaller for typical
LNURLs. Frontends use it directly: `<div v-html="resp.qr_svg" />`.
"""

from __future__ import annotations

from io import BytesIO

import qrcode
from qrcode.image.svg import SvgPathImage


def make_qr_svg(data: str, *, box_size: int = 10, border: int = 1) -> str:
    """Return an SVG string for a QR code encoding `data`.

    The error-correction level is M (15%), a good tradeoff for LNURL strings:
    H would inflate the size without practical benefit on a screen.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    buffer = BytesIO()
    img = qr.make_image(image_factory=SvgPathImage)
    img.save(buffer)
    return buffer.getvalue().decode("utf-8")
