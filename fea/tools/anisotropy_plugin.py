"""The Anisotropy menu in Abaqus/CAE (ADR-0094, step 8): Plug-ins > Anisotropy > "Open from Anisotropy..." and "Send to Anisotropy...".

Abaqus/CAE imports every file named `*_plugin.py` that it finds, when it starts, under a folder called `abaqus_plugins` in the user's
home directory, in the directory it is started in, or in its own installation, and in their subfolders. To install the menu, copy
the connector's folder (this file with `anisotropy_menu.py`, `anisotropy_build.py`, `anisotropy_connector.py`, `bundle.py`,
`abaqus_every_output.py` and `abaqus_extract_fields.py`) into `abaqus_plugins` in your home directory and start Abaqus/CAE again.

This file registers the two entries. Each is a kernel plug-in: a click makes Abaqus/CAE import `anisotropy_menu` in its kernel
and call one function there, which asks its questions with Abaqus's own input box. No window of our own is drawn. The menu is under
Plug-ins because that is where Abaqus/CAE puts what a user adds; a menu of its own on the main bar would mean replacing Abaqus/CAE's
own main window.

In an Abaqus/CAE that a click on the site started (amendment 1), and in no other, it also shows in the message area what the menu's
job-completed callback says (`Messages`). That is the one place that uses the window's toolkit, and the menu does not depend on it:
where it cannot be had, the entries are registered all the same and the kernel prints its own lines as before.
"""

import io
import os
import re
import time

from abaqusGui import getAFXApp

try:
    from abaqusGui import FXMAPFUNC, SEL_TIMEOUT, FXObject
except ImportError:  # a window made otherwise: the menu is registered all the same
    FXObject = object

VERSION = "0.7.0"
ENTRIES = (
    ("Anisotropy|Open from Anisotropy...", "open_from_anisotropy()",
     "Builds a coupon as a native model in this session from the coupon file that Send to Abaqus left on this PC. Nothing is saved "
     "until you save it."),
    ("Anisotropy|Send to Anisotropy...", "send_to_anisotropy()",
     "Writes one file from a finished job, its results, its input file and the model as built, and sends it to Anisotropy when you give "
     "the address and your upload key. Your .cae and your ODB are not changed."),
)

toolset = getAFXApp().getAFXMainWindow().getPluginToolset()
for text, function, about in ENTRIES:
    toolset.registerKernelMenuButton(buttonText=text, moduleName="anisotropy_menu", functionName=function, author="Anisotropy",
                                     version=VERSION, description=about)


# ------------------------------------------------------------------- what a completed job says, shown from the window's side (amendment 1)

SESSION = "ANISOTROPY_SESSION"  # `anisotropy_link.start` names the window it starts; `anisotropy_menu.window_files` reads the same
SESSION_SHAPE = re.compile(r"[0-9a-f]{16}")
TICK_MS = 500
OLD_S = 24 * 3600.0  # files of a session that long ago are cleared at the next start


def state_folder() -> str:
    return os.path.join(os.path.expanduser("~"), ".anisotropy")


def clear_old(folder: str, now: float) -> None:
    """Take away what windows that ended long ago left: nothing tells this file that its window ends."""
    try:
        names = [name for name in os.listdir(folder) if name.startswith("messages-")]
    except OSError:
        return
    for name in names:
        try:
            if now - os.path.getmtime(os.path.join(folder, name)) > OLD_S:
                os.remove(os.path.join(folder, name))
        except OSError:
            continue


class Messages(FXObject):
    """Shows in the message area, from the window's own side, the lines the menu's job-completed callback held back. A print from
    the kernel while the window has a command waiting can hold that command's answer until the next one, so a click made while the
    results are sent looked unfinished (the twelfth trial). The kernel writes its lines to a file named for this window instead,
    and every half second this takes the file and writes its lines here. It says that it does so by a second file, made at its first
    tick: until that is there the kernel prints as before."""
    ID_TICK = 1

    def __init__(self, session, folder):
        FXObject.__init__(self)
        self.file = os.path.join(folder, "messages-%s.txt" % session)
        self.marker = os.path.join(folder, "messages-%s.window" % session)
        FXMAPFUNC(self, SEL_TIMEOUT, Messages.ID_TICK, Messages.onTick)

    def arm(self):
        getAFXApp().addTimeout(TICK_MS, self, Messages.ID_TICK)  # FOX's order in Abaqus 2025: milliseconds, target, selector

    def onTick(self, sender, sel, ptr):  # noqa: N802  FOX's own way of naming a handler
        try:
            if not os.path.exists(self.marker):
                os.makedirs(os.path.dirname(self.marker), exist_ok=True)
                io.open(self.marker, "w", encoding="utf-8").close()
            if os.path.exists(self.file):
                taken = self.file + ".taken"
                os.replace(self.file, taken)
                with io.open(taken, encoding="utf-8") as handle:
                    lines = handle.read().splitlines()
                os.remove(taken)
                main = getAFXApp().getAFXMainWindow()
                for line in lines:
                    main.writeToMessageArea(line)
        except Exception:  # noqa: BLE001  a line not shown is no reason to stop showing the next ones
            pass
        try:
            self.arm()
        except Exception:  # noqa: BLE001  nothing shows the lines any more: say so to the kernel, which prints them again
            try:
                os.remove(self.marker)
            except OSError:
                pass
        return 1


MESSAGES = None
if SESSION_SHAPE.fullmatch(os.environ.get(SESSION, "")):
    try:
        clear_old(state_folder(), time.time())
        MESSAGES = Messages(os.environ[SESSION], state_folder())
        MESSAGES.arm()
    except Exception:  # noqa: BLE001  the menu is there without it
        MESSAGES = None
