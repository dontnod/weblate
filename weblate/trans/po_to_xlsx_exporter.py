# -*- coding: utf-8 -*-
#
# Copyright © 2012 - 2016 Michal Čihař <michal@cihar.com>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""Exporter using polib and openpyxl"""

import os
import re

from polib import *

from openpyxl import *
from openpyxl.styles import *
from openpyxl.utils import *

class PoToXlsxExporter(object):
    name = 'xlsx'
    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    extension = 'xlsx'

    def export(self, po_file):
        po_file_base, po_file_ext = os.path.splitext(po_file)
        xlsx_file = po_file_base + '.xlsx'
        po_data = pofile(po_file, wrapwidth=-1)
        wb = PoToXlsxExporter.build_workbook(po_data)
        wb.save(xlsx_file)
        return xlsx_file

    @staticmethod
    def build_workbook(po_data):
        wb, workbook_writing_instructions = PoToXlsxExporter.init_workbook(po_data)
        PoToXlsxExporter.fill_metadata(po_data, wb['metadata'], workbook_writing_instructions)
        i = 0
        for po_entry in po_data: 
            if not po_entry.obsolete:
                PoToXlsxExporter.add_po_entry(po_entry, wb['data'], i, workbook_writing_instructions)
                i += 1
        i = 0
        for po_entry in po_data.obsolete_entries(): 
            PoToXlsxExporter.add_po_entry(po_entry, wb['obsolete data'], i, workbook_writing_instructions)
            i += 1
        PoToXlsxExporter.finalize_workbook(wb)
        return wb

    @staticmethod
    def fill_metadata(po_data, ws, workbook_writing_instructions):
        i = workbook_writing_instructions[ws.title]['first_data_row']
        for name, value in po_data.ordered_metadata():
            ws.cell(row=i, column=1).value = name
            ws.cell(row=i, column=2).value = value
            i += 1

    @staticmethod
    def init_workbook(po_data):
        wb = Workbook()
        workbook_writing_instructions = {}
        # data sheet
        dws = wb.active
        dws.title = 'data'
        for po_entry in po_data: 
            if not po_entry.obsolete:
                workbook_writing_instructions[dws.title] = {}
                workbook_writing_instructions[dws.title]['first_data_row'] = 2
                workbook_writing_instructions[dws.title]['column_key'] = PoToXlsxExporter.write_header_row(dws, 1, po_entry)
                # assumes all entries are similar in terms of additional data
                break
        # metadata sheet
        hws = wb.create_sheet()
        hws.title = 'metadata'
        workbook_writing_instructions[hws.title] = {}
        workbook_writing_instructions[hws.title]['first_data_row'] = 1
        # obsolete data sheet (when applicable)
        for po_entry in po_data.obsolete_entries(): 
            ows = wb.create_sheet()
            ows.title = 'obsolete data'
            workbook_writing_instructions[ows.title] = {}
            workbook_writing_instructions[ows.title]['first_data_row'] = 2
            workbook_writing_instructions[ows.title]['column_key'] = PoToXlsxExporter.write_header_row(ows, 1, po_entry)
            # assumes all entries are similar in terms of additional data
            break
        return wb, workbook_writing_instructions

    @staticmethod
    def write_header_row_part(ws, i, j, column_key, prefix_for_column_key, headers):
        header_fill = PatternFill(fill_type='solid', fgColor = 'FFFFFF4D' if prefix_for_column_key == '' else 'FFB3B3FF')
        # different color for Regular data (classic po) vs. Additional data (DNE data, embedded in comment)
        for header in headers:
            ws.cell(row=i, column=j).value = header
            ws.cell(row=i, column=j).fill = header_fill
            if not column_key is None:
                column_key[prefix_for_column_key + header] = j
            j += 1
        return j

    @staticmethod
    def write_header_row(ws, i, po_entry):
        column_key = {}
        current_column = 1
        # Regular data (classic po): the important ones
        regular_important_columns = ['Source', 'Translation', 'Context'] # the Holy Trinity
        current_column = PoToXlsxExporter.write_header_row_part(ws, i, current_column, column_key, '', regular_important_columns)
        # Additional data (DNE data, embedded in comment)
        # (we consider that pretty important so show it before other classic po columns)
        dne_columns = list(PoToXlsxExporter.analyze_raw_comment(po_entry.comment).keys())
        dne_columns.sort()
        current_column = PoToXlsxExporter.write_header_row_part(ws, i, current_column, column_key, '[DNE]', dne_columns)
        # Regular data (classic po): the less important ones
        regular_less_important_columns = ['Occurrences', 'Flags', 'Translator Comment', 
                                          'Previous Source', 'Previous Context', 
                                          'Comment']
        # Comment (raw) is not considered important because it bears data that is not relevant 
        # for translation/recording ('key' unique id), or data repeated in occurrences, or
        # additional data visible as unique columns, etc. So we ditch it at the end
        current_column = PoToXlsxExporter.write_header_row_part(ws, i, current_column, column_key, '', regular_less_important_columns)
        # ignore_for_now  = ['Source Plural', 'Translation Plural', 'Previous Source Plural', 'Line Number']
        return column_key

    @staticmethod
    def analyze_raw_comment(comment):
        dict = {}
        # Empty additional data (trailing \t seems to kinda disappear at some point in that case, so...):
        p = re.compile(r'^\[AdditionalData\] (?P<key>[^:]*):$', re.MULTILINE)
        for m in re.finditer(p, comment):
            dict[m.group('key')] = None
        # Additional data with a value:
        p = re.compile(r'^\[AdditionalData\] (?P<key>[^:]*):\t(?P<value>[^\n]*)$', re.MULTILINE)
        for m in re.finditer(p, comment):
            dict[m.group('key')] = m.group('value')
        return dict

    @staticmethod
    def finalize_worksheet(ws):
        if ws.title == 'metadata':
            PoToXlsxExporter.finalize_metadata_worksheet(ws)
        else:
            PoToXlsxExporter.finalize_data_worksheet(ws)

    @staticmethod
    def finalize_data_worksheet(ws):
        # TODO: either get rid of workbook_writing_instructions's 'first_data_row' or use it here...
        header_font = Font(bold=True)
        for j in range(1, ws.max_column + 1):
            ws.cell(row=1, column=j).font = header_font
        ws.auto_filter.ref = "%s:%s" % (get_column_letter(1), get_column_letter(ws.max_column))
        ws.freeze_panes = ws['A2']

    @staticmethod
    def finalize_metadata_worksheet(ws):
        header_font = Font(bold=True)
        for i in range(1, ws.max_row + 1):
            ws.cell(row=i, column=1).font = header_font

    @staticmethod
    def finalize_workbook(wb):
        for ws in wb.worksheets:
            PoToXlsxExporter.finalize_worksheet(ws)

    @staticmethod
    def inject_value(prefix_for_column_key, key, value, ws, i, column_key):
        ws.cell(row=i, column=column_key[prefix_for_column_key + key]).value = value

    @staticmethod
    def add_po_entry(po_entry, ws, i, workbook_writing_instructions):
        def _format_comment(comment):
            return comment.replace('\t', '   ') 
            # as Excel does not like tabs in strings (removes/hides them) and they abound in big raw comments

        def _format_flags(flags):
            #return '\n'.join(str(flag) for flag in flags)
            return '\n'.join(flags)

        def _format_occurrence(fpath, lineno):
            if lineno:
                return '%s:%s' % (fpath, lineno)
            else:
                return fpath

        def _format_occurrences(occurrences):
            return '\n'.join(_format_occurrence(fpath, lineno) for fpath, lineno in occurrences)

        real_i = workbook_writing_instructions[ws.title]['first_data_row'] + i
        column_key = workbook_writing_instructions[ws.title]['column_key']
        PoToXlsxExporter.inject_value('', 'Source', po_entry.msgid, ws, real_i, column_key)
        PoToXlsxExporter.inject_value('', 'Translation', po_entry.msgstr, ws, real_i, column_key)
        PoToXlsxExporter.inject_value('', 'Context', po_entry.msgctxt, ws, real_i, column_key)
        PoToXlsxExporter.inject_value('', 'Comment', _format_comment(po_entry.comment), ws, real_i, column_key)
        PoToXlsxExporter.inject_value('', 'Translator Comment', po_entry.tcomment, ws, real_i, column_key)
        PoToXlsxExporter.inject_value('', 'Occurrences', _format_occurrences(po_entry.occurrences), ws, real_i, column_key)
        PoToXlsxExporter.inject_value('', 'Flags', _format_flags(po_entry.flags), ws, real_i, column_key)
        PoToXlsxExporter.inject_value('', 'Previous Source', po_entry.previous_msgid, ws, real_i, column_key)
        PoToXlsxExporter.inject_value('', 'Previous Context', po_entry.previous_msgctxt, ws, real_i, column_key)
        # Ignore for now
        # PoToXlsxExporter.inject_value('', 'Source Plural', po_entry.msgid_plural, ws, real_i, column_key)
        # PoToXlsxExporter.inject_value('', 'Translation Plural', po_entry.msgstr_plural, ws, real_i, column_key)
        # PoToXlsxExporter.inject_value('', 'Previous Source Plural', po_entry.previous_msgid_plural, ws, real_i, column_key)
        # PoToXlsxExporter.inject_value('', 'Line Number', po_entry.linenum, ws, real_i, column_key)
        for key, value in PoToXlsxExporter.analyze_raw_comment(po_entry.comment).items():
            PoToXlsxExporter.inject_value('[DNE]', key, value, ws, real_i, column_key)

def get_po_to_xlsx_exporter():
    return PoToXlsxExporter()
