from __future__ import unicode_literals

import argparse
from collections import OrderedDict
import os
import re
import signal
import subprocess
import sys

import six

from cdiff import (
    PatchStream, revision_control_diff, revision_control_log,
    VCS_INFO, DiffParser, DiffMarker, colorize
)


META_INFO = {
    'version': '1.0.0',
    'license': 'BSD-3',
    'author': 'Rory Geoghegan',
    'email': 'r.geoghegan(@)gmail(.)com',
    'url': 'https://github.com/rgeoghegan/cdifflint',
    'keywords': 'colored incremental side-by-side diff, with lint messages',
}

LINTERS = {
    'pep8': {
        'regex':
            '(?P<filename>\S+):(?P<linenumber>\d+):\d+: (?P<msg>[^\n]+)\n?',
        'file_extensions': ['.py'],
    },
    'pyflakes': {
        'regex': '(?P<filename>\S+):(?P<linenumber>\d+): (?P<msg>[^\n]+)\n?',
        'file_extensions': ['.py'],
    },
    'jslint': {
        'skip_lines': 2,
        'regex': ' #\d+ (?P<msg>[^\n]+)\n.*// Line'
            ' (?P<linenumber>\d+), Pos (?P<position>\d+)\n?',
        'file_extensions': ['.js'],
    }
}


def argparser():
    parser = argparse.ArgumentParser(
        description='View colored, incremental diff in a workspace, '
            'annotated with messages from your favorite linter.',
        epilog="Note: The option parser will stop on first unknown option and "
        "pass them down to underneath revision control"
    )

    parser.add_argument(
        '-s', '--side-by-side', action='store_true',
        help='enable side-by-side mode')
    parser.add_argument(
        '-w', '--width', type=int, default=80, metavar='N',
        help='set text width for side-by-side mode, 0 for auto detection, '
             'default is 80')
    parser.add_argument(
        '-l', '--log', action='store_true',
        help='show log with changes from revision control')
    parser.add_argument(
        '-c', '--color', default='auto', choices=('auto', 'always', 'never'),
        metavar='M',
        help="""colorize mode 'auto' (default), 'always', or 'never'""")
    parser.add_argument(
        '-t', '--lint', action='append', choices=LINTERS.keys(),
        help='run the given linters and show the lint messages in the diff. '
             'Currently supports {}. (Can be specified multiple '
             'times)'.format(", ".join(LINTERS.keys())))

    return parser


class CDiffException(Exception):
    pass


class LintMessage(object):
    def __init__(self, line, msg, end_line=None, tags=None):
        """
        A LintMessage is an individual instruction or message from the lint
        tool. The same line can have multiple LintMessages mapped to it.

            :param line: The start line matching the message
            :param msg: The message in question
            :param end_line: The end line for the message, if different
                from line.
            :param tags: Any tags or categorizations for the message.
        """
        self.line = line
        self.msg = msg
        self.end_line = end_line if end_line else line
        self.tags = tags

    def __str__(self):
        tags = u""
        if self.tags:
            tags = u" ({})".format(", ".join(self.tags))

        line = six.text_type(self.line)
        if self.end_line != self.line:
            line += "-" + six.text_type(self.end_line)

        return u"{}: {}{}".format(line, self.msg, tags)

    def __repr__(self):
        return u"<LintMessage: {}>".format(str(self))

    @classmethod
    def group_lint_messages(cls, messages):
        """
        Returns an OrderedDict of message line to a list of messages for
        that line. That list is ordered by end_line.
        """
        messages.sort(key=lambda x: (x.line, x.end_line))
        grouped = OrderedDict()
        for msg in messages:
            grouped.setdefault(msg.line, []).append(msg)

        return grouped


def parse_linter_output(linter, output):
    linter_details = LINTERS[linter]

    for n in range(linter_details.get('skip_lines', 0)):
        output = output[output.index('\n'):]

    regex = re.compile(LINTERS[linter]['regex'])
    for entry in regex.finditer(output):
        params = entry.groupdict()
        yield LintMessage(int(params['linenumber']), params['msg'])


def run_linter(linter, filepath):
    call = subprocess.Popen(
        [linter, filepath], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    text = call.stdout.read().decode('utf8')
    return list(parse_linter_output(linter, text))


def chain_linters(linter_names):
    """
    Given a sequence of linter_names (like the keys of LINTERS), returns a
    function that will returned an OrderedDict of lint messages
    keyed/ordered by line number.
    """
    def lint(filepath):
        lint_messages = {}
        for linter in linter_names:
            matches_linter_extension = any(
                filepath.endswith(n)
                for n in LINTERS[linter]['file_extensions']
            )
            if matches_linter_extension:
                for msg in run_linter(linter, filepath):
                    lint_messages.setdefault(msg.line, []).append(msg)

        return OrderedDict(sorted(lint_messages.items()))

    return lint


class DiffMarkerWithLint(DiffMarker):
    WRAP_CHAR = colorize('>', 'lightmagenta')
    COLOR_REGEX = re.compile(r'\\x1b\[\d{1,2}m')

    def __init__(self, width, linters):
        self.linter = chain_linters(linters)
        self.width = width

    def _markup_traditional(self, diff):
        """Returns a generator"""
        for line in diff._headers:
            yield self._markup_header(line)

        yield self._markup_old_path(diff._old_path)
        yield self._markup_new_path(diff._new_path)

        assert diff._new_path[:6] == '+++ b/'
        linting = self.linter(diff._new_path.strip('\n')[6:])
        lint_messages = 0

        for hunk in diff._hunks:
            for hunk_header in hunk._hunk_headers:
                yield self._markup_hunk_header(hunk_header)
            yield self._markup_hunk_meta(hunk._hunk_meta)
            for old, new, changed in hunk.mdiff():
                if changed:
                    if not old[0]:
                        # The '+' char after \x00 is kept
                        # DEBUG: yield 'NEW: %s %s\n' % (old, new)
                        line = new[1].strip('\x00\x01')
                        lint_message = linting.get(
                            self.hunk_line_number(hunk, new[0])
                        )
                        if lint_message:
                            lint_messages += 1

                        yield self._add_linting(
                            self._markup_new(line), lint_message
                        )
                    elif not new[0]:
                        # The '-' char after \x00 is kept
                        # DEBUG: yield 'OLD: %s %s\n' % (old, new)
                        line = old[1].strip('\x00\x01')
                        yield self._markup_old(line)
                    else:
                        # DEBUG: yield 'CHG: %s %s\n' % (old, new)
                        yield self._markup_old('-') + \
                            self._markup_mix(old[1], 'red')

                        lint_message = linting.get(
                            self.hunk_line_number(hunk, new[0])
                        )
                        if lint_message:
                            lint_messages += 1

                        yield self._add_linting(
                                self._markup_new('+') +
                                self._markup_mix(new[1], 'green'),
                                lint_message
                            )
                else:
                    lint_message = linting.get(
                        self.hunk_line_number(hunk, new[0])
                    )
                    if lint_message:
                        lint_messages += 1

                    yield self._add_linting(
                        self._markup_common(' ' + old[1]),
                        linting.get(self.hunk_line_number(hunk, new[0]))
                    )

        if lint_messages:
            yield self._markup_lint("{} Error(s)".format(lint_messages))

    def _add_linting(self, line, linting):
        if not linting:
            return line

        lint_text = self._markup_lint(", ".join(str(n) for n in linting))
        justified_line = self._justify(line)
        return "{} {}\n".format(justified_line, lint_text)

    def _markup_lint(self, text):
        return colorize(text, 'yellow')

    def _justify(self, line):
        """
        Given a diff line with shell color expressions (i.e. \\x1b[32m),
        justifies the visible part of the line to the proper width.
        """
        line = line.replace("\n", "")

        def text_parts():
            last_end = 0
            for match in self.COLOR_REGEX.finditer(line):
                if match.start() > last_end:
                    yield True, line[last_end:match.start()]
                yield False, line[match.start():match.end()]
                last_end = match.end()

            if last_end < len(line):
                yield True, line[last_end:]

        text_left = self.width - 1
        parts = []
        for is_visible, text in text_parts():
            if is_visible:
                if len(text) > text_left:
                    parts.append(text[:text_left - 1])
                    parts.append(self.WRAP_CHAR)
                    text_left = 0
                    break
                else:
                    parts.append(text)
                    text_left - len(text)
            else:
                parts.append(text)

        return "".join(parts) + " " * text_left

    def hunk_line_number(self, hunk, lineno):
        """
        Given a hunk diff and relative line number in the new diff, returns
        the file line number in the new file.
        """
        return hunk._new_addr[0] + lineno - 1


def markup_to_pager(stream, opts, marker):
    """Pipe unified diff stream to pager (less).

    Note: have to create pager Popen object before the translator Popen object
    in PatchStreamForwarder, otherwise the `stdin=subprocess.PIPE` would cause
    trouble to the translator pipe (select() never see EOF after input stream
    ended), most likely python bug 12607 (http://bugs.python.org/issue12607)
    which was fixed in python 2.7.3.

    See issue #30 (https://github.com/ymattw/cdiff/issues/30) for more
    information.
    """
    pager_cmd = ['less']
    if not os.getenv('LESS'):
        # Args stolen from git source: github.com/git/git/blob/master/pager.c
        pager_cmd.extend(['-FRSX', '--shift 1'])
    pager = subprocess.Popen(
        pager_cmd, stdin=subprocess.PIPE, stdout=sys.stdout)

    diffs = DiffParser(stream).get_diff_generator()
    color_diff = marker.markup(diffs, side_by_side=opts.side_by_side,
                               width=opts.width)

    for line in color_diff:
        pager.stdin.write(line.encode('utf-8'))

    pager.stdin.close()
    pager.wait()


def main():
    diff_hdl = None
    parser = argparser()

    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        args, extra = parser.parse_known_args()

        supported_vcs = sorted(VCS_INFO.keys())

        if args.log:
            diff_hdl = revision_control_log(extra)
        elif sys.stdin.isatty():
            diff_hdl = revision_control_diff(extra)
        else:
            diff_hdl = (sys.stdin.buffer if hasattr(sys.stdin, 'buffer')
                        else sys.stdin)

        if not diff_hdl:
            raise CDiffException(
                'Not in a supported workspace, supported are: {}'.format(
                    ', '.join(supported_vcs)
                )
            )

        stream = PatchStream(diff_hdl)

        # Don't let empty diff pass thru
        if stream.is_empty():
            return

        if args.color == 'always' or \
                (args.color == 'auto' and sys.stdout.isatty()):

            if args.lint:
                marker = DiffMarkerWithLint(args.width, args.lint)
            else:
                marker = DiffMarker()
            markup_to_pager(stream, args, marker)
        else:
            # pipe out stream untouched to make sure it is still a patch
            byte_output = (sys.stdout.buffer if hasattr(sys.stdout, 'buffer')
                           else sys.stdout)
            for line in stream:
                byte_output.write(line)

    except CDiffException as cde:
        sys.stderr.write("Error: {}\n".format(cde))
        if sys.stdin.isatty():
            parser.print_help()
        sys.exit(1)
    finally:
        if diff_hdl is not None and diff_hdl is not sys.stdin:
            diff_hdl.close()


if __name__ == '__main__':
    main()
