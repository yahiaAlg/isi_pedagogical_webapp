"""
documents/certificate_layout.py

Shared layout definitions for the attestation ("شهادة تكوين تأهيلي"),
ported verbatim from the standalone certificate_project prototype
(certificate_generator_html.py) — pixel-exact field boxes + fixed
institutional text, consumed by the on-screen/print HTML templates
(documents/print/attestation.html, batch_attestations.html) via
boxes_css()/column_offsets().

CANVAS_SIZE is the native resolution of the border artwork
(static/documents/img/attestation_border.jpg).
"""

# --------------------------------------------------------------------------
# 1. CANVAS  (native pixel size of attestation_border.jpg)
# --------------------------------------------------------------------------
CANVAS_SIZE = (1294, 861)

# --------------------------------------------------------------------------
# 2. FIELD BOXES  -- (x0, y0, x1, y1) in pixels on the CANVAS above.
#    Pixel-exact match of the standalone reference (certificate_output.html /
#    certificate_generator_html.py). `qr_box` is new: it sits directly below
#    the director signature block (same column, in the empty band before the
#    agrement/IF line) so it doesn't collide with any other field.
# --------------------------------------------------------------------------
BOXES = {
    "serial_year_box": (237, 206, 404, 230),  # "شهادة : ح.ط/{ANNEE}"
    "serial_num_box": (138, 230, 379, 264),  # "رقم التسلسلي : ..."
    "header_box": (
        374,
        91,
        916,
        265,
    ),  # republic / ministry / institute (4 lines, static)
    "title_box": (400, 261, 880, 347),  # "شهادة تكوين تأهيلي" (static)
    "logo_box": (931, 97, 1087, 234),  # institute logo
    "qr_box": (315, 700, 735, 770),  # verification QR — under the director signature
    "legal_box": (110, 350, 1169, 495),  # legal decree paragraphs + CIP line
    "attest_line_box": (968, 510, 1169, 530),  # "يشهد أن:" (static)
    "french_fields_box": (178, 535, 697, 684),
    "arabic_fields_box": (709, 535, 1121, 682),
    "director_box": (640, 665, 766, 719),  # static "المدير / Le Directeur"
    "date_box": (904, 693, 1161, 729),
    "no_copy_box": (850, 738, 1050, 758),  # "لا تسلم نسخة أخرى من الشهادة" (static)
    "agrement_box": (118, 792, 290, 813),
    "if_box": (1000, 792, 1179, 822),
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
#    Every value is wrapped in calc(...px * var(--s,1)) rather than a bare
#    px value. On screen --s is 1 (a no-op). For print, --s is set to
#    print_zoom() (see below) so the *real* box model shrinks to fit A4 —
#    this is deliberately not done with `zoom` or `transform`, both of
#    which turned out to be ignored or mis-measured by Chrome's print
#    pagination/auto-fit logic (it either double-shrank the page or
#    computed page breaks off the un-scaled size and produced a blank
#    extra page). calc() with a real px unit is a genuine layout value,
#    so there's nothing left for the browser to get wrong.
# --------------------------------------------------------------------------
def box_css(box, extra: str = "") -> str:
    x0, y0, x1, y1 = box
    return (
        f"left:calc({x0}px * var(--s,1));"
        f"top:calc({y0}px * var(--s,1));"
        f"width:calc({x1 - x0}px * var(--s,1));"
        f"height:calc({y1 - y0}px * var(--s,1));{extra}"
    )


def boxes_css() -> dict:
    """Pre-computed {box_name: css_style_string} for every entry in BOXES,
    for use in the print/download HTML templates."""
    return {name: box_css(box) for name, box in BOXES.items()}


# --------------------------------------------------------------------------
# 5. PRINT SCALING -- "Save as PDF" honors the exact @page size, so the
#    certificate always fits it perfectly. A real printer only offers
#    standard paper (A4), which is smaller than the certificate's native
#    canvas, so without this the browser has to auto-shrink the page and
#    tends to leave the unused height as blank space rather than
#    centering it.
#
#    print_zoom() is the CSS custom property --s used throughout this
#    file's calc() expressions (box positions, font sizes, canvas size —
#    see _certificate_style.html's @media print block): under print it's
#    set to this value everywhere at once, so the certificate becomes a
#    genuinely smaller, real-sized element that already fits A4 with no
#    further browser-side auto-fit needed.
# --------------------------------------------------------------------------
_A4_LANDSCAPE_PX = (1122.52, 793.70)  # 297mm x 210mm at 96dpi


def print_zoom() -> float:
    scale_w = _A4_LANDSCAPE_PX[0] / CANVAS_SIZE[0]
    scale_h = _A4_LANDSCAPE_PX[1] / CANVAS_SIZE[1]
    return round(min(scale_w, scale_h), 4)


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
