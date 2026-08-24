import torch

# Имя подпапки с pth файлом
model_path = "model"

# Загрузка модели
device = torch.device('cuda')
checkpoint = torch.load(f'{model_path}/best_model.pth', map_location=device)
config = checkpoint.get('config')
char_to_index = checkpoint['char_to_index']
max_len = config.get('max_len')
vocab_size = len(char_to_index)


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


def text_to_tensor(text, char_to_index, max_len):
    indices = []
    for char in text[:max_len]:  # Обрезаем текст до max_len
        indices.append(char_to_index.get(char, 0))  # 0 для неизвестных символов
    indices += [0] * (max_len - len(indices))  # Паддинг нулями
    return torch.tensor([indices], dtype=torch.long).to(device)


real_data_examples = [
    # (word1, trans1, word2, trans2)
    ("hello", "hɛləʊ", "hola", "oʊlɑ"),
    ("world", "wɜrld", "mundo", "mʊndoʊ")
]

# Инициализация модели
model = DualPathSiamese(
    vocab_size=vocab_size,
    embed_dim=config.get('embed_dim'),
    max_len=max_len
).to(device)
model.load_state_dict(checkpoint['model_state_dict'])

# Переведите модель в eval режим
model.eval()

example_inputs = []
for word1, trans1, word2, trans2 in real_data_examples:
    word1_tensor = text_to_tensor(word1, char_to_index, max_len)
    trans1_tensor = text_to_tensor(trans1, char_to_index, max_len)
    word2_tensor = text_to_tensor(word2, char_to_index, max_len)
    trans2_tensor = text_to_tensor(trans2, char_to_index, max_len)
    example_inputs.append((word1_tensor, trans1_tensor, word2_tensor, trans2_tensor))
# Подготовка данных
data = example_inputs[0]
word1_tensor, trans1_tensor, word2_tensor, trans2_tensor = data

# Трассировка с явной передачей четырех тензоров
try:
    traced_model = torch.jit.trace(
        model,
        (word1_tensor, trans1_tensor, word2_tensor, trans2_tensor),
        check_trace=False  # Отключите строгую проверку для диагностики
    )
    traced_model.save(f"{model_path}/model.pt")
    print(traced_model.graph)
    print(traced_model.code)
    print("Трассировка успешна!")
except Exception as e:
    print(f"Ошибка: {e}")
