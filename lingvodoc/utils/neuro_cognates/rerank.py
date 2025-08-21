import numpy as np
import os
import re
import pandas as pd
from typing import Dict, List, Tuple
from lingvodoc.utils.neuro_cognates.proto import df, lang_abbrs
from pdb import set_trace as A


## список и строка+полный вывод
class RerankerSingleWord:
    def __init__(
            self,
            ft_model,
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

        src_lang_abbr = None
        tgt_lang_abbr = None

        for lang in lang_abbrs.keys():
            if re.search(f'^{lang}|\W{lang}', self.src_lang):
                src_lang_abbr = lang_abbrs[lang]
            if re.search(f'^{lang}|\W{lang}', self.tgt_lang):
                tgt_lang_abbr = lang_abbrs[lang]

        if src_lang_abbr is None or tgt_lang_abbr is None:
            return False

        row_src = df[(df['proto'] == key) & (df['language'] == src_lang_abbr)]
        row_tgt = df[(df['proto'] == key) & (df['language'] == tgt_lang_abbr)]

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
            for i in range(min(len(word1), len(word2))):
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
            corr_df: pd.DataFrame = df
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

        #return sorted(results, key=lambda x: x[3], reverse=True)
        return results
