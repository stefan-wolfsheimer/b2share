# -*- coding: utf-8 -*-
#
# This file is part of EUDAT B2Share.
# Copyright (C) 2016 CERN, SurfsSara
#
# B2Share is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# B2Share is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with B2Share; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""B2Share demo command line interface."""

from __future__ import absolute_import, print_function

import logging
import os
from shutil import rmtree
import pathlib
from urllib.parse import urlunsplit
from shutil import copyfile

import click
from flask_cli import with_appcontext
from flask import current_app
from invenio_db import db
from invenio_files_rest.models import Location
from invenio_indexer.api import RecordIndexer

from .helpers import load_demo_data, download_v1_data, process_v1_record
from . import config as demo_config


@click.group(chain=True)
def demo():
    """Demonstration commands."""


@demo.command()
@with_appcontext
@click.option('-v', '--verbose', count=True)
def load_data(verbose):
    """Load demonstration data."""
    # add files location
    files_path = os.path.join(current_app.instance_path, 'files')
    if os.path.exists(files_path):
        rmtree(files_path)
    os.mkdir(files_path)
    with db.session.begin_nested():
        db.session.add(Location(name='local',
                                uri=pathlib.Path(files_path).as_uri(),
                                default=True))
        # load the demo
        load_demo_data(
            os.path.join(os.path.dirname(os.path.realpath(__file__)),
                         'data'),
            verbose=verbose)
    db.session.commit()


@demo.command()
@with_appcontext
@click.option('-v', '--verbose', count=True)
@click.option('-f', '--force', is_flag=True, default=False,
              help='Overwrite the current configuration if it exists.')
def load_config(verbose, force):
    """Copy the demo configuration to the application instance directory."""
    if verbose > 0:
        click.secho('Loading demo configuration.', fg='yellow', bold=True)
    instance_config_path = os.path.join(
        '{}'.format(current_app.instance_path),
        '{}.cfg'.format(current_app.name))
    if os.path.exists(instance_config_path):
        if not force:
            raise click.ClickException(
                'Application configuration file "{}" already exists. Use '
                'the -f option to overwrite it.'.format(
                    instance_config_path))
        elif verbose > 0:
            click.secho('Configuration file exists. Overriding it!',
                        fg='red', bold=True)
    demo_config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    copyfile(demo_config_path, instance_config_path)
    if verbose > 0:
        click.secho('Configuration file "{}" created.'.format(
            instance_config_path), fg='green')

@demo.command()
@with_appcontext
@click.option('-v', '--verbose', count=True)
@click.option('-d','--download', is_flag=True, default=False)
@click.option('-l','--limit', default=None)
@click.argument('token')
@click.argument('download_directory')
def import_v1_data(verbose, download, token,
         download_directory,limit):
    if verbose:
        click.secho("Importing data to the current instance")
        logger = logging.getLogger("sqlalchemy.engine")
        logger.setLevel(logging.ERROR)
    if os.path.isdir(download_directory):
        os.chdir(download_directory)
    else:
        raise click.ClickException("%s does not exist or is not a directory. If you want to import records specify an empty, existing directory." % download_directory)
    if limit and not download:
        raise click.ClickException("Limit can only be set with download")
    if download:
        filelist = os.listdir('.')
        if len(filelist)>0:
            raise click.ClickException("""You set download_dir to %s .
            If you want to download files, download_dir should be an empty
             directory.\n Please empty directory and try again.""" %
             download_directory)
        if verbose:
            click.secho("----------")
            click.secho("Downloading data into directory %s" %
                download_directory)
        if not(limit is None):
            limit = int(limit)
            click.secho("Limiting to %d records for debug purposes" % limit)
        download_v1_data(token, download_directory, limit, verbose)
    indexer = RecordIndexer(record_to_index=lambda record: ('records', 'record') )
    dirlist = os.listdir('.')
    if verbose:
        click.secho("-----------")
        click.secho("Processing %d downloaded records" %
                    (len(dirlist)))
    base_url = urlunsplit((
        current_app.config.get('PREFERRED_URL_SCHEME', 'http'),
        # current_app.config['SERVER_NAME'],
        current_app.config['JSONSCHEMAS_HOST'],
        current_app.config.get('APPLICATION_ROOT') or '', '', ''
    ))
    logfile = open(current_app.config.get('MIGRATION_LOGFILE'),'a')             
    for d in dirlist:
        process_v1_record(d, indexer, base_url, logfile, verbose)
    logfile.close()