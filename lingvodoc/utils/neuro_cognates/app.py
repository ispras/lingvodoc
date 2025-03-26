import torch
import torch.nn as nn
from torch.multiprocessing import Pool, set_start_method
import os
import gzip
import pickle
from time import time as now
from lingvodoc.queue.celery import celery
from lingvodoc.cache.caching import TaskStatus, initialize_cache


# Определение архитектуры модели -------------------------------------------------
class TransformerEncoderBlock(nn.Module):
    def __init__(self, embed_dim, num_heads, ff_dim, dropout=0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(embed_dim, num_heads, dropout=dropout, batch_first=True)
        self.norm1 = nn.LayerNorm(embed_dim)
        self.ff = nn.Sequential(
            nn.Linear(embed_dim, ff_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, embed_dim)
        )
        self.norm2 = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        attn_out, _ = self.attn(x, x, x)
        x = self.norm1(x + self.dropout(attn_out))
        ff_out = self.ff(x)
        return self.norm2(x + self.dropout(ff_out))


class DualPathSiamese(nn.Module):
    def __init__(self, vocab_size, embed_dim, max_len):
        super().__init__()
        self.max_len = max_len

        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.pos_embed = nn.Parameter(torch.zeros(1, max_len, embed_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

        self.word_encoder = nn.Sequential(
            nn.LSTM(embed_dim, 64, bidirectional=True, batch_first=True),
            TransformerEncoderBlock(128, 4, 128),
            TransformerEncoderBlock(128, 4, 128)
        )
        self.trans_encoder = nn.Sequential(
            nn.LSTM(embed_dim, 64, bidirectional=True, batch_first=True),
            *[TransformerEncoderBlock(128, 4, 128) for _ in range(4)]
        )

        self.alpha = nn.Parameter(torch.tensor(0.7))
        self.beta = nn.Parameter(torch.tensor(0.3))

        self.classifier = nn.Sequential(
            nn.Linear(4 * 128, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(256, 1)
        )

    def _encode(self, x, encoder):
        emb = self.embedding(x) + self.pos_embed[:, :x.size(1), :]
        for layer in encoder:
            if isinstance(layer, nn.LSTM):
                emb, _ = layer(emb)
            else:
                emb = layer(emb)
        return emb.mean(dim=1)

    def forward(self, word1, trans1, word2, trans2):
        w1 = self._encode(word1, self.word_encoder)
        t1 = self._encode(trans1, self.trans_encoder)
        pair1 = self.alpha * t1 + self.beta * w1

        w2 = self._encode(word2, self.word_encoder)
        t2 = self._encode(trans2, self.trans_encoder)
        pair2 = self.alpha * t2 + self.beta * w2

        diff = torch.abs(pair1 - pair2)
        mul = pair1 * pair2
        combined = torch.cat([pair1, pair2, diff, mul], dim=1)
        return self.classifier(combined)


def process_batch(args):
    self, input_word, input_tran, input_id, input_links = args
    similarities = []

    with torch.no_grad():
        base_word = self._process_text(input_word)
        base_tran = self._process_text(input_tran)

        for i, compare_list in enumerate(self.compare_lists):
            if not compare_list:
                continue

            (compare_words, compare_trans, compare_ids, _), links = (
                self.split_items(compare_list, input_links))

            # Создание батча
            batch = {
                'word1': [base_word] * len(compare_words),
                'trans1': [base_tran] * len(compare_words),
                'word2': [self._process_text(w) for w in compare_words],
                'trans2': [self._process_text(t) for t in compare_trans]
            }

            # Преобразование в тензоры
            word1 = torch.stack(batch['word1'])
            trans1 = torch.stack(batch['trans1'])
            word2 = torch.stack(batch['word2'])
            trans2 = torch.stack(batch['trans2'])

            # Предсказание
            outputs = self.model(word1, trans1, word2, trans2)
            probs = torch.sigmoid(outputs).squeeze()

            for idx, prob in enumerate(probs):
                if prob.item() > self.truth_threshold:
                    similarities.append((
                        i,
                        [compare_words[idx], compare_trans[idx]],
                        compare_ids[idx],
                        f"{prob.item():.4f}"
                    ))

    return (
        [(
            self.input_index,
            f"{input_word} '{input_tran}'",
            input_id,
            None,
            similarities,
            []
        )] if similarities else [],
        len(similarities))


class NeuroCognates:
    def __init__(self,
                 compare_lists,
                 input_index,
                 source_perspective_id,
                 perspective_name_list,
                 storage,
                 host_url,
                 cache_kwargs,
                 distilled=False,
                 truth_threshold=0.97,
                 only_orphans_flag=True):

        self.compare_lists = compare_lists
        self.input_index = input_index
        self.source_perspective_id = source_perspective_id
        self.truth_threshold = truth_threshold
        self.perspective_name_list = perspective_name_list
        self.storage = storage
        self.host_url = host_url
        self.cache_kwargs = cache_kwargs
        self.only_orphans_flag = only_orphans_flag

        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)

        # Загрузка модели
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        checkpoint = torch.load(os.path.join(script_dir, 'best_model.pth'), map_location=self.device)

        self.model = DualPathSiamese(
            vocab_size=len(checkpoint['char_to_index']),
            embed_dim=checkpoint['config']['embed_dim'],
            max_len=checkpoint['config']['max_len']
        ).to(self.device)

        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.char_to_index = checkpoint['char_to_index']
        self.max_len = checkpoint['config']['max_len']
        self.model.eval()

    def _process_text(self, text):
        indices = [self.char_to_index.get(c, 1) for c in text.lower()[:self.max_len]]
        indices += [0] * (self.max_len - len(indices))
        return torch.tensor(indices, dtype=torch.long, device=self.device)

    @staticmethod
    def split_items(items, input_links=None):
        links = 0
        result = ([], [], [], [])
        for i in range(len(items)):
            if input_links and set(input_links) & set(items[i][3]):
                links += 1
                continue
            for j in range(4):
                result[j].append(items[i][j])
        return result, links

    @celery.task
    def predict_cognates(self, word_pairs, task):

        start_time = now()
        results = []
        group_count = 0
        current_stage = 0
        result_link = ""
        input_len = len(word_pairs)
        compare_len = sum(map(len, self.compare_lists))
        initialize_cache(self.cache_kwargs)
        task = TaskStatus.get_from_cache(task.key)
        stamp_file = os.path.join(self.storage['path'], 'lingvodoc_stamps', str(task.id))

        def add_result(res):
            nonlocal current_stage, result_link, group_count
            if res is None:
                return

            result, links = res
            results.extend(result)
            group_count += links
            current_stage += 1
            finished = (current_stage == input_len)

            # Обновление статуса задачи
            passed = now() - start_time
            left = passed / current_stage * input_len - passed

            days = int(left / 86400)
            hours = int((left - days * 86400) / 3600)
            minutes = int((left - days * 86400 - hours * 3600) / 60)

            progress = 100 if finished else int(current_stage / input_len * 100)
            status = "Finished" if finished else f"~ {days}d:{hours}h:{minutes}m left ~"

            # Сохранение результатов
            if current_stage % 10 == 0 or finished:
                result_dict = dict(
                    suggestion_list=results,
                    perspective_name_list=self.perspective_name_list,
                    transcription_count=compare_len * current_stage,
                    group_count=f"{group_count} filtered" if self.only_orphans_flag else "non-filtered",
                    source_perspective_id=self.source_perspective_id
                )

                storage_dir = os.path.join(self.storage['path'], 'neuro_cognates')
                pickle_path = os.path.join(storage_dir, str(task.id))
                os.makedirs(storage_dir, exist_ok=True)

                with gzip.open(pickle_path, 'wb') as f:
                    pickle.dump(result_dict, f)

                result_link = f"{self.host_url}/suggestions/{task.id}"

            task.set(current_stage, progress, status, result_link)

        try:
            with Pool(processes=os.cpu_count() // 2) as pool:
                (input_words, input_trans, input_lex_ids, input_linked_groups), _ = self.split_items(word_pairs)
                args_list = zip([self] * len(input_words), input_words, input_trans, input_lex_ids, input_linked_groups)

                for result in pool.imap_unordered(process_batch, args_list):
                    add_result(result)
                    if os.path.exists(stamp_file):
                        pool.terminate()
                        raise InterruptedError("Task stopped manually")

        except InterruptedError:
            task.set(None, -1, "Stopped manually", result_link)

        finally:
            if os.path.exists(stamp_file):
                os.remove(stamp_file)

        return results

    def index(self, word_pairs, task):
        return NeuroCognates.predict_cognates.delay(
            self,
            word_pairs,
            task)
