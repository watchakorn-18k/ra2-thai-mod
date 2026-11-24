"""Build Thai-enabled GAME.FNT and shaped CSF files for Red Alert 2 / Yuri's Revenge."""
import os
import struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

THAI_MARKS = set(
    "\u0e31\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a"
    "\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e"
)
THAI_CONSONANTS = set(chr(c) for c in range(0x0E01, 0x0E2F))


def segment_thai_clusters(text: str) -> list[str]:
    """Split text into single chars, except Thai consonant + combining marks (incl. ำ)."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in THAI_CONSONANTS and i + 1 < n:
            j = i + 1
            while j < n and (text[j] in THAI_MARKS or text[j] == "\u0e33"):
                j += 1
            if j > i + 1:
                out.append(text[i:j])
                i = j
                continue
        out.append(ch)
        i += 1
    return out


class ThaiFontBuilder:
    def __init__(self, base_fnt_path: Path, ttf_path: Path, font_size: int = 11):
        data = base_fnt_path.read_bytes()
        magic, max_w, stride, height, pitch, num_glyphs, bpg = struct.unpack_from("<4sIIIIII", data, 0)
        assert magic == b"fonT", f"Bad magic: {magic}"
        assert stride == 3 and height == 16 and bpg == 49
        self.header = (magic, max_w, stride, height, pitch, num_glyphs, bpg)
        self.lut = list(struct.unpack_from("<65536H", data, 28))
        self.glyphs = bytearray(data[28 + 65536 * 2:])
        self.num_glyphs = num_glyphs
        self.font = ImageFont.truetype(str(ttf_path), font_size)
        self.cluster_to_pua: dict[str, str] = {}
        self.next_pua = 0xE000

    def _render_cluster(self, cluster: str) -> bytes:
        # Render on 24x16 canvas (max_w=20, stride=3)
        img = Image.new("L", (24, 16), 0)
        d = ImageDraw.Draw(img)
        d.text((0, 0), cluster, font=self.font, fill=255)
        bbox = img.getbbox()
        adv = int(round(self.font.getlength(cluster)))
        w = max(adv, (bbox[2] if bbox else 0))
        w = max(1, min(20, w))

        glyph = bytearray(49)
        glyph[0] = w
        for y in range(16):
            row_bits = 0
            for x in range(min(w, 20)):
                if img.getpixel((x, y)) > 110:
                    row_bits |= 1 << (23 - x)
            glyph[1 + y * 3] = (row_bits >> 16) & 0xFF
            glyph[1 + y * 3 + 1] = (row_bits >> 8) & 0xFF
            glyph[1 + y * 3 + 2] = row_bits & 0xFF
        return bytes(glyph)

    def add_standalone_thai(self):
        for cp in range(0x0E01, 0x0E5C):
            ch = chr(cp)
            if ch in THAI_MARKS:
                continue
            g = self._render_cluster(ch)
            self.glyphs.extend(g)
            self.num_glyphs += 1
            # GAME.FNT LUT is 1-based (0 = missing, k = glyph[k - 1])
            self.lut[cp] = self.num_glyphs

    def shape_text(self, text: str) -> str:
        res = []
        for cl in segment_thai_clusters(text):
            if len(cl) == 1:
                res.append(cl)
            else:
                if cl not in self.cluster_to_pua:
                    cp = self.next_pua
                    assert cp <= 0xF8FF, "PUA exhausted!"
                    self.next_pua += 1
                    g = self._render_cluster(cl)
                    self.glyphs.extend(g)
                    self.num_glyphs += 1
                    # GAME.FNT LUT is 1-based (0 = missing, k = glyph[k - 1])
                    self.lut[cp] = self.num_glyphs
                    self.cluster_to_pua[cl] = chr(cp)
                res.append(self.cluster_to_pua[cl])
        return "".join(res)

    def save(self, out_path: Path):
        magic, max_w, stride, height, pitch, _, bpg = self.header
        hdr = struct.pack("<4sIIIIII", magic, max_w, stride, height, pitch, self.num_glyphs, bpg)
        lut_bytes = struct.pack("<65536H", *self.lut)
        out_path.write_bytes(hdr + lut_bytes + bytes(self.glyphs))


def read_csf(path: Path):
    data = path.read_bytes()
    magic, ver, n_labels, n_strings, unk, lang = struct.unpack_from("<4sIIIII", data, 0)
    assert magic == b" FSC"
    pos = 24
    entries = []
    for _ in range(n_labels):
        lbl_magic, num_pairs, lbl_len = struct.unpack_from("<4sII", data, pos)
        assert lbl_magic == b" LBL"
        pos += 12
        lbl = data[pos:pos + lbl_len].decode("ascii")
        pos += lbl_len
        pairs = []
        for _ in range(num_pairs):
            str_magic, str_len = struct.unpack_from("<4sI", data, pos)
            pos += 8
            dec = bytes(~b & 0xFF for b in data[pos:pos + str_len * 2]).decode("utf-16le")
            pos += str_len * 2
            extra = None
            if str_magic == b"WRTS":
                extra_len, = struct.unpack_from("<I", data, pos)
                extra = data[pos + 4:pos + 4 + extra_len]
                pos += 4 + extra_len
            pairs.append((dec, extra))
        entries.append((lbl, pairs))
    return ver, unk, lang, entries


def write_csf(path: Path, ver: int, unk: int, lang: int, entries):
    n_labels = len(entries)
    n_strings = sum(len(p) for _, p in entries)
    out = bytearray(struct.pack("<4sIIIII", b" FSC", ver, n_labels, n_strings, unk, lang))
    for lbl, pairs in entries:
        lbl_b = lbl.encode("ascii")
        out.extend(struct.pack("<4sII", b" LBL", len(pairs), len(lbl_b)))
        out.extend(lbl_b)
        for text, extra in pairs:
            enc = bytes(~b & 0xFF for b in text.encode("utf-16le"))
            str_magic = b"WRTS" if extra is not None else b" RTS"
            out.extend(struct.pack("<4sI", str_magic, len(text)))
            out.extend(enc)
            if extra is not None:
                out.extend(struct.pack("<I", len(extra)))
                out.extend(extra)
    path.write_bytes(bytes(out))


if __name__ == "__main__":
    root = Path(r"D:\FILE_GAME\Ra2")
    fb = ThaiFontBuilder(
        root / "ThaiPatch/backup/GAME.FNT",
        Path(os.environ.get("THAI_FONT_PATH", str(root / "ThaiPatch/font.ttf"))),
        font_size=11,
    )
    fb.add_standalone_thai()

    test_menu = {
        "GUI:SinglePlayer": "เล่นคนเดียว",
        "GUI:NewCampaign": "เริ่มแคมเปญใหม่",
        "GUI:LoadGame": "โหลดเกม",
        "GUI:Skirmish": "รบแบบสคอร์มิช",
        "GUI:Options": "ตั้งค่า",
        "GUI:ExitGame": "ออกจากเกม",
        "GUI:Internet": "อินเทอร์เน็ต",
        "GUI:Network": "เครือข่าย (LAN)",
        "GUI:Back": "ย้อนกลับ",
        "GUI:StartGame": "เริ่มเกม",
    }

    ver, unk, lang, entries = read_csf(root / "ThaiPatch/backup/ra2md.csf")
    new_entries = []
    for lbl, pairs in entries:
        if lbl in test_menu:
            shaped = fb.shape_text(test_menu[lbl])
            new_pairs = [(shaped, pairs[0][1])] + pairs[1:]
            new_entries.append((lbl, new_pairs))
        else:
            new_entries.append((lbl, pairs))

    fb.save(root / "GAME.FNT")
    write_csf(root / "ra2md.csf", ver, unk, lang, new_entries)
    print(f"Wrote GAME.FNT (glyphs={fb.num_glyphs}, PUA clusters={len(fb.cluster_to_pua)}) and ra2md.csf")
