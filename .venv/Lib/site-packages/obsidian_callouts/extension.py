# SPDX-FileCopyrightText: © 2025 Serhii “GooRoo” Olendarenko
# SPDX-License-Identifier: BSD-3-Clause

# import logging
import re
import xml.etree.ElementTree as etree

import markdown
from markdown import util
from markdown.blockprocessors import BlockProcessor

# logger = logging.getLogger(f'markdown.extensions.{__name__}')


class ObsidianCalloutProcessor(BlockProcessor):
    """
    Process Obsidian-style callouts:
    https://help.obsidian.md/Editing+and+formatting/Callouts
    """

    RE_START = re.compile(
        r'(?:^|\n)[ ]{0,3}>[ ]?(?:\[!(?P<type>[^]]+)\](?P<expand>[-+])?[ ]*?(?:[ ]+(?P<title>[^\n]+))?)\n'
    )
    RE_LINE = re.compile(r'(^|\n)[ ]{0,3}>[ ]?(.*)')

    def test(self, parent: etree.Element, block: str) -> bool:
        return bool(self.RE_START.search(block)) and not util.nearing_recursion_limit()

    def run(self, parent: etree.Element, blocks: list[str]):
        block = blocks.pop(0)

        if m := self.RE_START.search(block):
            before = block[: m.start()]  # Lines before the callout
            self.parser.parseBlocks(parent, [before])  # Parse them first

            quote = self.tag_for_match(m, parent)

            # Remove the callout line from the block.
            block = block[m.end() :]
            # Remove `> ` from beginning of each line.
            block = '\n'.join([self.clean(line) for line in block.split('\n')])

        # Recursively parse block with callout as parent.
        self.parser.state.set('callout')
        self.parser.parseChunk(quote, block)
        self.parser.state.reset()

    def tag_for_match(self, m: re.Match[str], parent) -> etree.Element:
        callout_type, callout_caption = self.to_callout_type(m.group('type'))

        if m['expand'] is not None:
            callout = etree.SubElement(parent, 'details')
            callout.set('class', f'admonition {callout_type}')
            if m['expand'] == '+':
                callout.set('open', '1')

            summary = etree.SubElement(callout, 'summary')
            summary.text = m['title'] if m['title'] else callout_caption

        else:
            callout = etree.SubElement(parent, 'div')
            callout.set('class', f'admonition {callout_type}')

            title = etree.SubElement(callout, 'p')
            title.set('class', 'admonition-title')
            title.text = m['title'] if m['title'] else callout_caption

        return callout

    def to_callout_type(self, callout_type: str) -> tuple[str, str]:
        match ct := callout_type.lower():
            case ('summary' | 'tldr') as p:
                return 'abstract', p.capitalize()
            case ('hint' | 'important') as p:
                return 'tip', p.capitalize()
            case ('check' | 'done') as p:
                return 'success', p.capitalize()
            case ('help' | 'faq') as p:
                return 'question', p.capitalize()
            case ('caution' | 'attention') as p:
                return 'warning', p.capitalize()
            case ('fail' | 'missing') as p:
                return 'failure', p.capitalize()
            case 'error':
                return 'danger', 'Error'
            case 'cite':
                return 'quote', 'Cite'
            case _:
                return ct, ct.capitalize()

    def clean(self, line: str) -> str:
        """Remove `>` from beginning of a line."""
        m = self.RE_LINE.match(line)
        if line.strip() == '>':
            return ''
        elif m:
            return m.group(2)
        else:
            return line


class ObsidianCalloutsExtension(markdown.extensions.Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(ObsidianCalloutProcessor(md.parser), 'obsidian_callout', priority=25)
