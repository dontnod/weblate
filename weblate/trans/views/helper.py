# -*- coding: utf-8 -*-
#
# Copyright © 2012 - 2017 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Helper methods for views."""

import os
import zipfile
try:
    import zlib
    compression = zipfile.ZIP_DEFLATED
except:
    compression = zipfile.ZIP_STORED

from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
import django.utils.translation
from django.utils.translation import trans_real, ugettext as _

from weblate.utils import messages
from weblate.permissions.helpers import check_access
from weblate.trans.exporters import get_exporter
from weblate.trans.models import Project, SubProject, Translation


def get_translation(request, project, subproject, lang, skip_acl=False):
    """Return translation matching parameters."""
    translation = get_object_or_404(
        Translation.objects.prefetch(),
        language__code=lang,
        subproject__slug=subproject,
        subproject__project__slug=project,
        enabled=True
    )
    if not skip_acl:
        check_access(request, translation.subproject.project)
    return translation


def get_subproject(request, project, subproject, skip_acl=False):
    """Return subproject matching parameters."""
    subproject = get_object_or_404(
        SubProject.objects.prefetch(),
        project__slug=project,
        slug=subproject
    )
    if not skip_acl:
        check_access(request, subproject.project)
    return subproject


def get_project(request, project, skip_acl=False):
    """Return project matching parameters."""
    project = get_object_or_404(
        Project,
        slug=project,
    )
    if not skip_acl:
        check_access(request, project)
    return project


def get_project_translation(request, project=None, subproject=None, lang=None):
    """Return project, subproject, translation tuple for given parameters."""

    if lang is not None and subproject is not None:
        # Language defined? We can get all
        translation = get_translation(request, project, subproject, lang)
        subproject = translation.subproject
        project = subproject.project
    else:
        translation = None
        if subproject is not None:
            # Component defined?
            subproject = get_subproject(request, project, subproject)
            project = subproject.project
        elif project is not None:
            # Only project defined?
            project = get_project(request, project)

    # Return tuple
    return project, subproject, translation


def try_set_language(lang):
    """Try to activate language"""

    try:
        django.utils.translation.activate(lang)
        # workaround for https://code.djangoproject.com/ticket/26050
        # pylint: disable=W0212
        if trans_real.catalog()._catalog is None:
            raise Exception('Invalid language!')
    except Exception:
        # Ignore failure on activating language
        django.utils.translation.activate('en')


def import_message(request, count, message_none, message_ok):
    if count == 0:
        messages.warning(request, message_none)
    else:
        messages.success(request, message_ok % count)


def download_translation_file(translation, fmt=None):
    data_name, content_type, data = get_translation_file_data(translation, fmt)

    response = HttpResponse(
        data,
        content_type=content_type
    )
    response['Content-Disposition'] = 'attachment; filename={0}'.format(
        data_name
    )

    return response

def get_translation_file_data(translation, fmt=None):
    # It's ugly as hell, but for now I'll handle "Download as Excel workbook" 
    # very differently from the other (translate-toolkit-based) exports
    if fmt == 'xlsx':
        if translation.store.extension != 'po':
            raise Http404('Download as Excel workbook is only available when original file is a Gettext PO file!')
    if fmt is not None:
        try:
            if fmt == 'xlsx':
                exporter = get_exporter(fmt)()
            else:
                exporter = get_exporter(fmt)(translation=translation)
        except KeyError:
            raise Http404('File format not supported')
        if fmt != 'xlsx':
            exporter.add_units(translation)
            return (exporter.get_response_filename('{{project}}-{0}-{{language}}.{{extension}}'.format(translation.subproject.slug)), 
                    exporter.get_content_type(),
                    exporter.serialize())

    srcfilename = translation.get_filename()

    if fmt == 'xlsx':
        originalsrcfilename = srcfilename
        srcfilename = exporter.export(originalsrcfilename, translation.get_last_local_commit(commit_pending=True))

    with open(srcfilename) as handle:
        data = handle.read()

    if fmt == 'xlsx':
        os.remove(srcfilename)

    data_name = '{0}-{1}-{2}.{3}'.format(
        translation.subproject.project.slug,
        translation.subproject.slug,
        translation.language.code,
        'xlsx' if fmt == 'xlsx' else translation.store.extension 
    )

    content_type = exporter.content_type if fmt == 'xlsx' else translation.store.mimetype

    return (data_name, content_type, data)


def show_form_errors(request, form):
    """Show all form errors as a message."""
    for error in form.non_field_errors():
        messages.error(request, error)
    for field in form:
        for error in field.errors:
            messages.error(
                request,
                _('Error in parameter %(field)s: %(error)s') % {
                    'field': field.name,
                    'error': error
                }
            )

def download_translations_file(translations, fmt=None, level='subproject'):
    
    if fmt == 'singlexlsx':
        data_name, content_type, data = get_translations_as_single_xlsx_file_data(translations)
    else:
        if level=='project':
            zipfilename = '{0}-all.zip'.format(translations[0].subproject.project.slug)
        elif level=='project_lang':
            zipfilename = '{0}-{1}-all.zip'.format(translations[0].subproject.project.slug, translations[0].language.code)
        elif level=='subproject':
            zipfilename = '{0}-{1}-all.zip'.format(translations[0].subproject.project.slug, translations[0].subproject.slug)
        abs_zipfilename = os.path.join(translations[0].subproject.get_path(), zipfilename)
        zf = zipfile.ZipFile(abs_zipfilename, mode='w', compression=compression)
        
        try:
            for translation in translations:
                data_name, _, data = get_translation_file_data(translation, fmt)
                zf.writestr(data_name, data)
        finally:
            zf.close()
        
        with open(abs_zipfilename) as handle:
            data = handle.read()

        os.remove(abs_zipfilename)

        data_name = zipfilename
        content_type = 'application/zip'

    response = HttpResponse(
        data,
        content_type=content_type
    )
    response['Content-Disposition'] = 'attachment; filename={0}'.format(
        data_name
    )

    return response

def get_translations_as_single_xlsx_file_data(translations):
    for translation in translations:
        subproject = translation.subproject 
        # should be the same for all translations!
        break

    for translation in translations:
        if translation.store.extension != 'po':
            raise Http404('Download as Excel workbook is only available when original file is a Gettext PO file!')
    exporter = get_exporter('xlsx')()

    originalsrcfilenames = []
    for translation in translations:
        originalsrcfilenames.append(translation.get_filename())

    srcfilename = exporter.export_multiple(originalsrcfilenames, subproject.get_last_local_commit(commit_pending=True))

    # Construct file name (do not use real filename as it is usually not
    # that useful)
    filename = '{0}-{1}-all.xlsx'.format(
        translation.subproject.project.slug,
        translation.subproject.slug
    )

    # Create response
    with open(srcfilename) as handle:
        data = handle.read(),

    os.remove(srcfilename)

    return (filename, exporter.content_type, data)
