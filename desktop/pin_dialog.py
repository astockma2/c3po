"""PIN-Dialog fuer Admin-Aktionen.

Port aus C3PO-legacy/ui/pin_dialog.py mit angepasstem keyring-Helper.
Beim ersten Mal: Setup-Modus mit doppelter PIN-Eingabe.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from desktop.keyring_helper import is_admin_pin_set, set_admin_pin


def pin_dialog(
    tool_name: str,
    params: Dict[str, Any],
    *,
    timeout_ms: int = 60_000,
) -> Optional[str]:
    """Blockierender Dialog. Returns eingegebene PIN oder None bei Abbruch.

    Im Setup-Modus (kein PIN gesetzt) speichert der OK-Klick die neue PIN
    im Windows-Credential-Manager und gibt sie zur Verifikation zurueck.
    """
    result: Dict[str, Optional[str]] = {"value": None}
    setup_mode = not is_admin_pin_set()

    def show() -> None:
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.title(f"C3PO * PIN-Bestaetigung: {tool_name}")
        root.attributes("-topmost", True)
        root.geometry("480x320+220+220")
        root.configure(bg="#0a1929")

        header_text = "PIN festlegen (erstmalig)" if setup_mode else "Admin-PIN eingeben"
        tk.Label(
            root, text=header_text,
            bg="#0a1929", fg="#ff5577",
            font=("Segoe UI", 14, "bold"),
            pady=15,
        ).pack(fill="x")

        tk.Label(
            root, text=f"Tool: {tool_name}",
            bg="#0a1929", fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(0, 10))

        if setup_mode:
            tk.Label(
                root,
                text="Lege deinen 4-stelligen Admin-PIN fest.\n"
                     "Wird sicher im Windows-Credential-Manager gespeichert.",
                bg="#0a1929", fg="#cccccc",
                font=("Segoe UI", 10), justify="center",
            ).pack(pady=8)

        pin_var = tk.StringVar()
        pin_entry = tk.Entry(
            root, textvariable=pin_var, show="*",
            font=("Consolas", 22), justify="center", width=8,
            bg="#0e2540", fg="#00e5ff", insertbackground="#00e5ff",
            relief="flat",
        )
        pin_entry.pack(pady=15)
        pin_entry.focus()

        pin_var2 = tk.StringVar()
        if setup_mode:
            tk.Label(
                root, text="Wiederholen:",
                bg="#0a1929", fg="#cccccc",
                font=("Segoe UI", 9),
            ).pack()
            tk.Entry(
                root, textvariable=pin_var2, show="*",
                font=("Consolas", 18), justify="center", width=8,
                bg="#0e2540", fg="#00e5ff", insertbackground="#00e5ff",
                relief="flat",
            ).pack(pady=6)

        error_label = tk.Label(
            root, text="", bg="#0a1929", fg="#ff5577",
            font=("Segoe UI", 9),
        )
        error_label.pack()

        def on_ok() -> None:
            pin = pin_var.get().strip()
            if not pin.isdigit() or len(pin) != 4:
                error_label.configure(text="PIN muss 4 Ziffern sein.")
                return
            if setup_mode:
                if pin != pin_var2.get().strip():
                    error_label.configure(text="PINs stimmen nicht ueberein.")
                    return
                set_admin_pin(pin)
            result["value"] = pin
            root.destroy()

        def on_cancel() -> None:
            result["value"] = None
            root.destroy()

        btn_frame = tk.Frame(root, bg="#0a1929")
        btn_frame.pack(pady=12)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "PinOk.TButton", foreground="#0a1929", background="#00e5ff",
            font=("Segoe UI", 11, "bold"), padding=(20, 8),
        )
        style.configure(
            "PinCancel.TButton", foreground="#ffffff", background="#444",
            font=("Segoe UI", 11), padding=(20, 8),
        )
        ttk.Button(btn_frame, text="OK", style="PinOk.TButton",
                   command=on_ok).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="Abbrechen", style="PinCancel.TButton",
                   command=on_cancel).pack(side="left", padx=8)

        root.bind("<Return>", lambda _e: on_ok())
        root.bind("<Escape>", lambda _e: on_cancel())
        root.after(timeout_ms, on_cancel)
        root.mainloop()

    show()
    return result["value"]


__all__ = ["pin_dialog"]
