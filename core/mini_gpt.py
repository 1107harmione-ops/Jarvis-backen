import os, math, random, pickle

random.seed(42)

n_layer = 1
n_embd = 16
block_size = 16
n_head = 4
head_dim = n_embd // n_head

class Value:
    __slots__ = ('data', 'grad', '_children', '_local_grads')
    def __init__(self, data, children=(), local_grads=()):
        self.data = data
        self.grad = 0
        self._children = children
        self._local_grads = local_grads
    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data + other.data, (self, other), (1, 1))
    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data * other.data, (self, other), (other.data, self.data))
    def __pow__(self, other): return Value(self.data**other, (self,), (other * self.data**(other-1),))
    def log(self): return Value(math.log(self.data), (self,), (1/self.data,))
    def exp(self): return Value(math.exp(self.data), (self,), (math.exp(self.data),))
    def relu(self): return Value(max(0, self.data), (self,), (float(self.data > 0),))
    def __neg__(self): return self * -1
    def __radd__(self, other): return self + other
    def __sub__(self, other): return self + (-other)
    def __rsub__(self, other): return other + (-self)
    def __rmul__(self, other): return self * other
    def __truediv__(self, other): return self * other**-1
    def __rtruediv__(self, other): return other * self**-1

state_dict = {}
uchars = []
BOS = 0
vocab_size = 0

def linear(x, w):
    return [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w]

def softmax(logits):
    max_val = max(logits)
    exps = [math.exp(val - max_val) for val in logits]
    total = sum(exps)
    return [e / total for e in exps]

def rmsnorm(x):
    ms = sum(xi * xi for xi in x) / len(x)
    scale = (ms + 1e-5) ** -0.5
    return [xi * scale for xi in x]

def _init_dummy_model():
    global state_dict, uchars, BOS, vocab_size
    print("[mini_gpt] Warning: model.pkl not found. Initializing dummy weights.")
    uchars = list("abcdefghijklmnopqrstuvwxyz ")
    BOS = len(uchars)
    vocab_size = len(uchars) + 1
    matrix = lambda nout, nin, std=0.08: [[Value(random.gauss(0, std)) for _ in range(nin)] for _ in range(nout)]
    state_dict = {'wte': matrix(vocab_size, n_embd), 'wpe': matrix(block_size, n_embd), 'lm_head': matrix(vocab_size, n_embd)}
    for i in range(n_layer):
        state_dict[f'layer{i}.attn_wq'] = matrix(n_embd, n_embd)
        state_dict[f'layer{i}.attn_wk'] = matrix(n_embd, n_embd)
        state_dict[f'layer{i}.attn_wv'] = matrix(n_embd, n_embd)
        state_dict[f'layer{i}.attn_wo'] = matrix(n_embd, n_embd)
        state_dict[f'layer{i}.mlp_fc1'] = matrix(4 * n_embd, n_embd)
        state_dict[f'layer{i}.mlp_fc2'] = matrix(n_embd, 4 * n_embd)

def load_model(filepath='model.pkl'):
    global state_dict, uchars, BOS, vocab_size
    if os.path.exists(filepath):
        try:
            with open(filepath, 'rb') as f:
                checkpoint = pickle.load(f)
                state_dict = checkpoint.get('state_dict', {})
                uchars = checkpoint.get('uchars', [])
                BOS = len(uchars)
                vocab_size = len(uchars) + 1
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            _init_dummy_model()
    else:
        _init_dummy_model()

load_model()

def gpt(token_id, pos_id, keys, values):
    def _val(v): return v.data if hasattr(v, 'data') else v
    tok_emb = [_val(v) for v in state_dict['wte'][token_id]]
    pos_emb = [_val(v) for v in state_dict['wpe'][pos_id]]
    x = [t + p for t, p in zip(tok_emb, pos_emb)]
    x = rmsnorm(x)
    for li in range(n_layer):
        x_residual = x
        x = rmsnorm(x)
        w_wq = [[_val(wi) for wi in wo] for wo in state_dict[f'layer{li}.attn_wq']]
        w_wk = [[_val(wi) for wi in wo] for wo in state_dict[f'layer{li}.attn_wk']]
        w_wv = [[_val(wi) for wi in wo] for wo in state_dict[f'layer{li}.attn_wv']]
        w_wo = [[_val(wi) for wi in wo] for wo in state_dict[f'layer{li}.attn_wo']]
        q = [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w_wq]
        k = [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w_wk]
        v = [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w_wv]
        keys[li].append(k)
        values[li].append(v)
        x_attn = []
        for h in range(n_head):
            hs = h * head_dim
            q_h = q[hs:hs+head_dim]
            k_h = [ki[hs:hs+head_dim] for ki in keys[li]]
            v_h = [vi[hs:hs+head_dim] for vi in values[li]]
            attn_logits = [sum(q_h[j] * k_h[t][j] for j in range(head_dim)) / (head_dim**0.5) for t in range(len(k_h))]
            attn_weights = softmax(attn_logits)
            head_out = [sum(attn_weights[t] * v_h[t][j] for t in range(len(v_h))) for j in range(head_dim)]
            x_attn.extend(head_out)
        x = [sum(wi * xi for wi, xi in zip(wo, x_attn)) for wo in w_wo]
        x = [a + b for a, b in zip(x, x_residual)]
        x_residual = x
        x = rmsnorm(x)
        w_fc1 = [[_val(wi) for wi in wo] for wo in state_dict[f'layer{li}.mlp_fc1']]
        w_fc2 = [[_val(wi) for wi in wo] for wo in state_dict[f'layer{li}.mlp_fc2']]
        x = [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w_fc1]
        x = [max(0, xi) for xi in x]
        x = [sum(wi * xi for wi, xi in zip(wo, x)) for wo in w_fc2]
        x = [a + b for a, b in zip(x, x_residual)]
    lm_head_w = [[_val(wi) for wi in wo] for wo in state_dict['lm_head']]
    logits = [sum(wi * xi for wi, xi in zip(wo, x)) for wo in lm_head_w]
    return logits

def generate_text(prompt: str = "", max_len: int = 30) -> str:
    temperature = 0.5
    keys, values = [[] for _ in range(n_layer)], [[] for _ in range(n_layer)]
    tokens = []
    for ch in prompt:
        if ch in uchars:
            tokens.append(uchars.index(ch))
    if not tokens:
        tokens = [BOS]
    sample = list(prompt)
    token_id = tokens[0]
    pos_id = 0
    logits = []
    for i in range(len(tokens)):
        token_id = tokens[i]
        logits = gpt(token_id, pos_id, keys, values)
        pos_id += 1
        if pos_id >= block_size:
            pos_id = block_size - 1
    for _ in range(max_len):
        if pos_id >= block_size:
            break
        probs = softmax([l / temperature for l in logits])
        token_id = random.choices(range(vocab_size), weights=probs)[0]
        if token_id == BOS:
            break
        sample.append(uchars[token_id])
        logits = gpt(token_id, pos_id, keys, values)
        pos_id += 1
    return ''.join(sample)

def handle_mini_gpt_command(user_input: str) -> dict:
    try:
        lower_input = user_input.lower()
        prompt = ""
        if "generate " in lower_input:
            prompt = lower_input.split("generate ")[1].strip()
        elif "name" in lower_input:
            parts = lower_input.split("name")
            if len(parts) > 1:
                prompt = parts[1].strip()
        prompt = prompt[:block_size - 1]
        response = generate_text(prompt=prompt, max_len=30)
        if not response.strip():
            response = "Generated a sequence, but it was empty."
        return {"status": "success", "response": response}
    except Exception as e:
        return {"status": "error", "response": f"Failed to generate text: {str(e)}"}
