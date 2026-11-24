"""Validate all translated batches and build full Thai GAME.FNT, ra2md.csf, and ra2.csf."""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_fnt_and_csf import ThaiFontBuilder, read_csf, write_csf

FMT_RE = re.compile(r"%(?:\d+\$)?[-+0 #']*(?:\d+|\*)?(?:\.\d+|\.\*)?(?:hh|h|ll|l|L|z|j|t)?[diuoxXfFeEgGaAcspn%]")


def main():
    root = Path(r"D:\FILE_GAME\Ra2")
    patch = root / "ThaiPatch"
    batch_dir = patch / "translations" / "batches"

    en_to_th: dict[str, str] = {}
    warnings = []

    for b in range(13):
        src = json.loads((batch_dir / f"batch_{b:02d}.json").read_text(encoding="utf-8"))
        dst = json.loads((batch_dir / f"batch_{b:02d}_th.json").read_text(encoding="utf-8"))
        dst_map = {item["id"]: item["th"] for item in dst}
        assert len(src) == len(dst), f"Batch {b:02d} length mismatch: {len(src)} vs {len(dst)}"
        for item in src:
            i = item["id"]
            en = item["en"]
            assert i in dst_map, f"Missing id {i} in batch {b:02d}"
            th = dst_map[i]
            if en.strip() and not th.strip():
                warnings.append(f"Empty translation id={i} ({item['label']})")
                th = en
            en_fmts = FMT_RE.findall(en)
            th_fmts = FMT_RE.findall(th)
            if en_fmts != th_fmts:
                warnings.append(f"Format mismatch id={i} ({item['label']}): {en_fmts} vs {th_fmts}")
                # Fallback to en if format specifiers were broken
                th = en
            en_to_th[en] = th

    print(f"Loaded {len(en_to_th)} translations. Warnings: {len(warnings)}")
    for w in warnings[:20]:
        print("  WARN:", w)

    # Save merged dictionary
    (patch / "translations" / "merged_th.json").write_text(
        json.dumps(en_to_th, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Build GAME.FNT with standalone Thai + PUA ligatures for all clusters
    fb = ThaiFontBuilder(
        patch / "backup" / "GAME.FNT",
        Path(os.environ.get("THAI_FONT_PATH", str(root / "ThaiPatch/font.ttf"))),
        font_size=11,
    )
    fb.add_standalone_thai()

    # Keep Windows ANSI MessageBoxA fatal/video error strings in English so they never render as '??????'
    KEEP_ENGLISH_LABELS = {"TXT_VIDEO_ERROR"}

    for csf_name in ["ra2md", "ra2"]:
        ver, unk, lang, entries = read_csf(patch / "backup" / f"{csf_name}.csf")
        new_entries = []
        translated_count = 0
        for lbl, pairs in entries:
            new_pairs = []
            for idx, (en_text, extra) in enumerate(pairs):
                if idx == 0 and lbl not in KEEP_ENGLISH_LABELS and en_text in en_to_th:
                    th_text = en_to_th[en_text]
                    shaped = fb.shape_text(th_text)
                    new_pairs.append((shaped, extra))
                    translated_count += 1
                else:
                    new_pairs.append((en_text, extra))
            new_entries.append((lbl, new_pairs))
        out_csf = root / f"{csf_name}.csf"
        write_csf(out_csf, ver, unk, lang, new_entries)
        print(f"Wrote {out_csf} ({translated_count}/{len(entries)} entries translated)")

    out_fnt = root / "GAME.FNT"
    fb.save(out_fnt)
    print(f"Wrote {out_fnt} (total glyphs={fb.num_glyphs}, PUA clusters={len(fb.cluster_to_pua)})")


if __name__ == "__main__":
    main()
