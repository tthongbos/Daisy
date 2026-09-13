from pathlib import Path
from zipfile import ZipFile

from daisy_book.epub import load_epub


def make_epub(path: Path) -> None:
    container = b"""<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="EPUB/book.opf"/></rootfiles>
</container>
"""
    opf = b"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test Book</dc:title>
    <dc:creator>Morgan Housel</dc:creator>
    <dc:creator>Hoang Thi Minh Phuc (d\xe1\xbb\x8bch)</dc:creator>
    <dc:language>vi</dc:language>
    <dc:identifier>book-id</dc:identifier>
  </metadata>
  <manifest>
    <item id="last" href="z-last.xhtml" media-type="application/xhtml+xml"/>
    <item id="first" href="a-first.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="last"/><itemref idref="first"/></spine>
</package>
"""
    with ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("EPUB/book.opf", opf)
        archive.writestr("EPUB/a-first.xhtml", "<html><body>filename first</body></html>")
        archive.writestr("EPUB/z-last.xhtml", "<html><body>spine first</body></html>")


def test_manifest_resolution_and_spine_order(tmp_path: Path):
    epub_path = tmp_path / "book.epub"
    make_epub(epub_path)

    book = load_epub(epub_path)

    assert [document.id for document in book.documents] == ["last", "first"]
    assert [document.href for document in book.documents] == [
        "EPUB/z-last.xhtml",
        "EPUB/a-first.xhtml",
    ]
    assert book.documents[0].content.endswith(b"spine first</body></html>")
    assert book.metadata.title == "Test Book"
    assert book.metadata.authors == ("Morgan Housel",)
    assert book.metadata.translators == ("Hoang Thi Minh Phuc",)
    assert book.metadata.language == "vi"
    assert book.metadata.identifiers == ("book-id",)