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
    audio.set("clipBegin", "npt=2.000s")
    audio.set("clipEnd", "npt=1.000s")
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