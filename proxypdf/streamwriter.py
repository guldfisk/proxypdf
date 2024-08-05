from __future__ import annotations

import base64
import typing as t
import zlib
from abc import ABC, abstractmethod

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch

from proxypdf.write import BaseProxyWriter


B = t.Union[bytes, str, int, float]


def b(v: B) -> bytes:
    if isinstance(v, bytes):
        return v
    if isinstance(v, (int, float)):
        return str(v).encode("ascii")
    if isinstance(v, str):
        return v.encode("ascii")
    raise ValueError()


class PdfObjectBase(ABC):
    @abstractmethod
    def write(self, stream: t.IO[bytes]) -> None:
        pass


Writeable = t.Union[B, PdfObjectBase]


class PdfDict(PdfObjectBase):
    def __init__(self, values: t.Mapping[bytes, Writeable]):
        self._values = values

    @property
    def values(self) -> t.Mapping[bytes, Writeable]:
        return self._values

    def write(self, stream: t.IO[bytes]) -> None:
        stream.write(b"<<\n")
        for k, v in self._values.items():
            stream.write(b"    " + k + b" ")
            if isinstance(v, PdfObjectBase):
                v.write(stream)
            else:
                stream.write(b(v))
            stream.write(b"\n")
        stream.write(b">>\n")


class PdfStream(PdfObjectBase):
    def __init__(self, content: bytes, values: t.Optional[t.Mapping[bytes, Writeable]] = None):
        self._content: bytes = content
        self._values = values or {}

    def write(self, stream: t.IO[bytes]) -> None:
        encoded = b(base64.a85encode(zlib.compress(self._content)))
        PdfDict(
            {
                b"/Filter": PdfList([b"/ASCII85Decode", b"/FlateDecode"]),
                b"/Length": b(len(encoded)),
                **self._values,
            }
        ).write(stream)
        stream.write(b"stream\n")
        stream.write(encoded)
        stream.write(b"\nendstream\n")


class PdfList(PdfObjectBase):
    def __init__(self, values: t.Sequence[Writeable]):
        self._values = values

    def write(self, stream: t.IO[bytes]) -> None:
        stream.write(b"[ ")
        for v in self._values:
            if isinstance(v, PdfObjectBase):
                v.write(stream)
            else:
                stream.write(b(v))
            stream.write(b" ")
        stream.write(b"]")


O = t.TypeVar("O", bound=PdfObjectBase)


class IndirectObject(t.Generic[O], PdfObjectBase):
    def __init__(self, content: O):
        super().__init__()
        self._content = content

        self.number: int = -1
        self._bytes_offset: int = 0

    @property
    def content(self) -> O:
        return self._content

    @content.setter
    def content(self, value: O) -> None:
        self._content = value

    @property
    def reference(self) -> bytes:
        return b(self.number) + b" 0 R"

    def write(self, stream: t.IO[bytes]) -> None:
        self._bytes_offset = stream.tell()
        stream.write(b(self.number))
        stream.write(b" 0 obj\n")
        self._content.write(stream)
        stream.write(b"endobj\n")
        del self._content

    @property
    def byte_offset(self) -> int:
        return self._bytes_offset


class StreamProxyWriter(BaseProxyWriter):
    def __init__(
        self,
        file: t.Union[str, t.IO[bytes]],
        *,
        page_size: t.Tuple[float, float] = A4,
        margin_size: float = 0.1,
        card_margin_size: float = 0.0,
        close_stream: bool = True,
    ):
        self._file = file
        self._page_size = page_size
        self._margin_size = margin_size * inch
        self._card_margin_size = card_margin_size
        self._close_stream = close_stream

        self._stream: t.Optional[t.IO[bytes]] = None

        self._object_counter: int = 0
        self._objects = []
        self._root: t.Optional[IndirectObject[PdfDict]] = None
        self._pages: t.List[IndirectObject[PdfDict]] = []
        self._pages_root: t.Optional[IndirectObject[PdfDict]] = None

        self._proxy_positions: t.List[t.Tuple[IndirectObject, t.Tuple[float, float]]] = []

        if self._margin_size * 2 + self._PROXY_WIDTH > self._page_size[0]:
            self._margin_size = (self._page_size[0] - self._PROXY_WIDTH) / 2
        if self._margin_size * 2 + self._PROXY_HEIGHT > self._page_size[1]:
            self._margin_size = (self._page_size[1] - self._PROXY_HEIGHT) / 2

        self._card_margin_size = card_margin_size * inch
        self._cursor: t.Optional[t.Tuple[float, float]] = None

        self._reset_cursor()

    def _reset_cursor(self):
        self._cursor = (self._margin_size, self._page_size[1] - self._margin_size)

    def _write_tail(self) -> None:
        xref_offset = self._stream.tell()
        object_count = b(len(self._objects) + 1)
        self._stream.write(b"xref\n")
        self._stream.write(b"0 ")
        self._stream.write(object_count)
        self._stream.write(b"\n")
        self._stream.write(b"0000000000 65535 f \n")
        for pdf_object in self._objects:
            self._stream.write(str(pdf_object.byte_offset).rjust(10, "0").encode("ASCII"))
            self._stream.write(b" 00000 n \n")

        self._stream.write(b"trailer\n")
        PdfDict(
            {
                b"/Size": object_count,
                b"/Root": self._root.reference,
            }
        ).write(self._stream)

        self._stream.write(b"startxref\n")
        self._stream.write(b(xref_offset))
        self._stream.write(b"\n%%EOF\n")

    def _add_object(self, pdf_object: IndirectObject[O], write: bool = True) -> IndirectObject[O]:
        self._object_counter += 1
        pdf_object.number = self._object_counter
        self._objects.append(pdf_object)
        if write:
            pdf_object.write(self._stream)
        return pdf_object

    def _flush_page(self) -> None:
        self._reset_cursor()

        content_stream = self._add_object(
            IndirectObject(
                PdfStream(
                    b"1 0 0 1 0 0 cm "
                    + b" ".join(
                        b"q 180 0 0 252 " + b(x) + b" " + b(y) + b" cm /FormXob." + b(idx + 1) + b" Do Q"
                        for idx, (form, (x, y)) in enumerate(self._proxy_positions)
                    )
                )
            )
        )

        self._pages.append(
            self._add_object(
                IndirectObject(
                    PdfDict(
                        {
                            b"/MediaBox": PdfList([0, 0, *self._page_size]),
                            b"/Type": b"/Page",
                            b"/Parent": self._pages_root.reference,
                            b"/Contents": content_stream.reference,
                            b"/Resources": PdfDict(
                                {
                                    b"/ProcSet": PdfList([b"/PDF", b"/Text", b"/ImageB", b"/ImageC", b"/ImageI"]),
                                    b"/XObject": PdfDict(
                                        {
                                            b"/FormXob." + b(idx + 1): form.reference
                                            for idx, (form, position) in enumerate(self._proxy_positions)
                                        }
                                    ),
                                }
                            ),
                        }
                    )
                )
            )
        )

        del self._proxy_positions[:]
        self._stream.flush()

    def _add_image_form(self, image: Image.Image) -> IndirectObject:
        mask = self._add_object(
            IndirectObject(
                PdfStream(
                    image.getchannel("A").tobytes(),
                    {
                        b"/BitsPerComponent": b"8",
                        b"/ColorSpace": b"/DeviceGray",
                        b"/Decode": PdfList([b"0", b"1"]),
                        b"/Height": b(image.height),
                        b"/Width": b(image.width),
                        b"/Subtype": b"/Image",
                        b"/Type": b"/XObject",
                    },
                )
            )
        )

        return self._add_object(
            IndirectObject(
                PdfStream(
                    image.convert("RGB").tobytes(),
                    {
                        b"/BitsPerComponent": b"8",
                        b"/ColorSpace": b"/DeviceRGB",
                        b"/Height": b(image.height),
                        b"/Width": b(image.width),
                        b"/Subtype": b"/Image",
                        b"/Type": b"/XObject",
                        b"/SMask": mask.reference,
                    },
                )
            )
        )

    def _add_proxy(self, form: IndirectObject) -> None:
        self._proxy_positions.append(
            (
                form,
                (
                    self._cursor[0],
                    self._cursor[1] - self._PROXY_HEIGHT,
                ),
            )
        )

        if self._cursor[0] + (self._PROXY_WIDTH + self._card_margin_size) * 2 > self._page_size[0] - self._margin_size:
            if self._cursor[1] - (self._PROXY_HEIGHT - self._card_margin_size) * 2 < self._margin_size:
                self._flush_page()

            else:
                self._cursor = (self._margin_size, self._cursor[1] - self._PROXY_HEIGHT - self._card_margin_size)

        else:
            self._cursor = (self._cursor[0] + self._PROXY_WIDTH + self._card_margin_size, self._cursor[1])

    def add_proxy(self, image: Image.Image, amount: int = 1) -> None:
        if amount <= 0:
            return
        form = self._add_image_form(image)
        for _ in range(amount):
            self._add_proxy(form)

    def open(self):
        self._stream = open(self._file, "wb") if isinstance(self._file, str) else self._file

        self._stream.write(b"%PDF-1.3\n%cool beans\n")

        self._pages_root = self._add_object(
            IndirectObject(PdfDict({})),
            write=False,
        )

        self._root = self._add_object(
            IndirectObject(
                PdfDict(
                    {
                        b"/Type": b"/Catalog",
                        b"/Pages": self._pages_root.reference,
                    }
                )
            )
        )

    def save(self):
        if self._proxy_positions:
            self._flush_page()

        self._pages_root.content = PdfDict(
            {
                b"/Type": b"/Pages",
                b"/Count": b(len(self._pages)),
                b"/Kids": PdfList([page.reference for page in self._pages]),
            }
        )

        self._pages_root.write(self._stream)

        self._write_tail()
        if self._close_stream:
            self._stream.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_tb is not None:
            if self._close_stream:
                self._stream.close()
        else:
            self.save()
