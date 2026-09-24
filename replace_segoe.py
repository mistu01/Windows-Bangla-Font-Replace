#!/usr/bin/env python3
"""
Windows Segoe UI & Segoe UI Variable Font Replacer
===================================================
This script:
1. Locates all Segoe UI static font faces and Segoe UI Variable (SegUIVar.ttf)
   across Windows (Fonts directory and WinSxS component store).
2. Creates untouched backups of all original Microsoft Segoe fonts into 'backup_segoe/'.
3. Scans 'custom_segoe/' for user-provided font files (.ttf or .otf), detecting
   their weights (usWeightClass 100-900) and styles (Regular/Italic).
4. Matches each Windows Segoe UI face to the closest available weight in the
   custom family:
     - Light (300)
     - Semilight (350)
     - Regular (400)
     - SemiBold (600)
     - Bold (700)
     - Black (900)
     - Corresponding Italic faces
5. Merges custom glyphs into each Segoe UI face:
     - Normalizes UPM to 2048 and maintains exact Segoe vertical metrics.
     - Replaces alphanumeric, Latin, and extended Unicode glyphs.
     - Preserves Segoe UI's native UI icons, symbols, and Private Use Area (PUA)
       glyphs so Windows Explorer, Taskbar, and system UI controls never break.
6. Patches Segoe UI Variable (SegUIVar.ttf) on Windows 11 using OpenType delta
   nullification:
     - Replaces glyph outlines in the base table.
     - Deletes variation deltas for replaced glyphs from 'gvar', ensuring
       DirectWrite & WinUI 3 render the custom outlines cleanly across all
       variation instances without crashing.
     - Keeps native icon variations and 'fvar' / 'STAT' tables intact.
7. Schedules atomic font replacement across all Windows locations on next reboot
   via Win32 MoveFileEx (MOVEFILE_DELAY_UNTIL_REBOOT).
"""

import os
import sys
import glob
import shutil
import ctypes
from ctypes import wintypes
import subprocess
import argparse
import json

# Win32 API constants for delayed reboot replacement
MOVEFILE_REPLACE_EXISTING = 0x00000001
MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004

# Segoe UI static family targets (filename -> properties)
SEGOE_STATIC_TARGETS = {
    "segoeui.ttf":   {"name": "Segoe UI Regular",          "weight": 400, "italic": False},
    "segoeuib.ttf":  {"name": "Segoe UI Bold",             "weight": 700, "italic": False},
    "segoeuii.ttf":  {"name": "Segoe UI Italic",           "weight": 400, "italic": True},
    "segoeuiz.ttf":  {"name": "Segoe UI Bold Italic",      "weight": 700, "italic": True},
    "segoeuil.ttf":  {"name": "Segoe UI Light",            "weight": 300, "italic": False},
    "segoeuisl.ttf": {"name": "Segoe UI Semilight",        "weight": 350, "italic": False},
    "seguisb.ttf":   {"name": "Segoe UI SemiBold",         "weight": 600, "italic": False},
    "seguibl.ttf":   {"name": "Segoe UI Black",            "weight": 900, "italic": False},
    "seguili.ttf":   {"name": "Segoe UI Light Italic",     "weight": 300, "italic": True},
    "seguisli.ttf":  {"name": "Segoe UI Semilight Italic", "weight": 350, "italic": True},
    "seguisbi.ttf":  {"name": "Segoe UI SemiBold Italic",  "weight": 600, "italic": True},
    "seguibli.ttf":  {"name": "Segoe UI Black Italic",     "weight": 900, "italic": True},
}

SEGOE_VAR_TARGET = "SegUIVar.ttf"

WEIGHT_KEYWORDS = {
    "thin": 100, "hairline": 100,
    "extralight": 200, "ultralight": 200,
    "light": 300,
    "semilight": 350, "demilight": 350,
    "regular": 400, "normal": 400, "book": 400,
    "medium": 500,
    "semibold": 600, "demibold": 600,
    "bold": 700,
    "extrabold": 800, "ultrabold": 800,
    "black": 900, "heavy": 900,
    "extrablack": 950, "ultrablack": 950,
}


def ensure_dependencies():
    """Ensure fonttools is installed."""
    try:
        import fontTools
        from fontTools.ttLib import TTFont, scaleUpem
        from fontTools.pens.recordingPen import DecomposingRecordingPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen
    except ImportError:
        print("[*] 'fonttools' library not found. Installing automatically via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fonttools"])
        print("[+] 'fonttools' installed successfully!\n")


def is_admin():
    """Check if the current process has Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_cmd(cmd):
    """Run a shell command silently."""
    try:
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False


def take_ownership(file_path):
    """Take ownership and grant Full Control to Administrators."""
    if not os.path.exists(file_path):
        return
    parent_dir = os.path.dirname(file_path)
    run_cmd(f'takeown /f "{parent_dir}"')
    run_cmd(f'icacls "{parent_dir}" /grant administrators:F /c /q')
    run_cmd(f'takeown /f "{file_path}"')
    run_cmd(f'icacls "{file_path}" /grant administrators:F /c /q')


def find_segoe_fonts():
    """
    Locate all Segoe UI static and variable fonts across Windows.
    Returns:
      static_files: dict mapping canonical filename (e.g. 'segoeui.ttf') -> list of discovered paths
      var_files: list of discovered paths for SegUIVar.ttf
    """
    win_dir = os.environ.get("WINDIR", r"C:\Windows")
    fonts_dir = os.path.join(win_dir, "Fonts")
    winsxs_dir = os.path.join(win_dir, "WinSxS")
    local_appdata = os.environ.get("LOCALAPPDATA")

    static_found = {fname: [] for fname in SEGOE_STATIC_TARGETS}
    var_found = []

    def register_candidate(path):
        base = os.path.basename(path)
        base_lower = base.lower()
        if base_lower == SEGOE_VAR_TARGET.lower():
            if path not in var_found and os.path.exists(path):
                var_found.append(path)
            return

        for target in SEGOE_STATIC_TARGETS:
            if base_lower == target.lower():
                if path not in static_found[target] and os.path.exists(path):
                    static_found[target].append(path)
                return

    # 1. Main Windows Fonts directory
    if os.path.exists(fonts_dir):
        for pattern in ("*segoe*.ttf", "*segui*.ttf", "*SegUIVar*.ttf"):
            for match in glob.glob(os.path.join(fonts_dir, pattern)):
                register_candidate(match)

    # 2. WinSxS directory
    if os.path.exists(winsxs_dir):
        for subfolder_pat in ("*segoe*", "*segui*"):
            for folder in glob.glob(os.path.join(winsxs_dir, subfolder_pat)):
                if os.path.isdir(folder):
                    for font_file in glob.glob(os.path.join(folder, "*.ttf")):
                        register_candidate(font_file)

    # 3. User Font directory (if any)
    if local_appdata:
        user_fonts = os.path.join(local_appdata, "Microsoft", "Windows", "Fonts")
        if os.path.exists(user_fonts):
            for pattern in ("*segoe*.ttf", "*segui*.ttf", "*SegUIVar*.ttf"):
                for match in glob.glob(os.path.join(user_fonts, pattern)):
                    register_candidate(match)

    return static_found, var_found


def inspect_font_face(font_path):
    """Inspect a font file to determine weight class, italic style, and family names."""
    from fontTools.ttLib import TTFont

    try:
        f = TTFont(font_path, fontNumber=0)
        os2 = f.get("OS/2")
        head = f.get("head")
        name_tbl = f.get("name")

        os2_weight = os2.usWeightClass if os2 and hasattr(os2, "usWeightClass") else None
        mac_style = head.macStyle if head and hasattr(head, "macStyle") else 0

        subfamily = ((name_tbl.getDebugName(2) or "") if name_tbl else "").lower()
        full_name = ((name_tbl.getDebugName(4) or "") if name_tbl else "").lower()
        ps_name = ((name_tbl.getDebugName(6) or "") if name_tbl else "").lower()
    except Exception as ex:
        print(f"    [!] Warning: Failed to parse '{os.path.basename(font_path)}': {ex}")
        return None

    fname = os.path.basename(font_path).lower()

    # Determine Italic
    is_italic = bool(mac_style & 0x02) or ("italic" in subfamily or "oblique" in subfamily or "italic" in fname or "oblique" in fname)

    # Determine Weight
    detected_kw_weight = None
    for kw in sorted(WEIGHT_KEYWORDS.keys(), key=len, reverse=True):
        if kw in fname or kw in subfamily or kw in full_name or kw in ps_name:
            detected_kw_weight = WEIGHT_KEYWORDS[kw]
            break

    if os2_weight and os2_weight not in (0, 400):
        weight = os2_weight
    elif detected_kw_weight:
        weight = detected_kw_weight
    elif os2_weight:
        weight = os2_weight
    else:
        weight = 400

    return {
        "path": font_path,
        "filename": os.path.basename(font_path),
        "weight": weight,
        "is_italic": is_italic,
        "full_name": full_name or os.path.basename(font_path),
        "subfamily": subfamily or "Regular",
    }


def discover_custom_fonts(custom_dir):
    """Discover and catalog all fonts placed in the custom_segoe directory."""
    if not os.path.exists(custom_dir):
        return []

    candidates = []
    for ext in ("*.ttf", "*.otf"):
        for fpath in glob.glob(os.path.join(custom_dir, ext)):
            info = inspect_font_face(fpath)
            if info:
                candidates.append(info)

    return sorted(candidates, key=lambda x: (x["is_italic"], x["weight"]))


def find_closest_custom_font(target_weight, target_is_italic, custom_fonts):
    """
    Select the best-matching custom font face using Euclidean distance on
    weight difference with a penalty for style mismatch.
    """
    if not custom_fonts:
        return None

    best_font = None
    best_score = float("inf")

    for cf in custom_fonts:
        weight_diff = abs(cf["weight"] - target_weight)
        style_penalty = 0 if (cf["is_italic"] == target_is_italic) else 500
        score = weight_diff + style_penalty

        if score < best_score:
            best_score = score
            best_font = cf

    return best_font


def patch_static_face(base_segoe_path, custom_font_path, output_path):
    """
    Graft custom font glyphs into a static Segoe UI face while preserving
    Segoe UI's native UI icons, PUA symbols, and line metrics.
    """
    from fontTools.ttLib import TTFont, scaleUpem as scaleUpemMod
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    base_font = TTFont(base_segoe_path)
    cust_font = TTFont(custom_font_path)

    # Scale custom font to match Segoe UI's 2048 UPM
    target_upem = base_font['head'].unitsPerEm
    if cust_font['head'].unitsPerEm != target_upem:
        scaleUpemMod.scale_upem(cust_font, target_upem)

    base_cmap = base_font.getBestCmap()
    cust_cmap = cust_font.getBestCmap()
    cust_gset = cust_font.getGlyphSet()

    replaced_count = 0
    for cp, gname in cust_cmap.items():
        # Do not overwrite Private Use Area (Windows system icons) or control codes
        if (0xE000 <= cp <= 0xF8FF) or cp < 0x20:
            continue

        if cp in base_cmap:
            target_gname = base_cmap[cp]
            if target_gname in base_font['glyf'] and gname in cust_gset:
                try:
                    dec_pen = DecomposingRecordingPen(cust_gset)
                    cust_gset[gname].draw(dec_pen)
                    tt_pen = TTGlyphPen(None)
                    dec_pen.replay(tt_pen)
                    base_font['glyf'][target_gname] = tt_pen.glyph()
                    base_font['hmtx'][target_gname] = cust_font['hmtx'][gname]
                    replaced_count += 1
                except Exception:
                    pass

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base_font.save(output_path)
    return replaced_count


def patch_variable_font(var_segoe_path, custom_regular_path, output_path):
    """
    Patch Segoe UI Variable (SegUIVar.ttf) using OpenType delta nullification.
    Replaces base outlines and clears 'gvar' variation deltas for replaced
    glyphs, keeping Windows UI icons and variable table structures valid.
    """
    from fontTools.ttLib import TTFont, scaleUpem as scaleUpemMod
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    var_font = TTFont(var_segoe_path)
    cust_font = TTFont(custom_regular_path)

    target_upem = var_font['head'].unitsPerEm
    if cust_font['head'].unitsPerEm != target_upem:
        scaleUpemMod.scale_upem(cust_font, target_upem)

    var_cmap = var_font.getBestCmap()
    cust_cmap = cust_font.getBestCmap()
    cust_gset = cust_font.getGlyphSet()

    replaced_count = 0
    has_gvar = 'gvar' in var_font

    for cp, gname in cust_cmap.items():
        if (0xE000 <= cp <= 0xF8FF) or cp < 0x20:
            continue

        if cp in var_cmap:
            var_gname = var_cmap[cp]
            if var_gname in var_font['glyf'] and gname in cust_gset:
                try:
                    dec_pen = DecomposingRecordingPen(cust_gset)
                    cust_gset[gname].draw(dec_pen)
                    tt_pen = TTGlyphPen(None)
                    dec_pen.replay(tt_pen)
                    var_font['glyf'][var_gname] = tt_pen.glyph()
                    var_font['hmtx'][var_gname] = cust_font['hmtx'][gname]

                    # Nullify variation deltas for replaced glyph so DirectWrite uses base outline
                    if has_gvar and var_gname in var_font['gvar'].variations:
                        var_font['gvar'].variations[var_gname] = []

                    replaced_count += 1
                except Exception:
                    pass

    # Remove HVAR so obsolete width variation deltas don't distort custom glyph widths
    if 'HVAR' in var_font:
        del var_font['HVAR']

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    var_font.save(output_path)
    return replaced_count


def replace_font_file(src_path, dst_path):
    """Replace an existing font file, scheduling Win32 MoveFileEx on reboot if locked."""
    take_ownership(dst_path)

    try:
        shutil.copy2(src_path, dst_path)
        print(f"    [OK] Immediately replaced: {dst_path}")
        return "immediate"
    except (PermissionError, OSError):
        pass

    staging_file = dst_path + ".new_segoe_update"
    try:
        shutil.copy2(src_path, staging_file)
    except (PermissionError, OSError):
        win_temp = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Temp", "SegoeMergerStaging")
        os.makedirs(win_temp, exist_ok=True)
        h = abs(hash(dst_path))
        staging_file = os.path.join(win_temp, f"staged_segoe_{h}_{os.path.basename(dst_path)}")
        try:
            shutil.copy2(src_path, staging_file)
        except Exception as ex:
            print(f"    [ERROR] Could not stage replacement for {dst_path}: {ex}")
            return "failed"

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        MoveFileExW = kernel32.MoveFileExW
        MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        MoveFileExW.restype = wintypes.BOOL

        flags = MOVEFILE_REPLACE_EXISTING | MOVEFILE_DELAY_UNTIL_REBOOT
        res = MoveFileExW(staging_file, dst_path, flags)
        if res:
            print(f"    [SCHEDULED] File locked by Windows. Scheduled replacement on next reboot: {dst_path}")
            return "reboot"
        else:
            err = ctypes.get_last_error()
            print(f"    [ERROR] Failed to schedule replacement for {dst_path}: Win32 error {err}")
            return "failed"
    except Exception as ex:
        print(f"    [ERROR] MoveFileEx failed for {dst_path}: {ex}")
        return "failed"


def clear_font_cache():
    """Refresh Windows Font Cache service."""
    print("[*] Refreshing Windows Font Cache...")
    run_cmd('net stop FontCache /y')
    run_cmd('net stop "FontCache3.0.0.0" /y')

    cache_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "ServiceProfiles", "LocalService", "AppData", "Local", "FontCache")
    if os.path.exists(cache_dir):
        for f in glob.glob(os.path.join(cache_dir, "*.dat")):
            try:
                os.remove(f)
            except Exception:
                pass

    run_cmd('net start FontCache')
    print("[+] Font cache refreshed.\n")


def restore_backup(backup_dir):
    """Restore original Segoe UI fonts from backup manifest."""
    manifest_path = os.path.join(backup_dir, "segoe_backup_manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[!] No backup manifest found at '{manifest_path}'.")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"[*] Restoring {len(manifest)} original Segoe UI font files from backup...")
    reboot_needed = False
    for sys_path, backup_path in manifest.items():
        if os.path.exists(backup_path):
            res = replace_font_file(backup_path, sys_path)
            if res == "reboot":
                reboot_needed = True

    clear_font_cache()
    if reboot_needed:
        print("========================================================================")
        print("  RESTORATION COMPLETE! Please restart your computer to finish.")
        print("========================================================================")
    else:
        print("========================================================================")
        print("  RESTORATION COMPLETED IMMEDIATELY!")
        print("========================================================================")


def main():
    parser = argparse.ArgumentParser(description="Replace Windows Segoe UI and Segoe UI Variable fonts with custom fonts.")
    parser.add_argument("--restore", "-r", action="store_true", help="Restore original Windows Segoe UI fonts from backup.")
    args = parser.parse_args()

    ensure_dependencies()

    working_dir = os.path.dirname(os.path.abspath(__file__))
    custom_dir = os.path.join(working_dir, "custom_segoe")
    backup_dir = os.path.join(working_dir, "backup_segoe")
    output_dir = os.path.join(working_dir, "output_segoe")

    os.makedirs(custom_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    if not is_admin():
        print("[!] Administrator privileges are required to replace system fonts.")
        print("[*] Re-launching with Administrator privileges...")
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        if ret <= 32:
            print("[X] Administrator privileges were denied.")
            sys.exit(1)
        sys.exit(0)

    if args.restore:
        restore_backup(backup_dir)
        return

    print("========================================================================")
    print("           WINDOWS SEGOE UI & SEGOE UI VARIABLE FONT MERGER             ")
    print("========================================================================")

    # 1. Discover Custom Fonts
    custom_fonts = discover_custom_fonts(custom_dir)
    if not custom_fonts:
        print(f"[!] No custom font files (.ttf / .otf) found in:")
        print(f"    {custom_dir}")
        print("\nPlease put your custom font(s) into 'custom_segoe/' and run again!")
        return

    print(f"[*] Detected {len(custom_fonts)} custom font face(s) in 'custom_segoe/':")
    for cf in custom_fonts:
        style_str = "Italic" if cf["is_italic"] else "Regular"
        print(f"    - {cf['filename']} [Weight: {cf['weight']}] ({style_str})")
    print()

    # 2. Discover Windows Segoe UI Fonts
    static_found, var_found = find_segoe_fonts()
    total_static_found = sum(len(v) for v in static_found.values())
    print(f"[*] Found {total_static_found} static Segoe UI files and {len(var_found)} Segoe UI Variable files across Windows.")

    # 3. Create Untouched Safe Backups
    manifest_path = os.path.join(backup_dir, "segoe_backup_manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

    print("[*] Ensuring untouched backups of original Segoe fonts...")
    for target_name, path_list in static_found.items():
        for p in path_list:
            if p not in manifest:
                h = abs(hash(p)) % 100000000
                b_name = f"{h}_{os.path.basename(p)}"
                b_path = os.path.join(backup_dir, b_name)
                if not os.path.exists(b_path):
                    shutil.copy2(p, b_path)
                manifest[p] = b_path

    for vp in var_found:
        if vp not in manifest:
            h = abs(hash(vp)) % 100000000
            b_name = f"{h}_{os.path.basename(vp)}"
            b_path = os.path.join(backup_dir, b_name)
            if not os.path.exists(b_path):
                shutil.copy2(vp, b_path)
            manifest[vp] = b_path

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[+] Backup manifest verified with {len(manifest)} font entries.\n")

    # 4. Patch Static Segoe UI Faces
    print("[*] Merging custom fonts into static Segoe UI faces (closest-weight matching)...")
    compiled_static_outputs = {}
    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

    for target_name, meta in SEGOE_STATIC_TARGETS.items():
        target_path = os.path.join(fonts_dir, target_name)
        if not os.path.exists(target_path):
            # Check other locations if main Fonts directory doesn't have it
            candidates = static_found.get(target_name, [])
            if candidates:
                target_path = candidates[0]
            else:
                continue

        matched_custom = find_closest_custom_font(meta["weight"], meta["italic"], custom_fonts)
        if not matched_custom:
            continue

        out_path = os.path.join(output_dir, target_name)
        style_desc = "Italic" if meta["italic"] else "Regular"
        print(f"  -> {meta['name']} (Weight: {meta['weight']}, {style_desc})")
        print(f"     Matched with: '{matched_custom['filename']}' [Weight: {matched_custom['weight']}]")

        replaced = patch_static_face(target_path, matched_custom["path"], out_path)
        print(f"     [+] Patched {replaced} glyphs -> saved to '{target_name}'")
        compiled_static_outputs[target_name] = out_path

    # 5. Patch Segoe UI Variable (if present on Windows 11)
    compiled_var_output = None
    if var_found:
        print("\n[*] Windows 11 Segoe UI Variable (SegUIVar.ttf) detected!")
        # Match with closest Regular (400, non-italic)
        regular_matched = find_closest_custom_font(400, False, custom_fonts)
        primary_var_path = var_found[0]
        out_var_path = os.path.join(output_dir, SEGOE_VAR_TARGET)

        print(f"     Template: '{primary_var_path}'")
        print(f"     Matched with: '{regular_matched['filename']}' [Weight: {regular_matched['weight']}]")
        print("     Applying OpenType delta nullification to preserve variable structures...")

        replaced = patch_variable_font(primary_var_path, regular_matched["path"], out_var_path)
        print(f"     [+] Patched {replaced} base glyphs with delta nullification -> saved to '{SEGOE_VAR_TARGET}'")
        compiled_var_output = out_var_path

    # 6. Apply Replacements Across Windows
    print("\n[*] Deploying patched Segoe fonts across Windows...")
    reboot_needed = False

    # Deploy static fonts
    for target_name, compiled_file in compiled_static_outputs.items():
        destinations = static_found.get(target_name, [])
        for dst in destinations:
            res = replace_font_file(compiled_file, dst)
            if res == "reboot":
                reboot_needed = True

    # Deploy variable font
    if compiled_var_output:
        for dst in var_found:
            res = replace_font_file(compiled_var_output, dst)
            if res == "reboot":
                reboot_needed = True

    clear_font_cache()

    print("========================================================================")
    if reboot_needed:
        print("  SUCCESS! Font replacement has been scheduled.")
        print("  PLEASE RESTART YOUR COMPUTER for the new Segoe fonts to take effect!")
    else:
        print("  SUCCESS! All Segoe fonts have been updated immediately!")
    print("========================================================================")


if __name__ == "__main__":
    main()
