"""Confirm-Dialog fuer Tool-Calls.

Port aus C3PO-legacy/ui/confirm.py - tkinter (stdlib), dunkler Cyan-Theme.
"""
from __future__ import annotations

import json
from typing import Any, Dict


def confirm_dialog(tool_name: str, params: Dict[str, Any], *, timeout_ms: int = 30_000) -> bool:
    """Blockierender Dialog. Returns True wenn User auf 'Ausfuehren' klickt.

    Auto-Decline nach `timeout_ms` Millisekunden.
    """
    result = {"value": False}

    def show() -> None:
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.title(f"C3PO * Bestaetigung: {tool_name}")
        root.attributes("-topmost", True)
        root.geometry("560x380+200+200")
        root.configure(bg="#0a1929")

        header = tk.Label(
            root, text="Tool-Aufruf bestaetigen",
            bg="#0a1929", fg="#00e5ff",
            font=("Segoe UI", 14, "bold"),
            pady=15,
        )
        header.pack(fill="x")

        tk.Label(
            root, text=f"Tool: {tool_name}",
            bg="#0a1929", fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
            anchor="w", padx=20,
        ).pack(fill="x")

        params_text = (
            json.dumps(params, indent=2, ensure_ascii=False)
            if params else "(keine Parameter)"
        )
        params_box = tk.Text(
            root, height=12, wrap="word",
            bg="#0e2540", fg="#e0f0ff",
            font=("Consolas", 10),
            relief="flat", padx=12, pady=8,
        )
        params_box.insert("1.0", params_text)
        params_box.configure(state="disabled")
        params_box.pack(fill="both", expand=True, padx=20, pady=12)

        btn_frame = tk.Frame(root, bg="#0a1929")
        btn_frame.pack(pady=12)

        def on_yes() -> None:
            result["value"] = True
            root.destroy()

        def on_no() -> None:
            result["value"] = False
            root.destroy()

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Yes.TButton", foreground="#0a1929", background="#00e5ff",
            font=("Segoe UI", 11, "bold"), padding=(20, 8),
        )
        style.configure(
            "No.TButton", foreground="#ffffff", background="#444",
            font=("Segoe UI", 11), padding=(20, 8),
        )
        ttk.Button(btn_frame, text="Ausfuehren", style="Yes.TButton",
                   command=on_yes).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="Abbrechen", style="No.TButton",
                   command=on_no).pack(side="left", padx=8)

        root.bind("<Return>", lambda _e: on_yes())
        root.bind("<Escape>", lambda _e: on_no())
        root.after(timeout_ms, on_no)
        root.mainloop()

    show()
    return result["value"]


__all__ = ["confirm_dialog"]
