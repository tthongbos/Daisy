import unicodedata

from lxml import html

from daisy_book.normalize import normalize_document, paragraph_text


def test_unicode_and_repeated_whitespace_normalization():
    document = normalize_document("<html><body><p>Ta\u0302m   ly\u0301</p></body></html>")
    text = paragraph_text(document.xpath("//p")[0])

    assert text == "Tâm lý"
    assert unicodedata.is_normalized("NFC", text)


def test_removes_only_empty_paragraphs():
    document = normalize_document(
        '<html><body><p> \u00a0 </p><p><img src="images/chart.jpg" alt="Image"></p></body></html>'
    )

    paragraphs = document.xpath("//p")
    assert len(paragraphs) == 1
    assert paragraphs[0].xpath(".//img/@src") == ["images/chart.jpg"]


def test_unwraps_formatting_spans_and_concatenates_text():
    document = normalize_document(
        '<html><body><p><span class="calibre2">Ông</span> '
        '<span lang="en">không</span>  điên</p></body></html>'
    )

    paragraph = document.xpath("//p")[0]
    assert paragraph_text(paragraph) == "Ông không điên"
    assert paragraph.xpath(".//span") == []


def test_preserves_semantic_inline_elements_and_images():
    document = normalize_document(
        '<html><body><p><b>B</b><strong>S</strong><em>E</em>'
        '<sup>2</sup><sub>i</sub><img src="images/a.jpg" alt=" Image "></p></body></html>'
    )
    paragraph = document.xpath("//p")[0]

    assert [child.tag for child in paragraph] == ["b", "strong", "em", "sup", "sub", "img"]
    assert paragraph.xpath(".//img/@src") == ["images/a.jpg"]
    assert paragraph.xpath(".//img/@alt") == ["Image"]