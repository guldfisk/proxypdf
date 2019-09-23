import typing as t

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch


class ProxyWriter(object):
    _PROXY_WIDTH = 2.5*inch
    _PROXY_HEIGHT = 3.5*inch

    def __init__(
        self,
        file,
        page_size: t.Tuple[float, float] = A4,
        margin_size: float = 0.1,
        card_margin_size: float = 0.0,
    ):
        self._canvas = canvas.Canvas(
            file,
            pagesize = page_size,
        )
        self._pagesize = page_size
        self._margin_size = margin_size*inch

        if self._margin_size * 2 + self._PROXY_WIDTH > self._pagesize[0]:
            self._margin_size = (self._pagesize[0] - self._PROXY_WIDTH) / 2
        if self._margin_size * 2 + self._PROXY_HEIGHT > self._pagesize[1]:
            self._margin_size = (self._pagesize[1] - self._PROXY_HEIGHT) / 2

        self._card_margin_size = card_margin_size*inch
        self._cursor: t.Optional[t.Tuple[float, float]] = None
        self._reset_cursor()

    def _reset_cursor(self):
        self._cursor = (self._margin_size, self._pagesize[1] - self._margin_size)

    def add_proxy(self, image: t.Union[ImageReader, str, Image.Image]):
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
                self._cursor = (self._margin_size, self._cursor[1]-self._PROXY_HEIGHT - self._card_margin_size)

        else:
            self._cursor = (self._cursor[0]+self._PROXY_WIDTH + self._card_margin_size, self._cursor[1])

    def save(self):
        self._canvas.showPage()
        self._canvas.save()


def _save_proxy_pdf(
    file: t.BinaryIO,
    images: t.Iterable[t.Union[ImageReader, str, Image.Image]],
    margin_size: float = 0.1,
    card_margin_size = 0.0,
):
    proxy_writer = ProxyWriter(
        file=f,
        margin_size=margin_size,
        card_margin_size=card_margin_size,
    )

    for image in images:
        proxy_writer.add_proxy(image)

    proxy_writer.save()


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
