import json
import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from openai import OpenAI

from dataset_service import DeidentifiedDataset

DATASET_CANDIDATE_PATHS = [
    r"c:\Users\jtr06\Downloads\Deidentified Data Set 2.xlsx",
    os.path.join(os.path.dirname(__file__), "Deidentified Data Set 2.xlsx"),
]
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "app_config.json")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def load_config() -> dict:
    defaults = {
        "window": {"title": "MedBot Assistant", "geometry": "1160x760", "minsize": [920, 620]},
        "models": ["gpt-4.1-mini"],
        "defaults": {"top_k_matches": 5},
        "colors": {
            "bg": "#0F1F2E",
            "panel": "#F7F9FC",
            "border": "#D5DCE6",
            "muted_text": "#566274",
            "primary_text": "#1E2735",
            "accent": "#0A84FF",
        },
    }
    if not os.path.exists(CONFIG_PATH):
        return defaults
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for key, value in defaults.items():
            if key not in cfg:
                cfg[key] = value
        return cfg
    except Exception:
        return defaults


def load_local_env(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


class MedBotApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        load_local_env(ENV_PATH)
        self.config = load_config()
        self.colors = self.config["colors"]
        self.is_busy = False
        self.logo_img = None
        self.matches: list[dict] = []

        self.root.title(self.config["window"]["title"])
        self.root.geometry(self.config["window"]["geometry"])
        self.root.minsize(*self.config["window"]["minsize"])
        self.root.configure(bg=self.colors["bg"])

        self.dataset = DeidentifiedDataset(DATASET_CANDIDATE_PATHS)
        self._build_ui()
        self._load_logo()
        self.load_dataset()

    def _build_ui(self) -> None:
        self._build_styles()

        root_pad = ttk.Frame(self.root, padding=14)
        root_pad.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(root_pad, style="Panel.TFrame", padding=(12, 10))
        top.pack(fill=tk.X, pady=(0, 10))

        title = ttk.Label(top, text="MedBot Assistant", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")

        subtitle = ttk.Label(top, text="Advanced triage support with dataset-assisted context", style="Muted.TLabel")
        subtitle.grid(row=1, column=0, sticky="w")

        self.logo_label = tk.Label(top, bg=self.colors["panel"], bd=0)
        self.logo_label.grid(row=0, column=4, rowspan=2, sticky="e", padx=(10, 0))

        self.fixed_model = self.config["models"][0] if self.config["models"] else "gpt-4.1-mini"
        self.fixed_top_k = max(1, min(10, int(self.config["defaults"].get("top_k_matches", 5))))

        top.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Initializing...")
        status = ttk.Label(root_pad, textvariable=self.status_var, style="Status.TLabel")
        status.pack(fill=tk.X, pady=(0, 8))

        composer = ttk.Frame(root_pad, style="Panel.TFrame", padding=(10, 10))
        composer.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        ttk.Label(composer, text="Message", style="Section.TLabel").pack(anchor="w", pady=(0, 4))

        composer_row = ttk.Frame(composer, style="Panel.TFrame")
        composer_row.pack(fill=tk.X)

        self.prompt_text = tk.Text(
            composer_row,
            height=7,
            wrap=tk.WORD,
            bg="#FFFFFF",
            fg=self.colors["primary_text"],
            font=("Segoe UI", 12),
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            insertbackground=self.colors["primary_text"],
            padx=10,
            pady=8,
        )
        self.prompt_text.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 10))
        self.prompt_text.configure(state=tk.NORMAL)
        self.prompt_text.lift()
        self.prompt_text.bind("<Control-Return>", self._submit_shortcut)
        self.prompt_text.bind("<Return>", self._submit_shortcut)
        self.prompt_text.bind("<Button-1>", lambda _e: self.prompt_text.focus_set())

        action_col = ttk.Frame(composer_row, style="Panel.TFrame")
        action_col.pack(side=tk.RIGHT, fill=tk.Y)
        self.send_button = ttk.Button(action_col, text="Send", style="Primary.TButton", command=self.on_submit)
        self.send_button.pack(fill=tk.X)
        ttk.Button(action_col, text="Clear Chat", command=self.clear_chat).pack(fill=tk.X, pady=(8, 0))

        ttk.Label(
            composer,
            text="Tip: Ctrl+Enter sends message.",
            style="Muted.TLabel",
        ).pack(anchor="e", pady=(6, 0))

        split = ttk.Panedwindow(root_pad, orient=tk.HORIZONTAL)
        split.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = ttk.Frame(split, style="Panel.TFrame", padding=10)
        right = ttk.Frame(split, style="Panel.TFrame", padding=10)
        split.add(left, weight=3)
        split.add(right, weight=2)

        self.notebook = ttk.Notebook(left)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        chat_tab = ttk.Frame(self.notebook, padding=8)
        context_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(chat_tab, text="Conversation")
        self.notebook.add(context_tab, text="Dataset Context")

        self.chat = ScrolledText(
            chat_tab,
            wrap=tk.WORD,
            bg="#FFFFFF",
            fg=self.colors["primary_text"],
            font=("Segoe UI", 11),
            relief="flat",
            padx=10,
            pady=8,
        )
        self.chat.pack(fill=tk.BOTH, expand=True)
        self.chat.configure(state=tk.DISABLED)
        self._configure_chat_tags()

        self.context_preview = ScrolledText(
            context_tab,
            wrap=tk.WORD,
            bg="#FFFFFF",
            fg=self.colors["primary_text"],
            font=("Consolas", 10),
            relief="flat",
            padx=10,
            pady=8,
        )
        self.context_preview.pack(fill=tk.BOTH, expand=True)
        self.context_preview.configure(state=tk.DISABLED)

        ttk.Label(right, text="Matched Cases", style="Section.TLabel").pack(anchor="w")

        self.case_tree = ttk.Treeview(
            right,
            columns=("score", "encounter", "complaint"),
            show="headings",
            height=8,
        )
        self.case_tree.heading("score", text="Score")
        self.case_tree.heading("encounter", text="Encounter")
        self.case_tree.heading("complaint", text="Chief Complaint")
        self.case_tree.column("score", width=70, anchor="center")
        self.case_tree.column("encounter", width=95, anchor="center")
        self.case_tree.column("complaint", width=240, anchor="w")
        self.case_tree.pack(fill=tk.X, pady=(6, 8))
        self.case_tree.bind("<<TreeviewSelect>>", self._on_case_select)

        ttk.Label(right, text="Selected Case Details", style="Section.TLabel").pack(anchor="w")
        self.case_detail = ScrolledText(
            right,
            wrap=tk.WORD,
            height=16,
            bg="#FFFFFF",
            fg=self.colors["primary_text"],
            font=("Segoe UI", 10),
            relief="flat",
            padx=8,
            pady=8,
        )
        self.case_detail.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.case_detail.configure(state=tk.DISABLED)

    def _build_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("Title.TLabel", background=self.colors["panel"], foreground=self.colors["primary_text"], font=("Segoe UI Semibold", 20))
        style.configure("Muted.TLabel", background=self.colors["panel"], foreground=self.colors["muted_text"], font=("Segoe UI", 10))
        style.configure("Status.TLabel", background=self.colors["bg"], foreground="#D5E0EE", font=("Segoe UI Semibold", 10))
        style.configure("Section.TLabel", background=self.colors["panel"], foreground=self.colors["primary_text"], font=("Segoe UI Semibold", 11))
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10), padding=(14, 9), foreground="#FFFFFF", background=self.colors["accent"])
        style.map("Primary.TButton", background=[("active", "#0668C7")])
        style.configure("TNotebook", background=self.colors["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(10, 6), font=("Segoe UI Semibold", 10))

    def _configure_chat_tags(self) -> None:
        self.chat.tag_configure("user_title", foreground="#12538E", font=("Segoe UI Semibold", 10))
        self.chat.tag_configure("user_body", foreground=self.colors["primary_text"], lmargin1=10, lmargin2=10, background="#DFF0FF")
        self.chat.tag_configure("bot_title", foreground="#3E4653", font=("Segoe UI Semibold", 10))
        self.chat.tag_configure("bot_body", foreground=self.colors["primary_text"], lmargin1=10, lmargin2=10, background="#EFF3F8")
        self.chat.tag_configure("error", foreground="#B42318", font=("Segoe UI", 10, "italic"))

    def _load_logo(self) -> None:
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "jobsitecare-logo.png")
        if not os.path.exists(logo_path):
            return
        img = tk.PhotoImage(file=logo_path)
        max_w = 180
        max_h = 48
        scale_w = max(1, (img.width() + max_w - 1) // max_w)
        scale_h = max(1, (img.height() + max_h - 1) // max_h)
        scale = max(scale_w, scale_h)
        if scale > 1:
            img = img.subsample(scale, scale)
        self.logo_img = img
        self.logo_label.configure(image=self.logo_img)

    def _submit_shortcut(self, _event: tk.Event) -> str:
        self.on_submit()
        return "break"

    def set_status(self, message: str) -> None:
        self.status_var.set(message)

    def append_message(self, speaker: str, body: str, is_error: bool = False) -> None:
        self.chat.configure(state=tk.NORMAL)
        if is_error:
            self.chat.insert(tk.END, f"{speaker}\n", "bot_title")
            self.chat.insert(tk.END, f"{body}\n\n", "error")
        elif speaker == "You":
            self.chat.insert(tk.END, f"{speaker}\n", "user_title")
            self.chat.insert(tk.END, f"{body}\n\n", "user_body")
        else:
            self.chat.insert(tk.END, f"{speaker}\n", "bot_title")
            self.chat.insert(tk.END, f"{body}\n\n", "bot_body")
        self.chat.configure(state=tk.DISABLED)
        self.chat.see(tk.END)

    def clear_chat(self) -> None:
        self.chat.configure(state=tk.NORMAL)
        self.chat.delete("1.0", tk.END)
        self.chat.configure(state=tk.DISABLED)
        self.set_status("Chat cleared.")

    def set_context_preview(self, text: str) -> None:
        self.context_preview.configure(state=tk.NORMAL)
        self.context_preview.delete("1.0", tk.END)
        self.context_preview.insert(tk.END, text)
        self.context_preview.configure(state=tk.DISABLED)

    def _refresh_case_table(self, matches: list[dict]) -> None:
        self.matches = matches
        for row_id in self.case_tree.get_children():
            self.case_tree.delete(row_id)
        for idx, row in enumerate(matches):
            self.case_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(row.get("score", 0), row.get("encounter_id", ""), row.get("chief_complaint", "")[:46]),
            )
        if matches:
            self.case_tree.selection_set("0")
            self._show_case_detail(0)
        else:
            self._set_case_detail("No matched cases.")

    def _set_case_detail(self, text: str) -> None:
        self.case_detail.configure(state=tk.NORMAL)
        self.case_detail.delete("1.0", tk.END)
        self.case_detail.insert(tk.END, text)
        self.case_detail.configure(state=tk.DISABLED)

    def _show_case_detail(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.matches):
            return
        row = self.matches[idx]
        detail = (
            f"Score: {row.get('score', 0)}\n"
            f"Encounter ID: {row.get('encounter_id', '')}\n"
            f"Chief Complaint: {row.get('chief_complaint', '')}\n"
            f"Final Diagnosis: {row.get('final_dx', '')}\n\n"
            f"{row.get('summary', '')}"
        )
        self._set_case_detail(detail)

    def _on_case_select(self, _event: tk.Event) -> None:
        sel = self.case_tree.selection()
        if not sel:
            return
        self._show_case_detail(int(sel[0]))

    def load_dataset(self) -> None:
        try:
            ok, message = self.dataset.load()
            if ok:
                self.set_status(message)
            else:
                self.set_status(message)
        except Exception as exc:
            self.set_status(f"Dataset load failed: {exc}")

    def on_submit(self) -> None:
        if self.is_busy:
            return
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            self.set_status("Please enter a message.")
            return

        matches = self.dataset.search(prompt, top_k=self.fixed_top_k)
        context = self.dataset.build_context(matches)

        self.append_message("You", prompt)
        self._refresh_case_table(matches)
        self.set_context_preview(context)
        self.prompt_text.delete("1.0", tk.END)

        self.is_busy = True
        self.send_button.state(["disabled"])
        self.set_status("Generating response...")
        threading.Thread(target=self.get_ai_response, args=(prompt, context), daemon=True).start()

    def get_ai_response(self, prompt: str, context: str) -> None:
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("No API key found. Add OPENAI_API_KEY to your local .env file.")

            client = OpenAI(api_key=api_key)
            result = client.responses.create(
                model=self.fixed_model,
                instructions=(
                    "You are a medical information assistant. Provide general information only and suggest "
                    "seeing a licensed clinician for diagnosis or treatment decisions. "
                    "Use the provided de-identified reference cases as decision-support context."
                ),
                input=(
                    "Reference cases from local de-identified dataset:\n"
                    f"{context}\n\n"
                    "User question:\n"
                    f"{prompt}"
                ),
            )
            response = result.output_text or "No response text returned."
            self.root.after(0, lambda: self._finish_response(response, is_error=False))
        except Exception as exc:
            self.root.after(0, lambda: self._finish_response(f"An error occurred: {exc}", is_error=True))

    def _finish_response(self, response: str, is_error: bool) -> None:
        if is_error:
            self.append_message("System", response, is_error=True)
            self.set_status("Request failed.")
        else:
            self.append_message("MedBot Assistant", response)
            self.set_status("Ready.")
        self.is_busy = False
        self.send_button.state(["!disabled"])


if __name__ == "__main__":
    root = tk.Tk()
    app = MedBotApp(root)
    root.after(200, app.prompt_text.focus_set)
    root.mainloop()
