import os
import tgt

import pympi
from xml.etree import cElementTree as etree
import os
import re
import sys
import time

def to_eaf(file_path, eaf_obj, pretty=True):
    """
    modified function from https://github.com/dopefishh/pympi/blob/master/pympi/Elan.py
    Write an Eaf object to file.
    :param str file_path: Filepath to write to, - for stdout.
    :param pympi.Elan.Eaf eaf_obj: Object to write.
    :param bool pretty: Flag to set pretty printing.
    """
    def rm_none(x):
        try:  # Ugly hack to test if s is a string in py3 and py2
            basestring

            def isstr(s):
                return isinstance(s, basestring)
        except NameError:
            def isstr(s):
                return isinstance(s, str)
        return {k: v if isstr(v) else str(v) for k, v in x.items()
                if v is not None}
    # Annotation Document
    ADOCUMENT = etree.Element('ANNOTATION_DOCUMENT', eaf_obj.adocument)
    # Licence
    for m in eaf_obj.licenses:
        n = etree.SubElement(ADOCUMENT, 'LICENSE', {'LICENSE_URL': m[1]})
        n.text = m[0]
    # Header
    HEADER = etree.SubElement(ADOCUMENT, 'HEADER', eaf_obj.header)
    # Media descriptiors
    for m in eaf_obj.media_descriptors:
        etree.SubElement(HEADER, 'MEDIA_DESCRIPTOR', rm_none(m))
    # Linked file descriptors
    for m in eaf_obj.linked_file_descriptors:
        etree.SubElement(HEADER, 'LINKED_FILE_DESCRIPTOR', rm_none(m))
    # Properties
    for k, v in eaf_obj.properties:
        etree.SubElement(HEADER, 'PROPERTY', {'NAME': k}).text = str(v)
    # Time order
    TIME_ORDER = etree.SubElement(ADOCUMENT, 'TIME_ORDER')
    for t in sorted(eaf_obj.timeslots.items(), key=lambda x: int(x[0][2:])):
        etree.SubElement(TIME_ORDER, 'TIME_SLOT', rm_none(
            {'TIME_SLOT_ID': t[0], 'TIME_VALUE': t[1]}))
    # Tiers
    for t in sorted(eaf_obj.tiers.items(), key=lambda x: x[1][3]):
        tier = etree.SubElement(ADOCUMENT, 'TIER', rm_none(t[1][2]))
        for a in t[1][0].items():
            ann = etree.SubElement(tier, 'ANNOTATION')
            alan = etree.SubElement(ann, 'ALIGNABLE_ANNOTATION', rm_none(
                {'ANNOTATION_ID': a[0], 'TIME_SLOT_REF1': a[1][0],
                 'TIME_SLOT_REF2': a[1][1], 'SVG_REF': a[1][3]}))
            etree.SubElement(alan, 'ANNOTATION_VALUE').text = a[1][2]
        for a in t[1][1].items():
            ann = etree.SubElement(tier, 'ANNOTATION')
            rean = etree.SubElement(ann, 'REF_ANNOTATION', rm_none(
                {'ANNOTATION_ID': a[0], 'ANNOTATION_REF': a[1][0],
                 'PREVIOUS_ANNOTATION': a[1][2], 'SVG_REF': a[1][3]}))
            etree.SubElement(rean, 'ANNOTATION_VALUE').text = a[1][1]
    # Linguistic types
    for l in eaf_obj.linguistic_types.values():
        etree.SubElement(ADOCUMENT, 'LINGUISTIC_TYPE', rm_none(l))
    # Locales
    for lc, (cc, vr) in eaf_obj.locales.items():
        etree.SubElement(ADOCUMENT, 'LOCALE', rm_none(
            {'LANGUAGE_CODE': lc, 'COUNTRY_CODE': cc, 'VARIANT': vr}))
    # Languages
    for lid, (ldef, label) in eaf_obj.languages.items():
        etree.SubElement(ADOCUMENT, 'LANGUAGE', rm_none(
            {'LANG_ID': lid, 'LANG_DEF': ldef, 'LANG_LABEL': label}))
    # Constraints
    for l in eaf_obj.constraints.items():
        etree.SubElement(ADOCUMENT, 'CONSTRAINT', rm_none(
            {'STEREOTYPE': l[0], 'DESCRIPTION': l[1]}))
    # Controlled vocabularies
    for cvid, (descriptions, cv_entries, ext_ref) in\
            eaf_obj.controlled_vocabularies.items():
        cv = etree.SubElement(ADOCUMENT, 'CONTROLLED_VOCABULARY',
                              rm_none({'CV_ID': cvid, 'EXT_REF': ext_ref}))
        for lang_ref, description in descriptions:
            des = etree.SubElement(cv, 'DESCRIPTION', {'LANG_REF': lang_ref})
            if description:
                des.text = description
        for cveid, (values, ext_ref) in cv_entries.items():
            cem = etree.SubElement(cv, 'CV_ENTRY_ML', rm_none({
                'CVE_ID': cveid, 'EXT_REF': ext_ref}))
            for value, lang_ref, description in values:
                val = etree.SubElement(cem, 'CVE_VALUE', rm_none({
                    'LANG_REF': lang_ref, 'DESCRIPTION': description}))
                val.text = value
    # Lexicon refs
    for l in eaf_obj.lexicon_refs.values():
        etree.SubElement(ADOCUMENT, 'LEXICON_REF', rm_none(l))
    # Exteral refs
    for eid, (etype, value) in eaf_obj.external_refs.items():
        etree.SubElement(ADOCUMENT, 'EXTERNAL_REF', rm_none(
            {'EXT_REF_ID': eid, 'TYPE': etype, 'VALUE': value}))
    # https://github.com/dopefishh/pympi/blob/master/pympi/Elan.py

    return '<?xml version="1.0" encoding="UTF-8"?>'+etree.tostring(ADOCUMENT, encoding='utf-8').decode("utf-8")