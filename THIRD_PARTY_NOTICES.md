# Third-party notices

The MIT license covers Bible Finder's application code, not third-party texts or runtimes.

## Scripture

Chinese Union Version Simplified (cus), Traditional (cut), and World English Bible (web) are marked Public Domain in the GetBible v2 translation catalog. Original metadata and hashes are in `src/appcore/data/sources.json`; detailed attribution is in `docs/data-sources.md`.

Provider: https://getbible.net/ and CrossWire SWORD. Chinese source: http://bible.fhl.net ; WEB source: https://ebible.org/web/ . The name World English Bible identifies the source translation. No translated wording is changed; only layout whitespace is normalized.

No code, images, brand assets or scripture database from bibletool.konline.org is redistributed.

## Windows runtime

The Windows executable bundles CPython, Tcl/Tk and components of their standard library. Their full notices are provided in the `licenses/` directory included in the release ZIP. Python uses the Python Software Foundation license and additional bundled-library notices; Tcl/Tk use their respective permissive licenses. See https://docs.python.org/3/license.html and https://www.tcl.tk/software/tcltk/license.html .

PyInstaller's bootloader is distributed under GPL with an exception permitting bundled applications to retain their own license. See https://pyinstaller.org/en/stable/license.html . Build tools are pinned in requirements-dev.txt; they are not application runtime dependencies.
