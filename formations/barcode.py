"""
formations/barcode.py

Dependency-free Code 128 (subset B) barcode rendered as an inline SVG data URI.
Used on the attestation to carry the verification URL.
"""

import base64

# Bar/space width patterns (11 modules each), index = Code 128 symbol value.
_PATTERNS = (
    "11011001100", "11001101100", "11001100110",
    "10010011000", "10010001100", "10001001100",
    "10011001000", "10011000100", "10001100100",
    "11001001000", "11001000100", "11000100100",
    "10110011100", "10011011100", "10011001110",
    "10111001100", "10011101100", "10011100110",
    "11001110010", "11001011100", "11001001110",
    "11011100100", "11001110100", "11101101110",
    "11101001100", "11100101100", "11100100110",
    "11101100100", "11100110100", "11100110010",
    "11011011000", "11011000110", "11000110110",
    "10100011000", "10001011000", "10001000110",
    "10110001000", "10001101000", "10001100010",
    "11010001000", "11000101000", "11000100010",
    "10110111000", "10110001110", "10001101110",
    "10111011000", "10111000110", "10001110110",
    "11101110110", "11010001110", "11000101110",
    "11011101000", "11011100010", "11011101110",
    "11101011000", "11101000110", "11100010110",
    "11101101000", "11101100010", "11100011010",
    "11101111010", "11001000010", "11110001010",
    "10100110000", "10100001100", "10010110000",
    "10010000110", "10000101100", "10000100110",
    "10110010000", "10110000100", "10011010000",
    "10011000010", "10000110100", "10000110010",
    "11000010010", "11001010000", "11110111010",
    "11000010100", "10001111010", "10100111100",
    "10010111100", "10010011110", "10111100100",
    "10011110100", "10011110010", "11110100100",
    "11110010100", "11110010010", "11011011110",
    "11011110110", "11110110110", "10101111000",
    "10100011110", "10001011110", "10111101000",
    "10111100010", "11110101000", "11110100010",
    "10111011110", "10111101110", "11101011110",
    "11110101110", "11010000100", "11010010000",
    "11010011100",
)
_STOP = "11000111010"  # 11 modules; the final 2-module bar is appended on encode
_START_B = 104


def code128b_modules(text):
    """Return the module string ('1' = bar, '0' = space) for `text`."""
    values = []
    for ch in text:
        o = ord(ch)
        if not 32 <= o <= 126:
            raise ValueError("Code128-B only supports printable ASCII")
        values.append(o - 32)
    checksum = (_START_B + sum(v * (i + 1) for i, v in enumerate(values))) % 103
    seq = [_START_B] + values + [checksum]
    return "".join(_PATTERNS[v] for v in seq) + _STOP + "11"


def code128_svg_data_uri(text, bar_height=60, quiet=10):
    """Render `text` as a Code 128 barcode; returns a data: URI (SVG) or ''."""
    try:
        modules = code128b_modules(text)
    except ValueError:
        return ""
    # Merge consecutive bars into single rects to keep the SVG small.
    rects, x, n = [], 0, len(modules)
    while x < n:
        if modules[x] == "1":
            start = x
            while x < n and modules[x] == "1":
                x += 1
            rects.append(f'<rect x="{quiet + start}" y="0" width="{x - start}" height="{bar_height}"/>')
        else:
            x += 1
    width = n + 2 * quiet
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {bar_height}" '
        f'preserveAspectRatio="none" shape-rendering="crispEdges">'
        f'<rect width="{width}" height="{bar_height}" fill="#fff"/>'
        f'<g fill="#000">{"".join(rects)}</g></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode("ascii")
