cdifflint
=========

Term based tool to view *colored*, *incremental* diff in a *Git/Mercurial/Svn*
workspace or from stdin, side by side with affected linting errors. Requires
python (>= 2.7.0) and ``less``.

Installation
------------

Install with pip
~~~~~~~~~~~~~~~~

Cdifflint is already listed on `PyPI`_, you can install with ``pip`` if
you have the tool.

.. _PyPI: http://pypi.python.org/pypi/cdifflint

.. code-block:: bash

    pip install --upgrade cdifflint

Install with setup.py
~~~~~~~~~~~~~~~~~~~~~

You can also run the setup.py from the source if you don't have ``pip``.

.. code-block:: bash

    git clone https://github.com/rgeoghegan/cdifflint.git
    cd cdifflint
    ./setup.py install

Usage
-----

Type ``cdifflint -h`` to show usage::

    $ cdifflint -h
    usage: cdifflint [-h] [-s] [-w N] [-l] [-c M] [-t {pep8,jslint,pyflakes}]

    View colored, incremental diff in a workspace, annotated with messages from
    your favorite linter.

    optional arguments:
      -h, --help            show this help message and exit
      -s, --side-by-side    enable side-by-side mode
      -w N, --width N       set text width for side-by-side mode, 0 for auto
                            detection, default is 80
      -l, --log             show log with changes from revision control
      -c M, --color M       colorize mode 'auto' (default), 'always', or 'never'
      -t {pep8,jslint,pyflakes}, --lint {pep8,jslint,pyflakes}
                            run the given linters and show the lint messages in
                            the diff. Currently supports pep8, jslint, pyflakes.
                            (Can be specified multiple times)

    Note: Option parser will stop on first unknown option and pass them down to
    underneath revision control

See also
--------

The original code I cribbed from heavily is the `cdiff`_ tool, which does most
of the heavy lifting.

.. _cdiff: https://github.com/ymattw/cdiff

.. vim:set ft=rst et sw=4 sts=4 tw=79:
