"""テキストブロック抽出パッケージ。

textBlockItemType の Fact からセクション構造化テキストを抽出し、
HTML → プレーンテキスト変換を提供する。

利用例::

    from edinet.xbrl.text import extract_text_blocks, build_section_map, clean_html

    blocks = extract_text_blocks(parsed.facts, context_map)
    section_map = build_section_map(blocks, resolver)

    risk = section_map["事業等のリスク"]
    for block in risk:
        print(clean_html(block.html))
"""

from edinet.xbrl.text.blocks import TextBlock as TextBlock
from edinet.xbrl.text.blocks import extract_text_blocks as extract_text_blocks
from edinet.xbrl.text.clean import clean_html as clean_html
from edinet.xbrl.text.sections import SectionMap as SectionMap
from edinet.xbrl.text.sections import build_section_map as build_section_map

__all__ = [
    "TextBlock",
    "extract_text_blocks",
    "SectionMap",
    "build_section_map",
    "clean_html",
]
