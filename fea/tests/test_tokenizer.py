"""The keyword tokenizer: comments, line endings, parameters and data lines."""

import pytest

from anisotropy_fea.abaqus_reader import DeckError, tokenize


def test_comments_blank_lines_and_crlf_are_dropped_and_data_lines_keep_their_numbers():
    text = "*Heading\r\n** a comment\r\n\r\nmy model\r\n*Node\r\n 1, 0., 0.,\r\n"
    blocks = tokenize(text)
    assert [block.name for block in blocks] == ["heading", "node"]
    assert blocks[0].data == (("my model",),)
    assert blocks[1].data == (("1", "0.", "0."),)  # the trailing comma leaves no empty token
    assert blocks[1].line == 5 and blocks[1].data_lines == (6,)


def test_parameters_flags_and_case():
    (block,) = tokenize("*Shell Section, elset=A, composite, Orientation=Ori-1, layup=L\n")
    assert block.name == "shell section"
    assert block.params == {"elset": "A", "composite": None, "orientation": "Ori-1", "layup": "L"}


def test_keyword_name_whitespace_is_collapsed_and_lower_cased():
    (block,) = tokenize("*End   Part\n")
    assert block.name == "end part"


def test_multi_line_data_is_kept_in_order():
    (block,) = tokenize("*Nset, nset=A\n 1, 2, 3\n 4, 5\n")
    assert block.data == (("1", "2", "3"), ("4", "5"))


def test_repeated_parameter_is_refused():
    with pytest.raises(DeckError, match="line 1: .*repeats the parameter 'nset'"):
        tokenize("*Nset, nset=A, nset=B\n")


def test_data_before_any_keyword_is_refused():
    with pytest.raises(DeckError, match="line 2: data before any keyword"):
        tokenize("** only a comment\n1, 2, 3\n")


def test_leading_spaces_before_a_keyword_are_allowed():
    (block,) = tokenize("   *Static\n1., 1.\n")
    assert block.name == "static" and block.data == (("1.", "1."),)
