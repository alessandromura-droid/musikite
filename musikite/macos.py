"""
macOS-only details of the desktop app (no Qt; does nothing on other systems, Android
included).

AppKit adds its own items to every menu titled "Edit": Emoji & Symbols, Start
Dictation… and, from macOS 14, AutoFill. They are not MusiKitE's (owner, 2026-11-24:
"take them away"). They are switched off with NSUserDefaults keys put in the
REGISTRATION domain of the process (`registerDefaults:`): nothing is written on disk,
nothing changes for other programs (also when the app runs from the source and the
process is Python). Must run BEFORE the QApplication is created (AppKit reads the keys
when it sets up the menu bar).

AutoFill (owner, 2026-11-25: still there with the key below): AppKit recognises the
Edit menu BY ITS TITLE, so the menu bar uses `edit_menu_title()` = "Edit" followed by an
invisible WORD JOINER (U+2060): it looks the same, AppKit no longer treats it as the
Edit menu and adds none of its items (AutoFill included). The keys stay as a second
safety for Emoji and Dictation.
"""
import sys

# NSUserDefaults key -> value
EDIT_MENU_DEFAULTS = {
    "NSDisabledCharacterPaletteMenuItem": True,      # Emoji & Symbols
    "NSDisabledDictationMenuItem": True,             # Start Dictation…
    "NSAutoFillHeuristicControllerEnabled": False,   # AutoFill (macOS 14+)
}

_done = False

# invisible character after "Edit": AppKit does not recognise the menu (no AutoFill…)
WORD_JOINER = "\u2060"


def edit_menu_title():
    """Title of the Edit menu: on macOS "Edit" + an invisible word joiner (no system
    items added by AppKit); elsewhere "&Edit" as before."""
    if sys.platform == "darwin":
        return "&Edit" + WORD_JOINER
    return "&Edit"


def hide_system_edit_items():
    """Switch off the items AppKit adds to the Edit menu. True if done (macOS only);
    called once, before the QApplication exists; never raises."""
    global _done
    if _done or sys.platform != "darwin":
        return False
    _done = True
    try:
        import ctypes
        import ctypes.util
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary(ctypes.util.find_library("Foundation"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.objc_autoreleasePoolPush.restype = ctypes.c_void_p
        objc.objc_autoreleasePoolPush.argtypes = []
        objc.objc_autoreleasePoolPop.restype = None
        objc.objc_autoreleasePoolPop.argtypes = [ctypes.c_void_p]
        address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value

        def send(restype, *argtypes):
            # objc_msgSend with the exact prototype of each call (needed on arm64)
            return ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p,
                                    *argtypes)(address)

        def cls(name):
            return objc.objc_getClass(name.encode())

        def sel(name):
            return objc.sel_registerName(name.encode())

        pool = objc.objc_autoreleasePoolPush()
        try:
            make_str = send(ctypes.c_void_p, ctypes.c_char_p)
            make_bool = send(ctypes.c_void_p, ctypes.c_bool)
            d = send(ctypes.c_void_p)(cls("NSMutableDictionary"), sel("dictionary"))
            put = send(None, ctypes.c_void_p, ctypes.c_void_p)
            for key, value in EDIT_MENU_DEFAULTS.items():
                v = make_bool(cls("NSNumber"), sel("numberWithBool:"), bool(value))
                k = make_str(cls("NSString"), sel("stringWithUTF8String:"), key.encode())
                put(d, sel("setObject:forKey:"), v, k)
            ud = send(ctypes.c_void_p)(cls("NSUserDefaults"), sel("standardUserDefaults"))
            send(None, ctypes.c_void_p)(ud, sel("registerDefaults:"), d)
        finally:
            objc.objc_autoreleasePoolPop(pool)
        return True
    except Exception:
        return False
