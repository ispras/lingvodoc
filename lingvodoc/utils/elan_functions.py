import os

import pympi
from xml.etree import cElementTree as etree
import os
import re
import sys
import time
from lingvodoc.utils.search import eaf_words
import requests
import random
import string

from lingvodoc.schema.gql_holders import ResponseError
import sys
import os
import random
import string
import requests
import tempfile
from sqlalchemy.exc import IntegrityError
from lingvodoc.exceptions import CommonException
from lingvodoc.scripts.convert_rules import praat_to_elan


def eaf_wordlist(content):

    if len(content) > 50 * 1048576:

        raise KeyError('File too big')

    with tempfile.NamedTemporaryFile() as temp_file:

        temp_file.write(content)
        temp_file.flush()

        try:

            eaf_obj = (
                pympi.Eaf(file_path = temp_file.name))

            return eaf_words(eaf_obj)

        except:

            textgrid_obj = (
                pympi.TextGrid(file_path = temp_file.name))

            eaf_obj = (
                textgrid_obj.to_eaf())

            return eaf_words(eaf_obj)


def tgt_to_eaf(content, additional_metadata):
    from urllib import request
    try:
        try:
            fd, filename = tempfile.mkstemp()
            with open(filename, 'wb') as f:
                f.write(content)
            #if os.path.getsize(filename) / (10 * 1024 * 1024.0) < 2:
            if 'data_type' in additional_metadata :
                if 'praat' in additional_metadata['data_type']:
                    content = praat_to_elan(filename)
                    #if sys.getsizeof(content) / (10 * 1024 * 1024.0) < 2:
                        # filename2 = 'abc.xml'
                        # f2 = open(filename2, 'w')
                        # try:
                        #     f2.write(content)
                        #     f2.close()
                        #     # os.system('xmllint --noout --dtdvalid ' + filename2 + '> xmloutput 2>&1')
                        #     os.system('xmllint --dvalid ' + filename2 + '> xmloutput 2>&1')
                        # except:
                        #     print('fail with xmllint')
                        # finally:
                        #     pass
                        #     os.remove(filename2)
                    return content
                elif 'elan' in additional_metadata['data_type']:
                    with open(filename, 'r', encoding="utf8") as f:
                        return f.read()
                else:
                    raise KeyError("Not allowed convert option")
                raise KeyError('File too big')
            raise KeyError("Not allowed convert option")
            #raise KeyError('File too big')
        except Exception as e:
            raise ResponseError(message=str(e))
            #request.response.status = HTTPInternalServerError.code
            #return {'error': str(e)}
        finally:
            os.close(fd)
            os.remove(filename)
            pass
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}
