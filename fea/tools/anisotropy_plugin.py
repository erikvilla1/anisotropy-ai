"""The Anisotropy menu in Abaqus/CAE (ADR-0094, step 8): Plug-ins > Anisotropy > "Open from Anisotropy..." and "Send to Anisotropy...".

Abaqus/CAE imports every file named `*_plugin.py` that it finds, when it starts, under a folder called `abaqus_plugins` in the user's
home directory, in the directory it is started in, or in its own installation, and in their subfolders. To install the menu, copy
the connector's folder (this file with `anisotropy_menu.py`, `anisotropy_connector.py`, `bundle.py`, `abaqus_every_output.py` and
`abaqus_extract_fields.py`) into `abaqus_plugins` in your home directory and start Abaqus/CAE again.

This file only registers the two entries. Each is a kernel plug-in: a click makes Abaqus/CAE import `anisotropy_menu` in its kernel
and call one function there, which asks its questions with Abaqus's own input box. No window of our own is drawn, so nothing here
depends on the toolkit Abaqus/CAE's windows are made with. The menu is under Plug-ins because that is where Abaqus/CAE puts what a
user adds; a menu of its own on the main bar would mean replacing Abaqus/CAE's own main window.
"""

from abaqusGui import getAFXApp

VERSION = "0.4.0"
ENTRIES = (
    ("Anisotropy|Open from Anisotropy...", "open_from_anisotropy()",
     "Builds a coupon from the build script you downloaded from Anisotropy as a native model in this session. Nothing is saved until you save it."),
    ("Anisotropy|Send to Anisotropy...", "send_to_anisotropy()",
     "Writes one file from a finished job, its results, its input file and the model as built, and sends it to Anisotropy when you give "
     "the address and your upload key. Your .cae and your ODB are not changed."),
)

toolset = getAFXApp().getAFXMainWindow().getPluginToolset()
for text, function, about in ENTRIES:
    toolset.registerKernelMenuButton(buttonText=text, moduleName="anisotropy_menu", functionName=function, author="Anisotropy",
                                     version=VERSION, description=about)
