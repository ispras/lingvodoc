import torch
#import torch.nn as nn
from torch.multiprocessing import Pool, set_start_method
import os
import gzip
import pickle
from time import sleep, time as now
from lingvodoc.queue.celery import celery
from lingvodoc.cache.caching import TaskStatus, initialize_cache
import tritonclient.grpc as grpcclient
import numpy as np
import requests
import re
import json
import unicodedata

from lingvodoc.utils.neuro_cognates.rerank import RerankerSingleWord
from pdb import set_trace as A

# Model is hosted on remote server now. This code is used there.
'''
# Choose model architecture
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
        self.match_coef = nn.Parameter(torch.tensor(0.8), requires_grad=False)

        self.classifier = nn.Sequential(
            nn.Linear(4 * 128, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(256, 1)
        )

        self.init_weights()

    def _get_exact_match(self, trans1, trans2):
        """Сравнение первых 4 символов в переводах"""
        t1_first4 = trans1[:, :4]  # [B, 4]
        t2_first4 = trans2[:, :4]  # [B, 4]

        # Сравниваем символы и учитываем паддинг
        exact_match = (t1_first4 == t2_first4).all(dim=1).float().unsqueeze(1)
        return exact_match

    def init_weights(self):
        for name, module in self.named_modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.constant_(module.bias, 0)
            elif isinstance(module, nn.LSTM):
                for name, param in module.named_parameters():
                    if 'weight_ih' in name:
                        nn.init.xavier_uniform_(param)
                    elif 'weight_hh' in name:
                        nn.init.orthogonal_(param)
                    elif 'bias' in name:
                        nn.init.constant_(param, 0)

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

        exact_match = self._get_exact_match(trans1, trans2)

        base_pred = self.classifier(combined)
        return base_pred + self.match_coef * exact_match

    def freeze_layers(self):
        # Заморозка первых слоев
        for name, param in self.named_parameters():
            if any([s in name for s in ['embedding', 'pos_embed', 'word_encoder.0', 'trans_encoder.0']]):
                param.requires_grad = False
'''


def _load_json(path):
    with open(path, encoding='utf-8') as source:
        return json.load(source)


class Stage2TextPreprocessor:
    PAD = '<PAD>'
    UNK = '<UNK>'
    BOS = '<BOS>'
    EOS = '<EOS>'

    TRANSLATION_PAD = 0
    TRANSLATION_BOS = 1
    TRANSLATION_EOS = 2
    TRANSLATION_SEP = 3
    TRANSLATION_BYTE_OFFSET = 4

    def __init__(self, model_dir):
        word_data = _load_json(
            os.path.join(model_dir, 'word_tokenizer.json'))
        stage1_config = _load_json(
            os.path.join(model_dir, 'stage1_model_config.json'))
        stage2_config = _load_json(
            os.path.join(model_dir, 'stage2_model_config.json'))

        self.word_token_to_id = {
            token: index
            for index, token in enumerate(word_data['tokens'])
        }
        for token in (self.PAD, self.UNK, self.BOS, self.EOS):
            if token not in self.word_token_to_id:
                raise ValueError(
                    f'word_tokenizer.json has no {token} token')

        self.unicode_form = word_data.get('unicode_form', 'NFC')
        self.casefold = bool(word_data.get('casefold', True))
        self.max_word_length = int(stage1_config['max_word_length'])
        self.max_translation_bytes = int(
            stage2_config['max_translation_bytes'])

    @staticmethod
    def _truncate_middle(values, available):
        if len(values) <= available:
            return values
        left_count = (available + 1) // 2
        right_count = available - left_count
        return values[:left_count] + (
            values[-right_count:] if right_count else [])

    def encode_word(self, value):
        if value is None:
            text = ''
        else:
            text = str(value)
            if text.casefold() in {'nan', 'none', 'null', '-'}:
                text = ''
        text = unicodedata.normalize(self.unicode_form, text)
        text = re.sub(r'\s+', ' ', text.strip())
        if self.casefold:
            text = text.casefold()

        unknown = self.word_token_to_id[self.UNK]
        body = [
            self.word_token_to_id.get(character, unknown)
            for character in text
        ]
        body = self._truncate_middle(
            body, self.max_word_length - 2)
        indices = [
            self.word_token_to_id[self.BOS],
            *body,
            self.word_token_to_id[self.EOS],
        ]
        indices += [self.word_token_to_id[self.PAD]] * (
            self.max_word_length - len(indices))
        return torch.tensor(indices, dtype=torch.int32)

    def encode_translation(self, value):
        if value is None:
            text = ''
        else:
            text = unicodedata.normalize(
                'NFC', str(value)).casefold().strip()
        text = re.sub(r'\s*[;/|]+\s*', ' ; ', text)
        text = re.sub(r'\s*,\s*', ' , ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.replace(
            ' ; ', ' <SEP> ').replace(' , ', ' <SEP> ')

        body = []
        for index, piece in enumerate(text.split('<SEP>')):
            if index:
                body.append(self.TRANSLATION_SEP)
            body.extend(
                byte + self.TRANSLATION_BYTE_OFFSET
                for byte in piece.strip().encode('utf-8'))
        body = self._truncate_middle(
            body, self.max_translation_bytes - 2)
        indices = [
            self.TRANSLATION_BOS,
            *body,
            self.TRANSLATION_EOS,
        ]
        indices += [self.TRANSLATION_PAD] * (
            self.max_translation_bytes - len(indices))
        return torch.tensor(indices, dtype=torch.int32)


## fast text отдельно
def load_fasttext_model(path: str):
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
    root = os.path.splitext(path)[0].lower()
    ext = os.path.splitext(root)[1].lower()
    ext += os.path.splitext(path)[1].lower()
    #print(f"{ext=}")

    print(f"{'Loading gensim...':<30}", end="", flush=True)
    try:
        from gensim.models import KeyedVectors
    except ImportError:
        raise ImportError("Please install gensim: pip install gensim")
    print("DONE", flush=True)

    print(f"{'Loading fasttext model...':<30}", end="", flush=True)
    result = KeyedVectors.load_word2vec_format(
        path,
        binary=('.vec' not in ext),
        unicode_errors='ignore',
        #limit=10**6
    )
    print("DONE", flush=True)

    return result


def process_batch(args):
    self, ft_model, input_word, input_tran, input_id, input_links = args
    similarities = []
    inferring_duration = 0
    rerank_duration = 0

    base_word_tensor = self._process_word(input_word)
    base_tran_tensor = self._process_translation(input_tran)

    with grpcclient.InferenceServerClient(url="10.100.192.136:8001") as triton_client:

        for i, compare_list in enumerate(self.compare_lists):
            if not compare_list:
                continue

            (compare_words, compare_trans, compare_ids, _), links = (
                self.split_items(compare_list, input_links))

            # Batch creation
            batch_size = len(compare_words)
            batch = {
                'word1': base_word_tensor.repeat(batch_size, 1),
                'trans1': base_tran_tensor.repeat(batch_size, 1),
                'word2': torch.stack([
                    self._process_word(w)
                    for w in compare_words
                ]),
                'trans2': torch.stack([
                    self._process_translation(t)
                    for t in compare_trans
                ])
            }

            inputs = []

            for field, tensor in batch.items():
                inputs.append(grpcclient.InferInput(
                    field,
                    list(tensor.shape),
                    "INT32"
                ))
                inputs[-1].set_data_from_numpy(np.array(tensor, dtype=np.int32))

            # Prediction
            #print(f"{'':<15}{'Inferring...':<15}", end="", flush=True)
            inferring_start = now()
            with torch.no_grad():
                outputs = triton_client.infer(f"neuro_{self.mode}", inputs)
                logits = torch.from_numpy(
                    outputs.as_numpy('output')
                ).reshape(-1)
                probs = torch.sigmoid(logits).cpu().numpy()
            inferring_duration += now() - inferring_start
            #print("DONE", flush=True)

            outputs = []

            for word, trans, ids, prob in zip(compare_words, compare_trans, compare_ids, [p.item() for p in probs]):
                if prob >= self.truth_threshold:
                    outputs.append({
                        'word': word,
                        'trans': trans,
                        'ids': ids,
                        'prob': prob
                    })

            """
            # Init reranker
            #print(f"{'':<15}{'Init reranker':<15}", end="", flush=True)
            rerank_start = now()
            reranker = RerankerSingleWord(
                ft_model,
                self.language_name_list[self.input_index],
                self.language_name_list[i]
            )
            #print("DONE", flush=True)

            # Compute rerank value
            #print(f"{'':<15}{'Reranking...':<15}", flush=True)
            ranks = reranker.rerank(
                f"{input_word}:{input_tran}",
                [f"{outputs[j]['word']}:{outputs[j]['trans']}" for j in range(len(outputs))]
            )
            rerank_duration += now() - rerank_start
            #print(f"{'':<30}Reranked!", flush=True)
            """
            # Dirty hack
            ranks = [[0, 0, 0, 0]] * len(outputs)

            for n in range(len(outputs)):
                similarities.append((
                    i,
                    [outputs[n]['word'], outputs[n]['trans']],
                    outputs[n]['ids'],
                    f"{(outputs[n]['prob'] + ranks[n][3]):.4f}"
                ))

    similarities.sort(key=lambda s: s[3], reverse=True)

    return (
        [(
            self.input_index,
            f"{input_word} '{input_tran}'",
            input_id,
            None,
            similarities[:5],
            []
        )] if similarities else [], links, inferring_duration, rerank_duration)


class NeuroCognates:
    def __init__(self,
                 mode,
                 compare_lists,
                 input_index,
                 source_perspective_id,
                 perspective_name_list,
                 language_name_list,
                 storage,
                 host_url,
                 cache_kwargs,
                 truth_threshold=None,
                 only_orphans_flag=True,
                 suggestion_field_id=(66, 25)):

        self.mode = mode
        self.compare_lists = compare_lists
        self.input_index = input_index
        self.source_perspective_id = source_perspective_id
        self.perspective_name_list = perspective_name_list
        self.language_name_list = language_name_list
        self.storage = storage
        self.host_url = host_url
        self.cache_kwargs = cache_kwargs
        self.only_orphans_flag = only_orphans_flag
        self.suggestion_field_id = suggestion_field_id

        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)

        if self.mode == 'borrowing':
            self.preprocessor = Stage2TextPreprocessor(script_dir)
            calibration = _load_json(
                os.path.join(script_dir, 'calibration.json'))
            self.truth_threshold = float(
                calibration['threshold']
                if truth_threshold is None
                else truth_threshold
            )
        elif self.mode == 'cognates':
            checkpoint = torch.load(
                os.path.join(script_dir, 'best_model.pth'))
            config = checkpoint.get('config', {})
            self.max_len = config.get('max_len', 43)
            self.char_to_index = checkpoint['char_to_index']
            self.truth_threshold = float(
                0.97 if truth_threshold is None else truth_threshold)
        self.inferring_sumtime = 0
        self.rerank_sumtime = 0

        '''
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        self.model = DualPathSiamese(
            vocab_size=len(checkpoint['char_to_index']),
            embed_dim=config.get('embed_dim', 128),
            max_len=config.get('max_len', 43)
        ).to(self.device)

        self.model.load_state_dict(checkpoint['model_state_dict'])

        if 'alpha' in config:
            self.model.alpha.data.fill_(config['alpha'])
        if 'beta' in config:
            self.model.beta.data.fill_(config['beta'])
        if 'match_coef' in config:
            self.model.match_coef.data.fill_(config['match_coef'])

        self.model.eval()
        '''

    def _process_legacy_text(self, text):
        indices = [self.char_to_index.get(c, 1) for c in text.lower()[:self.max_len]]
        indices += [0] * (self.max_len - len(indices))
        return torch.tensor(indices, dtype=torch.int32)  # device=self.device)

    def _process_word(self, text):
        if self.mode == 'borrowing':
            return self.preprocessor.encode_word(text)
        return self._process_legacy_text(text)

    def _process_translation(self, text):
        if self.mode == 'borrowing':
            return self.preprocessor.encode_translation(text)
        return self._process_legacy_text(text)

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

            result, links, _, _ = res
            results.extend(result)
            group_count += links
            current_stage += 1
            finished = (current_stage == input_len)

            # Task status
            passed = now() - start_time
            left = passed / current_stage * input_len - passed

            days = int(left / 86400)
            hours = int((left - days * 86400) / 3600)
            minutes = int((left - days * 86400 - hours * 3600) / 60)

            progress = 100 if finished else int(current_stage / input_len * 100)
            status = "Finished" if finished else f"~ {days}d:{hours}h:{minutes}m left ~"

            # Save results
            if current_stage % 10 == 0 or finished:
                result_dict = dict(
                    suggestion_list=results,
                    perspective_name_list=self.perspective_name_list,
                    transcription_count=compare_len * current_stage,
                    group_count=f"{group_count} filtered" if self.only_orphans_flag else "non-filtered",
                    source_perspective_id=self.source_perspective_id,
                    suggestion_field_id=self.suggestion_field_id
                )

                storage_dir = os.path.join(self.storage['path'], 'neuro_cognates')
                pickle_path = os.path.join(storage_dir, str(task.id))
                os.makedirs(storage_dir, exist_ok=True)

                with gzip.open(pickle_path, 'wb') as f:
                    pickle.dump(result_dict, f)

                result_link = f"{self.host_url}/suggestions/{task.id}"

            task.set(current_stage, progress, status, result_link)

        (input_words, input_trans, input_lex_ids, input_linked_groups), _ = self.split_items(word_pairs)

        task.set(None, 0, f"Loading fasttext model...")

        """
        ft_model = load_fasttext_model(
            os.path.join('/', 'opt', 'fasttext', 'cc.ru.300.vec'))
        """

        # Dirty hack
        ft_model = None

        args_list = zip(
            [self] * input_len,
            [ft_model] * input_len,
            input_words,
            input_trans,
            input_lex_ids,
            input_linked_groups
        )

        def f(proc):
            nonlocal start_time
            pool = None
            task.set(None, 0, f"Using {proc} process(es)...")

            try:
                memory_free_mibs = 10**5  # this is like a limit

                # Check metrics 15 times every second
                for i in range(15):
                    memory_values = []

                    if i:
                        sleep(1)

                    metrics_req = requests.get("http://10.100.192.136:8002/metrics")

                    if metrics_req.status_code != 200:
                        raise ConnectionRefusedError("Server is not available now. Please ask administrator.")

                    for value in 'total', 'used':
                        memory_values.append(
                            int(re.search(f'\nnv_gpu_memory_{value}_bytes[^\s]* ([\d]*)', metrics_req.text).group(1)))

                    memory_free_mibs = min((memory_values[0] - memory_values[1]) / (2**20), memory_free_mibs)

                memory_free_words = int(memory_free_mibs * 1.55)  # coef 1.55 is selected empirically

                if compare_len > memory_free_words:
                    raise MemoryError("No enough memory for this task now. Try again later.")

                pool = Pool(proc)
                jobs = pool.imap_unordered(process_batch, args_list)
                start_time = now()  # correcting start time after metrics checking
                pool.close()

                for idx in range(input_len):
                    if os.path.exists(stamp_file):
                        os.remove(stamp_file)
                        raise InterruptedError("Task stopped manually")

                    else:
                        print(f"{idx + 1:>5} of {input_len:<5} {'Processing...':<15}", end="", flush=True)
                        result = jobs.next(timeout=300)
                        add_result(result)
                        self.inferring_sumtime += result[2]
                        self.rerank_sumtime += result[3]
                        print(f"DONE: {self.inferring_sumtime=:.3f} | {self.rerank_sumtime=:.3f}", flush=True)

            except RuntimeError:
                msg = "No enough memory for the task"

                if proc > 1:
                    task.set(None, -1, msg)
                    pool.terminate()
                    f(proc - 1)
                    return

                else:
                    raise MemoryError(msg)

            except (InterruptedError, ConnectionRefusedError, MemoryError) as e:
                task.set(None, -1, str(e), result_link)

                if pool is not None:
                    pool.terminate()

                return

            except Exception as e:
                print(e)
                task.set(None, -1, "Something went wrong, probably server is busy. Try again later.", result_link)

                if pool is not None:
                    pool.terminate()

                return

        set_start_method('spawn')
        f(1)

        return results

    def index(self, word_pairs, task):
        return self.predict_cognates.delay(
            self,
            word_pairs,
            task)
