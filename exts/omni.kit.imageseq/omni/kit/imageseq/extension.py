import asyncio
from functools import partial

import omni.ext
import omni.kit.app
import omni.kit.ui
import omni.ui
import omni.usd

from .window import KitImageSequenceWindow


class KitImageSequenceExtension(omni.ext.IExt):
    WINDOW_NAME = "Image Sequence Importer"
    MENU_PATH = f"Window/{WINDOW_NAME}"

    def on_startup(self):
        # The ability to show up the window if the system requires it. We use it
        # in QuickLayout.
        self._window = None
        omni.ui.Workspace.set_show_window_fn(KitImageSequenceExtension.WINDOW_NAME, partial(self.show_window, None))
        # Put the new menu
        editor_menu = omni.kit.ui.get_editor_menu()
        if editor_menu:
            self._menu = editor_menu.add_item(
                KitImageSequenceExtension.MENU_PATH, self.show_window, toggle=True, value=True
            )

        # Show the window. It will call `self.show_window`
        omni.ui.Workspace.show_window(KitImageSequenceExtension.WINDOW_NAME)

    def on_shutdown(self):
        if self._window:
            self._window.destroy()
            self._window = None

        editor_menu = omni.kit.ui.get_editor_menu()
        if editor_menu:
            editor_menu.remove_item(KitImageSequenceExtension.MENU_PATH)
        self._menu = None

        # Deregister the function that shows the window from omni.ui
        omni.ui.Workspace.set_show_window_fn(KitImageSequenceExtension.WINDOW_NAME, None)

    def _set_menu(self, value):
        """Set the menu to create this window on and off"""
        editor_menu = omni.kit.ui.get_editor_menu()
        if editor_menu:
            editor_menu.set_value(KitImageSequenceExtension.MENU_PATH, value)

    async def _destroy_window_async(self):
        # wait one frame, this is due to the one frame defer
        # in Window::_moveToMainOSWindow()
        await omni.kit.app.get_app().next_update_async()
        if self._window:
            self._window.destroy()
            self._window = None

    def _visibility_changed_fn(self, visible):
        # Called when the user pressed "X"
        self._set_menu(visible)
        if not visible:
            # Destroy the window, since we are creating new window
            # in show_window
            asyncio.ensure_future(self._destroy_window_async())

    def show_window(self, menu, value):
        if value:
            self._window = KitImageSequenceWindow(KitImageSequenceExtension.WINDOW_NAME, width=300, height=365)
            self._window.set_visibility_changed_fn(self._visibility_changed_fn)
        elif self._window:
            self._window.visible = False
