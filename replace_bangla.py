#!/usr/bin/env python3
"""
Windows Bangla Font Replacer (Nirmala UI)
=========================================
This script:
1. Searches for Nirmala UI font files across Windows (Fonts directory and WinSxS).
2. Copies and creates a safe backup of the original Nirmala.ttc.
3. Separates the TrueType Collection (TTC) into individual TTF font faces.
4. Scans all Segoe UI font files for embedded Bengali numbers (U+09E6-U+09EF)
   and currency marks (U+09F2, U+09F3). If found, creates safe backups and
   strips them so Segoe UI will not override your custom Bengali font.
5. Merges your custom Bengali font (from the 'custom_bangla' directory) into each
   Nirmala UI face, rescaling metrics and replacing the Bengali glyphs while
   preserving all other scripts (Latin, Devanagari, Tamil, etc.) and original font names.
6. Rebuilds a Windows-format TTC bundle (Nirmala.ttc).
7. Replaces both Nirmala UI and patched Segoe UI fonts in all detected
   Windows locations (with automatic reboot scheduling via Win32 MoveFileEx
   since active system fonts are locked in memory).
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

# Win32 API constants for file replacement on reboot
MOVEFILE_REPLACE_EXISTING = 0x00000001
MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004

BENGALI_UNICODE_RANGE = range(0x0980, 0x0A00)  # U+0980 to U+09FF (includes numbers U+09E6 to U+09EF)


def ensure_dependencies():
    """Ensure fonttools is installed."""
    try:
        import fontTools
        from fontTools.ttLib import TTCollection, TTFont, scaleUpem
        from fontTools.merge import Merger
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


def find_nirmala_fonts():
    """Find all instances of Nirmala font files in Windows."""
    locations = []
    
    # 1. Main Windows Fonts folder
    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    main_ttc = os.path.join(win_fonts, "Nirmala.ttc")
    if os.path.exists(main_ttc):
        locations.append(main_ttc)

    # Check for individual TTFs if any
    for ttf in glob.glob(os.path.join(win_fonts, "Nirmala*.ttf")):
        if ttf not in locations:
            locations.append(ttf)

    # 2. WinSxS component store
    winsxs = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "WinSxS")
    if os.path.exists(winsxs):
        pattern = os.path.join(winsxs, "*nirmalaui*", "Nirmala.ttc")
        for match in glob.glob(pattern):
            if match not in locations:
                locations.append(match)

    # 3. User font directory
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        user_fonts = os.path.join(local_appdata, "Microsoft", "Windows", "Fonts")
        for match in glob.glob(os.path.join(user_fonts, "Nirmala*.tt*")):
            if match not in locations:
                locations.append(match)

    return locations


def extract_ttc_to_ttfs(ttc_path, output_dir):
    """Extract all font faces from a TTC collection into separate TTF files."""
    from fontTools.ttLib import TTCollection

    os.makedirs(output_dir, exist_ok=True)
    ttc = TTCollection(ttc_path)
    extracted = []

    print(f"[*] Found {len(ttc)} font face(s) inside '{os.path.basename(ttc_path)}':")
    for idx, font in enumerate(ttc):
        name_record = font['name']
        ps_name = name_record.getDebugName(6) or f"Font_{idx}"
        full_name = name_record.getDebugName(4) or ps_name
        subfamily = name_record.getDebugName(2) or "Regular"

        safe_filename = f"{ps_name}.ttf".replace(" ", "_")
        out_path = os.path.join(output_dir, safe_filename)
        font.save(out_path)

        is_bold = "bold" in subfamily.lower() or "bold" in ps_name.lower()
        is_semilight = "semilight" in subfamily.lower() or "semilight" in ps_name.lower()

        target_weight = 400
        if "OS/2" in font and hasattr(font["OS/2"], "usWeightClass"):
            target_weight = font["OS/2"].usWeightClass
        elif is_bold:
            target_weight = 700
        elif is_semilight:
            target_weight = 350

        extracted.append({
            "index": idx,
            "path": out_path,
            "filename": safe_filename,
            "ps_name": ps_name,
            "full_name": full_name,
            "subfamily": subfamily,
            "is_bold": is_bold,
            "is_semilight": is_semilight,
            "target_weight": target_weight,
        })
        print(f"    [{idx}] {full_name} ({subfamily}) [Weight: {target_weight}] -> {safe_filename}")

    return extracted


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


def get_font_weight_info(font_path):
    """
    Extract the weight class (100-950) from an OpenType/TrueType font.
    Uses OS/2 usWeightClass with fallback/refinement from style/name keywords.
    """
    from fontTools.ttLib import TTFont

    try:
        f = TTFont(font_path, fontNumber=0)
        os2_weight = f["OS/2"].usWeightClass if "OS/2" in f else None
        subfamily = ((f["name"].getDebugName(2) or "") if "name" in f else "").lower()
        full_name = ((f["name"].getDebugName(4) or "") if "name" in f else "").lower()
    except Exception:
        os2_weight = None
        subfamily = ""
        full_name = ""

    fname = os.path.basename(font_path).lower()

    detected_kw_weight = None
    for kw in sorted(WEIGHT_KEYWORDS.keys(), key=len, reverse=True):
        if kw in fname or kw in subfamily or kw in full_name:
            detected_kw_weight = WEIGHT_KEYWORDS[kw]
            break

    if os2_weight and os2_weight != 400:
        weight = os2_weight
    elif detected_kw_weight:
        weight = detected_kw_weight
    else:
        weight = os2_weight or 400

    human_style = subfamily.capitalize() or "Regular"
    if detected_kw_weight:
        for kw, w in WEIGHT_KEYWORDS.items():
            if w == weight:
                human_style = kw.capitalize()
                break

    return {
        "path": font_path,
        "filename": os.path.basename(font_path),
        "weight": weight,
        "style": human_style,
    }


def find_user_bengali_fonts(working_dir, specified_file=None):
    """
    Detect all available custom Bengali font files and analyze their weights.
    Looks first in working_dir/custom_font, then falls back to working_dir.
    """
    if specified_file and os.path.exists(specified_file):
        info = get_font_weight_info(specified_file)
        return {"candidates": [info], "source_dir": os.path.dirname(specified_file)}

    search_dirs = [
        os.path.join(working_dir, "custom_bangla"),
        os.path.join(working_dir, "custom_font"),
        working_dir
    ]

    ignore_names = {"nirmala", "merged", "extracted", "output", "backup", "segoe"}

    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        candidates = []
        for f in os.listdir(sdir):
            if f.lower().endswith((".ttf", ".otf")):
                lower_name = f.lower()
                if any(ign in lower_name for ign in ignore_names) or "tmp" in lower_name or lower_name.startswith((".", "~")):
                    continue
                p = os.path.join(sdir, f)
                info = get_font_weight_info(p)
                candidates.append(info)

        if candidates:
            return {"candidates": candidates, "source_dir": sdir}

    return None


def find_closest_font(target_weight, candidates):
    """
    Find the candidate font whose weight is closest to target_weight.
    Tie-breaking:
    - If target <= 350 (Semilight/Light), prefer a lighter font to preserve contrast with Regular.
    - If target >= 700 (Bold), prefer a heavier font to ensure prominent emphasis.
    """
    def sort_key(c):
        diff = abs(c["weight"] - target_weight)
        tie_pref = 0
        if target_weight <= 350 and c["weight"] < target_weight:
            tie_pref = -0.1
        elif target_weight >= 700 and c["weight"] > target_weight:
            tie_pref = -0.1
        return (diff + tie_pref)

    return min(candidates, key=sort_key)


def strip_bengali_from_font(font):
    """Remove Bengali Unicode codepoints from a font's cmap tables."""
    removed = 0
    if "cmap" in font:
        for subtable in font["cmap"].tables:
            for cp in list(subtable.cmap.keys()):
                if cp in BENGALI_UNICODE_RANGE:
                    del subtable.cmap[cp]
                    removed += 1
    return removed

def optimize_gasp_table(font):
    """
    Ensure the font has an optimized OpenType 'gasp' table and integer scaler flags.
    Enables DirectWrite ClearType symmetric smoothing and subpixel antialiasing
    across all point sizes to eliminate color-fringing ('bleeding') and fuzzy edges.
    """
    try:
        from fontTools.ttLib.tables._g_a_s_p import table__g_a_s_p
        gasp = table__g_a_s_p()
        gasp.version = 1
        gasp.gaspRange = {8: 10, 65535: 15}
        font['gasp'] = gasp

        if 'head' in font and hasattr(font['head'], 'flags'):
            font['head'].flags |= 0x0008
    except Exception:
        pass


def scan_and_patch_segoe_ui(backup_dir, patched_dir):
    """
    Scans Segoe UI fonts in Windows to detect if any contain Bengali digits or characters.
    If found, backs them up, strips the Bengali codepoints, and returns the list of
    (patched_file, original_system_path) to be replaced.
    """
    from fontTools.ttLib import TTFont

    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    winsxs = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "WinSxS")
    segoe_backup_dir = os.path.join(backup_dir, "segoe")
    os.makedirs(segoe_backup_dir, exist_ok=True)
    os.makedirs(patched_dir, exist_ok=True)

    target_names = {"segoeui.ttf", "segoeuib.ttf", "segoeuil.ttf", "segoeuisl.ttf", "seguisb.ttf"}
    target_files = []

    for name in target_names:
        p = os.path.join(win_fonts, name)
        if os.path.exists(p):
            target_files.append(p)

    if os.path.exists(winsxs):
        for match in glob.glob(os.path.join(winsxs, "*segoeui*", "*.ttf")):
            if os.path.basename(match).lower() in target_names and match not in target_files:
                target_files.append(match)

    patched_tasks = []
    manifest_path = os.path.join(segoe_backup_dir, "segoe_manifest.json")
    manifest = {}

    for sys_path in target_files:
        fname = os.path.basename(sys_path)
        try:
            font = TTFont(sys_path)
            has_bengali = False
            bengali_count = 0
            for subtable in font['cmap'].tables:
                if subtable.isUnicode():
                    for cp in list(subtable.cmap.keys()):
                        if cp in BENGALI_UNICODE_RANGE:
                            has_bengali = True
                            bengali_count += 1
                            del subtable.cmap[cp]

            if has_bengali:
                rel_hash = f"{abs(hash(sys_path)):x}"
                backup_name = f"{rel_hash}_{fname}"
                backup_path = os.path.join(segoe_backup_dir, backup_name)

                if not os.path.exists(backup_path):
                    shutil.copy2(sys_path, backup_path)

                manifest[sys_path] = backup_path

                patched_file = os.path.join(patched_dir, f"Patched_{rel_hash}_{fname}")
                optimize_gasp_table(font)
                font.save(patched_file)
                patched_tasks.append((patched_file, sys_path))
                print(f"    [!] Detected & stripped {bengali_count} Bengali codepoints from: {fname}")
                print(f"        Path: {sys_path}")
        except Exception as e:
            print(f"    [-] Could not scan {sys_path}: {e}")

    with open(manifest_path, "w") as mf:
        json.dump(manifest, mf, indent=2)

    return patched_tasks


# Bengali script Unicode ranges to include from the custom font.
# U+0980-U+09FF  Bengali block (primary)
# The following shared/utility codepoints are also always included as they
# are required for correct Unicode text rendering:
#   U+200C  ZERO WIDTH NON-JOINER   (used for explicit half-form in Bengali)
#   U+200D  ZERO WIDTH JOINER       (used for ZWJ-conjunct formation)
#   U+25CC  DOTTED CIRCLE           (standard base for displaying combining marks)
BENGALI_SCRIPT_RANGES = [range(0x0980, 0x0A00)]
BENGALI_SHARED_CODEPOINTS = [0x200C, 0x200D, 0x25CC]


def _get_script_active_lookup_count(script_record, feature_list):
    """
    Count how many GSUB/GPOS lookups a script entry still references.
    Used after subsetting to determine if the script has any remaining rules.
    """
    script = script_record.Script
    feature_indices = set()
    if script.DefaultLangSys:
        feature_indices.update(script.DefaultLangSys.FeatureIndex)
    for ls in script.LangSysRecord:
        feature_indices.update(ls.LangSys.FeatureIndex)

    active_lookups = set()
    for fi in feature_indices:
        feature = feature_list.FeatureRecord[fi].Feature
        active_lookups.update(feature.LookupListIndex)
    return len(active_lookups)


def create_bengali_only_subset(font_path, target_upem):
    """
    Extract a Bengali-only subset from ANY Bengali font — works universally
    regardless of the font's name, script tags, or internal structure.

    How it works:
    1. Collects every codepoint in U+0980-U+09FF actually present in the font,
       plus three essential shared rendering chars (ZWNJ, ZWJ, DOTTED CIRCLE).
    2. Uses fontTools.subset to keep only glyphs reachable from those codepoints.
       fontTools.subset automatically prunes:
         - All Latin/Greek/Cyrillic/other glyphs not reachable from Bengali
         - All GSUB/GPOS lookups that referenced only the now-removed glyphs
    3. Removes any GSUB/GPOS ScriptList entries that have zero active lookups
       after subsetting (these are the empty Latin/Greek/Cyrillic entries left
       over by the font's internal structure — their lookups were all pruned away
       since none of them reference Bengali glyphs).
       This step is purely mechanical: it does NOT rely on knowing any specific
       script tag names (no hardcoded 'latn', 'beng', 'bng2', etc.), making it
       work correctly with every Bengali font in existence.
    4. Rescales metrics to match Nirmala UI's UPM.

    Returns (subsetted TTFont, number_of_bengali_codepoints_found).
    """
    from fontTools.ttLib import TTFont, scaleUpem as scaleUpemMod
    from fontTools import subset as ft_subset

    # --- Step 1: Discover which Bengali codepoints exist in this font ---
    src = TTFont(font_path)
    bengali_cps = []
    for t in src['cmap'].tables:
        if t.isUnicode():
            for cp in t.cmap.keys():
                for rng in BENGALI_SCRIPT_RANGES:
                    if cp in rng:
                        bengali_cps.append(cp)
                        break
    src.close()

    if not bengali_cps:
        raise ValueError(
            "No Bengali codepoints (U+0980-U+09FF) found in '%s'.\n"
            "Please make sure your font contains Bengali characters." % font_path
        )

    all_keep = list(set(bengali_cps) | set(BENGALI_SHARED_CODEPOINTS))

    # --- Step 2: Subset to Bengali glyphs only ---
    # layout_features='*' retains all OpenType feature tags but fontTools.subset
    # automatically prunes any lookup whose input/output glyphs no longer exist
    # in the subset — so only Bengali shaping rules will survive.
    options = ft_subset.Options()
    options.retain_gids = False
    options.layout_features = ['*']
    options.name_IDs = ['*']
    options.notdef_outline = True
    options.recommended_glyphs = False  # don't pull in non-Bengali recommended chars

    subsetter = ft_subset.Subsetter(options=options)
    subsetter.populate(unicodes=all_keep)

    b_sub = TTFont(font_path)
    subsetter.subset(b_sub)

    # --- Step 3: Remove script entries with zero active lookups ---
    # After subsetting, any ScriptList entry whose features all have empty
    # LookupListIndex arrays was previously serving non-Bengali scripts (like
    # 'latn', 'cyrl', 'grek').  We remove those entries so they cannot compete
    # with Nirmala's own layout rules for those scripts.
    # Crucially, this does NOT rely on knowing specific script tag names —
    # it works the same way for any font, any script registration scheme.
    for table_tag in ('GSUB', 'GPOS'):
        if table_tag not in b_sub:
            continue
        tbl = b_sub[table_tag].table
        if not tbl.ScriptList:
            continue
        active_script_records = [
            sr for sr in tbl.ScriptList.ScriptRecord
            if _get_script_active_lookup_count(sr, tbl.FeatureList) > 0
        ]
        if active_script_records:
            tbl.ScriptList.ScriptRecord = active_script_records
            tbl.ScriptList.ScriptCount = len(active_script_records)
        # If ALL scripts became empty (edge case: font had no Bengali shaping),
        # we leave the ScriptList as-is — the empty tables are harmless.

    # --- Step 4: Rescale to match Nirmala's UPM ---
    if b_sub['head'].unitsPerEm != target_upem:
        scaleUpemMod.scale_upem(b_sub, target_upem)

    return b_sub, len(bengali_cps)



def merge_single_face(nirmala_ttf_path, bengali_font_path, output_path):
    """
    Merge a single Nirmala UI TTF with a custom Bengali font.

    Only Bengali-script glyphs from the custom font are introduced into the
    merged result. Latin, Greek, Cyrillic and all other non-Bengali glyphs in
    the custom font are discarded before the merge, so Nirmala's own glyphs
    and layout rules for those scripts remain completely untouched.
    """
    from fontTools.ttLib import TTFont, scaleUpem
    from fontTools.merge import Merger

    temp_dir = os.path.join(os.path.dirname(output_path), ".temp_merge")
    os.makedirs(temp_dir, exist_ok=True)
    fname_n = os.path.basename(nirmala_ttf_path)
    fname_b = os.path.basename(bengali_font_path)

    temp_stripped = os.path.join(temp_dir, f"stripped_{fname_n}")
    temp_bengali_only = os.path.join(temp_dir, f"bengali_only_{fname_b}")

    try:
        # --- Step A: Strip existing Bengali entries from Nirmala ---
        n_font = TTFont(nirmala_ttf_path)
        target_upem = n_font['head'].unitsPerEm
        removed = strip_bengali_from_font(n_font)
        n_font.save(temp_stripped)

        # --- Step B: Produce a Bengali-only subset of the custom font ---
        b_sub, bengali_count = create_bengali_only_subset(bengali_font_path, target_upem)
        print(f"        Bengali glyphs in subset: {bengali_count} codepoints kept, non-Bengali glyphs discarded.")

        # Drop tables that are incompatible with fontTools.merge or not present
        # in Nirmala (vertical metrics, variable font tables, STAT, etc.)
        tags_to_drop = {
            'vhea', 'vmtx', 'STAT', 'DSIG', 'fvar', 'gvar', 'HVAR',
            'VVAR', 'cvar', 'avar', 'MVAR', 'meta'
        }
        for tag in list(b_sub.keys()):
            if tag in tags_to_drop or tag not in n_font:
                del b_sub[tag]

        b_sub.save(temp_bengali_only)

        # --- Step C: Merge Nirmala + Bengali-only subset ---
        merger = Merger()
        merger.options.drop_tables = list(set(merger.options.drop_tables) | tags_to_drop)
        merged = merger.merge([temp_stripped, temp_bengali_only])
        optimize_gasp_table(merged)
        merged.save(output_path)

    finally:
        for temp in (temp_stripped, temp_bengali_only):
            if os.path.exists(temp):
                try:
                    os.remove(temp)
                except Exception:
                    pass
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass


def rebuild_ttc(merged_ttf_info_list, output_ttc_path):
    """Rebuild a Windows TrueType Collection (.ttc) from merged TTFs in original order."""
    from fontTools.ttLib import TTCollection, TTFont

    sorted_info = sorted(merged_ttf_info_list, key=lambda x: x["index"])
    ttc = TTCollection()
    ttc.fonts = [TTFont(item["merged_path"]) for item in sorted_info]
    for f in ttc.fonts:
        optimize_gasp_table(f)
    ttc.save(output_ttc_path)
    print(f"[+] Rebuilt TrueType Collection saved to: {output_ttc_path}")


def replace_font_file(src_path, dst_path):
    """
    Replace a font file in Windows.
    Takes ownership, grants permissions, attempts immediate copy,
    and falls back to Windows MoveFileEx (delay until reboot) if locked.
    """
    take_ownership(dst_path)

    # Attempt 1: Direct copy
    try:
        shutil.copy2(src_path, dst_path)
        print(f"    [OK] Immediately replaced: {dst_path}")
        return "immediate"
    except (PermissionError, OSError):
        pass

    # Attempt 2: Win32 MoveFileEx with delay until reboot
    staging_file = dst_path + ".new_update"
    try:
        shutil.copy2(src_path, staging_file)
    except (PermissionError, OSError):
        win_temp = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Temp", "FontMergerStaging")
        os.makedirs(win_temp, exist_ok=True)
        h = abs(hash(dst_path))
        staging_file = os.path.join(win_temp, f"staged_{h}_{os.path.basename(dst_path)}")
        try:
            shutil.copy2(src_path, staging_file)
        except Exception as ex:
            print(f"    [ERROR] Could not stage font replacement for {dst_path}: {ex}")
            return "failed"

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        MoveFileExW = kernel32.MoveFileExW
        MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        MoveFileExW.restype = wintypes.BOOL

        flags = MOVEFILE_REPLACE_EXISTING | MOVEFILE_DELAY_UNTIL_REBOOT
        res = MoveFileExW(staging_file, dst_path, flags)
        if res:
            print(f"    [SCHEDULED] File is in-use by Windows. Replacement scheduled on next reboot: {dst_path}")
            return "reboot"
        else:
            err = ctypes.get_last_error()
            print(f"    [ERROR] Failed to schedule replacement for {dst_path}: Win32 error {err}")
            return "failed"
    except Exception as ex:
        print(f"    [ERROR] Could not schedule MoveFileEx for {dst_path}: {ex}")
        return "failed"


def clear_font_cache():
    """Clear Windows Font Cache to ensure newly merged fonts take effect."""
    print("[*] Clearing Windows Font Cache...")
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
    print("[+] Windows Font Cache refreshed.")


def restore_backup(backup_dir, nirmala_locations):
    """Restore both original Nirmala and Segoe UI fonts from backup."""
    # 1. Restore Nirmala
    backup_file = os.path.join(backup_dir, "Nirmala_backup.ttc")
    if not os.path.exists(backup_file):
        legacy_backup = os.path.join(os.path.dirname(backup_dir), "backup", "Nirmala_backup.ttc")
        if os.path.exists(legacy_backup):
            backup_file = legacy_backup

    if os.path.exists(backup_file):
        print(f"[*] Restoring original Nirmala font from '{backup_file}'...")
        for loc in nirmala_locations:
            replace_font_file(backup_file, loc)
    else:
        print("[!] No Nirmala backup file found.")

    # 2. Restore Segoe UI
    segoe_manifest = os.path.join(backup_dir, "segoe", "segoe_manifest.json")
    if not os.path.exists(segoe_manifest):
        legacy_segoe = os.path.join(os.path.dirname(backup_dir), "backup", "segoe", "segoe_manifest.json")
        if os.path.exists(legacy_segoe):
            segoe_manifest = legacy_segoe
    if os.path.exists(segoe_manifest):
        try:
            with open(segoe_manifest, "r") as mf:
                manifest = json.load(mf)
            print("[*] Restoring original Segoe UI fonts...")
            for sys_path, bkp_path in manifest.items():
                if os.path.exists(bkp_path):
                    replace_font_file(bkp_path, sys_path)
        except Exception as e:
            print(f"[!] Error reading Segoe manifest: {e}")

    clear_font_cache()
    print("[+] Restoration complete! Please restart your computer to apply the original fonts.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Merge custom Bengali font into Windows Nirmala UI and Segoe UI, replacing system fonts.")
    parser.add_argument("--bengali-font", "-b", help="Path to your custom Bengali .ttf or .otf font file.")
    parser.add_argument("--restore", "-r", action="store_true", help="Restore original Windows Nirmala and Segoe UI fonts from backup.")
    args = parser.parse_args()

    print("=" * 68)
    print("      Nirmala UI & Segoe UI Bengali Font Merger & Replacer")
    print("=" * 68)

    if not is_admin():
        print("[!] WARNING: Administrator privileges are required to replace system fonts.")
        print("[!] Please run this script or batch file as Administrator.\n")

    ensure_dependencies()

    working_dir = os.path.dirname(os.path.abspath(__file__))
    custom_bangla_dir = os.path.join(working_dir, "custom_bangla")
    if not os.path.exists(custom_bangla_dir) and os.path.exists(os.path.join(working_dir, "custom_font")):
        custom_bangla_dir = os.path.join(working_dir, "custom_font")
    custom_font_dir = custom_bangla_dir

    backup_dir = os.path.join(working_dir, "backup_bangla")
    # Fallback to existing legacy backup directory if present
    if not os.path.exists(os.path.join(backup_dir, "Nirmala_backup.ttc")) and os.path.exists(os.path.join(working_dir, "backup", "Nirmala_backup.ttc")):
        backup_dir = os.path.join(working_dir, "backup")

    extracted_dir = os.path.join(working_dir, "extracted_ttf")
    merged_dir = os.path.join(working_dir, "merged_ttf")
    output_dir = os.path.join(working_dir, "output")
    segoe_patched_dir = os.path.join(output_dir, "segoe_patched")

    os.makedirs(custom_font_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(extracted_dir, exist_ok=True)
    os.makedirs(merged_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(segoe_patched_dir, exist_ok=True)

    # 1. Search for Nirmala UI in Windows
    print("\n[Step 1/7] Searching for Nirmala UI in Windows...")
    locations = find_nirmala_fonts()
    if not locations:
        print("[!] Could not locate any Nirmala font files on your system.")
        return

    print(f"[+] Found {len(locations)} location(s):")
    for loc in locations:
        print(f"    - {loc}")

    # Handle Restore Option
    if args.restore:
        restore_backup(backup_dir, locations)
        return

    # Find the primary TTC
    primary_ttc = next((loc for loc in locations if loc.lower().endswith(".ttc")), locations[0])

    # 2. Copy and Backup Nirmala
    print("\n[Step 2/7] Backing up original Nirmala font...")
    backup_file = os.path.join(backup_dir, "Nirmala_backup.ttc")
    if not os.path.exists(backup_file):
        shutil.copy2(primary_ttc, backup_file)
        print(f"[+] Backup created at: {backup_file}")
    else:
        print(f"[*] Existing backup preserved at: {backup_file}")

    # 3. Separate TTC to TTFs
    print("\n[Step 3/7] Extracting font faces from TTC...")
    extracted_faces = extract_ttc_to_ttfs(primary_ttc, extracted_dir)

    # 4. Scan and Patch Segoe UI (Removing Bengali numbers / currency marks)
    print("\n[Step 4/7] Scanning Segoe UI fonts for conflicting Bengali numbers/marks...")
    segoe_tasks = scan_and_patch_segoe_ui(backup_dir, segoe_patched_dir)
    if segoe_tasks:
        print(f"[+] Successfully prepared {len(segoe_tasks)} patched Segoe UI font(s) without Bengali numbers.")
    else:
        print("[*] No conflicting Bengali numbers found in Segoe UI fonts.")

    # 5. Locate user's provided Bengali font(s)
    print("\n[Step 5/7] Locating custom Bengali font(s)...")
    bengali_info = find_user_bengali_fonts(working_dir, args.bengali_font)

    if not bengali_info or not bengali_info.get("candidates"):
        print("\n" + "!" * 68)
        print("[!] NO CUSTOM BENGALI FONT FOUND!")
        print(f"[*] Please place your Bengali font (.ttf or .otf) inside:")
        print(f"    {custom_font_dir}")
        print("[*] (Example: Kalpurush.ttf, SolaimanLipi.ttf, Siyamrupali.ttf)")
        print("[*] Then run this script or run_merger.bat again!")
        print("!" * 68 + "\n")
        return

    candidates = bengali_info["candidates"]
    source_dir = bengali_info.get("source_dir", custom_font_dir)

    print(f"[*] Found {len(candidates)} custom font file(s) in: {source_dir}")
    for c in sorted(candidates, key=lambda x: x["weight"]):
        print(f"    - {c['filename']:32} [Weight: {c['weight']} - {c['style']}]")

    # 6. Perform the merge operation
    print("\n[Step 6/7] Performing font merge operations for Nirmala UI...")
    merged_faces = []
    for face in extracted_faces:
        target_weight = face.get("target_weight", 400)
        matched_font = find_closest_font(target_weight, candidates)
        chosen_bengali = matched_font["path"]

        merged_filename = f"Merged_{face['filename']}"
        merged_path = os.path.join(merged_dir, merged_filename)

        weight_diff = abs(matched_font["weight"] - target_weight)
        print(f"[*] Merging '{face['full_name']}' (Target Weight: {target_weight})")
        print(f"    -> Closest Weight Match: '{matched_font['filename']}' (Weight: {matched_font['weight']}, Diff: {weight_diff})")
        merge_single_face(face["path"], chosen_bengali, merged_path)
        face["merged_path"] = merged_path
        merged_faces.append(face)

    # Rebuild TTC collection
    output_ttc = os.path.join(output_dir, "Nirmala.ttc")
    rebuild_ttc(merged_faces, output_ttc)

    # 7. Replace in Windows
    print("\n[Step 7/7] Replacing fonts in Windows...")
    needs_reboot = False

    # Replace Nirmala UI fonts
    print("[*] Replacing Nirmala UI collection...")
    for target in locations:
        result = replace_font_file(output_ttc, target)
        if result == "reboot":
            needs_reboot = True

    # Replace patched Segoe UI fonts
    if segoe_tasks:
        print("[*] Replacing Segoe UI fonts (removing Bengali digits/marks)...")
        for patched_src, target_dst in segoe_tasks:
            result = replace_font_file(patched_src, target_dst)
            if result == "reboot":
                needs_reboot = True

    clear_font_cache()

    print("\n" + "=" * 68)
    if needs_reboot:
        print(" [!] SUCCESS! Fonts have been scheduled for replacement.")
        print("     Because Windows keeps system fonts locked in memory,")
        print("     the replacement will automatically complete on REBOOT.")
        print("     >>> PLEASE RESTART YOUR COMPUTER TO APPLY THE NEW FONT! <<<")
    else:
        print(" [+] SUCCESS! All fonts have been replaced immediately.")
        print("     Restarting your applications or PC will reflect the new font.")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
