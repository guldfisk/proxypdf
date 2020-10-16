from __future__ import annotations

import os
import tempfile
import typing as t
from abc import ABC, abstractmethod

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch


class BaseProxyWriter(ABC):
    _PROXY_WIDTH = 2.5 * inch
    _PROXY_HEIGHT = 3.5 * inch

    def __enter__(self) -> BaseProxyWriter:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self.save()

    # @abstractmethod
    # def open(self) -> bool:
    #     pass

    @abstractmethod
    def add_proxy(self, image: t.Union[ImageReader, str, Image.Image]):
        pass

    @abstractmethod
    def save(self):
        pass


class ProxyWriter(BaseProxyWriter):

    def __init__(
        self,
        file: t.Union[str, t.IO[bytes]],
        page_size: t.Tuple[float, float] = A4,
        margin_size: float = 0.1,
        card_margin_size: float = 0.0,
    ):
        self._canvas = canvas.Canvas(
            file,
            pagesize = page_size,
        )
        self._pagesize = page_size
        self._margin_size = margin_size * inch

        if self._margin_size * 2 + self._PROXY_WIDTH > self._pagesize[0]:
            self._margin_size = (self._pagesize[0] - self._PROXY_WIDTH) / 2
        if self._margin_size * 2 + self._PROXY_HEIGHT > self._pagesize[1]:
            self._margin_size = (self._pagesize[1] - self._PROXY_HEIGHT) / 2

        self._card_margin_size = card_margin_size * inch
        self._cursor: t.Optional[t.Tuple[float, float]] = None
        self._reset_cursor()

    def _reset_cursor(self):
        self._cursor = (self._margin_size, self._pagesize[1] - self._margin_size)

    def add_proxy(self, image: t.Union[ImageReader, str, Image.Image]) -> None:
        self._canvas.drawImage(
            ImageReader(image) if isinstance(image, Image.Image) else image,
            self._cursor[0],
            self._cursor[1] - self._PROXY_HEIGHT,
            self._PROXY_WIDTH,
            self._PROXY_HEIGHT,
            mask = 'auto',
        )

        if (
            self._cursor[0] + (self._PROXY_WIDTH + self._card_margin_size) * 2
            > self._pagesize[0] - self._margin_size
        ):
            if (
                self._cursor[1] - (self._PROXY_HEIGHT - self._card_margin_size) * 2
                < self._margin_size
            ):
                self._canvas.showPage()
                self._reset_cursor()

            else:
                self._cursor = (self._margin_size, self._cursor[1] - self._PROXY_HEIGHT - self._card_margin_size)

        else:
            self._cursor = (self._cursor[0] + self._PROXY_WIDTH + self._card_margin_size, self._cursor[1])

    def save(self):
        self._canvas.save()


# class MaxPagesProxyWriter(ProxyWriter):
#
#     def __init__(
#         self,
#         file,
#         page_size: t.Tuple[float, float] = A4,
#         margin_size: float = 0.1,
#         card_margin_size: float = 0.0,
#         max_pages: int = 8,
#     ):
#         super().__init__(file, page_size, margin_size, card_margin_size)
#         self._max_pages = max_pages
#
#     def _on_next_page(self):
#         if self._canvas.getPageNumber() >= self._max_pages:
#             self.save()
#             return False
#         return super()._on_next_page()
#
#
# class StreamProxyWriter(BaseProxyWriter):
#
#     def __init__(
#         self,
#         destination: str,
#         page_size: t.Tuple[float, float] = A4,
#         margin_size: float = 0.1,
#         card_margin_size: float = 0.0,
#         page_chunk_size: int = 8,
#         target_dir: t.Optional[str] = None,
#     ):
#         self._destination = destination
#         self._page_size = page_size
#         self._margin_size = margin_size
#         self._card_margin_size = card_margin_size
#         self._page_chunk_size = page_chunk_size
#
#         self._temp_dir = tempfile.TemporaryDirectory() if target_dir is None else None
#         self._target_dir = target_dir
#         self._parts: int = 0
#
#         self._writer: MaxPagesProxyWriter
#         self._new_writer()
#
#     def _new_writer(self) -> None:
#         self._writer = MaxPagesProxyWriter(
#             os.path.join(self._target_dir or self._temp_dir.name, str(self._parts)),
#             page_size = self._page_size,
#             margin_size = self._margin_size,
#             card_margin_size = self._card_margin_size,
#             max_pages = self._page_chunk_size,
#         )
#         self._parts += 1
#
#     def add_proxy(self, image: t.Union[ImageReader, str, Image.Image]):
#         if not self._writer.add_proxy(image):
#             self._new_writer()
#
#     def _clean_up(self):
#         if self._writer and self._writer.open():
#             self._writer.save()
#
#     def open(self) -> bool:
#         return self._writer and self._writer.open()
#
#     def save(self):
#         if self.open():
#             self._writer.save()
#
#         merger = PdfFileMerger()
#
#         for part in range(self._parts):
#             merger.append(PdfFileReader(os.path.join(self._target_dir or self._temp_dir.name, str(part))))
#
#         merger.write(self._destination)
#
#         if not self._target_dir:
#             self._temp_dir.cleanup()


# class AnnotatedProxyWriter(BaseProxyWriter):
#
#     def __init__(
#         self,
#         file,
#         page_size: t.Tuple[float, float] = A4,
#         margin_size: float = 0.1,
#         card_margin_size: float = 0.0,
#     ):
#         self._canvas = canvas.Canvas(
#             file,
#             pagesize = page_size,
#         )
#         self._pagesize = page_size
#         self._margin_size = margin_size * inch
#
#         if self._margin_size * 2 + self._PROXY_WIDTH > self._pagesize[0]:
#             self._margin_size = (self._pagesize[0] - self._PROXY_WIDTH) / 2
#
#         if self._margin_size * 2 + self._PROXY_HEIGHT > self._pagesize[1]:
#             self._margin_size = (self._pagesize[1] - self._PROXY_HEIGHT) / 2
#
#         self._card_margin_size = card_margin_size * inch
#         self._cursor: t.Optional[t.Tuple[float, float]] = None
#         self._reset_cursor()
#
#     def _reset_cursor(self):
#         self._cursor = (self._margin_size, self._pagesize[1] - self._margin_size)


def _save_proxy_pdf(
    file: t.BinaryIO,
    images: t.Iterable[t.Union[ImageReader, str, Image.Image]],
    margin_size: float = 0.1,
    card_margin_size = 0.0,
):
    with ProxyWriter(
        file = file,
        margin_size = margin_size,
        card_margin_size = card_margin_size,
    ) as writer:
        for image in images:
            writer.add_proxy(image)


def save_proxy_pdf(
    file: t.Union[t.BinaryIO, str],
    images: t.Iterable[t.Union[ImageReader, str, Image.Image]],
    margin_size: float = 0.1,
    card_margin_size = 0.0,
):
    if isinstance(file, str):
        with open(file, 'wb') as f:
            _save_proxy_pdf(
                f,
                images,
                margin_size,
                card_margin_size,
            )
    else:
        _save_proxy_pdf(
            file,
            images,
            margin_size,
            card_margin_size,
        )
