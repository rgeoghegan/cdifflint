import argparse
import sys
import signal

from cdiff import (
    PatchStream, markup_to_pager, revision_control_diff, revision_control_log,
    VCS_INFO
)


META_INFO = {
    'version': '1.0.0',
    'license': 'BSD-3',
    'author': 'Rory Geoghegan',
    'email': 'r.geoghegan(@)gmail(.)com',
    'url': 'https://github.com/rgeoghegan/cdifflint',
    'keywords': 'colored incremental side-by-side diff, with lint messagse',
    'description': 'View colored, incremental diff in a workspace, '
                    'annotated with messages from your favorite linter.',
}

LINTERS = {
    'pep8': {
        'regex': '(?P<filename>\S+):(?P<linenumber>\d+):\d+: (?P<msg>[^\n]+)\n?',
        'file_extensions': ['.py'],
    },
    'pyflakes': {
        'regex': '(?P<filename>\S+):(?P<linenumber>\d+): (?P<msg>[^\n]+)\n?',
        'file_extensions': ['.py'],
    },
    'jslint': {
        'regex': '(?P<filename>\S\+)\n #\d+ (?P<msg>[^\n]+)\n.*// Line'
            ' (?P<linenumber>\d\+), Pos (?P<position>\d\+)\n?',
        'file_extensions': ['.js'],
    }
}

def argparser():
    parser = argparse.ArgumentParser(
        description=META_INFO['description'],
        epilog="Note: Option parser will stop on first unknown option and "
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
        '-t', '--lint', action='append',
        help='run the given linters and show the lint messages in the diff. '
             'Currently supports {}. (Can be specified multiple '
             'times)'.format(",".join(LINTERS.keys())))

    return parser


class CDiffException(Exception):
    pass

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
            markup_to_pager(stream, args)
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
