from time import sleep
import re
import os, sys
import requests
import webbrowser
from html import unescape
from urllib.parse import quote
from pdb import set_trace as A

hostname = 'glosbe.com'

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Please set language name as an argument")
        exit(1)

    lang = sys.argv[1]
    #limit = 17500
    delta = 0.5
    suffix = 'fasmer'

    os.makedirs(lang, exist_ok=True)

    with open(f"russian_{suffix}.txt", 'r') as input_list, \
         open(f"{lang}/{lang}_{suffix}_absent.txt", 'a', 1) as input_absent, \
         open(f"{lang}/{lang}_{suffix}_done.txt", 'a+', 1) as input_done, \
         open(f"{lang}/{lang}_{suffix}_dict.txt", 'a', 1) as output_file:

        input_done.seek(0)
        lines_done = input_done.readlines()

        cur_line = lines_done[-1].strip() if lines_done else None
        count = len(lines_done) if lines_done else 0

        while cur_line and input_list.readline().strip() != cur_line:
            pass

        line = input_list.readline()  # first line

        while line:

            try:
                line = line.strip()

                if not line or line in lines_done:
                    line = input_list.readline()  # next line
                    continue

                url = f'https://{hostname}/ru/{lang}/{quote(line)}'
                response = requests.get(url, timeout=5).text

                result = None
                absent = None
                alarm = False
                human = 0

                while (
                    not (result := re.search("<strong>(.*)</strong> is the translation of", response)) and
                    not (result := re.search("<strong>(.*)</strong> are the top translations of", response)) and
                    not (result := re.search("<strong>(.*)</strong> — это перевод", response)) and
                    not (result := re.search("<strong>(.*)</strong> — самые популярные переводы слова", response)) and
                    not (absent := re.search("Currently we have no translations for", response)) and
                    not (absent := re.search("В настоящее время у нас нет переводов для", response)) and
                    response.find("Human test") > -1
                ):
                    if not human:
                        print(f"Human test happened on {count+1}'th step! Waiting...")

                    human += 1
                    if human > 10 and not alarm:
                        webbrowser.open("https://glosbe.com/ru/fi/%D0%B4%D0%B5%D1%80%D0%B5%D0%B2%D0%BE")
                        alarm = True

                    sleep(delta * 2)
                    
                    try:
                        response = requests.get(url, timeout=5).text

                    except:
                        response = "Human test"

            except:
                continue

            if result:
                words = unescape(result.group(1)).split(', ')
                entry = f"{words}: {line}"
                output_file.write(entry + '\n')
                print(f"{lang} {entry}")

            elif absent:
                input_absent.write(line + '\n')
                print(f"{lang} {line}: none")

            else:
                print("Not implemented case!")

            input_done.write(line + '\n')  # store current line
            line = input_list.readline()  # get next line
            count += 1
            sleep(delta)
