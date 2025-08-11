import numpy as np
import os
import re
import pandas as pd
from typing import Dict, List, Tuple

try:
    from gensim.models import KeyedVectors
except ImportError:
    raise ImportError("Please install gensim: pip install gensim")


## fast text отдельно
def load_fasttext_model(path: str) -> KeyedVectors:
    """
    Загрузить эмбеддинги FastText (cc.ru.300).
    Args:
        path: путь к файлу с эмбеддингами:
              - бинарный .bin или распакованный .bin.gz
              - текстовый .vec или .vec.gz
    Returns:
        Объект KeyedVectors с русскими эмбеддингами.
    """
    # Определяем формат по расширению
    ext = os.path.splitext(path)[1].lower()
    if ext in ['.bin', '.gz']:
        binary = True
    elif ext in ['.vec']:
        binary = False
    else:
        # По умолчанию считаем бинарным
        binary = True

    return KeyedVectors.load_word2vec_format(
        path,
        binary=binary,
        unicode_errors='ignore'
    )


def rerank_with_fasttext(
        base: str,
        candidates: List[str],
        ft_model: KeyedVectors
) -> Dict[str, float]:
    """
    Ранжировать кандидатов по семантической близости переводов через FastText.
    Args:
        base: базовый элемент в формате "word:translation",
        candidates: список кандидатов в формате ["word:translation", ...],
        ft_model: загруженная модель FastText (KeyedVectors).
    Returns:
        Словарь с нормированными скорами семантической близости {"word:translation": score}.
    """
    # извлекаем базовый перевод
    base_translation = base.split(':', 1)[1]

    # извлекаем переводы из кандидатов
    translations = [cand.split(':', 1)[1] for cand in candidates]

    # получаем векторы
    def get_vector(word: str) -> np.ndarray:
        try:
            vec = ft_model[word]
        except KeyError:
            vec = np.zeros(ft_model.vector_size, dtype=float)
        return vec

    # получаем и нормализуем базовый вектор
    base_vec = get_vector(base_translation)
    if np.linalg.norm(base_vec) > 0:
        base_vec = base_vec / np.linalg.norm(base_vec)
    cand_vecs = []
    for tr in translations:
        vec = get_vector(tr)
        if np.linalg.norm(vec) > 0:
            vec = vec / np.linalg.norm(vec)
        cand_vecs.append(vec)

    cand_matrix = np.vstack(cand_vecs)
    sem_sims = cand_matrix.dot(base_vec)
    print(f"Базовый перевод: '{base_translation}'")
    print("Переводы кандидатов:", translations)
    print("Косинусные сходства:", sem_sims)
    print(f"Min: {sem_sims.min():.6f}, Max: {sem_sims.max():.6f}")

    # возвращаем сырые косинусные сходства (от -1 до 1)
    # преобразуем в диапазон [0, 1]
    normalized_sims = (sem_sims + 1) / 2

    return {cand: float(sim) for cand, sim in zip(candidates, normalized_sims)}


if __name__ == '__main__':
    base = 'simá:глаз'
    candidates = [
        'шӹнзä:глаз', 'kaadél:лицо', 'šiĺmät:лицо',
        'khömyskä́:бровь', 'simaáz\'et:слепой',
        'avá:отец', 'minä́:бровь', 'mo:берлога',
        'sys\'ký:лопатка'
    ]

    ft = load_fasttext_model('cc.ru.300.vec')
    scores = rerank_with_fasttext(base, candidates, ft)
    for k, v in sorted(scores.items(), key=lambda x: -x[1]):
        print(f"{k}: {v:.4f}")

# датафрейм всех соответсвий из файла
data = [
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
]

df = pd.DataFrame(data)
## условия отдельно
# словарь транслитерации из DataFrame
CYR2LAT = {
    'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
    'ж': 'ž', 'з': 'z', 'й': 'j', 'к': 'k',
    'л': 'l', 'м': 'm', 'н': 'n', 'п': 'p',
    'р': 'r', 'с': 's', 'т': 't', 'ф': 'f',
    'х': 'h', 'ц': 'c', 'ч': 'č', 'ш': 'š',
    'щ': 'šč',
}


def translit_char(ch: str) -> str:
    """
    транслитерирует один символ через словарь CYR2LAT.
    Если символ не найден — возвращает сам символ.
    """
    return CYR2LAT.get(ch, ch)


def translit(word: str) -> str:
    """
    транслитерирует все символы слова, используя translit_char.
    """
    return ''.join(translit_char(ch) for ch in word)


def get_proto_key(c: str, pos: int, length: int) -> str:
    """
    определяем ключ прафонемы с учетом позиции в слове.
    pos=0 -> '*c-'; pos=end -> '-c*'; else '*-c-'
    """
    if pos == 0:
        return f'*{c}-'
    elif pos == length - 1:
        return f'-{c}*'
    else:
        return f'*-{c}-'


def is_regular_char_match(
        c_src: str,
        c_tgt: str,
        corr_df: pd.DataFrame,
        src_lang: str,
        tgt_lang: str,
        pos: int,
        word_len: int
) -> bool:
    """
    Проверка c_src → c_tgt через таблицу соответствий.
    Перед сравнением символы транслитерируются.
    """
    c1 = translit_char(c_src)
    c2 = translit_char(c_tgt)

    proto_key = get_proto_key(c1, pos, word_len)
    row_src = corr_df[(corr_df['proto'] == proto_key) & (corr_df['language'] == src_lang)]
    row_tgt = corr_df[(corr_df['proto'] == proto_key) & (corr_df['language'] == tgt_lang)]
    if row_src.empty or row_tgt.empty:
        return False
    variants_src = re.split(r"[/,]", row_src.iloc[0]['reflex'])
    variants_tgt = re.split(r"[/,]", row_tgt.iloc[0]['reflex'])
    return any(vs.strip() == c1 for vs in variants_src) and any(vt.strip() == c2 for vt in variants_tgt)


def rank_cognates(
        base_pair: str,
        candidates: List[str],
        corr_df: pd.DataFrame,
        src_lang: str,
        tgt_lang: str
) -> List[Tuple[str, float]]:
    """
     +0.5 за консонантную пару
     +1.0 за полное совпадение перевода
     +0.5 за совпадение первых 4 символов перевода
    """
    word1, trans1 = base_pair.split(':', 1)
    # транслитерируем базовое слово
    w1_lat = translit(word1)
    results: List[Tuple[str, float]] = []

    for cand in candidates:
        word2, trans2 = cand.split(':', 1)
        w2_lat = translit(word2)
        consonant_score = 0.0
        # сравниваем все символы
        for i in range(min(len(w1_lat), len(w2_lat))):
            if is_regular_char_match(word1[i], word2[i], corr_df, src_lang, tgt_lang, i, len(w1_lat)):
                consonant_score += 0.5
        translation_score = 1.0 if trans1 == trans2 else 0.0
        prefix4_score = 0.5 if len(trans1) >= 4 and trans1[:4] == trans2[:4] else 0.0
        total_score = consonant_score + translation_score + prefix4_score
        results.append((cand, total_score))
    return sorted(results, key=lambda x: x[1], reverse=True)


ranked = rank_cognates(
    base_pair='simá:глаз',
    candidates=[
        'шӹнзä:глаз', 'kaadél:лицо', 'šiĺmät:лицо',
        'khömyskä́:бровь', 'simaáz\'et:слепой',
        'avá:отец', 'minä́:бровь', 'mo:берлога',
        'sys\'ký:лопатка'
    ],
    corr_df=df,
    src_lang='коми',
    tgt_lang='удм'
)
for cand, score in ranked:
    print(f"{cand} → {score:.2f}")


## список и строка+полный вывод
class RerankerSingleWord:
    def __init__(
            self,
            ft_model: KeyedVectors,
            src_lang: str,
            tgt_lang: str,
            sem_threshold: float = 0.5,
    ):
        """
        Args:
            ft_model: Модель FastText (KeyedVectors)
            src_lang: Язык-источник
            tgt_lang: Язык в сравнениях
            sem_threshold: Порог семантической близости
        """
        self.ft = ft_model
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.sem_threshold = sem_threshold

    def _get_semantic_scores(
            self, base: str, candidates: List[str]
    ) -> Dict[str, float]:
        """
        Считает нормированные семантические косинусные сходства.
        """
        base_trans = base.split(':', 1)[1]
        cand_trans = [c.split(':', 1)[1] for c in candidates]

        def get_vec(word: str) -> np.ndarray:
            try:
                vec = self.ft[word]
            except KeyError:
                vec = np.zeros(self.ft.vector_size, dtype=float)
            norm = np.linalg.norm(vec)
            return vec / norm if norm > 0 else vec

        base_vec = get_vec(base_trans)
        cand_vecs = [get_vec(t) for t in cand_trans]
        sims = np.array([np.dot(v, base_vec) for v in cand_vecs])
        normed = (sims + 1) / 2
        return {cand: float(normed[i]) for i, cand in enumerate(candidates)}

    @staticmethod
    def translit_char(ch: str) -> str:
        CYR2LAT = {
            'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'ж': 'ž', 'з': 'z', 'й': 'j', 'к': 'k',
            'л': 'l', 'м': 'm', 'н': 'n', 'п': 'p',
            'р': 'r', 'с': 's', 'т': 't', 'ф': 'f',
            'х': 'h', 'ц': 'c', 'ч': 'č', 'ш': 'š',
            'щ': 'šč',
        }
        return CYR2LAT.get(ch, ch)

    @staticmethod
    def get_proto_key(c: str, pos: int, length: int) -> str:
        if pos == 0:
            return f'{c}-'
        elif pos == length - 1:
            return f'-{c}'
        else:
            return f'-{c}-'

    def is_regular_char_match(
            self, c_src: str, c_tgt: str, corr_df: pd.DataFrame, pos: int, length: int
    ) -> bool:
        c1 = self.translit_char(c_src)
        c2 = self.translit_char(c_tgt)
        key = self.get_proto_key(c1, pos, length)
        df = corr_df
        row_src = df[(df['proto'] == key) & (df['language'] == self.src_lang)]
        row_tgt = df[(df['proto'] == key) & (df['language'] == self.tgt_lang)]
        if row_src.empty or row_tgt.empty:
            return False
        vs = re.split(r"[/,]", row_src.iloc[0]['reflex'])
        vt = re.split(r"[/,]", row_tgt.iloc[0]['reflex'])
        return any(x.strip() == c1 for x in vs) and any(x.strip() == c2 for x in vt)

    def _get_cognate_scores(
            self, base: str, candidates: List[str], corr_df: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Оценивает кандидатов по соответсвиям и совпадениям переводов.
        """
        word1, trans1 = base.split(':', 1)
        w1_lat = ''.join(self.translit_char(c) for c in word1)
        scores = {}
        for cand in candidates:
            word2, trans2 = cand.split(':', 1)
            w2_lat = ''.join(self.translit_char(c) for c in word2)
            cons_score = 0.0
            for i in range(min(len(w1_lat), len(w2_lat))):
                if self.is_regular_char_match(word1[i], word2[i], corr_df, i, len(w1_lat)):
                    cons_score += 0.5
            trans_score = 1.0 if trans1 == trans2 else 0.0
            pref4 = 0.5 if len(trans1) >= 4 and trans1[:4] == trans2[:4] else 0.0
            scores[cand] = cons_score + trans_score + pref4
        return scores

    def rerank(
            self,
            base: str,
            candidates: List[str],
            corr_df: pd.DataFrame
    ) -> List[Tuple[str, float, float, float]]:
        """
        Возвращает комбинированное ранжирование кандидатов.

        Args:
            base: базовый элемент в формате "word:translation"
            candidates: список кандидатов в том же формате
            corr_df: DataFrame с таблицей соответствий прафонем

        Returns:
            Список кортежей (candidate, sem_score, cog_score, combined_score)
        """
        sem_scores = self._get_semantic_scores(base, candidates)
        passed = [c for c, s in sem_scores.items() if s >= self.sem_threshold]
        cog_scores = self._get_cognate_scores(base, passed, corr_df) if passed else {}

        results = []
        for cand in candidates:
            s = sem_scores.get(cand, 0.0)
            c = cog_scores.get(cand, 0.0) if s >= self.sem_threshold else 0.0
            comb = s + c
            results.append((cand, s, c, comb))

        return sorted(results, key=lambda x: x[3], reverse=True)


base_pair = 'simá:глаз'
candidate = [
    'шӹнзä:глаз', 'kaadél:лицо', 'šiĺmät:лицо',
    'khömyskä́:бровь', 'simaáz\'et:слепой',
    'avá:отец', 'minä́:бровь', 'mo:берлога',
    'sys\'ký:лопатка'
]
ft = load_fasttext_model('cc.ru.300.vec')
reranker = RerankerSingleWord(ft, 'коми', 'удм', sem_threshold=0.5)
ranked = reranker.rerank('simá:глаз', candidate, df)
for cand, s, c, comb in ranked:
    print(f"{cand}: sem={s:.3f}, cog={c:.3f}, total={comb:.3f}")


## список и список+полный вывод

class Reranker:
    def __init__(
            self,
            ft_model: KeyedVectors,
            src_lang: str,
            tgt_lang: str,
            sem_threshold: float = 0.5,
    ):
        """
        Args:
            ft_model: FastText model (KeyedVectors)
            src_lang: source language
            tgt_lang: target language for cognate comparison
            sem_threshold: threshold for semantic similarity
        """
        self.ft = ft_model
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.sem_threshold = sem_threshold

    def _get_semantic_scores(
            self, base: str, candidates: List[str]
    ) -> Dict[str, float]:
        base_trans = base.split(':', 1)[1]
        cand_trans = [c.split(':', 1)[1] for c in candidates]

        def get_vec(word: str) -> np.ndarray:
            try:
                vec = self.ft[word]
            except KeyError:
                vec = np.zeros(self.ft.vector_size, dtype=float)
            norm = np.linalg.norm(vec)
            return vec / norm if norm > 0 else vec

        base_vec = get_vec(base_trans)
        cand_vecs = [get_vec(t) for t in cand_trans]
        sims = np.array([np.dot(v, base_vec) for v in cand_vecs])
        normed = (sims + 1) / 2
        return {cand: float(normed[i]) for i, cand in enumerate(candidates)}

    @staticmethod
    def translit_char(ch: str) -> str:
        CYR2LAT = {
            'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
            'ж': 'ž', 'з': 'z', 'й': 'j', 'к': 'k',
            'л': 'l', 'м': 'm', 'н': 'n', 'п': 'p',
            'р': 'r', 'с': 's', 'т': 't', 'ф': 'f',
            'х': 'h', 'ц': 'c', 'ч': 'č', 'ш': 'š',
            'щ': 'šč',
        }
        return CYR2LAT.get(ch, ch)

    @staticmethod
    def get_proto_key(c: str, pos: int, length: int) -> str:
        if pos == 0:
            return f'{c}-'
        elif pos == length - 1:
            return f'-{c}'
        else:
            return f'-{c}-'

    def is_regular_char_match(
            self, c_src: str, c_tgt: str, corr_df: pd.DataFrame, pos: int, length: int
    ) -> bool:
        c1 = self.translit_char(c_src)
        c2 = self.translit_char(c_tgt)
        key = self.get_proto_key(c1, pos, length)
        df = corr_df
        row_src = df[(df['proto'] == key) & (df['language'] == self.src_lang)]
        row_tgt = df[(df['proto'] == key) & (df['language'] == self.tgt_lang)]
        if row_src.empty or row_tgt.empty:
            return False
        vs = re.split(r"[/,]", row_src.iloc[0]['reflex'])
        vt = re.split(r"[/,]", row_tgt.iloc[0]['reflex'])
        return any(x.strip() == c1 for x in vs) and any(x.strip() == c2 for x in vt)

    def _get_cognate_scores(
            self, base: str, candidates: List[str], corr_df: pd.DataFrame
    ) -> Dict[str, float]:
        word1, trans1 = base.split(':', 1)
        w1_lat = ''.join(self.translit_char(c) for c in word1)
        scores = {}
        for cand in candidates:
            word2, trans2 = cand.split(':', 1)
            w2_lat = ''.join(self.translit_char(c) for c in word2)
            cons_score = 0.0
            for i in range(min(len(w1_lat), len(w2_lat))):
                if self.is_regular_char_match(word1[i], word2[i], corr_df, i, len(w1_lat)):
                    cons_score += 0.5
            trans_score = 1.0 if trans1 == trans2 else 0.0
            pref4 = 0.5 if len(trans1) >= 4 and trans1[:4] == trans2[:4] else 0.0
            scores[cand] = cons_score + trans_score + pref4
        return scores

    def rerank(
            self,
            base: str,
            candidates: List[str],
            corr_df: pd.DataFrame
    ) -> List[Tuple[str, float, float, float]]:
        sem_scores = self._get_semantic_scores(base, candidates)
        passed = [c for c, s in sem_scores.items() if s >= self.sem_threshold]
        cog_scores = self._get_cognate_scores(base, passed, corr_df) if passed else {}

        results = []
        for cand in candidates:
            s = sem_scores.get(cand, 0.0)
            c = cog_scores.get(cand, 0.0) if s >= self.sem_threshold else 0.0
            comb = s + c
            results.append((cand, s, c, comb))

        return sorted(results, key=lambda x: x[3], reverse=True)

    def rerank_lists(
            self,
            sources: List[str],
            targets: List[str],
            corr_df: pd.DataFrame
    ) -> Dict[str, List[Tuple[str, float, float, float]]]:
        all_rankings: Dict[str, List[Tuple[str, float, float, float]]] = {}
        for src in sources:
            all_rankings[src] = self.rerank(src, targets, corr_df)
        return all_rankings


source = ['чальм:глаз', 'budá:крюк', 'soj:сестра', 'ajá:мать', 'mará:край', 'kolá:мёд']
target = ['шӹнзä:глаз', 'bazá:охотно', 'udá:рука',
          'nestá:старший мужчина', 'almá:сон', 'ujá:мясо',
          'kuzá:человек', 'adjá̆:старшая женщина', 'avá:отец', 'simá:глаз',
          'urgajá:бабушка', 'naaná:брюхо', 'phadá:желчь', 'nargá:тальник', 'thungá:боярышник',
          'kŭlŭká:жеребенок', 'argá:вино', 'sa:поясница', 'phaná:лапа', 'kuwá:кожа', 'mieká:икра', 'namá:зеленый']
ft = load_fasttext_model('cc.ru.300.vec')
reranker = Reranker(ft, 'коми', 'удм', sem_threshold=0.5)
rankings = reranker.rerank_lists(source, target, df)
for src, ranks in rankings.items():
    print(f"Base: {src}")
    for cand, sem, cog, tot in ranks:
        print(f"  {cand}: sem={sem:.3f}, cog={cog:.3f}, total={tot:.3f}")
