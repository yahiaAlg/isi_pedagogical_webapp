"""
documents/certificate_layout.py

Shared layout definitions for the attestation ("شهادة تكوين تأهيلي"),
ported verbatim from the standalone certificate_project prototype
(certificate_generator_html.py) — pixel-exact field boxes + fixed
institutional text, consumed by the on-screen/print HTML templates
(documents/print/attestation.html, batch_attestations.html) via
boxes_css()/column_offsets().

CANVAS_SIZE is the pixel size of the border artwork
(static/documents/img/attestation_border.jpg), which has been stretched
to exactly match the A4 landscape aspect ratio (297:210 = 1.41429). The
artwork's native scan was 1294x861 (ratio 1.503) — a 6% mismatch with A4
that no amount of print-side scaling could fully resolve without leaving
a blank strip on real printers. It was resized once, non-uniformly
(area-preserving: ~2.9% narrower, ~3.1% taller), to 1256x888 (ratio
1.41441, within 0.01% of true A4) so that screen preview, browser print,
and "Save as PDF" are all now the *same* exact-fit rendering with no
special-casing. BOXES below are defined directly on this baked canvas.
"""

# --------------------------------------------------------------------------
# 1. CANVAS  (pixel size of attestation_border.jpg, baked to A4 ratio)
# --------------------------------------------------------------------------
CANVAS_SIZE = (1256, 888)

# --------------------------------------------------------------------------
# 2. FIELD BOXES  -- (x0, y0, x1, y1) in pixels on the CANVAS above.
#    Pixel-exact match of the standalone reference (certificate_output.html /
#    certificate_generator_html.py). `qr_box` is new: it sits directly below
#    the director signature block (same column, in the empty band before the
#    agrement/IF line) so it doesn't collide with any other field.
# --------------------------------------------------------------------------
BOXES = {
    "serial_year_box": (230, 212, 392, 237),  # "شهادة : ح.ط/{ANNEE}"
    "serial_num_box": (134, 237, 368, 272),  # "رقم التسلسلي : ..."
    "header_box": (
        363,
        94,
        889,
        273,
    ),  # republic / ministry / institute (4 lines, static)
    "title_box": (388, 269, 854, 358),  # "شهادة تكوين تأهيلي" (static)
    "logo_box": (904, 100, 1055, 241),  # institute logo
    "qr_box": (306, 722, 713, 794),  # verification QR — under the director signature
    "legal_box": (107, 361, 1135, 511),  # legal decree paragraphs + CIP line
    "attest_line_box": (940, 526, 1135, 547),  # "يشهد أن:" (static)
    "french_fields_box": (173, 552, 677, 705),
    "arabic_fields_box": (688, 552, 1088, 703),
    "director_box": (621, 686, 744, 742),  # static "المدير / Le Directeur"
    "date_box": (877, 715, 1127, 752),
    "no_copy_box": (825, 761, 1019, 782),  # "لا تسلم نسخة أخرى من الشهادة" (static)
    "agrement_box": (115, 817, 281, 838),
    "if_box": (971, 817, 1144, 848),
}

# --------------------------------------------------------------------------
# 3. STATIC TEXT (never changes between certificates) -- ported verbatim.
# --------------------------------------------------------------------------
STATIC = {
    "header_lines": [
        "الجمهورية الجزائرية الديمقراطية الشعبية",
        "وزارة التكوين و التعليم المهنيين",
        "مؤسسة خاصة لتكوين المهني معـتمدة",
        "التميز للإدارة و السلامة",
    ],
    "title": "شهادة تكوين تأهيلي",
    "legal_lines": [
        "بمقتضى المرسوم التنفيذي رقم 18-162 المؤرخ في 29 رمضان 1439 الموافق 14 يونيو 2018 "
        "الذي يحدد شروط إنشاء المؤسسة الخاصة للتكوين أو التعليم المهني وفتحها ومراقبتها.",
        "بمقتضى القرار الوزاري المؤرخ في 4 نوفمبر 2018 الذي يحدد دفتر الشروط المتعلق بإنشاء "
        "المؤسسة الخاصة للتكوين أو التعليم المهني وفتحها ومراقبتها.",
        "بمقتضى القرار الوزاري رقم 003 المؤرخ في 14 مارس 2022 المتضمن اعتماد المؤسسة الخاصة "
        "للتكوين المهني المسماة: التميز للإدارة و السلامة",
        "و بناءا على مقرر الفتح رقم 055 المؤرخ 18 أفريل 2022 يتضمن فتح المؤسسة الخاصة للتكوين المهني",
    ],
    "cip_prefix": "وبناءا على محضر نهاية التكوين :",
    "attest_line": "يشهد أن:",
    "director_ar": "المدير",
    "director_fr": "Le Directeur",
    "no_copy": "لا تسلم نسخة أخرى من الشهادة",
    "date_prefix": "حرر ب سطيف في : ",
    "agrement_prefix": "Agrément n° ",
    "if_prefix": "IF n° ",
    "suivi_line": "A suivi une session de formation qualifiante professionnelle à la carte",
    "qadtabi_line": "قد تابع (ت) دورة في التكوين المهني التأهيلي حسب الطلب",
}


# --------------------------------------------------------------------------
# 4. HTML helper -- turns a BOXES tuple into an absolutely-positioned style
#    string, matching exactly the region the PIL renderer draws into.
#    Ported from certificate_project/certificate_generator_html.py.
#
#    Plain px values. No print-time rescaling is needed: the canvas itself
#    (CANVAS_SIZE / attestation_border.jpg) is already baked to the A4
#    aspect ratio, so `@page { size: {{ canvas_w }}px {{ canvas_h }}px }`
#    in _certificate_style.html fits real A4 paper exactly on its own —
#    screen preview, browser print, and "Save as PDF" all render this one
#    unscaled box model.
# --------------------------------------------------------------------------
def box_css(box, extra: str = "") -> str:
    x0, y0, x1, y1 = box
    return f"left:{x0}px;top:{y0}px;width:{x1 - x0}px;height:{y1 - y0}px;{extra}"


def boxes_css() -> dict:
    """Pre-computed {box_name: css_style_string} for every entry in BOXES,
    for use in the print/download HTML templates."""
    return {name: box_css(box) for name, box in BOXES.items()}


# --------------------------------------------------------------------------
# Two-column split used inside french_fields_box / arabic_fields_box (both
# the PIL renderer and the HTML template split the second column at 55% of
# the box's own width, mirrored for the RTL Arabic box).
# --------------------------------------------------------------------------
def column_offsets() -> dict:
    fb = BOXES["french_fields_box"]
    ab2 = BOXES["arabic_fields_box"]
    return {
        "french_col2_left": int((fb[2] - fb[0]) * 0.55),
        "arabic_col2_right": int((ab2[2] - ab2[0]) * (1 - 0.55)),
    }
