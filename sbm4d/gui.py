"""Modern, single-image Tkinter interface for SBM4D."""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk, UnidentifiedImageError

from .cutter import (
    ExistingOutputError,
    SUPPORTED_IMAGE_SIZES,
    UnsupportedImageSizeError,
    UnsupportedMultiFrameImageError,
    cut_image,
)


IMAGE_FILE_TYPES = (
    ("이미지 파일", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif"),
    ("PNG 파일", "*.png"),
    ("모든 파일", "*.*"),
)

APP_BACKGROUND = "#F3F6FA"
CARD_BACKGROUND = "#FFFFFF"
PREVIEW_BACKGROUND = "#111827"
TEXT_PRIMARY = "#172033"
TEXT_SECONDARY = "#667085"
ACCENT = "#2563EB"
ACCENT_HOVER = "#1D4ED8"
GUIDE_COLOR = "#FFFFFF"
GUIDE_SHADOW = "#111827"
SUCCESS = "#047857"
WARNING = "#B54708"
PREVIEW_IMAGE_MAX_SIZE = (1600, 900)
WINDOW_INITIAL_SIZE = (820, 440)
WINDOW_MIN_SIZE = (820, 440)
WINDOW_MAX_SIZE = (980, 720)
WINDOW_SCREEN_MARGIN = (80, 100)
# The preview canvas keeps 20 px around the image. The remaining vertical
# space is used by the compact controls and outer spacing.
WINDOW_IMAGE_OVERHEAD = (64, 200)
APP_ICON_FILENAME = "icon.ico"


@dataclass(frozen=True)
class CropGuideRegion:
    """One numbered crop region expressed in preview-canvas coordinates."""

    index: int
    box: tuple[float, float, float, float]


def bundled_resource_path(filename: str) -> Path:
    """Return a resource path in both source and PyInstaller one-file runs."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(bundle_root) / filename
    return Path(__file__).resolve().parent.parent / filename


def middle_ellipsis(value: str, max_characters: int) -> str:
    """Shorten a long UI label while keeping both recognizable ends."""

    if max_characters < 5:
        raise ValueError("Ellipsis length must be at least five characters.")
    if len(value) <= max_characters:
        return value
    remaining = max_characters - 1
    leading = (remaining + 1) // 2
    trailing = remaining - leading
    return f"{value[:leading]}…{value[-trailing:]}"


def preview_fit_size(
    source_size: tuple[int, int],
    bounds: tuple[int, int],
) -> tuple[int, int]:
    """Fit an image inside *bounds* without changing its ratio or enlarging it."""

    source_width, source_height = source_size
    bound_width, bound_height = bounds
    if min(source_width, source_height, bound_width, bound_height) <= 0:
        raise ValueError("Image and preview dimensions must be positive.")

    scale = min(
        bound_width / source_width,
        bound_height / source_height,
        1.0,
    )
    width = min(bound_width, max(1, round(source_width * scale)))
    height = min(bound_height, max(1, round(source_height * scale)))
    return width, height


def adaptive_window_size(
    source_size: tuple[int, int],
    screen_size: tuple[int, int],
) -> tuple[int, int]:
    """Choose a compact window size whose preview follows the image ratio."""

    source_width, source_height = source_size
    screen_width, screen_height = screen_size
    if min(source_width, source_height, screen_width, screen_height) <= 0:
        raise ValueError("Image and screen dimensions must be positive.")

    min_width, min_height = WINDOW_MIN_SIZE
    max_width = max(
        min_width,
        min(WINDOW_MAX_SIZE[0], screen_width - WINDOW_SCREEN_MARGIN[0]),
    )
    max_height = max(
        min_height,
        min(WINDOW_MAX_SIZE[1], screen_height - WINDOW_SCREEN_MARGIN[1]),
    )
    horizontal_overhead, vertical_overhead = WINDOW_IMAGE_OVERHEAD
    available_preview = (
        max(1, max_width - horizontal_overhead),
        max(1, max_height - vertical_overhead),
    )
    preview_width, preview_height = preview_fit_size(source_size, available_preview)
    return (
        max(min_width, min(max_width, preview_width + horizontal_overhead)),
        max(min_height, min(max_height, preview_height + vertical_overhead)),
    )


def crop_guide_geometry(
    source_size: tuple[int, int],
    preview_bbox: tuple[float, float, float, float],
) -> tuple[CropGuideRegion, ...]:
    """Return numbered crop regions for a supported source and preview box.

    ``preview_bbox`` is ``(left, top, right, bottom)`` in canvas coordinates.
    Unsupported source sizes intentionally return no regions.
    """

    source_width, source_height = source_size
    left, top, right, bottom = preview_bbox
    if source_width <= 0 or source_height <= 0:
        raise ValueError("Source dimensions must be positive.")
    if right <= left or bottom <= top:
        raise ValueError("Preview bounds must have a positive area.")

    if source_size == (720, 450):
        columns, rows = 1, 3
    elif source_size == (1440, 450):
        columns, rows = 2, 3
    else:
        return ()

    preview_width = right - left
    preview_height = bottom - top
    regions: list[CropGuideRegion] = []
    index = 1
    for row in range(rows):
        region_top = top + preview_height * row / rows
        region_bottom = top + preview_height * (row + 1) / rows
        for column in range(columns):
            region_left = left + preview_width * column / columns
            region_right = left + preview_width * (column + 1) / columns
            regions.append(
                CropGuideRegion(
                    index=index,
                    box=(region_left, region_top, region_right, region_bottom),
                )
            )
            index += 1
    return tuple(regions)


class SBM4DApp:
    """Beginner-friendly desktop interface for one banner image at a time."""

    def __init__(self, root: tk.Tk, output_dir: Path | None = None) -> None:
        self.root = root
        self.root.title("SBM4D · SOOP 하단 배너 자동 자르기")
        self._set_window_icon()
        self.root.geometry(f"{WINDOW_INITIAL_SIZE[0]}x{WINDOW_INITIAL_SIZE[1]}")
        self.root.minsize(*WINDOW_MIN_SIZE)
        self.root.configure(background=APP_BACKGROUND)

        self._configured_output_dir = (
            Path(output_dir).expanduser() if output_dir is not None else None
        )
        self._custom_output_selected = output_dir is not None
        initial_output = self._configured_output_dir or (Path.cwd() / "output")
        self.output_var = tk.StringVar(value=str(initial_output))
        self.file_name_var = tk.StringVar(value="선택된 이미지가 없습니다")
        self.file_location_var = tk.StringVar(
            value="이미지를 선택하시면 이곳에서 바로 확인할 수 있습니다."
        )
        self.dimension_var = tk.StringVar(value="원본 크기  —")
        self.compatibility_var = tk.StringVar(value="이미지를 먼저 선택해 주세요")
        self._source_path: Path | None = None
        self._source_size: tuple[int, int] | None = None
        self._preview_image: Image.Image | None = None
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._preview_error_text: str | None = None
        self._supported = False
        self._working = False
        self._last_output_dir: Path | None = None
        self._render_after_id: str | None = None

        self._configure_styles()
        self._build_widgets()
        self.root.after_idle(self._render_preview)

    def _set_window_icon(self) -> None:
        icon_path = bundled_resource_path(APP_ICON_FILENAME)
        if not icon_path.is_file():
            return
        try:
            self.root.iconbitmap(str(icon_path))
        except tk.TclError:
            # The image cutter must remain usable even if a platform cannot
            # load the Windows ICO resource.
            pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=APP_BACKGROUND)
        style.configure("Card.TFrame", background=CARD_BACKGROUND)
        style.configure(
            "Body.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=("맑은 고딕", 10),
        )
        style.configure(
            "Muted.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_SECONDARY,
            font=("맑은 고딕", 9),
        )
        style.configure(
            "FileName.TLabel",
            background=CARD_BACKGROUND,
            foreground=TEXT_PRIMARY,
            font=("맑은 고딕", 11, "bold"),
        )
        style.configure(
            "NeutralBadge.TLabel",
            background="#EEF2F6",
            foreground="#475467",
            font=("맑은 고딕", 9, "bold"),
            padding=(10, 6),
        )
        style.configure(
            "SupportedBadge.TLabel",
            background="#ECFDF3",
            foreground=SUCCESS,
            font=("맑은 고딕", 9, "bold"),
            padding=(10, 6),
        )
        style.configure(
            "UnsupportedBadge.TLabel",
            background="#FFF4E5",
            foreground=WARNING,
            font=("맑은 고딕", 9, "bold"),
            padding=(10, 6),
        )
        style.configure(
            "Primary.TButton",
            background=ACCENT,
            foreground="#FFFFFF",
            borderwidth=0,
            focusthickness=2,
            focuscolor="#BFDBFE",
            font=("맑은 고딕", 11, "bold"),
            padding=(15, 10),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("disabled", "#AAB7CF"),
                ("focus", ACCENT_HOVER),
                ("pressed", "#1E40AF"),
                ("active", ACCENT_HOVER),
            ],
            foreground=[("disabled", "#F8FAFC")],
        )
        style.configure(
            "Secondary.TButton",
            background="#E9EFF8",
            foreground="#23416D",
            borderwidth=0,
            focusthickness=2,
            focuscolor="#93C5FD",
            font=("맑은 고딕", 10, "bold"),
            padding=(12, 8),
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("disabled", "#EEF1F5"),
                ("focus", "#D7E5FA"),
                ("pressed", "#D7E2F2"),
                ("active", "#DDE7F5"),
            ],
            foreground=[("disabled", "#98A2B3")],
        )
        style.configure(
            "Modern.TEntry",
            fieldbackground="#F8FAFC",
            foreground=TEXT_PRIMARY,
            bordercolor="#D0D5DD",
            lightcolor="#D0D5DD",
            darkcolor="#D0D5DD",
            padding=9,
        )
        style.map(
            "Modern.TEntry",
            fieldbackground=[("readonly", "#F8FAFC")],
            foreground=[("readonly", TEXT_PRIMARY)],
        )
        style.configure(
            "Card.TSeparator",
            background="#E8ECF2",
        )

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame", padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(
            outer,
            background=PREVIEW_BACKGROUND,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", self._schedule_preview_render)

        control_card = ttk.Frame(
            outer,
            style="Card.TFrame",
            padding=(14, 12),
        )
        control_card.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        control_card.columnconfigure(1, weight=1)

        self.choose_button = ttk.Button(
            control_card,
            text="이미지 선택",
            command=self._select_image,
            style="Primary.TButton",
        )
        self.choose_button.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        file_info = ttk.Frame(control_card, style="Card.TFrame")
        file_info.grid(row=0, column=1, sticky="nsew")
        file_info.columnconfigure(0, weight=1)

        self.file_name_label = ttk.Label(
            file_info,
            textvariable=self.file_name_var,
            style="FileName.TLabel",
            anchor="w",
            justify="left",
            width=1,
        )
        self.file_name_label.grid(row=0, column=0, sticky="ew")
        self.file_location_label = ttk.Label(
            file_info,
            textvariable=self.file_location_var,
            style="Muted.TLabel",
            anchor="w",
            justify="left",
            width=1,
        )
        self.file_location_label.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        image_state = ttk.Frame(control_card, style="Card.TFrame")
        image_state.grid(row=0, column=2, sticky="w", padx=(12, 12))
        ttk.Label(
            image_state,
            textvariable=self.dimension_var,
            style="Body.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.compatibility_label = ttk.Label(
            image_state,
            textvariable=self.compatibility_var,
            style="NeutralBadge.TLabel",
        )
        self.compatibility_label.grid(row=1, column=0, sticky="w", pady=(3, 0))

        self.process_button = ttk.Button(
            control_card,
            text="PNG로 자르기",
            command=self._process_image,
            style="Primary.TButton",
            state=tk.DISABLED,
        )
        self.process_button.grid(row=0, column=3, sticky="nsew")

        output_row = ttk.Frame(control_card, style="Card.TFrame")
        output_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        output_row.columnconfigure(1, weight=1)
        ttk.Label(
            output_row,
            text="저장 위치",
            style="Muted.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.output_entry = ttk.Entry(
            output_row,
            textvariable=self.output_var,
            style="Modern.TEntry",
            state="readonly",
        )
        self.output_entry.grid(row=0, column=1, sticky="ew")
        self.output_button = ttk.Button(
            output_row,
            text="변경",
            command=self._select_output_dir,
            style="Secondary.TButton",
        )
        self.output_button.grid(row=0, column=2, padx=(8, 0))

        self.open_output_button = ttk.Button(
            control_card,
            text="결과 폴더 열기",
            command=self._open_output_dir,
            style="Secondary.TButton",
            state=tk.DISABLED,
        )
        self.open_output_button.grid(row=1, column=3, sticky="nsew", pady=(10, 0))

    def _select_image(self) -> None:
        initial_dir = (
            self._source_path.parent
            if self._source_path is not None
            else Path.cwd()
        )
        chosen = filedialog.askopenfilename(
            parent=self.root,
            title="자를 이미지 한 장을 선택해 주세요",
            initialdir=str(initial_dir),
            filetypes=IMAGE_FILE_TYPES,
        )
        if not chosen:
            return

        source = Path(chosen)
        self._source_path = source
        self._last_output_dir = None
        self.open_output_button.configure(state=tk.DISABLED)
        self.file_name_var.set(middle_ellipsis(source.name, 32))
        self.file_location_var.set(middle_ellipsis(str(source.parent), 40))
        self.choose_button.configure(
            text="다른 이미지 선택",
            style="Secondary.TButton",
        )
        if not self._custom_output_selected:
            self.output_var.set(str(source.parent / "output"))

        self._load_preview(source)

    def _load_preview(self, source: Path) -> None:
        self._replace_preview_image(None)
        self._preview_error_text = None
        self._source_size = None
        self._supported = False
        self.process_button.configure(state=tk.DISABLED)
        self.dimension_var.set("원본 크기  확인할 수 없음")
        self.compatibility_var.set("이미지를 읽는 중입니다")
        self.compatibility_label.configure(style="NeutralBadge.TLabel")
        self.root.update_idletasks()

        try:
            with Image.open(source) as opened:
                frame_count = int(getattr(opened, "n_frames", 1))
                source_size = opened.size
                opened.seek(0)
                has_alpha = "A" in opened.getbands() or "transparency" in opened.info
                opened.thumbnail(PREVIEW_IMAGE_MAX_SIZE, Image.Resampling.LANCZOS)
                preview = opened.convert("RGBA" if has_alpha else "RGB")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            self.compatibility_var.set("이미지를 읽을 수 없습니다")
            self.compatibility_label.configure(style="UnsupportedBadge.TLabel")
            self._preview_error_text = (
                "미리보기를 만들 수 없습니다\n다른 이미지 파일을 선택해 주세요"
            )
            self._render_preview()
            messagebox.showwarning(
                "이미지를 열 수 없습니다",
                (
                    "선택하신 이미지를 읽을 수 없습니다.\n\n"
                    "파일이 손상되지 않았는지 확인한 뒤 다른 이미지를 선택해 주세요.\n\n"
                    f"오류: {exc}"
                ),
                parent=self.root,
            )
            return
        except Exception as exc:
            self.compatibility_var.set("이미지를 읽을 수 없습니다")
            self.compatibility_label.configure(style="UnsupportedBadge.TLabel")
            self._preview_error_text = "미리보기를 만들 수 없습니다"
            self._render_preview()
            messagebox.showwarning(
                "이미지를 열 수 없습니다",
                f"선택하신 이미지를 확인하지 못했습니다.\n\n오류: {exc}",
                parent=self.root,
            )
            return

        self._source_size = source_size
        self._replace_preview_image(preview)
        self._resize_for_image(source_size)
        self.dimension_var.set(f"원본 크기  {source_size[0]} × {source_size[1]} px")

        if frame_count != 1:
            self.compatibility_var.set(f"사용할 수 없음 · {frame_count}프레임 이미지")
            self.compatibility_label.configure(style="UnsupportedBadge.TLabel")
        elif source_size in SUPPORTED_IMAGE_SIZES:
            output_count = 3 if source_size == (720, 450) else 6
            self._supported = True
            self.compatibility_var.set(f"분할 가능 · PNG {output_count}개 생성")
            self.compatibility_label.configure(style="SupportedBadge.TLabel")
            self.process_button.configure(state=tk.NORMAL)
        else:
            self.compatibility_var.set("지원하지 않는 이미지 크기")
            self.compatibility_label.configure(style="UnsupportedBadge.TLabel")

        self._render_preview()

    def _resize_for_image(self, source_size: tuple[int, int]) -> None:
        """Resize around the current window center to suit the selected image."""

        target_width, target_height = adaptive_window_size(
            source_size,
            (self.root.winfo_screenwidth(), self.root.winfo_screenheight()),
        )
        self.root.update_idletasks()
        current_width = self.root.winfo_width()
        current_height = self.root.winfo_height()
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        target_x = current_x + (current_width - target_width) // 2
        target_y = current_y + (current_height - target_height) // 2

        # Keep the resized window visible on the primary work area. Negative
        # coordinates are preserved for windows already placed on another screen.
        if current_x >= 0:
            target_x = max(
                0,
                min(target_x, self.root.winfo_screenwidth() - target_width),
            )
        if current_y >= 0:
            target_y = max(
                0,
                min(target_y, self.root.winfo_screenheight() - target_height),
            )
        self.root.geometry(
            f"{target_width}x{target_height}+{target_x}+{target_y}"
        )
        self.root.update_idletasks()

    def _replace_preview_image(self, image: Image.Image | None) -> None:
        previous = self._preview_image
        self._preview_image = image
        if previous is not None:
            previous.close()

    def _schedule_preview_render(self, _event: tk.Event[tk.Misc]) -> None:
        if self._render_after_id is not None:
            self.root.after_cancel(self._render_after_id)
        self._render_after_id = self.root.after(50, self._render_preview)

    def _render_preview(self, error_text: str | None = None) -> None:
        self._render_after_id = None
        canvas = self.preview_canvas
        canvas.delete("all")
        canvas_width = max(1, canvas.winfo_width())
        canvas_height = max(1, canvas.winfo_height())

        if self._preview_image is None:
            placeholder = error_text or self._preview_error_text or (
                "이미지를 선택해 주세요\n\n"
                "720×450  ·  1440×450"
            )
            canvas.create_text(
                canvas_width / 2,
                canvas_height / 2,
                text=placeholder,
                fill="#9CA9BC",
                font=("맑은 고딕", 12),
                justify="center",
            )
            self._preview_photo = None
            return

        available_width = max(1, canvas_width - 40)
        available_height = max(1, canvas_height - 40)
        display_size = preview_fit_size(
            self._preview_image.size,
            (available_width, available_height),
        )
        if display_size == self._preview_image.size:
            rendered = self._preview_image.copy()
        else:
            rendered = self._preview_image.resize(
                display_size,
                Image.Resampling.LANCZOS,
            )
        try:
            self._preview_photo = ImageTk.PhotoImage(rendered, master=self.root)
        finally:
            rendered.close()

        left = (canvas_width - display_size[0]) / 2
        top = (canvas_height - display_size[1]) / 2
        right = left + display_size[0]
        bottom = top + display_size[1]
        canvas.create_image(left, top, image=self._preview_photo, anchor="nw")
        canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            outline="#D7E0EC",
            width=1,
        )

        if not self._supported or self._source_size is None:
            return

        regions = crop_guide_geometry(
            self._source_size,
            (left, top, right, bottom),
        )
        # A dark under-stroke keeps the camera-like white crop grid visible on
        # both very bright and very dark artwork.
        canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            outline=GUIDE_SHADOW,
            width=4,
        )
        canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            outline=GUIDE_COLOR,
            width=2,
        )
        grid_lines: list[tuple[float, float, float, float]] = [
            (left, top + (bottom - top) / 3, right, top + (bottom - top) / 3),
            (left, top + (bottom - top) * 2 / 3, right, top + (bottom - top) * 2 / 3),
        ]
        if self._source_size == (1440, 450):
            center_x = left + (right - left) / 2
            grid_lines.append((center_x, top, center_x, bottom))
        for line in grid_lines:
            canvas.create_line(*line, fill=GUIDE_SHADOW, width=4)
            canvas.create_line(*line, fill=GUIDE_COLOR, width=2)

        for region in regions:
            x0, y0, x1, y1 = region.box
            center_x = (x0 + x1) / 2
            center_y = (y0 + y1) / 2
            radius = 15
            canvas.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                fill=ACCENT,
                outline="#FFFFFF",
                width=2,
            )
            canvas.create_text(
                center_x,
                center_y,
                text=str(region.index),
                fill="#FFFFFF",
                font=("Segoe UI", 10, "bold"),
            )

    def _select_output_dir(self) -> None:
        output_text = self.output_var.get().strip()
        current = Path(output_text).expanduser() if output_text else Path.cwd()
        if current.is_dir():
            initial = current
        elif current.parent.is_dir():
            initial = current.parent
        else:
            initial = Path.cwd()

        chosen = filedialog.askdirectory(
            parent=self.root,
            title="결과를 저장할 폴더를 선택해 주세요",
            initialdir=str(initial),
        )
        if chosen:
            self.output_var.set(chosen)
            self._custom_output_selected = True

    def _process_image(self) -> None:
        if self._working:
            return
        source = self._source_path
        if source is None or not self._supported:
            messagebox.showwarning(
                "이미지를 확인해 주세요",
                "먼저 720×450 또는 1440×450 이미지 한 장을 선택해 주세요.",
                parent=self.root,
            )
            return

        output_text = self.output_var.get().strip()
        if not output_text:
            messagebox.showwarning(
                "저장 폴더를 선택해 주세요",
                "결과 PNG 파일을 저장할 폴더를 선택해 주세요.",
                parent=self.root,
            )
            return
        output_dir = Path(output_text).expanduser()

        self._set_working(True)
        try:
            try:
                generated = cut_image(source, output_dir, overwrite=False)
            except ExistingOutputError as error:
                if not self._confirm_overwrite(source, error):
                    return
                generated = cut_image(source, output_dir, overwrite=True)
        except UnsupportedImageSizeError as error:
            self._supported = False
            self.process_button.configure(state=tk.DISABLED)
            message = self._unsupported_size_message(source, error)
            messagebox.showwarning("이미지 크기가 맞지 않습니다", message, parent=self.root)
            self._load_preview(source)
        except UnsupportedMultiFrameImageError:
            self._supported = False
            self.process_button.configure(state=tk.DISABLED)
            message = (
                f"{source.name}: 움직이는 이미지나 여러 페이지 이미지는 지원하지 않습니다. "
                "한 장짜리 이미지로 저장해 주세요."
            )
            messagebox.showwarning("이미지를 자를 수 없습니다", message, parent=self.root)
            self._load_preview(source)
        except Exception as exc:
            messagebox.showerror(
                "이미지를 자르지 못했습니다",
                (
                    "처리 중 문제가 발생했습니다. 원본 파일과 저장 폴더를 확인해 주세요.\n\n"
                    f"오류: {exc}"
                ),
                parent=self.root,
            )
        else:
            self._last_output_dir = output_dir
            self.open_output_button.configure(state=tk.NORMAL)
            messagebox.showinfo(
                "이미지 자르기 완료",
                (
                    f"‘{source.name}’ 이미지를 잘랐습니다.\n\n"
                    f"생성된 PNG 파일: {len(generated)}개\n"
                    f"저장 위치: {output_dir}"
                ),
                parent=self.root,
            )
        finally:
            self._set_working(False)

    def _confirm_overwrite(
        self,
        source: Path,
        error: ExistingOutputError,
    ) -> bool:
        return messagebox.askyesno(
            "기존 결과 파일이 있습니다",
            (
                f"‘{source.name}’의 결과 파일 {len(error.paths)}개가 이미 있습니다.\n\n"
                "계속하면 기존 결과 파일을 새 파일로 바꿉니다. 덮어쓰시겠습니까?"
            ),
            parent=self.root,
            default=messagebox.NO,
            icon=messagebox.WARNING,
        )

    def _set_working(self, working: bool) -> None:
        self._working = working
        if working:
            self.choose_button.configure(state=tk.DISABLED)
            self.output_entry.configure(state=tk.DISABLED)
            self.output_button.configure(state=tk.DISABLED)
            self.process_button.configure(state=tk.DISABLED, text="자르는 중...")
            self.root.update_idletasks()
            return

        self.choose_button.configure(state=tk.NORMAL)
        self.output_entry.configure(state="readonly")
        self.output_button.configure(state=tk.NORMAL)
        self.process_button.configure(
            state=tk.NORMAL if self._supported else tk.DISABLED,
            text="PNG로 자르기",
        )

    @staticmethod
    def _unsupported_size_message(
        source: Path,
        error: UnsupportedImageSizeError,
    ) -> str:
        width, height = error.actual_size
        return (
            f"{source.name}: 이미지 크기가 {width}×{height}입니다. "
            "720×450 또는 1440×450 이미지를 선택해 주세요."
        )

    def _open_output_dir(self) -> None:
        output_dir = self._last_output_dir
        if output_dir is None or not output_dir.is_dir():
            messagebox.showwarning(
                "결과 폴더를 찾을 수 없습니다",
                "먼저 이미지를 자르거나 저장 폴더가 존재하는지 확인해 주세요.",
                parent=self.root,
            )
            return

        try:
            if sys.platform == "win32":
                os.startfile(str(output_dir))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output_dir)])
            else:
                subprocess.Popen(["xdg-open", str(output_dir)])
        except OSError as exc:
            messagebox.showerror(
                "결과 폴더를 열지 못했습니다",
                f"폴더를 직접 열어 주세요.\n\n{output_dir}\n\n오류: {exc}",
                parent=self.root,
            )


def launch_gui(output_dir: Path | None = None) -> None:
    """Create and run the SBM4D desktop application."""

    root = tk.Tk()
    SBM4DApp(root, output_dir=output_dir)
    root.mainloop()
