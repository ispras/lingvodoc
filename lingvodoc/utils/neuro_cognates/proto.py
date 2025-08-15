import pandas as pd

# датафрейм всех соответсвий из файла
df = pd.DataFrame([

    # ————— Proto *t- —————
    # Финский: t или sI
    {"language": "фин", "proto": "*t-", "reflex": "t", "prob": None},
    {"language": "фин", "proto": "*t-", "reflex": "sI", "prob": None},

    # Саамский: t или d
    {"language": "саам", "proto": "*t-", "reflex": "t", "prob": None},
    {"language": "саам", "proto": "*t-", "reflex": "d", "prob": None},

    # Мордва: t
    {"language": "морд", "proto": "*t-", "reflex": "t", "prob": None},

    # Марий: t
    {"language": "мар", "proto": "*t-", "reflex": "t", "prob": None},

    # Коми: t или d
    {"language": "коми", "proto": "*t-", "reflex": "t", "prob": None},
    {"language": "коми", "proto": "*t-", "reflex": "d", "prob": None},

    # Удмурт: t или d
    {"language": "удм", "proto": "*t-", "reflex": "t", "prob": None},
    {"language": "удм", "proto": "*t-", "reflex": "d", "prob": None},

    # Ханты: t
    {"language": "хант", "proto": "*t-", "reflex": "t", "prob": None},

    # Мансий: t
    {"language": "манс", "proto": "*t-", "reflex": "t", "prob": None},

    # Венгерский: t
    {"language": "венг", "proto": "*t-", "reflex": "t", "prob": None},

    # ————— Proto *-t- —————
    # Финский: t или si
    {"language": "фин", "proto": "*-t-", "reflex": "t", "prob": None},
    {"language": "фин", "proto": "*-t-", "reflex": "si", "prob": None},

    # Саамский: t, tt или đ
    {"language": "саам", "proto": "*-t-", "reflex": "t", "prob": None},
    {"language": "саам", "proto": "*-t-", "reflex": "tt", "prob": None},
    {"language": "саам", "proto": "*-t-", "reflex": "đ", "prob": None},

    # Мордва: d
    {"language": "морд", "proto": "*-t-", "reflex": "d", "prob": None},

    # Марий: δV/t# и δ
    {"language": "мар", "proto": "*-t-", "reflex": "δV/t#", "prob": None},
    {"language": "мар", "proto": "*-t-", "reflex": "δ", "prob": None},

    # Коми: 0 (нулевой)
    {"language": "коми", "proto": "*-t-", "reflex": "0", "prob": None},

    # Удмурт: 0 (нулевой)
    {"language": "удм", "proto": "*-t-", "reflex": "0", "prob": None},

    # Ханты: t
    {"language": "хант", "proto": "*-t-", "reflex": "t", "prob": None},

    # Мансий: t
    {"language": "манс", "proto": "*-t-", "reflex": "t", "prob": None},

    # Венгерский: z
    {"language": "венг", "proto": "*-t-", "reflex": "z", "prob": None},

    # ————— Proto *-tt- —————
    # Финский: tt, si или t
    {"language": "фин", "proto": "*-tt-", "reflex": "tt", "prob": None},
    {"language": "фин", "proto": "*-tt-", "reflex": "si", "prob": None},
    {"language": "фин", "proto": "*-tt-", "reflex": "t", "prob": None},

    # Саамский: tt или t’t
    {"language": "саам", "proto": "*-tt-", "reflex": "tt", "prob": None},
    {"language": "саам", "proto": "*-tt-", "reflex": "t’t", "prob": None},

    # Мордва: t
    {"language": "морд", "proto": "*-tt-", "reflex": "t", "prob": None},

    # Марий: t
    {"language": "мар", "proto": "*-tt-", "reflex": "t", "prob": None},

    # Коми: t
    {"language": "коми", "proto": "*-tt-", "reflex": "t", "prob": None},

    # Удмурт: t
    {"language": "удм", "proto": "*-tt-", "reflex": "t", "prob": None},

    # Ханты: t
    {"language": "хант", "proto": "*-tt-", "reflex": "t", "prob": None},

    # Мансий: t
    {"language": "манс", "proto": "*-tt-", "reflex": "t", "prob": None},

    # Венгерский: t
    {"language": "венг", "proto": "*-tt-", "reflex": "t", "prob": None},

    # ————— Proto *p- —————
    # По Иллич‑Свитычу 1971 и Sammallahti/Bereczki
    {"language": "фин", "proto": "*p-", "reflex": "p", "prob": 1.0},
    {"language": "саам", "proto": "*p-", "reflex": "p", "prob": 1.0},
    {"language": "морд", "proto": "*p-", "reflex": "p", "prob": 1.0},
    {"language": "мар", "proto": "*p-", "reflex": "p", "prob": 1.0},
    {"language": "коми", "proto": "*p-", "reflex": "p", "prob": None},
    {"language": "коми", "proto": "*p-", "reflex": "b", "prob": None},
    {"language": "удм", "proto": "*p-", "reflex": "p", "prob": None},
    {"language": "удм", "proto": "*p-", "reflex": "b", "prob": None},
    {"language": "хант", "proto": "*p-", "reflex": "p", "prob": 1.0},
    {"language": "манс", "proto": "*p-", "reflex": "p", "prob": 1.0},
    {"language": "венг", "proto": "*p-", "reflex": "f", "prob": 1.0},

    # ————— Proto *-p- —————
    # Из всех трёх источников
    {"language": "фин", "proto": "*-p-", "reflex": "p", "prob": None},
    {"language": "фин", "proto": "*-p-", "reflex": "v", "prob": None},
    {"language": "саам", "proto": "*-p-", "reflex": "p", "prob": None},
    {"language": "саам", "proto": "*-p-", "reflex": "d", "prob": None},
    {"language": "саам", "proto": "*-p-", "reflex": "pp", "prob": None},  # из Sammallahti
    {"language": "морд", "proto": "*-p-", "reflex": "v", "prob": None},
    {"language": "мар", "proto": "*-p-", "reflex": "w", "prob": None},
    {"language": "коми", "proto": "*-p-", "reflex": "0", "prob": None},
    {"language": "удм", "proto": "*-p-", "reflex": "0", "prob": None},
    {"language": "хант", "proto": "*-p-", "reflex": "p", "prob": None},
    {"language": "манс", "proto": "*-p-", "reflex": "p", "prob": None},
    {"language": "венг", "proto": "*-p-", "reflex": "v", "prob": None},
    {"language": "венг", "proto": "*-p-", "reflex": "w", "prob": None},  # из Sammallahti

    # ————— Proto *-pp- —————
    # Счёты из первой таблицы (pp:6, w:5 → total=11)
    {"language": "фин", "proto": "*-pp-", "reflex": "pp", "prob": 6 / 11},
    {"language": "фин", "proto": "*-pp-", "reflex": "w", "prob": 5 / 11},
    {"language": "саам", "proto": "*-pp-", "reflex": "si", "prob": None},
    {"language": "морд", "proto": "*-pp-", "reflex": "tt", "prob": None},
    {"language": "мар", "proto": "*-pp-", "reflex": "t", "prob": None},
    {"language": "коми", "proto": "*-pp-", "reflex": "t", "prob": None},
    {"language": "удм", "proto": "*-pp-", "reflex": "t", "prob": None},
    {"language": "хант", "proto": "*-pp-", "reflex": "p", "prob": None},  # из Sammallahti
    {"language": "манс", "proto": "*-pp-", "reflex": "p", "prob": None},
    {"language": "венг", "proto": "*-pp-", "reflex": "p", "prob": None},
    # ————— Proto *č- —————
    # (Иллич‑Свитыч 1971, первая таблица)
    {"language": "фин", "proto": "*č-", "reflex": "h", "prob": 1.0},
    {"language": "саам", "proto": "*č-", "reflex": "c", "prob": 1.0},
    {"language": "морд", "proto": "*č-", "reflex": "č", "prob": 1.0},
    {"language": "мар", "proto": "*č-", "reflex": "š", "prob": 1.0},
    # Коми: č – 3, ǯ – 4 → total = 7
    {"language": "коми", "proto": "*č-", "reflex": "č", "prob": 3 / 7},
    {"language": "коми", "proto": "*č-", "reflex": "ǯ", "prob": 4 / 7},
    # Удмурт: č – 5, ǯ – 3 → total = 8
    {"language": "удм", "proto": "*č-", "reflex": "č", "prob": 5 / 8},
    {"language": "удм", "proto": "*č-", "reflex": "ǯ", "prob": 3 / 8},
    {"language": "хант", "proto": "*č-", "reflex": "č", "prob": 1.0},
    {"language": "манс", "proto": "*č-", "reflex": "s", "prob": 1.0},
    {"language": "венг", "proto": "*č-", "reflex": "s", "prob": 1.0},

    # ————— Proto *-č- —————
    # (агрегация всех таблиц — никаких количественных данных)
    {"language": "фин", "proto": "*-č-", "reflex": "t", "prob": None},
    {"language": "фин", "proto": "*-č-", "reflex": "d", "prob": None},
    {"language": "саам", "proto": "*-č-", "reflex": "t", "prob": None},
    {"language": "саам", "proto": "*-č-", "reflex": "d", "prob": None},
    {"language": "морд", "proto": "*-č-", "reflex": "d", "prob": None},
    {"language": "мар", "proto": "*-č-", "reflex": "δ", "prob": None},
    {"language": "коми", "proto": "*-č-", "reflex": "0", "prob": None},
    {"language": "удм", "proto": "*-č-", "reflex": "0", "prob": None},
    {"language": "хант", "proto": "*-č-", "reflex": "t", "prob": None},
    {"language": "манс", "proto": "*-č-", "reflex": "t", "prob": None},
    {"language": "венг", "proto": "*-č-", "reflex": "z", "prob": None},

    # ————— Proto *-čč- —————
    # (агрегация всех таблиц — никаких количественных данных)
    {"language": "фин", "proto": "*-čč-", "reflex": "t", "prob": None},
    {"language": "фин", "proto": "*-čč-", "reflex": "d", "prob": None},
    {"language": "фин", "proto": "*-čč-", "reflex": "h", "prob": None},
    {"language": "саам", "proto": "*-čč-", "reflex": "c’c", "prob": None},
    {"language": "саам", "proto": "*-čč-", "reflex": "cc", "prob": None},
    {"language": "морд", "proto": "*-čč-", "reflex": "č", "prob": None},
    {"language": "морд", "proto": "*-čč-", "reflex": "š", "prob": None},
    {"language": "морд", "proto": "*-čč-", "reflex": "ž", "prob": None},
    {"language": "мар", "proto": "*-čč-", "reflex": "č", "prob": None},
    {"language": "мар", "proto": "*-čč-", "reflex": "š", "prob": None},
    {"language": "коми", "proto": "*-čč-", "reflex": "č", "prob": None},
    {"language": "коми", "proto": "*-čč-", "reflex": "š", "prob": None},
    {"language": "коми", "proto": "*-čč-", "reflex": "ǯ", "prob": None},
    {"language": "коми", "proto": "*-čč-", "reflex": "ž", "prob": None},
    {"language": "удм", "proto": "*-čč-", "reflex": "č", "prob": None},
    {"language": "удм", "proto": "*-čč-", "reflex": "š", "prob": None},
    {"language": "удм", "proto": "*-čč-", "reflex": "ǯ", "prob": None},
    {"language": "удм", "proto": "*-čč-", "reflex": "ž", "prob": None},
    {"language": "хант", "proto": "*-čč-", "reflex": "č", "prob": None},
    {"language": "хант", "proto": "*-čč-", "reflex": "š", "prob": None},
    {"language": "манс", "proto": "*-čč-", "reflex": "č", "prob": None},
    {"language": "манс", "proto": "*-čč-", "reflex": "š", "prob": None},
    {"language": "венг", "proto": "*-čč-", "reflex": "s", "prob": None},
    # ————— Proto *ć- —————
    # Финский: s
    {"language": "фин", "proto": "*ć-", "reflex": "s", "prob": 1.0},

    # Саамский: č
    {"language": "саам", "proto": "*ć-", "reflex": "č", "prob": 1.0},

    # Мордва: ć
    {"language": "морд", "proto": "*ć-", "reflex": "ć", "prob": 1.0},

    # Марий: ć
    {"language": "мар", "proto": "*ć-", "reflex": "ć", "prob": 1.0},

    # Коми: c (4 случаев → prob = 1.0, других вариантов нет)
    {"language": "коми", "proto": "*ć-", "reflex": "c", "prob": 1.0},

    # Удмурт: ć
    {"language": "удм", "proto": "*ć-", "reflex": "ć", "prob": 1.0},

    # Ханты: (неоднозначно отмечено как *ć; без чисел)
    {"language": "хант", "proto": "*ć-", "reflex": "ć", "prob": None},

    # Мансий: cs (16 случаев → prob = 1.0)
    {"language": "манс", "proto": "*ć-", "reflex": "cs", "prob": 1.0},

    # Венгерский: (приведено как *ć без уточнения)
    {"language": "венг", "proto": "*ć-", "reflex": "ć", "prob": None},

    # ————— Proto *-ć- —————
    # Финский: s
    {"language": "фин", "proto": "*-ć-", "reflex": "s", "prob": 1.0},

    # Саамский: č
    {"language": "саам", "proto": "*-ć-", "reflex": "č", "prob": 1.0},

    # Мордва: ć
    {"language": "морд", "proto": "*-ć-", "reflex": "ć", "prob": 1.0},

    # Марий: z (5 случаев → prob = 1.0)
    {"language": "мар", "proto": "*-ć-", "reflex": "z", "prob": 1.0},

    # Коми: ć (без счётов)
    {"language": "коми", "proto": "*-ć-", "reflex": "ć", "prob": None},

    # Удмурт: ʒ́ (ǯ́) (без счётов)
    {"language": "удм", "proto": "*-ć-", "reflex": "ʒ́", "prob": None},

    # Ханты: ć (без счётов)
    {"language": "хант", "proto": "*-ć-", "reflex": "ć", "prob": None},

    # Мансий: cs (4 случаев → prob = 1.0)
    {"language": "манс", "proto": "*-ć-", "reflex": "cs", "prob": 1.0},

    # Венгерский: (без уточнения)
    {"language": "венг", "proto": "*-ć-", "reflex": "ć", "prob": None},

    # ————— Proto *-ćć- —————
    # Финский: (преобразуется в cì ~ с)
    {"language": "фин", "proto": "*-ćć-", "reflex": "cì", "prob": None},
    {"language": "фин", "proto": "*-ćć-", "reflex": "s", "prob": None},

    # Саамский: č̣ ~ č ~ с́ ~ с
    {"language": "саам", "proto": "*-ćć-", "reflex": "č̣", "prob": None},
    {"language": "саам", "proto": "*-ćć-", "reflex": "č", "prob": None},
    {"language": "саам", "proto": "*-ćć-", "reflex": "ś", "prob": None},
    {"language": "саам", "proto": "*-ćć-", "reflex": "s", "prob": None},

    # Мордва: s ~ ś
    {"language": "морд", "proto": "*-ćć-", "reflex": "s", "prob": None},
    {"language": "морд", "proto": "*-ćć-", "reflex": "ś", "prob": None},

    # Марий: š
    {"language": "мар", "proto": "*-ćć-", "reflex": "š", "prob": None},

    # Коми: cì ~ с
    {"language": "коми", "proto": "*-ćć-", "reflex": "cì", "prob": None},
    {"language": "коми", "proto": "*-ćć-", "reflex": "s", "prob": None},

    # Удмурт: cs > s, sz
    {"language": "удм", "proto": "*-ćć-", "reflex": "cs", "prob": None},
    {"language": "удм", "proto": "*-ćć-", "reflex": "sz", "prob": None},

    # Ханты: сì
    {"language": "хант", "proto": "*-ćć-", "reflex": "сì", "prob": None},

    # Мансий: сì
    {"language": "манс", "proto": "*-ćć-", "reflex": "сì", "prob": None},

    # Венгерский: (не указано)
    {"language": "венг", "proto": "*-ćć-", "reflex": None, "prob": None},
    # ————— Proto *ś- —————
    # Финский: всегда s
    {"language": "фин", "proto": "*ś-", "reflex": "s", "prob": 1.0},

    # Саамский: всегда č
    {"language": "саам", "proto": "*ś-", "reflex": "č", "prob": 1.0},

    # Мордва: всегда ś
    {"language": "морд", "proto": "*ś-", "reflex": "ś", "prob": 1.0},

    # Марий: всегда š
    {"language": "мар", "proto": "*ś-", "reflex": "š", "prob": 1.0},

    # Коми: s и š
    {"language": "коми", "proto": "*ś-", "reflex": "s", "prob": None},
    {"language": "коми", "proto": "*ś-", "reflex": "š", "prob": None},

    # Удмурт: всегда ś
    {"language": "удм", "proto": "*ś-", "reflex": "ś", "prob": 1.0},

    # Ханты: всегда s
    {"language": "хант", "proto": "*ś-", "reflex": "s", "prob": 1.0},

    # Мансий: обычно sz
    {"language": "манс", "proto": "*ś-", "reflex": "sz", "prob": 1.0},

    # Венгерский: всегда ś
    {"language": "венг", "proto": "*ś-", "reflex": "ś", "prob": 1.0},

    # ————— Proto *-ś- —————
    # Финский: всегда s
    {"language": "фин", "proto": "*-ś-", "reflex": "s", "prob": 1.0},

    # Саамский: s и z
    {"language": "саам", "proto": "*-ś-", "reflex": "s", "prob": None},
    {"language": "саам", "proto": "*-ś-", "reflex": "z", "prob": None},

    # Мордва: всегда ź
    {"language": "морд", "proto": "*-ś-", "reflex": "ź", "prob": 1.0},

    # Марий: всегда ž
    {"language": "мар", "proto": "*-ś-", "reflex": "ž", "prob": 1.0},

    # Коми: всегда ś
    {"language": "коми", "proto": "*-ś-", "reflex": "ś", "prob": 1.0},

    # Удмурт: всегда ś
    {"language": "удм", "proto": "*-ś-", "reflex": "ś", "prob": 1.0},

    # Ханты: всегда s
    {"language": "хант", "proto": "*-ś-", "reflex": "s", "prob": 1.0},

    # Мансий: всегда sz
    {"language": "манс", "proto": "*-ś-", "reflex": "sz", "prob": 1.0},

    # Венгерский: всегда sz
    {"language": "венг", "proto": "*-ś-", "reflex": "sz", "prob": 1.0},
    # ————— Proto *š- —————
    {"language": "фин", "proto": "*š-", "reflex": "h", "prob": None},
    {"language": "саам", "proto": "*š-", "reflex": "s", "prob": None},
    {"language": "морд", "proto": "*š-", "reflex": "č", "prob": None},
    {"language": "морд", "proto": "*š-", "reflex": "š", "prob": None},
    {"language": "мар", "proto": "*š-", "reflex": "š", "prob": None},
    {"language": "коми", "proto": "*š-", "reflex": "š", "prob": None},
    {"language": "удм", "proto": "*š-", "reflex": "š", "prob": None},
    {"language": "хант", "proto": "*š-", "reflex": "θ", "prob": None},
    {"language": "манс", "proto": "*š-", "reflex": "θ", "prob": None},
    {"language": "венг", "proto": "*š-", "reflex": "0", "prob": None},

    # ————— Proto *-š- —————
    {"language": "фин", "proto": "*-š-", "reflex": "h", "prob": None},
    {"language": "саам", "proto": "*-š-", "reflex": "ss", "prob": None},
    {"language": "морд", "proto": "*-š-", "reflex": "ž", "prob": None},
    {"language": "мар", "proto": "*-š-", "reflex": "ž", "prob": None},
    {"language": "коми", "proto": "*-š-", "reflex": "ž", "prob": None},
    {"language": "удм", "proto": "*-š-", "reflex": "š", "prob": None},
    {"language": "хант", "proto": "*-š-", "reflex": "θ", "prob": None},
    {"language": "манс", "proto": "*-š-", "reflex": "θ", "prob": None},
    {"language": "венг", "proto": "*-š-", "reflex": "θ", "prob": None},
    # ————— Proto *s- —————
    # Финский: всегда s
    {"language": "фин", "proto": "*s-", "reflex": "s", "prob": 1.0},

    # Саамский: s
    {"language": "саам", "proto": "*s-", "reflex": "s", "prob": 1.0},

    # Мордва: s
    {"language": "морд", "proto": "*s-", "reflex": "s", "prob": 1.0},

    # Марий: s или ś
    {"language": "мар", "proto": "*s-", "reflex": "s", "prob": None},
    {"language": "мар", "proto": "*s-", "reflex": "ś", "prob": None},

    # Коми: š или s
    {"language": "коми", "proto": "*s-", "reflex": "š", "prob": None},
    {"language": "коми", "proto": "*s-", "reflex": "s", "prob": None},

    # Удмурт: всегда s
    {"language": "удм", "proto": "*s-", "reflex": "s", "prob": 1.0},

    # Ханты: θ
    {"language": "хант", "proto": "*s-", "reflex": "θ", "prob": 1.0},

    # Мансий: θ
    {"language": "манс", "proto": "*s-", "reflex": "θ", "prob": 1.0},

    # Венгерский: 0
    {"language": "венг", "proto": "*s-", "reflex": "0", "prob": 1.0},

    # ————— Proto *-s- —————
    # Финский: s
    {"language": "фин", "proto": "*-s-", "reflex": "s", "prob": 1.0},

    # Саамский: s
    {"language": "саам", "proto": "*-s-", "reflex": "s", "prob": 1.0},

    # Мордва: z
    {"language": "морд", "proto": "*-s-", "reflex": "z", "prob": 1.0},

    # Марий: ž
    {"language": "мар", "proto": "*-s-", "reflex": "ž", "prob": 1.0},

    # Коми: z
    {"language": "коми", "proto": "*-s-", "reflex": "z", "prob": 1.0},

    # Удмурт: θ
    {"language": "удм", "proto": "*-s-", "reflex": "θ", "prob": 1.0},

    # Ханты: θ
    {"language": "хант", "proto": "*-s-", "reflex": "θ", "prob": 1.0},

    # Мансий: sz
    {"language": "манс", "proto": "*-s-", "reflex": "sz", "prob": 1.0},

    # Венгерский: sz или ź или ž (несколько вариантов)
    {"language": "венг", "proto": "*-s-", "reflex": "sz", "prob": None},
    {"language": "венг", "proto": "*-s-", "reflex": "ź", "prob": None},
    {"language": "венг", "proto": "*-s-", "reflex": "ž", "prob": None},

    # ————— Proto *δ́- —————
    {"language": "фин", "proto": "*δ́-", "reflex": "t", "prob": 1.0},
    {"language": "саам", "proto": "*δ́-", "reflex": "δ", "prob": 1.0},
    {"language": "морд", "proto": "*δ́-", "reflex": "ĺ", "prob": 1.0},
    {"language": "мар", "proto": "*δ́-", "reflex": "l", "prob": 1.0},
    {"language": "коми", "proto": "*δ́-", "reflex": "ĺ", "prob": 1.0},
    {"language": "удм", "proto": "*δ́-", "reflex": "ĺ", "prob": 1.0},
    {"language": "хант", "proto": "*δ́-", "reflex": "j", "prob": 1.0},
    {"language": "манс", "proto": "*δ́-", "reflex": "ĺ", "prob": 1.0},
    {"language": "венг", "proto": "*δ́-", "reflex": "gy", "prob": 1.0},

    # ————— Proto *-δ́- —————
    # объявления Иллич-Свитыч 1971
    {"language": "фин", "proto": "*-δ́-", "reflex": "t", "prob": None},
    {"language": "фин", "proto": "*-δ́-", "reflex": "d", "prob": None},
    {"language": "саам", "proto": "*-δ́-", "reflex": "đđ", "prob": None},
    {"language": "саам", "proto": "*-δ́-", "reflex": "đ", "prob": None},
    {"language": "морд", "proto": "*-δ́-", "reflex": "d", "prob": None},
    {"language": "мар", "proto": "*-δ́-", "reflex": "δ", "prob": None},
    {"language": "мар", "proto": "*-δ́-", "reflex": "j", "prob": None},
    {"language": "мар", "proto": "*-δ́-", "reflex": "0", "prob": None},
    {"language": "коми", "proto": "*-δ́-", "reflex": "ĺ", "prob": None},
    {"language": "удм", "proto": "*-δ́-", "reflex": "ĺ", "prob": None},
    {"language": "хант", "proto": "*-δ́-", "reflex": "ĺ", "prob": None},
    {"language": "хант", "proto": "*-δ́-", "reflex": "j", "prob": None},
    {"language": "манс", "proto": "*-δ́-", "reflex": "ĺ", "prob": None},
    {"language": "манс", "proto": "*-δ́-", "reflex": "j", "prob": None},
    {"language": "венг", "proto": "*-δ́-", "reflex": "j", "prob": None},
    {"language": "венг", "proto": "*-δ́-", "reflex": "gy", "prob": None},
    # Финский: t, si; Illich: t, d; Sammallahti: δ, j, 0
    {"language": "фин", "proto": "*-δ-", "reflex": "t", "prob": None},
    {"language": "фин", "proto": "*-δ-", "reflex": "si", "prob": None},
    {"language": "фин", "proto": "*-δ-", "reflex": "d", "prob": None},
    {"language": "фин", "proto": "*-δ-", "reflex": "δ", "prob": None},
    {"language": "фин", "proto": "*-δ-", "reflex": "j", "prob": None},
    {"language": "фин", "proto": "*-δ-", "reflex": "0", "prob": None},

    # Саамский: d; Illich: đđ, đ; Sammallahti: δ, j, 0
    {"language": "саам", "proto": "*-δ-", "reflex": "d", "prob": None},
    {"language": "саам", "proto": "*-δ-", "reflex": "đđ", "prob": None},
    {"language": "саам", "proto": "*-δ-", "reflex": "đ", "prob": None},
    {"language": "саам", "proto": "*-δ-", "reflex": "δ", "prob": None},
    {"language": "саам", "proto": "*-δ-", "reflex": "j", "prob": None},
    {"language": "саам", "proto": "*-δ-", "reflex": "0", "prob": None},

    # Мордва: d; Illich: d; Sammallahti: δ, j, 0; дополнительно l из первой табл.
    {"language": "морд", "proto": "*-δ-", "reflex": "d", "prob": None},
    {"language": "морд", "proto": "*-δ-", "reflex": "l", "prob": None},
    {"language": "морд", "proto": "*-δ-", "reflex": "δ", "prob": None},
    {"language": "морд", "proto": "*-δ-", "reflex": "j", "prob": None},
    {"language": "морд", "proto": "*-δ-", "reflex": "0", "prob": None},

    # Марий: d, dì; Illich: d; Sammallahti: δ, j, 0; l из первой табл.
    {"language": "мар", "proto": "*-δ-", "reflex": "d", "prob": None},
    {"language": "мар", "proto": "*-δ-", "reflex": "dì", "prob": None},
    {"language": "мар", "proto": "*-δ-", "reflex": "l", "prob": None},
    {"language": "мар", "proto": "*-δ-", "reflex": "δ", "prob": None},
    {"language": "мар", "proto": "*-δ-", "reflex": "j", "prob": None},
    {"language": "мар", "proto": "*-δ-", "reflex": "0", "prob": None},

    # Коми: 0; Illich: 0; Sammallahti: δ, j, 0; l из первой табл.
    {"language": "коми", "proto": "*-δ-", "reflex": "0", "prob": None},
    {"language": "коми", "proto": "*-δ-", "reflex": "l", "prob": None},
    {"language": "коми", "proto": "*-δ-", "reflex": "δ", "prob": None},
    {"language": "коми", "proto": "*-δ-", "reflex": "j", "prob": None},

    # Удмурт: 0; Illich: l, 0; Sammallahti: δ, j, 0
    {"language": "удм", "proto": "*-δ-", "reflex": "0", "prob": None},
    {"language": "удм", "proto": "*-δ-", "reflex": "l", "prob": None},
    {"language": "удм", "proto": "*-δ-", "reflex": "δ", "prob": None},
    {"language": "удм", "proto": "*-δ-", "reflex": "j", "prob": None},

    # Ханты: l; Illich: l; Sammallahti: l, 0
    {"language": "хант", "proto": "*-δ-", "reflex": "l", "prob": None},
    {"language": "хант", "proto": "*-δ-", "reflex": "0", "prob": None},

    # Мансий: l; Illich: l; Sammallahti: l, 0
    {"language": "манс", "proto": "*-δ-", "reflex": "l", "prob": None},
    {"language": "манс", "proto": "*-δ-", "reflex": "0", "prob": None},

    # Венгерский: l; Illich: l; Sammallahti: l, 0
    {"language": "венг", "proto": "*-δ-", "reflex": "l", "prob": None},
    {"language": "венг", "proto": "*-δ-", "reflex": "0", "prob": None},
    # ————— Proto *j- —————
    # Финский: всегда j
    {"language": "фин", "proto": "*j-", "reflex": "j", "prob": 1.0},

    # Саамский: варианты 0, i, e
    {"language": "саам", "proto": "*j-", "reflex": "0", "prob": None},
    {"language": "саам", "proto": "*j-", "reflex": "i", "prob": None},
    {"language": "саам", "proto": "*j-", "reflex": "e", "prob": None},

    # Марий: всегда j
    {"language": "мар", "proto": "*j-", "reflex": "j", "prob": 1.0},

    # Ханты: всегда j
    {"language": "хант", "proto": "*j-", "reflex": "j", "prob": 1.0},

    # Мансий: варианты 0, e, i
    {"language": "манс", "proto": "*j-", "reflex": "0", "prob": None},
    {"language": "манс", "proto": "*j-", "reflex": "e", "prob": None},
    {"language": "манс", "proto": "*j-", "reflex": "i", "prob": None},

    # Венгерский: j и gy (gy дважды упоминается — считаем единственным нестандартным рефлексом)
    {"language": "венг", "proto": "*j-", "reflex": "j", "prob": 1.0},
    {"language": "венг", "proto": "*j-", "reflex": "gy", "prob": 1.0},

    # ————— Proto *-j- —————
    # Финский: j
    {"language": "фин", "proto": "*-j-", "reflex": "j", "prob": 1.0},

    # Саамский: j (ср. d́, но оформлено как j)
    {"language": "саам", "proto": "*-j-", "reflex": "j", "prob": 1.0},

    # Мордва: j
    {"language": "морд", "proto": "*-j-", "reflex": "j", "prob": 1.0},

    # Марий: j
    {"language": "мар", "proto": "*-j-", "reflex": "j", "prob": 1.0},

    # Коми: j
    {"language": "коми", "proto": "*-j-", "reflex": "j", "prob": 1.0},

    # Удмурт: j
    {"language": "удм", "proto": "*-j-", "reflex": "j", "prob": 1.0},

    # Ханты: j
    {"language": "хант", "proto": "*-j-", "reflex": "j", "prob": 1.0},

    # Мансий: j
    {"language": "манс", "proto": "*-j-", "reflex": "j", "prob": 1.0},

    # Венгерский: j и 0
    {"language": "венг", "proto": "*-j-", "reflex": "j", "prob": None},
    {"language": "венг", "proto": "*-j-", "reflex": "0", "prob": None},
    # ————— Proto *l- —————
    # Все языки: всегда l
    {"language": "фин", "proto": "*l-", "reflex": "l", "prob": 1.0},
    {"language": "саам", "proto": "*l-", "reflex": "l", "prob": 1.0},
    {"language": "морд", "proto": "*l-", "reflex": "l", "prob": 1.0},
    {"language": "мар", "proto": "*l-", "reflex": "l", "prob": 1.0},
    {"language": "коми", "proto": "*l-", "reflex": "l", "prob": 1.0},
    {"language": "удм", "proto": "*l-", "reflex": "l", "prob": 1.0},
    {"language": "хант", "proto": "*l-", "reflex": "l", "prob": 1.0},
    {"language": "манс", "proto": "*l-", "reflex": "l", "prob": 1.0},
    {"language": "венг", "proto": "*l-", "reflex": "l", "prob": 1.0},

    # ————— Proto *-l- —————
    # Финский: только l
    {"language": "фин", "proto": "*-l-", "reflex": "l", "prob": 1.0},

    # Саамский: ll и l
    {"language": "саам", "proto": "*-l-", "reflex": "ll", "prob": None},
    {"language": "саам", "proto": "*-l-", "reflex": "l", "prob": None},

    # Мордва: l и ĺ
    {"language": "морд", "proto": "*-l-", "reflex": "l", "prob": None},
    {"language": "морд", "proto": "*-l-", "reflex": "ĺ", "prob": None},

    # Марий: l и ĺ
    {"language": "мар", "proto": "*-l-", "reflex": "l", "prob": None},
    {"language": "мар", "proto": "*-l-", "reflex": "ĺ", "prob": None},

    # Коми: l, w, v, 0
    {"language": "коми", "proto": "*-l-", "reflex": "l", "prob": None},
    {"language": "коми", "proto": "*-l-", "reflex": "w", "prob": None},
    {"language": "коми", "proto": "*-l-", "reflex": "v", "prob": None},
    {"language": "коми", "proto": "*-l-", "reflex": "0", "prob": None},

    # Удмурт: l, w, v, 0
    {"language": "удм", "proto": "*-l-", "reflex": "l", "prob": None},
    {"language": "удм", "proto": "*-l-", "reflex": "w", "prob": None},
    {"language": "удм", "proto": "*-l-", "reflex": "v", "prob": None},
    {"language": "удм", "proto": "*-l-", "reflex": "0", "prob": None},

    # Ханты: l, ƛ, t
    {"language": "хант", "proto": "*-l-", "reflex": "l", "prob": None},
    {"language": "хант", "proto": "*-l-", "reflex": "ƛ", "prob": None},
    {"language": "хант", "proto": "*-l-", "reflex": "t", "prob": None},

    # Мансий: l, ƛ, t
    {"language": "манс", "proto": "*-l-", "reflex": "l", "prob": None},
    {"language": "манс", "proto": "*-l-", "reflex": "ƛ", "prob": None},
    {"language": "манс", "proto": "*-l-", "reflex": "t", "prob": None},

    # Венгерский: l (собирательный вариант)
    {"language": "венг", "proto": "*-l-", "reflex": "l", "prob": 1.0},
    # ————— Proto *ĺ- —————
    # Саамский: всегда l
    {"language": "саам", "proto": "*ĺ-", "reflex": "l", "prob": 1.0},
    # Мордва: l или ĺ (без данных о количестве)
    {"language": "морд", "proto": "*ĺ-", "reflex": "l", "prob": None},
    {"language": "морд", "proto": "*ĺ-", "reflex": "ĺ", "prob": None},
    # Марий: всегда l
    {"language": "мар", "proto": "*ĺ-", "reflex": "l", "prob": 1.0},
    # Коми: всегда l’
    {"language": "коми", "proto": "*ĺ-", "reflex": "l’", "prob": 1.0},
    # Удмурт: всегда l’
    {"language": "удм", "proto": "*ĺ-", "reflex": "l’", "prob": 1.0},
    # Ханты: l’ (2) или l (1) → total = 3
    {"language": "хант", "proto": "*ĺ-", "reflex": "l’", "prob": 2 / 3},
    {"language": "хант", "proto": "*ĺ-", "reflex": "l", "prob": 1 / 3},
    # Мансий: всегда l’
    {"language": "манс", "proto": "*ĺ-", "reflex": "l’", "prob": 1.0},

    # ————— Proto *-ĺ- —————
    # Финский: всегда l
    {"language": "фин", "proto": "*-ĺ-", "reflex": "l", "prob": 1.0},
    # Саамский: всегда l
    {"language": "саам", "proto": "*-ĺ-", "reflex": "l", "prob": 1.0},
    # Мордва: всегда l
    {"language": "морд", "proto": "*-ĺ-", "reflex": "l", "prob": 1.0},
    # Марий: всегда l
    {"language": "мар", "proto": "*-ĺ-", "reflex": "l", "prob": 1.0},
    # Коми: всегда l’
    {"language": "коми", "proto": "*-ĺ-", "reflex": "l’", "prob": 1.0},
    # Удмурт: всегда l’
    {"language": "удм", "proto": "*-ĺ-", "reflex": "l’", "prob": 1.0},
    # Ханты: всегда l’
    {"language": "хант", "proto": "*-ĺ-", "reflex": "l’", "prob": 1.0},
    # Мансий: всегда l’
    {"language": "манс", "proto": "*-ĺ-", "reflex": "l’", "prob": 1.0},
    # Венгерский: ly
    {"language": "венг", "proto": "*-ĺ-", "reflex": "ly", "prob": 1.0},
    # ————— Proto *r- —————
    {"language": "фин", "proto": "*r-", "reflex": "r", "prob": 1.0},
    {"language": "саам", "proto": "*r-", "reflex": "r", "prob": 1.0},
    {"language": "морд", "proto": "*r-", "reflex": "r", "prob": 1.0},
    {"language": "мар", "proto": "*r-", "reflex": "r", "prob": 1.0},
    {"language": "коми", "proto": "*r-", "reflex": "r", "prob": None},
    {"language": "коми", "proto": "*r-", "reflex": "ǯ", "prob": None},
    {"language": "коми", "proto": "*r-", "reflex": "ʒ́", "prob": None},
    {"language": "удм", "proto": "*r-", "reflex": "r", "prob": 1.0},
    {"language": "хант", "proto": "*r-", "reflex": "r", "prob": 1.0},
    {"language": "манс", "proto": "*r-", "reflex": "r", "prob": 1.0},
    {"language": "венг", "proto": "*r-", "reflex": "r", "prob": 1.0},

    # ————— Proto *-r- —————
    {"language": "фин", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    {"language": "саам", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    {"language": "морд", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    {"language": "мар", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    {"language": "коми", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    {"language": "удм", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    {"language": "хант", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    {"language": "манс", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    {"language": "венг", "proto": "*-r-", "reflex": "r", "prob": 1.0},
    # ————— Proto *m- —————
    # Все языки: всегда m
    {"language": "фин", "proto": "*m-", "reflex": "m", "prob": 1.0},
    {"language": "саам", "proto": "*m-", "reflex": "m", "prob": 1.0},
    {"language": "морд", "proto": "*m-", "reflex": "m", "prob": 1.0},
    {"language": "мар", "proto": "*m-", "reflex": "m", "prob": 1.0},
    {"language": "коми", "proto": "*m-", "reflex": "m", "prob": 1.0},
    {"language": "удм", "proto": "*m-", "reflex": "m", "prob": 1.0},
    {"language": "хант", "proto": "*m-", "reflex": "m", "prob": 1.0},
    {"language": "манс", "proto": "*m-", "reflex": "m", "prob": 1.0},
    {"language": "венг", "proto": "*m-", "reflex": "m", "prob": 1.0},

    # ————— Proto *-m- —————
    # Финский: m
    {"language": "фин", "proto": "*-m-", "reflex": "m", "prob": 1.0},

    # Саамский: m и mm
    {"language": "саам", "proto": "*-m-", "reflex": "m", "prob": None},
    {"language": "саам", "proto": "*-m-", "reflex": "mm", "prob": None},

    # Мордва: m и v
    {"language": "морд", "proto": "*-m-", "reflex": "m", "prob": None},
    {"language": "морд", "proto": "*-m-", "reflex": "v", "prob": None},

    # Марий: m и 0
    {"language": "мар", "proto": "*-m-", "reflex": "m", "prob": None},
    {"language": "мар", "proto": "*-m-", "reflex": "0", "prob": None},

    # Коми: m
    {"language": "коми", "proto": "*-m-", "reflex": "m", "prob": None},

    # Удмурт: m
    {"language": "удм", "proto": "*-m-", "reflex": "m", "prob": None},

    # Ханты: m
    {"language": "хант", "proto": "*-m-", "reflex": "m", "prob": None},

    # Мансий: m
    {"language": "манс", "proto": "*-m-", "reflex": "m", "prob": None},

    # Венгерский: m
    {"language": "венг", "proto": "*-m-", "reflex": "m", "prob": None},
    # ————— Proto *n- —————
    # Финский: всегда n
    {"language": "фин", "proto": "*n-", "reflex": "n", "prob": 1.0},
    # Саамский: n и ń
    {"language": "саам", "proto": "*n-", "reflex": "n", "prob": None},
    {"language": "саам", "proto": "*n-", "reflex": "ń", "prob": None},
    # Мордва: n и ń
    {"language": "морд", "proto": "*n-", "reflex": "n", "prob": None},
    {"language": "морд", "proto": "*n-", "reflex": "ń", "prob": None},
    # Марий: n и ń
    {"language": "мар", "proto": "*n-", "reflex": "n", "prob": None},
    {"language": "мар", "proto": "*n-", "reflex": "ń", "prob": None},
    # Коми: n
    {"language": "коми", "proto": "*n-", "reflex": "n", "prob": None},
    # Удмурт: n
    {"language": "удм", "proto": "*n-", "reflex": "n", "prob": None},
    # Ханты: n
    {"language": "хант", "proto": "*n-", "reflex": "n", "prob": None},
    # Мансий: n
    {"language": "манс", "proto": "*n-", "reflex": "n", "prob": None},
    # Венгерский: всегда n
    {"language": "венг", "proto": "*n-", "reflex": "n", "prob": 1.0},

    # ————— Proto *-n- —————
    # Финский: n
    {"language": "фин", "proto": "*-n-", "reflex": "n", "prob": 1.0},
    # Саамский: n и nn
    {"language": "саам", "proto": "*-n-", "reflex": "n", "prob": None},
    {"language": "саам", "proto": "*-n-", "reflex": "nn", "prob": None},
    # Мордва: n, nì и j
    {"language": "морд", "proto": "*-n-", "reflex": "n", "prob": None},
    {"language": "морд", "proto": "*-n-", "reflex": "nì", "prob": None},
    {"language": "морд", "proto": "*-n-", "reflex": "j", "prob": None},
    # Марий: n и nì
    {"language": "мар", "proto": "*-n-", "reflex": "n", "prob": None},
    {"language": "мар", "proto": "*-n-", "reflex": "nì", "prob": None},
    # Коми: n
    {"language": "коми", "proto": "*-n-", "reflex": "n", "prob": None},
    # Удмурт: n
    {"language": "удм", "proto": "*-n-", "reflex": "n", "prob": None},
    # Ханты: n
    {"language": "хант", "proto": "*-n-", "reflex": "n", "prob": None},
    # Мансий: n
    {"language": "манс", "proto": "*-n-", "reflex": "n", "prob": None},
    # Венгерский: n
    {"language": "венг", "proto": "*-n-", "reflex": "n", "prob": None},
    # ————— Proto *ń- —————
    {"language": "фин", "proto": "*ń-", "reflex": "n", "prob": 1.0},
    {"language": "саам", "proto": "*ń-", "reflex": "nj", "prob": None},
    {"language": "морд", "proto": "*ń-", "reflex": "n", "prob": None},
    {"language": "мар", "proto": "*ń-", "reflex": "nì", "prob": None},
    {"language": "коми", "proto": "*ń-", "reflex": "ń", "prob": None},
    {"language": "удм", "proto": "*ń-", "reflex": "nì", "prob": None},
    {"language": "хант", "proto": "*ń-", "reflex": "ń", "prob": None},
    {"language": "манс", "proto": "*ń-", "reflex": "ń", "prob": None},
    {"language": "венг", "proto": "*ń-", "reflex": "ny", "prob": None},

    # ————— Proto *-ń- —————
    {"language": "фин", "proto": "*-ń-", "reflex": "n", "prob": 1.0},
    {"language": "саам", "proto": "*-ń-", "reflex": "ń", "prob": None},
    {"language": "морд", "proto": "*-ń-", "reflex": "ń", "prob": None},
    {"language": "мар", "proto": "*-ń-", "reflex": "ń", "prob": None},
    {"language": "коми", "proto": "*-ń-", "reflex": "ń", "prob": None},
    {"language": "удм", "proto": "*-ń-", "reflex": "ń", "prob": None},
    {"language": "хант", "proto": "*-ń-", "reflex": "ń", "prob": None},
    {"language": "манс", "proto": "*-ń-", "reflex": "ń", "prob": None},
    {"language": "венг", "proto": "*-ń-", "reflex": "ny", "prob": None},
    # ————— Proto *ŋ- —————
    {"language": "фин", "proto": "*ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "саам", "proto": "*ŋ-", "reflex": "v", "prob": None},
    {"language": "морд", "proto": "*ŋ-", "reflex": "0", "prob": None},
    {"language": "мар", "proto": "*ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "коми", "proto": "*ŋ-", "reflex": "j", "prob": None},
    {"language": "удм", "proto": "*ŋ-", "reflex": "v", "prob": None},
    {"language": "хант", "proto": "*ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "манс", "proto": "*ŋ-", "reflex": "n", "prob": None},
    {"language": "венг", "proto": "*ŋ-", "reflex": "m", "prob": None},

    # ————— Proto *-ŋ- —————
    {"language": "фин", "proto": "*-ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "саам", "proto": "*-ŋ-", "reflex": "ŋŋ", "prob": None},
    {"language": "морд", "proto": "*-ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "мар", "proto": "*-ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "коми", "proto": "*-ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "удм", "proto": "*-ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "хант", "proto": "*-ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "манс", "proto": "*-ŋ-", "reflex": "ŋ", "prob": None},
    {"language": "венг", "proto": "*-ŋ-", "reflex": "ŋk", "prob": None},
    # *w-
    {"language": "фин", "proto": "*w-", "reflex": "v", "prob": None},
    {"language": "саам", "proto": "*w-", "reflex": "0", "prob": None},
    {"language": "морд", "proto": "*w-", "reflex": "0", "prob": None},
    {"language": "мар", "proto": "*w-", "reflex": "0", "prob": None},
    {"language": "коми", "proto": "*w-", "reflex": "v", "prob": None},
    {"language": "удм", "proto": "*w-", "reflex": "v", "prob": None},
    {"language": "хант", "proto": "*w-", "reflex": "w", "prob": None},
    {"language": "манс", "proto": "*w-", "reflex": "0", "prob": None},
    {"language": "венг", "proto": "*w-", "reflex": "w", "prob": None},
    # *-w-
    {"language": "фин", "proto": "*-w-", "reflex": "v", "prob": None},
    {"language": "саам", "proto": "*-w-", "reflex": "0", "prob": None},
    {"language": "морд", "proto": "*-w-", "reflex": "0", "prob": None},
    {"language": "мар", "proto": "*-w-", "reflex": "0", "prob": None},
    {"language": "коми", "proto": "*-w-", "reflex": "w", "prob": None},
    {"language": "удм", "proto": "*-w-", "reflex": "v", "prob": None},
    {"language": "хант", "proto": "*-w-", "reflex": "0", "prob": None},
    {"language": "манс", "proto": "*-w-", "reflex": "w", "prob": None},
    {"language": "венг", "proto": "*-w-", "reflex": "v", "prob": None},
    # *-ɣ-
    {"language": "фин", "proto": "*-ɣ-", "reflex": "0", "prob": None},
    {"language": "саам", "proto": "*-ɣ-", "reflex": "kk", "prob": None},
    {"language": "морд", "proto": "*-ɣ-", "reflex": "j", "prob": None},
    {"language": "мар", "proto": "*-ɣ-", "reflex": "0", "prob": None},
    {"language": "коми", "proto": "*-ɣ-", "reflex": "0", "prob": None},
    {"language": "удм", "proto": "*-ɣ-", "reflex": "0", "prob": None},
    {"language": "хант", "proto": "*-ɣ-", "reflex": "0", "prob": None},
    {"language": "манс", "proto": "*-ɣ-", "reflex": "0", "prob": None},
    {"language": "венг", "proto": "*-ɣ-", "reflex": "0", "prob": None},
])

lang_abbrs = {
    "финск": "фин",
    "саамск": "саам",
    "мордовск": "морд",
    "марийск": "мар",
    "коми": "коми",
    "удмуртск": "удм",
    "хантыйск": "хант",
    "мансийск": "манс",
    "венгерск": "венг"
}
