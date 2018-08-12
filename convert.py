#!/usr/bin/env python2
"""Script to export a Hatta wiki to plain HTML. Most useful for migrating to
gitit or other wikis."""

# Script incorporates code from the Hatta wiki, and is thus GPLv2, like Hatta
# itself; see COPYING for details.

import argparse
import errno
import os
import textwrap
import urllib

import bs4
import hatta
import werkzeug
from werkzeug import html
from hatta.page import page_mime


def name_to_file(name):
    """Map a page title (as str) into a valid filename (as str)."""
    valid_parts = [c for c in name.split('/') if c]
    assert len(valid_parts) > 0, "couldn't extract parts from name '%s'" % name
    escape_parts = [urllib.quote(p, safe=' _-.') for p in valid_parts]
    return os.path.join(*escape_parts)


def mkdir_p(dir_path):
    """Recursively create a new directory, ignoring any 'directory exists'
    errors that may occur along the way."""
    parts = []
    head = dir_path.rstrip(os.path.sep)
    old_head = None
    while head and head != old_head:
        old_head = head
        head, tail = os.path.split(head)
        head = head.rstrip(os.path.sep)
        parts.append(tail)
    parts = parts[::-1]
    for part_idx in range(len(parts)):
        prefix = os.path.join(*parts[:part_idx + 1]) + os.path.sep
        try:
            os.mkdir(prefix)
        except OSError as ex:
            # EEXIST is fine, whatever; everything else re-raises
            if ex.errno != errno.EEXIST:
                raise


class CustomRenderComponents:
    def __init__(self, converter, page_name, strip_html_link_ext):
        self.converter = converter
        self.wiki = converter.wiki
        self.page_name = page_name
        self.strip_html_link_ext = strip_html_link_ext

        # for _link_alias
        if self.wiki.alias_page and self.wiki.alias_page in self.wiki.storage:
            self._aliases = dict(
                self.wiki.index.page_links_and_labels(self.wiki.alias_page))
        else:
            self._aliases = {}

    def get_ref_path(self, other_title):
        # now need to get file paths & relative path between those two
        this_subpath = self.converter.out_subpath(
            self.page_name, omit_html_ext=self.strip_html_link_ext)
        this_dir = os.path.dirname(this_subpath)
        other_subpath = self.converter.out_subpath(
            other_title, omit_html_ext=self.strip_html_link_ext)
        relpath = os.path.relpath(other_subpath, start=this_dir)
        return relpath

    def _link_alias(self, addr):
        try:
            alias, target = addr.split(':', 1)
        except ValueError:
            return self.wiki.alias_page
        try:
            pattern = self._aliases[alias]
        except KeyError:
            return self.wiki.alias_page
        try:
            link = pattern % target
        except TypeError:
            link = pattern + target
        return link

    def wiki_image(self, addr, alt, class_='wiki', lineno=0):
        addr = addr.strip()
        chunk = ''
        if hatta.parser.external_link(addr):
            return html.img(
                src=werkzeug.url_fix(addr), class_="external", alt=alt)
        if '#' in addr:
            addr, chunk = addr.split('#', 1)
        if addr == '':
            return html.a(name=chunk)
        elif addr.startswith(':'):
            if chunk:
                chunk = '#' + chunk
            alias = self._link_alias(addr[1:])
            href = werkzeug.url_fix(alias + chunk)
            return html.img(src=href, class_="external alias", alt=alt)
        elif addr in self.wiki.storage:
            mime = page_mime(addr)
            if mime.startswith('image/'):
                return html.img(
                    src=self.get_ref_path(addr), class_=class_, alt=alt)
            else:
                return html.img(href=self.get_ref_path(addr), alt=alt)
        else:
            return html.a(html(alt), href=self.get_ref_path(addr))

    def wiki_link(self, addr, label=None, class_=None, image=None, lineno=0):
        addr = addr.strip()
        text = werkzeug.escape(label or addr)
        chunk = ''
        if class_ is not None:
            classes = [class_]
        else:
            classes = []
        if hatta.parser.external_link(addr):
            classes.append('external')
            if addr.startswith('mailto:'):
                # Obfuscate e-mails a little bit.
                classes.append('mail')
                text = text.replace('@', '&#64;').replace('.', '&#46;')
                href = werkzeug.escape(
                    addr, quote=True).replace('@', '%40').replace('.', '%2E')
            else:
                href = werkzeug.escape(werkzeug.url_fix(addr), quote=True)
        else:
            if '#' in addr:
                addr, chunk = addr.split('#', 1)
                chunk = '#' + werkzeug.url_fix(chunk)
            if addr.startswith(':'):
                alias = self._link_alias(addr[1:])
                href = werkzeug.escape(werkzeug.url_fix(alias) + chunk, True)
                classes.append('external')
                classes.append('alias')
            elif addr == u'':
                href = werkzeug.escape(chunk, True)
                classes.append('anchor')
            else:
                classes.append('wiki')
                href = werkzeug.escape(self.get_ref_path(addr) + chunk, True)
                if addr not in self.wiki.storage:
                    classes.append('nonexistent')
        class_ = werkzeug.escape(' '.join(classes) or '', True)
        # We need to output HTML on our own to prevent escaping of href
        return u'<a href="%s" class="%s" title="%s">%s</a>' % (
            href, class_, werkzeug.escape(addr + chunk, True), image or text)

    def wiki_math(self, math_text, display=False):
        # ape the 'mathjax' case in WikiPageWiki.wiki_math
        if display:
            return werkzeug.escape(u'$$\n%s\n$$' % math_text)
        return werkzeug.escape(u'$%s$' % math_text)


def scrub_html(html_string):
    """Strip unneeded attributes inserted by Hatta from some HTML source (e.g.
    classes, reference anchors with generic IDs, etc.)."""
    soup = bs4.BeautifulSoup(html_string, features="html.parser")
    # delete all classes
    for elem in soup.select("[class]"):
        del elem['class']
    # delete generic IDs (if the form line_32 etc.)
    for elem in soup.select("[id^='line_']"):
        del elem['id']
    # delete all <a name="head-*" /> anchors
    for elem in soup.select("a[name^='head-']"):
        if len(list(elem.children)) == 0:
            elem.decompose()
    return unicode(soup)


class WikiConverter:
    def __init__(self, wiki, file_prefix=None, strip_html_link_ext=False):
        self.wiki = wiki
        self.file_prefix = file_prefix
        self.strip_html_link_ext = strip_html_link_ext

    def is_raw(self, title):
        return page_mime(title) != 'text/x-wiki'

    def out_subpath(self, title, omit_html_ext=False):
        subpath = name_to_file(title)
        if self.file_prefix is not None and self.is_raw(title):
            subpath = os.path.join(self.file_prefix, subpath)
        if not self.is_raw(title) and not omit_html_ext:
            subpath += '.html'
        return subpath

    def render(self, title):
        lines = self.wiki.storage.page_text(title).splitlines(True)
        comp = CustomRenderComponents(self, title, self.strip_html_link_ext)
        # WikiWikiParser (which autolinks WikiWords) is unsupported for now,
        # but should be easy to add if ever needed
        parser = hatta.WikiParser(
            lines,
            wiki_link=comp.wiki_link,
            wiki_image=comp.wiki_image,
            wiki_math=comp.wiki_math,
            # no code highlighting since Pandoc HTML reader doesn't support it
            wiki_syntax=None)
        parser_output = parser.parse()
        # FIXME (probable Hatta bug): apparently the parser assumes no gaps
        # between output; for some reason it produces a different output block
        # for each character in a table cell. '\n'.join() won't work. (probable
        # sign of bug?)
        inner_html = ''.join(parser_output)
        html_template = """\
<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <title>%s</title>
    </head>
    <body>%s</body>
</html>"""
        outer_html = html_template % (title, inner_html)
        clean_html = scrub_html(outer_html)
        return clean_html


def convert_page(page_name,
                 wiki,
                 out_dir,
                 file_prefix=None,
                 strip_html_link_ext=False):
    converter = WikiConverter(
        wiki, file_prefix=file_prefix, strip_html_link_ext=strip_html_link_ext)

    # find & construct destination dir
    out_subpath = converter.out_subpath(page_name)
    out_path = os.path.join(out_dir, out_subpath)
    mkdir_p(os.path.dirname(out_path))

    if converter.is_raw(page_name):
        # copy files straight through
        page_data = wiki.storage.page_data(page_name)
        with open(out_path, 'wb') as out_fp:
            out_fp.write(page_data)
        coarse_type = 'file'
    else:
        # render pages & copy in rendered output
        page_html = converter.render(page_name)
        with open(out_path, 'wb') as out_fp:
            out_fp.write(page_html.encode('utf8'))
        coarse_type = 'page'

    # log progress
    mime_type = page_mime(page_name)
    print('%s (%s): %s -> %s' %
          (coarse_type, mime_type, page_name, out_subpath))


def main(args):
    hatta_config = hatta.WikiConfig()
    hatta_config.parse_files(files=[args.input_config])
    hatta_config.set('read_only', True)
    wiki = hatta.Wiki(hatta_config)
    # list of all page names
    page_names = list(wiki.storage.all_pages())
    mkdir_p(args.output_dir)
    print('Converting %d wiki entries' % len(page_names))
    for page_name in page_names:
        convert_page(
            page_name,
            wiki=wiki,
            out_dir=args.output_dir,
            file_prefix=args.file_prefix,
            strip_html_link_ext=args.strip_html_link_ext)
    print('Done!')


def _rewrap(text, **kwargs):
    unwrapped = ' '.join(text.splitlines())
    wrapped_lines = textwrap.wrap(text, **kwargs)
    wrapped = '\n'.join(wrapped_lines)
    return wrapped


parser = argparse.ArgumentParser(description=_rewrap(__doc__))
parser.add_argument(
    'input_config', help='path to INI configuration file defining wiki')
parser.add_argument(
    'output_dir', help='output directory to write .html files to')
parser.add_argument(
    '--file-prefix',
    default=None,
    help="move files (anything that\'s not a wiki page) into this "
    "subdirectory of output_dir")
parser.add_argument(
    '--strip-html-link-ext', action='store_true', default='false')

if __name__ == '__main__':
    main(parser.parse_args())
