from lxml import etree

from daisy_book.build_daisy import build_daisy
from daisy_book.validate_daisy import validate_daisy
from test_daisy_generation import write_inputs


def built_sample(tmp_path):
    book_path, manifest_path, audio_dir, _ = write_inputs(tmp_path)
    output = tmp_path / "daisy"
    build_daisy(book_path, manifest_path, audio_dir, output, "chapter_01")
    return output


def test_generated_sample_passes_structural_validation(tmp_path):
    output = built_sample(tmp_path)

    errors, warnings = validate_daisy(output)

    assert errors == []
    assert warnings == []


def test_rejects_broken_fragment_reference(tmp_path):
    output = built_sample(tmp_path)
    smil_path = output / "chapter_01.smil"
    text = smil_path.read_text(encoding="utf-8").replace(
        "book.xml#chapter_01_p0001", "book.xml#missing"
    )
    smil_path.write_text(text, encoding="utf-8")

    errors, _ = validate_daisy(output)

    assert any("Broken fragment" in error and "missing" in error for error in errors)


def test_rejects_duplicate_xml_ids(tmp_path):
    output = built_sample(tmp_path)
    book_path = output / "book.xml"
    text = book_path.read_text(encoding="utf-8").replace(
        'id="chapter_01_p0001"', 'id="chapter_01_title"'
    )
    book_path.write_text(text, encoding="utf-8")

    errors, _ = validate_daisy(output)

    assert any("Duplicate XML id" in error for error in errors)


def test_rejects_uid_mismatch_and_invalid_clip(tmp_path):
    output = built_sample(tmp_path)
    smil_path = output / "chapter_01.smil"
    tree = etree.parse(str(smil_path))
    uid = tree.xpath("//*[local-name()='meta'][@name='dtb:uid']")[0]
    uid.set("content", "urn:uuid:different")
    audio = tree.xpath("//*[local-name()='audio']")[0]
    audio.set("clipBegin", "0:00:02.000")
    audio.set("clipEnd", "0:00:01.000")
    tree.write(str(smil_path), encoding="utf-8", xml_declaration=True)

    errors, _ = validate_daisy(output)

    assert any("Inconsistent dtb:uid" in error for error in errors)
    assert any("clipBegin must be less than clipEnd" in error for error in errors)


def test_rejects_unknown_opf_spine_idref(tmp_path):
    output = built_sample(tmp_path)
    opf_path = output / "book.opf"
    text = opf_path.read_text(encoding="utf-8").replace(
        'idref="smil_chapter_01"', 'idref="missing"'
    )
    opf_path.write_text(text, encoding="utf-8")

    errors, _ = validate_daisy(output)

    assert any("OPF spine idref does not resolve" in error for error in errors)


def test_rejects_wrong_opf_metadata_and_non_smil_spine_target(tmp_path):
    output = built_sample(tmp_path)
    opf_path = output / "book.opf"
    tree = etree.parse(str(opf_path))
    tree.xpath("//*[local-name()='Format']")[0].text = "wrong"
    tree.xpath("//*[local-name()='meta'][@name='dtb:multimediaType']")[0].set(
        "content", "textNCX"
    )
    tree.xpath("//*[local-name()='meta'][@name='dtb:multimediaContent']")[0].set(
        "content", "text"
    )
    tree.xpath("//*[local-name()='meta'][@name='dtb:audioFormat']")[0].set(
        "content", "WAV"
    )
    tree.xpath("//*[local-name()='meta'][@name='dtb:totalTime']")[0].set(
        "content", "00:00:00.000"
    )
    tree.xpath("//*[local-name()='spine']/*[local-name()='itemref']")[0].set(
        "idref", "dtbook"
    )
    tree.write(str(opf_path), encoding="utf-8", xml_declaration=True)

    errors, _ = validate_daisy(output)

    assert any("dc:Format must occur exactly once" in error for error in errors)
    assert any("dtb:multimediaType must occur exactly once" in error for error in errors)
    assert any("dtb:multimediaContent must occur exactly once" in error for error in errors)
    assert any("dtb:audioFormat must include MP3" in error for error in errors)
    assert any("dtb:totalTime must be greater than zero" in error for error in errors)
    assert any("OPF spine must reference a SMIL manifest item" in error for error in errors)


def test_accepts_additional_multimedia_content_values(tmp_path):
    output = built_sample(tmp_path)
    opf_path = output / "book.opf"
    tree = etree.parse(str(opf_path))
    tree.xpath("//*[local-name()='meta'][@name='dtb:multimediaContent']")[0].set(
        "content", "audio,text,image"
    )
    tree.write(str(opf_path), encoding="utf-8", xml_declaration=True)

    errors, _ = validate_daisy(output)

    assert not any("dtb:multimediaContent" in error for error in errors)


def test_rejects_duplicate_opf_self_entry_and_wrong_manifest_media_types(tmp_path):
    output = built_sample(tmp_path)
    opf_path = output / "book.opf"
    tree = etree.parse(str(opf_path))
    manifest = tree.xpath("//*[local-name()='manifest']")[0]
    opf_item = tree.xpath("//*[local-name()='item'][@href='book.opf']")[0]
    manifest.append(etree.fromstring(etree.tostring(opf_item)))
    expected_types = {
        "book.opf": "application/oebps-package+xml",
        "book.xml": "text/xml",
        "book.ncx": "text/xml",
        "chapter_01.smil": "application/xml",
        "chapter_01.mp3": "audio/mp3",
    }
    for item in tree.xpath("//*[local-name()='manifest']/*[local-name()='item']"):
        item.set("media-type", expected_types[item.get("href")])
    tree.write(str(opf_path), encoding="utf-8", xml_declaration=True)

    errors, _ = validate_daisy(output)

    assert any("exactly one book.opf manifest entry" in error for error in errors)
    for href in expected_types:
        assert any(f"OPF manifest media type for {href}" in error for error in errors)


def test_rejects_smil_audio_not_listed_as_manifest_mp3(tmp_path):
    output = built_sample(tmp_path)
    other_audio = output / "other.mp3"
    other_audio.write_bytes((output / "chapter_01.mp3").read_bytes())
    smil_path = output / "chapter_01.smil"
    tree = etree.parse(str(smil_path))
    for audio in tree.xpath("//*[local-name()='audio']"):
        audio.set("src", "other.mp3")
    tree.write(str(smil_path), encoding="utf-8", xml_declaration=True)

    errors, _ = validate_daisy(output)

    assert any("SMIL audio src is not an OPF manifest MP3" in error for error in errors)


def test_rejects_missing_smil_audio_and_nonmonotonic_or_overlong_timing(tmp_path):
    output = built_sample(tmp_path)
    smil_path = output / "chapter_01.smil"
    tree = etree.parse(str(smil_path))
    audio_elements = tree.xpath("//*[local-name()='audio']")
    audio_elements[0].getparent().remove(audio_elements[0])
    audio_elements[2].set("clipBegin", "0:00:00.500")
    audio_elements[-1].set("clipEnd", "0:00:05.200")
    tree.write(str(smil_path), encoding="utf-8", xml_declaration=True)

    errors, _ = validate_daisy(output)

    assert any("SMIL synchronization unit has no audio" in error for error in errors)
    assert any("SMIL audio timing is not monotonic" in error for error in errors)
    assert any("SMIL final clip exceeds OPF dtb:totalTime" in error for error in errors)