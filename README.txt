========================================================================
             NIRMALA UI BENGALI FONT MERGER FOR WINDOWS
========================================================================

HOW IT WORKS:
-------------
- AUTOMATIC DISCOVERY & BACKUP:
  You do NOT need to extract or provide any Nirmala font files.
  On any Windows PC, the script automatically locates the original
  Windows Nirmala UI and Segoe UI fonts, creates untouched backups in
  the "backup\" directory, and splits the TrueType Collection into
  individual TTFs for merging.

- CLOSEST-WEIGHT MATCHING:
  You can place any number of font weights from your custom font family
  into "custom_font\" (e.g. Light, Regular, Medium, SemiBold, Bold, Black).
  The script automatically reads the OpenType weight class (usWeightClass
  100-900) and matches each Windows Nirmala UI face to the closest
  available weight in your custom family:
    * Nirmala UI Semilight (Weight: 350) -> matches Light / Regular
    * Nirmala UI Regular   (Weight: 400) -> matches Regular / Normal / Book
    * Nirmala UI Bold      (Weight: 700) -> matches Bold / SemiBold / Black

WHERE TO PUT YOUR CUSTOM FONT:
------------------------------
Put your custom Bengali font (.ttf or .otf files) inside:

    custom_font\

Examples:
- Single font:
    custom_font\Kalpurush.ttf
- Multi-weight family:
    custom_font\NotoSerifBengali-Light.ttf
    custom_font\NotoSerifBengali-Regular.ttf
    custom_font\NotoSerifBengali-Medium.ttf
    custom_font\NotoSerifBengali-Bold.ttf

HOW TO RUN:
-----------
1. Put your font file(s) into the "custom_font" folder.
2. Double-click "run_merger.bat" from the main folder.
   Click "Yes" on the Administrator prompt.
3. Once complete, restart your computer!

HOW TO RESTORE:
---------------
If you ever want to revert back to Microsoft's original default fonts:
1. Double-click "restore_original.bat".
2. Restart your computer.
   Both original Nirmala UI and Segoe UI fonts will be fully restored!
========================================================================
