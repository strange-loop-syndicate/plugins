#!/usr/bin/env python3
"""
Markdown to HTML converter for research reports
Properly converts markdown sections to HTML while preserving structure and formatting.

Handles: headers, bold, italic, inline code, code blocks (```), inline links,
blockquotes, nested lists, tables, paragraphs, and bibliography entries.
"""

import re
from typing import Tuple, List
from pathlib import Path


def convert_markdown_to_html(markdown_text: str) -> Tuple[str, str]:
    """
    Convert markdown to HTML in two parts: content and bibliography

    Args:
        markdown_text: Full markdown report text

    Returns:
        Tuple of (content_html, bibliography_html)
    """
    # Split content and bibliography
    parts = markdown_text.split('## Bibliography')
    content_md = parts[0]
    bibliography_md = parts[1] if len(parts) > 1 else ""

    # Convert content (everything except bibliography)
    content_html = _convert_content_section(content_md)

    # Convert bibliography separately
    bibliography_html = _convert_bibliography_section(bibliography_md)

    return content_html, bibliography_html


def _convert_content_section(markdown: str) -> str:
    """Convert main content sections to HTML"""
    html = markdown

    # Remove title and front matter (first ## heading is handled separately)
    lines = html.split('\n')
    processed_lines = []
    skip_until_first_section = True

    for line in lines:
        # Skip everything until we hit "## Executive Summary" or first major section
        if skip_until_first_section:
            if line.startswith('## ') and not line.startswith('### '):
                skip_until_first_section = False
                processed_lines.append(line)
            continue
        processed_lines.append(line)

    html = '\n'.join(processed_lines)

    # Convert code blocks first (before any inline processing)
    html = _convert_code_blocks(html)

    # Convert headers
    # ## Section Title -> <div class="section"><h2 class="section-title">Section Title</h2></div>
    html = re.sub(
        r'^## (.+)$',
        r'<div class="section"><h2 class="section-title">\1</h2>',
        html,
        flags=re.MULTILINE
    )

    # ### Subsection -> <h3 class="subsection-title">Subsection</h3>
    html = re.sub(
        r'^### (.+)$',
        r'<h3 class="subsection-title">\1</h3>',
        html,
        flags=re.MULTILINE
    )

    # #### Subsubsection -> <h4 class="subsubsection-title">Title</h4>
    html = re.sub(
        r'^#### (.+)$',
        r'<h4 class="subsubsection-title">\1</h4>',
        html,
        flags=re.MULTILINE
    )

    # Convert **bold** text
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

    # Convert *italic* text
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Convert inline code `code` (but not inside <pre><code> blocks)
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)

    # Convert inline links [text](url) -> <a href="url" target="_blank">text</a>
    html = re.sub(
        r'\[([^\]]+)\]\((https?://[^\)]+)\)',
        r'<a href="\2" target="_blank">\1</a>',
        html
    )
    # Also handle relative links
    html = re.sub(
        r'\[([^\]]+)\]\(([^\)]+)\)',
        r'<a href="\2" target="_blank">\1</a>',
        html
    )

    # Convert blockquotes
    html = _convert_blockquotes(html)

    # Convert unordered/ordered lists (with nesting support)
    html = _convert_lists(html)

    # Convert tables
    html = _convert_tables(html)

    # Convert paragraphs (wrap non-HTML lines in <p> tags)
    html = _convert_paragraphs(html)

    # Close all open sections
    html = _close_sections(html)

    # Wrap executive summary if present
    html = html.replace(
        '<h2 class="section-title">Executive Summary</h2>',
        '<div class="executive-summary"><h2 class="section-title">Executive Summary</h2>'
    )
    if '<div class="executive-summary">' in html:
        # Close executive summary at the next section
        html = html.replace(
            '</h2>\n<div class="section">',
            '</h2></div>\n<div class="section">',
            1
        )

    # Restore code block placeholders
    html = _restore_code_blocks(html)

    return html


def _code_block_placeholders():
    """Storage for code block placeholders during processing"""
    if not hasattr(_code_block_placeholders, 'blocks'):
        _code_block_placeholders.blocks = {}
        _code_block_placeholders.counter = 0
    return _code_block_placeholders


def _convert_code_blocks(html: str) -> str:
    """Convert triple-backtick code blocks to <pre><code> and replace with placeholders"""
    storage = _code_block_placeholders()
    storage.blocks = {}
    storage.counter = 0

    lines = html.split('\n')
    result = []
    in_code_block = False
    code_lines: List[str] = []
    code_lang = ''

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```') and not in_code_block:
            in_code_block = True
            code_lang = stripped[3:].strip()
            code_lines = []
        elif stripped.startswith('```') and in_code_block:
            in_code_block = False
            code_content = '\n'.join(code_lines)
            # Escape HTML entities inside code
            code_content = code_content.replace('&', '&amp;')
            code_content = code_content.replace('<', '&lt;')
            code_content = code_content.replace('>', '&gt;')
            lang_attr = f' class="language-{code_lang}"' if code_lang else ''
            block_html = f'<pre><code{lang_attr}>{code_content}</code></pre>'
            placeholder = f'<!--CODEBLOCK_{storage.counter}-->'
            storage.blocks[placeholder] = block_html
            storage.counter += 1
            result.append(placeholder)
        elif in_code_block:
            code_lines.append(line)
        else:
            result.append(line)

    # If file ends while still in a code block, close it
    if in_code_block:
        code_content = '\n'.join(code_lines)
        code_content = code_content.replace('&', '&amp;')
        code_content = code_content.replace('<', '&lt;')
        code_content = code_content.replace('>', '&gt;')
        lang_attr = f' class="language-{code_lang}"' if code_lang else ''
        block_html = f'<pre><code{lang_attr}>{code_content}</code></pre>'
        placeholder = f'<!--CODEBLOCK_{storage.counter}-->'
        storage.blocks[placeholder] = block_html
        storage.counter += 1
        result.append(placeholder)

    return '\n'.join(result)


def _restore_code_blocks(html: str) -> str:
    """Restore code block placeholders with actual HTML"""
    storage = _code_block_placeholders()
    for placeholder, block_html in storage.blocks.items():
        html = html.replace(placeholder, block_html)
    storage.blocks = {}
    storage.counter = 0
    return html


def _convert_blockquotes(html: str) -> str:
    """Convert lines starting with > to <blockquote> elements"""
    lines = html.split('\n')
    result = []
    in_blockquote = False
    quote_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('> '):
            if not in_blockquote:
                in_blockquote = True
                quote_lines = []
            quote_lines.append(stripped[2:])
        elif stripped == '>' and in_blockquote:
            # Empty blockquote continuation line
            quote_lines.append('')
        else:
            if in_blockquote:
                quote_content = ' '.join(l for l in quote_lines if l)
                result.append(f'<blockquote><p>{quote_content}</p></blockquote>')
                in_blockquote = False
                quote_lines = []
            result.append(line)

    if in_blockquote:
        quote_content = ' '.join(l for l in quote_lines if l)
        result.append(f'<blockquote><p>{quote_content}</p></blockquote>')

    return '\n'.join(result)


def _convert_bibliography_section(markdown: str) -> str:
    """Convert bibliography section to HTML"""
    if not markdown.strip():
        return ""

    html = markdown

    # Convert each [N] citation to a proper bibliography entry
    # Look for patterns like [1] Title - URL
    html = re.sub(
        r'\[(\d+)\]\s*(.+?)\s*-\s*(https?://[^\s\)]+)',
        r'<div class="bib-entry"><span class="bib-number">[\1]</span> <a href="\3" target="_blank">\2</a></div>',
        html
    )

    # Convert any remaining **bold** sections
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

    # Wrap in bibliography content div
    html = f'<div class="bibliography-content">{html}</div>'

    return html


def _convert_lists(html: str) -> str:
    """Convert markdown lists to HTML lists with proper nesting"""
    lines = html.split('\n')
    result = []
    # Stack of (list_type, indent_level) to track nesting
    list_stack: List[Tuple[str, int]] = []

    def _close_lists_to_level(target_level: int):
        """Close lists down to the target indentation level"""
        while list_stack and list_stack[-1][1] >= target_level:
            lt, _ = list_stack.pop()
            tag = '</ul>' if lt == 'ul' else '</ol>'
            result.append(tag)

    def _close_all_lists():
        """Close all open lists"""
        while list_stack:
            lt, _ = list_stack.pop()
            tag = '</ul>' if lt == 'ul' else '</ol>'
            result.append(tag)

    for i, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # Check for unordered list item
        ul_match = re.match(r'^(\s*)([-*])\s(.+)$', line)
        ol_match = re.match(r'^(\s*)\d+\.\s(.+)$', line)

        if ul_match:
            item_indent = len(ul_match.group(1))
            content = ul_match.group(3)
            list_type = 'ul'

            if not list_stack:
                # Start new list
                result.append('<ul>')
                list_stack.append(('ul', item_indent))
            elif item_indent > list_stack[-1][1]:
                # Nested deeper - open new sublist
                result.append('<ul>')
                list_stack.append(('ul', item_indent))
            elif item_indent < list_stack[-1][1]:
                # Back to a shallower level - close deeper lists
                while list_stack and list_stack[-1][1] > item_indent:
                    lt, _ = list_stack.pop()
                    result.append('</li>')
                    result.append('</ul>' if lt == 'ul' else '</ol>')
                # If stack is empty or different indent, start fresh
                if not list_stack:
                    result.append('<ul>')
                    list_stack.append(('ul', item_indent))
            # Same level, same type: just continue

            result.append(f'<li>{content}')

            # Check if next line is a deeper list item; if not, close <li>
            next_is_deeper = False
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()
                next_indent = len(next_line) - len(next_line.lstrip())
                if (re.match(r'^[-*]\s', next_stripped) or re.match(r'^\d+\.\s', next_stripped)) and next_indent > item_indent:
                    next_is_deeper = True

            if not next_is_deeper:
                result.append('</li>')

        elif ol_match:
            item_indent = len(ol_match.group(1))
            content = ol_match.group(2)

            if not list_stack:
                result.append('<ol>')
                list_stack.append(('ol', item_indent))
            elif item_indent > list_stack[-1][1]:
                result.append('<ol>')
                list_stack.append(('ol', item_indent))
            elif item_indent < list_stack[-1][1]:
                while list_stack and list_stack[-1][1] > item_indent:
                    lt, _ = list_stack.pop()
                    result.append('</li>')
                    result.append('</ul>' if lt == 'ul' else '</ol>')
                if not list_stack:
                    result.append('<ol>')
                    list_stack.append(('ol', item_indent))

            result.append(f'<li>{content}')

            next_is_deeper = False
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()
                next_indent = len(next_line) - len(next_line.lstrip())
                if (re.match(r'^[-*]\s', next_stripped) or re.match(r'^\d+\.\s', next_stripped)) and next_indent > item_indent:
                    next_is_deeper = True

            if not next_is_deeper:
                result.append('</li>')

        else:
            # Not a list item
            if list_stack:
                if stripped and indent > list_stack[-1][1]:
                    # Continuation text of previous list item - append to last li
                    if result and result[-1] == '</li>':
                        result.pop()  # Remove the </li> we just added
                        result.append(' ' + stripped)
                        result.append('</li>')
                    else:
                        result.append(line)
                    continue
                else:
                    # End of all lists
                    _close_all_lists()

            result.append(line)

    # Close any remaining open lists
    _close_all_lists()

    return '\n'.join(result)


def _convert_tables(html: str) -> str:
    """Convert markdown tables to HTML tables"""
    lines = html.split('\n')
    result = []
    in_table = False

    for i, line in enumerate(lines):
        if '|' in line and line.strip().startswith('|'):
            if not in_table:
                result.append('<table>')
                in_table = True
                # This is the header row
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                result.append('<thead><tr>')
                for cell in cells:
                    result.append(f'<th>{cell}</th>')
                result.append('</tr></thead>')
                result.append('<tbody>')
            elif '---' in line:
                # Skip separator row
                continue
            else:
                # Data row
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                result.append('<tr>')
                for cell in cells:
                    result.append(f'<td>{cell}</td>')
                result.append('</tr>')
        else:
            if in_table:
                result.append('</tbody></table>')
                in_table = False
            result.append(line)

    if in_table:
        result.append('</tbody></table>')

    return '\n'.join(result)


def _convert_paragraphs(html: str) -> str:
    """Wrap non-HTML lines in paragraph tags"""
    lines = html.split('\n')
    result = []
    in_paragraph = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            if in_paragraph:
                result.append('</p>')
                in_paragraph = False
            result.append(line)
            continue

        # Skip lines that are already HTML tags or special elements
        if (stripped.startswith('<') and stripped.endswith('>')) or \
           stripped.startswith('</') or \
           '<h' in stripped or '<div' in stripped or '<ul' in stripped or \
           '<ol' in stripped or '<li' in stripped or '<table' in stripped or \
           '</div>' in stripped or '</ul>' in stripped or '</ol>' in stripped or \
           '<pre>' in stripped or '<blockquote>' in stripped or \
           stripped.startswith('<!--CODEBLOCK_'):
            if in_paragraph:
                result.append('</p>')
                in_paragraph = False
            result.append(line)
            continue

        # Regular text line - wrap in paragraph
        if not in_paragraph:
            result.append('<p>' + line)
            in_paragraph = True
        else:
            result.append(line)

    if in_paragraph:
        result.append('</p>')

    return '\n'.join(result)


def _close_sections(html: str) -> str:
    """Close all open section divs"""
    lines = html.split('\n')
    result = []
    section_open = False

    for i, line in enumerate(lines):
        if '<div class="section">' in line:
            if section_open:
                result.append('</div>')  # Close previous section
            section_open = True
        result.append(line)

    # Close final section if still open
    if section_open:
        result.append('</div>')

    return '\n'.join(result)


def main():
    """Convert a markdown file to HTML and print the result"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python md_to_html.py <markdown_file>")
        sys.exit(1)

    md_file = Path(sys.argv[1])
    if not md_file.exists():
        print(f"Error: File {md_file} not found")
        sys.exit(1)

    markdown_text = md_file.read_text()
    content_html, bib_html = convert_markdown_to_html(markdown_text)

    print("=== CONTENT HTML ===")
    print(content_html)
    print("\n=== BIBLIOGRAPHY HTML ===")
    print(bib_html)


if __name__ == "__main__":
    main()
