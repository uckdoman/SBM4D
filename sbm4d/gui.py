"""Tkinter desktop interface for SBM4D."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .batch import BatchOutputConflict, find_batch_output_conflicts
from .cutter import (
    ExistingOutputError,
    UnsupportedImageSizeError,
    UnsupportedMultiFrameImageError,
    cut_image,
)


IMAGE_FILE_TYPES = (
    ("이미지 파일", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
    ("PNG 파일", "*.png"),
    ("모든 파일", "*.*"),
)


@dataclass(frozen=True)
class BatchResult:
    """Final result sent from the worker to the Tk event-loop thread."""

    processed: int
    generated: tuple[Path, ...]
    skipped: tuple[str, ...]
    errors: tuple[str, ...]
    output_dir: Path


@dataclass(frozen=True)
class OverwriteRequest:
    """An overwrite question that must be answered on the Tk thread."""

    source: Path
    response: queue.Queue[bool]


WorkerMessage = BatchResult | OverwriteRequest


class SBM4DApp:
    """Beginner-friendly desktop interface for cutting banner images."""

    def __init__(self, root: tk.Tk, output_dir: Path | None = None) -> None:
        self.root = root
        self.root.title("SBM4D - 깡담비 SOOP 하단 배너 자동 자르기")
        self.root.geometry("780x620")
        self.root.minsize(660, 520)

        default_output = output_dir or (Path.cwd() / "output")
        self._auto_output_from_first_image = output_dir is None
        self.output_var = tk.StringVar(value=str(default_output))
        self.selection_var = tk.StringVar(value="선택한 이미지가 없습니다.")
        self.status_var = tk.StringVar(value="1단계부터 차례대로 진행해 주세요.")
        self._messages: queue.Queue[WorkerMessage] = queue.Queue()
        self._working = False
        self._last_output_dir: Path | None = None

        self._build_widgets()

    def _build_widgets(self) -> None:
        style = ttk.Style(self.root)
        style.configure("Primary.TButton", font=("맑은 고딕", 12, "bold"), padding=(18, 10))
        style.configure("Step.TLabelframe.Label", font=("맑은 고딕", 10, "bold"))

        outer = ttk.Frame(self.root, padding=18)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        outer.columnconfigure(0, weight=1)

        ttk.Label(
            outer,
            text="SOOP BANNER MAKER FOR DAMBI",
            font=("맑은 고딕", 17, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=(
                "이미지를 고르고 저장 폴더를 확인한 뒤 버튼 한 번만 누르시면 됩니다.\n"
                "지원 이미지 크기: 720×450 또는 1440×450"
            ),
            font=("맑은 고딕", 10),
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 14))

        files_frame = ttk.LabelFrame(
            outer,
            text="1단계 · 자를 이미지를 선택해 주세요",
            padding=10,
            style="Step.TLabelframe",
        )
        files_frame.grid(row=2, column=0, sticky="nsew")
        files_frame.rowconfigure(1, weight=1)
        files_frame.columnconfigure(0, weight=1)

        selection_row = ttk.Frame(files_frame)
        selection_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        selection_row.columnconfigure(0, weight=1)
        ttk.Label(selection_row, textvariable=self.selection_var).grid(row=0, column=0, sticky="w")
        self.add_button = ttk.Button(selection_row, text="이미지 추가...", command=self._select_images)
        self.add_button.grid(row=0, column=1, sticky="e")

        self.file_list = tk.Listbox(
            files_frame,
            selectmode=tk.EXTENDED,
            activestyle="dotbox",
            font=("맑은 고딕", 10),
            height=9,
        )
        self.file_list.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(files_frame, orient="vertical", command=self.file_list.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scrollbar.set)

        list_buttons = ttk.Frame(files_frame)
        list_buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))
        self.remove_button = ttk.Button(list_buttons, text="선택 항목 삭제", command=self._remove_selected)
        self.remove_button.grid(row=0, column=0)
        self.clear_button = ttk.Button(list_buttons, text="목록 비우기", command=self._clear_images)
        self.clear_button.grid(row=0, column=1, padx=(7, 0))

        output_frame = ttk.LabelFrame(
            outer,
            text="2단계 · 결과를 저장할 폴더를 확인해 주세요",
            padding=10,
            style="Step.TLabelframe",
        )
        output_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        output_frame.columnconfigure(0, weight=1)
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_var)
        self.output_entry.grid(row=0, column=0, sticky="ew")
        self.output_button = ttk.Button(output_frame, text="폴더 선택...", command=self._select_output_dir)
        self.output_button.grid(row=0, column=1, padx=(8, 0))

        action_frame = ttk.LabelFrame(
            outer,
            text="3단계 · 자동으로 잘라 주세요",
            padding=10,
            style="Step.TLabelframe",
        )
        action_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        action_frame.columnconfigure(0, weight=1)
        self.process_button = ttk.Button(
            action_frame,
            text="이미지 자동 자르기",
            command=self._start_processing,
            style="Primary.TButton",
        )
        self.process_button.grid(row=0, column=0, sticky="ew")

        self.progress = ttk.Progressbar(action_frame, mode="indeterminate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        status_row = ttk.Frame(outer)
        status_row.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        status_row.columnconfigure(0, weight=1)
        ttk.Label(status_row, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.open_output_button = ttk.Button(
            status_row,
            text="결과 폴더 열기",
            command=self._open_output_dir,
            state=tk.DISABLED,
        )
        self.open_output_button.grid(row=0, column=1, sticky="e", padx=(10, 0))

    def _select_images(self) -> None:
        was_empty = self.file_list.size() == 0
        chosen = filedialog.askopenfilenames(
            parent=self.root,
            title="자를 이미지를 선택해 주세요",
            filetypes=IMAGE_FILE_TYPES,
        )
        if not chosen:
            return

        existing = set(self.file_list.get(0, tk.END))
        for path in chosen:
            if path not in existing:
                self.file_list.insert(tk.END, path)
                existing.add(path)

        if was_empty and self._auto_output_from_first_image:
            self.output_var.set(str(Path(chosen[0]).parent / "output"))
            self._auto_output_from_first_image = False
        self._update_selection_status()

    def _remove_selected(self) -> None:
        for index in reversed(self.file_list.curselection()):
            self.file_list.delete(index)
        self._update_selection_status()

    def _clear_images(self) -> None:
        self.file_list.delete(0, tk.END)
        self._update_selection_status()

    def _update_selection_status(self) -> None:
        count = self.file_list.size()
        if count:
            self.selection_var.set(f"선택한 이미지: {count}장")
            self.status_var.set("저장 폴더를 확인한 뒤 '이미지 자동 자르기'를 눌러 주세요.")
        else:
            self.selection_var.set("선택한 이미지가 없습니다.")
            self.status_var.set("먼저 자를 이미지를 추가해 주세요.")

    def _select_output_dir(self) -> None:
        current = Path(self.output_var.get().strip()).expanduser()
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
            self._auto_output_from_first_image = False

    def _start_processing(self) -> None:
        if self._working:
            return

        sources = tuple(Path(path) for path in self.file_list.get(0, tk.END))
        if not sources:
            messagebox.showwarning(
                "이미지를 선택해 주세요",
                "먼저 1단계에서 자를 이미지를 한 장 이상 추가해 주세요.",
                parent=self.root,
            )
            return

        output_text = self.output_var.get().strip()
        if not output_text:
            messagebox.showwarning(
                "저장 폴더를 선택해 주세요",
                "2단계에서 결과를 저장할 폴더를 선택해 주세요.",
                parent=self.root,
            )
            return

        output_dir = Path(output_text).expanduser()
        conflicts = find_batch_output_conflicts(
            (source, output_dir) for source in sources
        )
        if conflicts:
            messagebox.showerror(
                "결과 파일 이름이 겹칩니다",
                self._batch_conflict_message(conflicts),
                parent=self.root,
            )
            return

        self._set_working(True)
        threading.Thread(
            target=self._process_images,
            args=(sources, output_dir),
            name="sbm4d-image-cutter",
            daemon=True,
        ).start()
        self.root.after(100, self._poll_messages)

    def _process_images(self, sources: tuple[Path, ...], output_dir: Path) -> None:
        generated: list[Path] = []
        skipped: list[str] = []
        errors: list[str] = []
        processed = 0

        for source in sources:
            try:
                generated.extend(cut_image(source, output_dir, overwrite=False))
                processed += 1
            except ExistingOutputError:
                response: queue.Queue[bool] = queue.Queue(maxsize=1)
                self._messages.put(OverwriteRequest(source=source, response=response))
                if not response.get():
                    skipped.append(f"{source.name}: 기존 결과 파일을 그대로 두었습니다.")
                    continue
                try:
                    generated.extend(cut_image(source, output_dir, overwrite=True))
                    processed += 1
                except UnsupportedImageSizeError as exc:
                    errors.append(self._unsupported_size_message(source, exc))
                except UnsupportedMultiFrameImageError:
                    errors.append(
                        f"{source.name}: 움직이는 이미지나 여러 페이지 이미지는 지원하지 않습니다."
                    )
                except Exception as exc:
                    errors.append(f"{source.name}: 덮어쓰지 못했습니다. ({exc})")
            except UnsupportedImageSizeError as exc:
                errors.append(self._unsupported_size_message(source, exc))
            except UnsupportedMultiFrameImageError:
                errors.append(
                    f"{source.name}: 움직이는 이미지나 여러 페이지 이미지는 지원하지 않습니다."
                )
            except Exception as exc:
                errors.append(f"{source.name}: 처리하지 못했습니다. ({exc})")

        self._messages.put(
            BatchResult(
                processed=processed,
                generated=tuple(generated),
                skipped=tuple(skipped),
                errors=tuple(errors),
                output_dir=output_dir,
            )
        )

    @staticmethod
    def _batch_conflict_message(
        conflicts: tuple[BatchOutputConflict, ...],
    ) -> str:
        details: list[str] = []
        for conflict in conflicts:
            names = "\n".join(f"  · {source}" for source in conflict.sources)
            details.append(f"'{conflict.stem}' 이름이 겹칩니다.\n{names}")
        return (
            "선택한 이미지 중 결과 파일명이 같아질 항목이 있습니다.\n\n"
            + "\n\n".join(details)
            + "\n\n원본 파일명을 서로 다르게 바꾼 뒤 다시 시도해 주세요."
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

    def _poll_messages(self) -> None:
        try:
            message = self._messages.get_nowait()
        except queue.Empty:
            if self._working:
                self.root.after(100, self._poll_messages)
            return

        if isinstance(message, OverwriteRequest):
            overwrite = messagebox.askyesno(
                "기존 결과 파일이 있습니다",
                (
                    f"'{message.source.name}'의 결과 파일이 이미 있습니다.\n\n"
                    "기존 결과 파일을 덮어쓰시겠습니까?\n"
                    "'아니요'를 누르면 이 이미지만 건너뜁니다."
                ),
                parent=self.root,
                default=messagebox.NO,
            )
            message.response.put(overwrite)
            self.root.after(100, self._poll_messages)
            return

        self._set_working(False)
        self._show_result(message)

    def _set_working(self, working: bool) -> None:
        self._working = working
        state = tk.DISABLED if working else tk.NORMAL
        for widget in (
            self.add_button,
            self.remove_button,
            self.clear_button,
            self.output_entry,
            self.output_button,
            self.process_button,
        ):
            widget.configure(state=state)

        if working:
            self.status_var.set("이미지를 자르고 있습니다. 잠시만 기다려 주세요...")
            self.progress.start(12)
        else:
            self.progress.stop()

    def _show_result(self, result: BatchResult) -> None:
        summary = (
            f"이미지 {result.processed}장을 처리하여 "
            f"PNG 파일 {len(result.generated)}개를 만들었습니다."
        )
        self.status_var.set(summary)
        self._last_output_dir = result.output_dir
        if result.output_dir.is_dir():
            self.open_output_button.configure(state=tk.NORMAL)

        details = [summary]
        if result.skipped:
            details.append(
                f"건너뛴 이미지 {len(result.skipped)}장:\n"
                + "\n".join(f"- {item}" for item in result.skipped)
            )
        if result.errors:
            details.append(
                f"처리하지 못한 이미지 {len(result.errors)}장:\n"
                + "\n".join(f"- {item}" for item in result.errors)
            )
        details.append(f"저장 위치:\n{result.output_dir}")
        dialog_text = "\n\n".join(details)

        if result.skipped or result.errors:
            messagebox.showwarning("이미지 자르기 결과", dialog_text, parent=self.root)
        else:
            messagebox.showinfo("이미지 자르기 완료", dialog_text, parent=self.root)

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
