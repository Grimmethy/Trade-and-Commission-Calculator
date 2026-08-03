"""ZPL label generation + printing for inventory items, ported from
~/screaming-goat/scripts/print_labels.py. The ZPL-building functions
(pick_font_size, format_price, esc, image_to_zpl_gf, logo_to_zpl_gf, make_zpl)
are carried over near-verbatim — they were already pure and reusable there.
What changed: config comes from env vars instead of hardcoded constants
(matching DATABASE_PATH's pattern), and printing is gated by PRINT_ENABLED so
a deployment with no attached printer (e.g. a future hosted instance) fails
with a clear message instead of hanging on `lp` against a nonexistent queue."""

import os
import subprocess
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from app.models import InventoryItem

PRINTER = os.environ.get("LABEL_PRINTER", "4B-2063C")
LOGO_FILE = os.environ.get(
    "LOGO_PATH", str(Path(__file__).resolve().parent / "static" / "branding" / "logo.png")
)
OUTPUT_DIR = os.environ.get("LABEL_OUTPUT_DIR", "labels/output")
PRINT_ENABLED = os.environ.get("PRINT_ENABLED", "true").lower() == "true"

# 4x6 label at 203 DPI — fixed by the physical label stock + printer, not deployment config.
LABEL_W = 812
LABEL_H = 1218

# Product image area
IMG_X = 10
IMG_Y = 590
IMG_W_DOTS = 792  # must be multiple of 8
IMG_H_DOTS = 608


def pick_font_size(text):
    """Return (height, width) for ^A0N to fit text in ~772 usable dots."""
    n = len(text)
    if n <= 14:
        return (120, 72)
    if n <= 20:
        return (96, 56)
    if n <= 32:
        return (64, 40)
    return (48, 28)


def format_price(raw):
    try:
        return f"${float(raw):.2f}"
    except (ValueError, TypeError):
        return raw.strip() if raw and raw.strip() else "TBD"


def esc(s):
    """Escape ZPL field delimiters."""
    return str(s).replace("^", "").replace("~", "").strip()


def image_to_zpl_gf(image_path, width_dots, height_dots):
    """
    Load an image, convert to dithered 1-bit, return a ZPL ^GF field string.
    Uses ASCII hex encoding — no raw binary, no protocol issues.
    """
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("L")

    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(2.2)

    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.0)

    img.thumbnail((width_dots, height_dots), Image.LANCZOS)
    canvas = Image.new("L", (width_dots, height_dots), 255)
    paste_x = (width_dots - img.width) // 2
    paste_y = (height_dots - img.height) // 2
    canvas.paste(img, (paste_x, paste_y))

    mono = canvas.convert("1")
    width_bytes = width_dots // 8  # width_dots is a multiple of 8
    total_bytes = width_bytes * height_dots

    # PIL "1" tobytes: 0-bit=black. ZPL ^GF: 1-bit=black. Invert.
    raw = mono.tobytes()
    inverted = bytes(b ^ 0xFF for b in raw)
    hex_data = inverted.hex().upper()

    return f"^GFA,{total_bytes},{total_bytes},{width_bytes},{hex_data}"


def logo_to_zpl_gf(logo_path, max_w, max_h):
    """Convert logo file to a ^GF field sized to fit the logo box."""
    return image_to_zpl_gf(logo_path, max_w, max_h)


def make_zpl(sku, name, qty, price, notes, image_path=None):
    fh, fw = pick_font_size(name)
    price_str = format_price(price)
    notes_str = esc(notes) if notes.strip() else "N/A"

    # --- Logo section ---
    if os.path.exists(LOGO_FILE):
        logo_gf = logo_to_zpl_gf(LOGO_FILE, 208, 112)  # fits in 210x120 box
        logo_section = f"^FO20,14{logo_gf}^FS"
    else:
        logo_section = (
            "^FO20,15^GB210,120,2^FS\n"
            "^FO55,62^A0N,24,14^FD[ LOGO ]^FS"
        )

    # --- Product image section ---
    if image_path and os.path.exists(image_path):
        try:
            gf = image_to_zpl_gf(image_path, IMG_W_DOTS, IMG_H_DOTS)
            image_section = f"^FO{IMG_X},{IMG_Y}{gf}^FS"
        except Exception as e:
            print(f"  Warning: image skipped — {e}")
            image_section = f"^FO20,530^A0N,24,14^FDImage unavailable^FS"
    else:
        image_section = f"^FO20,530^A0N,24,14^FDNo image on file^FS"

    return (
        f"^XA\n"
        f"^PW{LABEL_W}\n"
        f"^LL{LABEL_H}\n"
        f"^LH0,0\n"
        f"\n"
        # Outer border
        f"^FO10,10^GB{LABEL_W-20},{LABEL_H-20},3^FS\n"
        f"\n"
        # Header: logo + company name
        f"{logo_section}\n"
        f"^FO245,22^A0N,80,48^FDScreaming Goat^FS\n"
        f"^FO245,112^A0N,56,32^FDCollectibles^FS\n"
        f"^FO10,185^GB{LABEL_W-20},2,2^FS\n"
        f"\n"
        # SKU + item name
        f"^FO20,200^A0N,56,32^FDSKU: {esc(sku)}^FS\n"
        f"^FO20,270^A0N,{fh},{fw}^FD{esc(name)}^FS\n"
        f"^FO10,415^GB{LABEL_W-20},2,2^FS\n"
        f"\n"
        # Qty + Price
        f"^FO20,430^A0N,56,32^FDQty: {esc(qty)}^FS\n"
        f"^FO430,430^A0N,56,32^FDPrice: {price_str}^FS\n"
        f"^FO10,500^GB{LABEL_W-20},2,2^FS\n"
        f"\n"
        # Notes
        f"^FO20,515^A0N,48,28^FDNotes: {notes_str}^FS\n"
        f"^FO10,575^GB{LABEL_W-20},2,2^FS\n"
        f"\n"
        # Product image
        f"{image_section}\n"
        f"\n"
        f"^XZ\n"
    )


def send_to_printer(zpl_path):
    # DUMP MODE: if the printer outputs raw ZPL text instead of rendering,
    # it's stuck in dump mode. ~JN (cancel dump) does NOT reliably exit it
    # on this firmware. Fix: run `printf '~JR\n' | lp -d 4B-2063C -o raw -`
    # to reset the printer, wait ~15s for reboot, then reprint. Power cycling
    # also works. This has bitten us multiple times — don't waste time on ~JN.
    if not PRINT_ENABLED:
        return False, "Printing is disabled on this instance (PRINT_ENABLED=false) — run this locally, where the printer is actually attached."
    result = subprocess.run(["lp", "-d", PRINTER, zpl_path], capture_output=True, text=True)
    return result.returncode == 0, result.stderr.strip()


def build_label_zpl(
    item: InventoryItem, photo_path: Path | str | None, price_override: float | None = None
) -> str:
    """Maps an inventory item + its chosen photo onto make_zpl's signature.
    Price defaults to item.label_price (sp_max -> sp_min -> third_party_price,
    or sell_price once sold) — price_override lets a human type a different
    number at print time without overwriting the stored pricing data."""
    price = price_override if price_override is not None else item.label_price
    return make_zpl(
        sku=item.sku,
        name=item.name,
        qty=item.qty,
        price=price,
        notes=item.notes or "",
        image_path=str(photo_path) if photo_path else None,
    )
