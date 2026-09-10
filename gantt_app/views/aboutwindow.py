"""
The "About PySimplePMT" window.

A small, modal card that shows the application logo, name, version, author and
licence. It is deliberately thin: one instance at a time, centred over the
window that opened it, and never fatal - if the logo cannot be read it simply
does not appear and the text stands on its own.

The logo comes from gantt_app.resources.appicon, the same source the window
icon and the packaged marks read, so the About box cannot show a mark the
application does not otherwise wear.
"""

import tkinter as tk

import customtkinter as ctk

from gantt_app import __author__, __version__
from gantt_app import theme
from gantt_app.utils.log import get_logger
from gantt_app.views.modal import grab_when_visible

logger = get_logger(__name__)

#: The width the logo is shown at in the card. The height follows the source
#: image's aspect ratio.
LOGO_WIDTH = 380

#: A one-line description of what the application is.
TAGLINE = "A cross-platform desktop project planner with Gantt scheduling."


class AboutWindow(ctk.CTkToplevel):
    """The About card. Use :meth:`show` rather than constructing directly."""

    TITLE = "About PySimplePMT"

    #: The one instance, so opening About twice raises the first rather than
    #: stacking a second copy.
    _open_window = None

    def __init__(self, master=None):
        super().__init__(master)
        self.title(self.TITLE)
        self.resizable(False, False)
        if master is not None:
            try:
                self.transient(master.winfo_toplevel())
            except Exception:
                pass

        self._logo_image = None
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda _event: self._close())

        self.update_idletasks()
        self._centre_over(master)
        grab_when_visible(self)

    # -- construction -------------------------------------------------------

    def _build(self):
        """Lay out the logo, the wordmark and the credits."""
        container = ctk.CTkFrame(self, fg_color=theme.pair(theme.DASH_BOARD_BG))
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self._add_logo(container)

        ctk.CTkLabel(
            container, text="PySimplePMT",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.pair(theme.TEXT),
        ).pack(pady=(14, 0))

        ctk.CTkLabel(
            container, text=f"Version {__version__}",
            font=ctk.CTkFont(size=13),
            text_color=theme.pair(theme.MUTED_TEXT),
        ).pack(pady=(2, 0))

        ctk.CTkLabel(
            container, text=TAGLINE, wraplength=LOGO_WIDTH,
            font=ctk.CTkFont(size=12),
            text_color=theme.pair(theme.TEXT),
        ).pack(pady=(12, 0))

        ctk.CTkLabel(
            container, text=f"Created by {__author__}",
            font=ctk.CTkFont(size=12),
            text_color=theme.pair(theme.MUTED_TEXT),
        ).pack(pady=(10, 0))

        ctk.CTkLabel(
            container, text="Released under the MIT License",
            font=ctk.CTkFont(size=12),
            text_color=theme.pair(theme.MUTED_TEXT),
        ).pack(pady=(2, 0))

        # Update status (issue #41): its own frame so the Download button can
        # appear under the message without disturbing the Close button below.
        # Filled in by a background check, so the window opens at once and
        # never hangs on the network.
        update_frame = ctk.CTkFrame(container, fg_color="transparent")
        update_frame.pack(pady=(12, 0))
        self._update_label = ctk.CTkLabel(
            update_frame, text="Checking for updates…", wraplength=LOGO_WIDTH,
            font=ctk.CTkFont(size=12),
            text_color=theme.pair(theme.MUTED_TEXT),
        )
        self._update_label.pack()
        # The assisted download-verify-open button, and a plain page link as a
        # fallback; both packed only when there is an update to act on.
        self._install_button = ctk.CTkButton(
            update_frame, text="Download & Install…", width=180,
            command=self._download_and_install)
        self._download_button = ctk.CTkButton(
            update_frame, text="Open the download page", width=180,
            fg_color="transparent", border_width=1,
            border_color=theme.pair(theme.SEPARATOR),
            text_color=theme.pair(theme.TEXT),
            command=self._open_download)
        self._update_frame = update_frame
        self._download_url = None
        self._update_info = None
        self._downloading = False

        ctk.CTkButton(
            container, text="Close", width=110, command=self._close,
        ).pack(pady=(14, 4))

        self._start_update_check()

    def _add_logo(self, parent):
        """
        Put the logo on a white plate so it reads the same in day and night.

        The logo is drawn on a white ground; on a dark card that would float
        as a bright rectangle. Seating it on an explicit white, rounded plate
        makes the ground look chosen rather than accidental in both themes.
        """
        try:
            from gantt_app.resources.appicon import logo_image

            image = logo_image(LOGO_WIDTH)
            self._logo_image = ctk.CTkImage(
                light_image=image, dark_image=image, size=image.size,
            )
        except Exception:
            logger.exception("Could not load the About logo")
            self._logo_image = None

        if self._logo_image is None:
            return

        plate = ctk.CTkFrame(parent, fg_color=("#ffffff", "#ffffff"),
                             corner_radius=12)
        plate.pack(pady=(0, 4))
        ctk.CTkLabel(plate, image=self._logo_image, text="").pack(
            padx=10, pady=10)

    # -- update check (issue #41) -------------------------------------------

    def _start_update_check(self):
        """
        Ask GitHub for the latest release on a background thread.

        The window must open at once and stay responsive, so the network call
        runs off the main thread and its result is marshalled back with
        after(). A failure to even start the thread leaves the "Checking…"
        line as a neutral "couldn't check", never an error dialog.
        """
        import threading

        def worker():
            from gantt_app.update_check import check_for_update

            info = check_for_update(__version__)
            try:
                self.after(0, self._apply_update_result, info)
            except Exception:
                pass  # the window has gone; nothing to update

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            logger.exception("Could not start the update check")
            self._apply_update_result(None)

    def _apply_update_result(self, info):
        """Show the outcome of the update check, if the window is still up."""
        from gantt_app import update_check as uc

        try:
            if not self._update_label.winfo_exists():
                return
        except Exception:
            return

        if info is None or info.status == uc.STATUS_UNKNOWN:
            self._update_label.configure(
                text="Couldn't check for updates.",
                text_color=theme.pair(theme.MUTED_TEXT))
            return

        if info.status == uc.STATUS_UPDATE:
            from gantt_app import update_download as ud

            self._update_info = info
            self._download_url = info.download_url
            self._update_label.configure(
                text=f"A new version is available: {info.latest} "
                     f"(you have {info.current}).",
                text_color=theme.pair(theme.WARNING_TEXT))
            # Offer the verified download when the release carries an
            # installer for this platform and a SHA256SUMS to check it
            # against; always offer the page as a fallback.
            if ud.can_assist(info):
                self._install_button.pack(pady=(8, 0))
            self._download_button.pack(pady=(6, 0))
            return

        self._update_label.configure(
            text="You have the latest version.",
            text_color=theme.pair(theme.POSITIVE_TEXT))

    def _download_and_install(self):
        """
        Download the installer, verify it, and open it (issue #41, tier 2).

        Runs on a background thread so the window stays responsive, reporting
        progress on the status line. The verified installer is opened for the
        person to complete the install; a file that fails its checksum is
        deleted and never opened, and the page link stays available as a
        fallback.
        """
        if self._downloading or self._update_info is None:
            return
        import threading

        from gantt_app import update_download as ud

        self._downloading = True
        try:
            self._install_button.configure(state="disabled")
        except Exception:
            pass
        self._update_label.configure(
            text="Downloading the update…",
            text_color=theme.pair(theme.MUTED_TEXT))

        info = self._update_info

        def progress(received, total):
            if total > 0:
                pct = int(received * 100 / total)
                self._safe_after(self._set_update_text,
                                 f"Downloading the update… {pct}%",
                                 theme.pair(theme.MUTED_TEXT))

        def worker():
            try:
                path = ud.fetch_verified_installer(info, progress=progress)
            except ud.IntegrityError as error:
                self._safe_after(self._download_failed, str(error), True)
            except ud.UpdateError as error:
                self._safe_after(self._download_failed, str(error), False)
            except Exception as error:   # never let the thread die silently
                logger.exception("Assisted update failed")
                self._safe_after(self._download_failed, str(error), False)
            else:
                self._safe_after(self._download_succeeded, path)

        threading.Thread(target=worker, daemon=True).start()

    def _download_succeeded(self, path):
        """Verified: open the installer and say so."""
        from gantt_app import update_download as ud

        self._downloading = False
        self._set_update_text(
            "Downloaded and verified — opening the installer…",
            theme.pair(theme.POSITIVE_TEXT))
        try:
            ud.open_installer(path)
        except Exception:
            logger.exception("Could not open the verified installer")
            self._set_update_text(
                f"Downloaded and verified. Open it yourself: {path}",
                theme.pair(theme.TEXT))

    def _download_failed(self, message, integrity):
        """A download that could not be trusted or completed."""
        self._downloading = False
        try:
            self._install_button.configure(state="normal")
        except Exception:
            pass
        colour = theme.pair(
            theme.NEGATIVE_TEXT if integrity else theme.WARNING_TEXT)
        self._set_update_text(message, colour)

    def _set_update_text(self, text, colour):
        """Set the status line, if the window is still open."""
        try:
            if self._update_label.winfo_exists():
                self._update_label.configure(text=text, text_color=colour)
        except Exception:
            pass

    def _safe_after(self, func, *args):
        """Schedule a UI update from the worker thread, guarding teardown."""
        try:
            self.after(0, func, *args)
        except Exception:
            pass

    def _open_download(self):
        """Open the release page in the browser for the reader to download."""
        if not self._download_url:
            return
        import webbrowser

        logger.info("Opening the release page %s", self._download_url)
        try:
            webbrowser.open(self._download_url)
        except Exception:
            logger.exception("Could not open the release page")

    # -- geometry -----------------------------------------------------------

    def _centre_over(self, master):
        """Centre the card over its parent, or the screen when there is none."""
        try:
            width = self.winfo_width()
            height = self.winfo_height()
            if master is not None and master.winfo_exists():
                top = master.winfo_toplevel()
                x = top.winfo_rootx() + (top.winfo_width() - width) // 2
                y = top.winfo_rooty() + (top.winfo_height() - height) // 2
            else:
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    # -- lifecycle ----------------------------------------------------------

    def _close(self):
        """Release the grab and dispose of the window and the instance slot."""
        try:
            self.grab_release()
        except Exception:
            pass
        if type(self)._open_window is self:
            type(self)._open_window = None
        self.destroy()

    @classmethod
    def show(cls, master=None):
        """
        Open the About window, or raise the one already open.

        Returns the live instance so a caller can hold it if it wants to.
        """
        existing = cls._open_window
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    existing.focus_set()
                    return existing
            except Exception:
                pass
            cls._open_window = None

        cls._open_window = cls(master)
        return cls._open_window


def show_about(master=None):
    """Open the About PySimplePMT window."""
    logger.info("Showing About PySimplePMT (version %s)", __version__)
    return AboutWindow.show(master)
