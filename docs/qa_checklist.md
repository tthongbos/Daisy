# DAISY 3 QA checklist

## Source

- [ ] Correct Vietnamese edition selected
- [ ] ISBN matches the selected edition
- [ ] Source provenance is recorded
- [ ] No copyrighted source text/audio is committed publicly without permission

## Metadata

- [ ] title
- [ ] creator
- [ ] subject
- [ ] description
- [ ] publisher
- [ ] date
- [ ] source / ISBN
- [ ] language = vi
- [ ] collector and source URL recorded when available

## Text

- [ ] No missing chapter
- [ ] Chapter titles are correctly marked
- [ ] No obvious OCR/conversion artifacts
- [ ] Punctuation produces sensible pauses
- [ ] Foreign names, currencies, acronyms and percentages are reviewed

## Audio

- [ ] No clipped beginning/end
- [ ] No long accidental silence
- [ ] Stable volume
- [ ] Natural pace for long-form listening
- [ ] Pronunciation corrections were listened to, not guessed blindly

## DAISY structure

- [ ] XML/DTBook is valid
- [ ] SMIL references exist
- [ ] MP3 references exist
- [ ] NCX navigation works
- [ ] OPF manifest references exist
- [ ] Text/audio synchronization is acceptable

## Reader test

- [ ] Opens in Dolphin EasyReader or Thorium
- [ ] Can jump to chapters
- [ ] Next/previous navigation works
- [ ] Playback position is understandable and stable
- [ ] Chapter 1 has been tested before full-book generation

## Submission

- [ ] Whole book is complete
- [ ] Final ZIP created
- [ ] SHA-256 checksum created
- [ ] README contains reproduction instructions
- [ ] Report records tools, failures, fixes and limitations
