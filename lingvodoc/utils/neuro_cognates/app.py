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
    print(f"{ext=}")

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

    base_word_tensor = self._process_text(input_word)
    base_tran_tensor = self._process_text(input_tran)

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
                'word2': torch.stack([self._process_text(w) for w in compare_words]),
                'trans2': torch.stack([self._process_text(t) for t in compare_trans])
            }

            inputs = []

            for field, tensor in batch.items():
                inputs.append(grpcclient.InferInput(field, [batch_size, self.max_len], "INT32"))
                inputs[-1].set_data_from_numpy(np.array(tensor, dtype=np.int32))

            # Prediction
            #print(f"{'':<15}{'Infering...':<15}", end="", flush=True)
            with torch.no_grad():
                outputs = triton_client.infer("neuro_cognates", inputs)
                #probs = torch.sigmoid(outputs).squeeze()
                probs = torch.sigmoid(torch.tensor([out[0] for out in outputs.as_numpy('output')])).cpu().numpy().flatten()
            #print("DONE", flush=True)

            # Init reranker
            #print(f"{'':<15}{'Init reranker':<15}", end="", flush=True)
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
                [f"{compare_words[j]}:{compare_trans[j]}"
                 for j in range(batch_size) if probs[j].item() > self.truth_threshold]
            )
            #print(f"{'':<30}Reranked!", flush=True)

            for idx, (_, _, _, rank) in enumerate(ranks):
                similarities.append((
                    i,
                    [compare_words[idx], compare_trans[idx]],
                    compare_ids[idx],
                    f'{rank:.4f}'
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
        )] if similarities else [], links)


class NeuroCognates:
    def __init__(self,
                 compare_lists,
                 input_index,
                 source_perspective_id,
                 perspective_name_list,
                 language_name_list,
                 storage,
                 host_url,
                 cache_kwargs,
                 truth_threshold=0.97,
                 only_orphans_flag=True):

        self.compare_lists = compare_lists
        self.input_index = input_index
        self.source_perspective_id = source_perspective_id
        self.truth_threshold = truth_threshold
        self.perspective_name_list = perspective_name_list
        self.language_name_list = language_name_list
        self.storage = storage
        self.host_url = host_url
        self.cache_kwargs = cache_kwargs
        self.only_orphans_flag = only_orphans_flag

        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)

        # Load model
        checkpoint = torch.load(os.path.join(script_dir, 'best_model.pth'))  # map_location=self.device)
        config = checkpoint.get('config', {})

        self.max_len = config.get('max_len', 43)
        self.char_to_index = checkpoint['char_to_index']

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

    def _process_text(self, text):
        indices = [self.char_to_index.get(c, 1) for c in text.lower()[:self.max_len]]
        indices += [0] * (self.max_len - len(indices))
        return torch.tensor(indices, dtype=torch.int32)  # device=self.device)

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
                    source_perspective_id=self.source_perspective_id
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

        ft_model = load_fasttext_model(
            os.path.join(os.path.dirname(__file__), 'cc.ru.300.vec'))

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
                memory_free_mibs = 25000

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
                        #print(f"{idx + 1:>5} of {input_len:<5} {'Processing...':<15}", end="", flush=True)
                        result = jobs.next(timeout=120)
                        add_result(result)
                        #print("DONE", flush=True)

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
