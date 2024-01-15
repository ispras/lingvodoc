#!/usr/bin/python3
from hfst_dev import compile_xfst_file
import cgi
import cgitb
import shutil

STACK_FILENAME = 'rules.xfst.hfst'
DIR = '/var/www/cgi-bin/xal/'
TMP = '/var/www/tmp/'

cgitb.enable(format='text')
POST = cgi.FieldStorage()

print('Content-Type: text/html; charset=utf-8')
print('')

try:
	LF = POST['LEXC'].filename
	RF = POST['RULES'].filename
except:
	LF = ''
	RF = ''
if LF != '' and RF != '':
	LexcFile = open(TMP + POST['LEXC'].filename, 'wb')
	LexcFile.write(POST['LEXC'].file.read())
	LexcFile.flush()
	LexcFile.close()
	RulesFile = open(TMP + POST['RULES'].filename, 'wb')
	RulesFile.write(POST['RULES'].file.read())
	RulesFile.flush()
	RulesFile.close()
	RulesFile = open(TMP + POST['RULES'].filename, 'a+')
	RulesFile.write('\nsave stack ' + STACK_FILENAME)
	RulesFile.flush()
	RulesFile.close()
	shutil.copyfile(TMP + POST['LEXC'].filename, DIR + POST['LEXC'].filename)
	shutil.copyfile(TMP + POST['RULES'].filename, DIR + POST['RULES'].filename)
	compile_xfst_file(DIR + POST['RULES'].filename)
	print('XFST compiled!')
else:
	print('''
	<form method="post" enctype="multipart/form-data">
		<input type="file" name="LEXC"><br/>
		<input type="file" name="RULES"><br/>
		<input type="submit" value="COMPILE!">
	</form>
	''')
