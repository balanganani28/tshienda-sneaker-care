"""QR code generator with pure Python / PIL fallback."""
import io, base64
try:
    import qrcode
    from PIL import Image
    _HAS_QRCODE_LIB = True
except ImportError:
    _HAS_QRCODE_LIB = False
    try:
        from PIL import Image, ImageDraw
        _HAS_PIL = True
    except ImportError:
        _HAS_PIL = False

def _get_qr_matrix(data: str) -> list[list[int]]:
    if _HAS_QRCODE_LIB:
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        return qr.get_matrix()
    return _pure_python_qr_matrix(data)

def _pure_python_qr_matrix(text: str) -> list[list[int]]:
    data_bytes = text.encode('utf-8')
    data_len = len(data_bytes)
    if data_len <= 14: version, size, total_cw, ec_cw = 1, 21, 26, 10
    elif data_len <= 26: version, size, total_cw, ec_cw = 2, 25, 44, 16
    elif data_len <= 42: version, size, total_cw, ec_cw = 3, 29, 70, 26
    else: version, size, total_cw, ec_cw = 4, 33, 100, 36
    data_cw = total_cw - ec_cw
    bits = [0, 1, 0, 0]
    for b in format(data_len, '08b'): bits.append(int(b))
    for byte in data_bytes:
        for b in format(byte, '08b'): bits.append(int(b))
    needed_bits = data_cw * 8
    bits.extend([0] * min(4, needed_bits - len(bits)))
    while len(bits) % 8 != 0: bits.append(0)
    pad_bytes, p_idx = [0xEC, 0x11], 0
    while len(bits) < needed_bits:
        for b in format(pad_bytes[p_idx % 2], '08b'): bits.append(int(b))
        p_idx += 1
    raw = [int("".join(str(x) for x in bits[i:i+8]), 2) for i in range(0, len(bits), 8)]
    ec = _rs_compute(raw, ec_cw)
    full = raw + ec
    matrix = [[None for _ in range(size)] for _ in range(size)]
    _draw_finder(matrix, 0, 0); _draw_finder(matrix, size-7, 0); _draw_finder(matrix, 0, size-7)
    for i in range(8, size-8):
        v = 1 if i % 2 == 0 else 0
        if matrix[6][i] is None: matrix[6][i] = v
        if matrix[i][6] is None: matrix[i][6] = v
    matrix[size-8][8] = 1
    if version == 2: _draw_alignment(matrix, 18, 18)
    elif version == 3: _draw_alignment(matrix, 22, 22)
    elif version == 4: _draw_alignment(matrix, 26, 26)
    for i in range(9):
        if matrix[8][i] is None: matrix[8][i] = 0
        if matrix[i][8] is None: matrix[i][8] = 0
    for i in range(size-8, size):
        if matrix[8][i] is None: matrix[8][i] = 0
        if matrix[i][8] is None: matrix[i][8] = 0
    all_bits = []
    for b in full:
        for bit in format(b, '08b'): all_bits.append(int(bit))
    b_idx, row, col, dir_up = 0, size-1, size-1, True
    while col > 0:
        if col == 6: col -= 1
        for _ in range(size):
            for c_off in (0, -1):
                c, r = col + c_off, row
                if matrix[r][c] is None:
                    b_val = all_bits[b_idx] if b_idx < len(all_bits) else 0
                    if (r + c) % 2 == 0: b_val ^= 1
                    matrix[r][c] = b_val
                    b_idx += 1
            row += -1 if dir_up else 1
        dir_up = not dir_up; row += 1 if dir_up else -1; col -= 2
    f_bits = [1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0]
    seq1 = [(8,0),(8,1),(8,2),(8,3),(8,4),(8,5),(8,7),(8,8),(7,8),(5,8),(4,8),(3,8),(2,8),(1,8),(0,8)]
    for idx, (r, c) in enumerate(seq1): matrix[r][c] = f_bits[idx]
    for idx in range(7): matrix[size-1-idx][8] = f_bits[idx]
    for idx in range(8): matrix[8][size-8+idx] = f_bits[7+idx]
    return [[1 if matrix[r][c] else 0 for c in range(size)] for r in range(size)]

def _draw_finder(matrix, top, left):
    for r in range(7):
        for c in range(7):
            if r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4): matrix[top+r][left+c] = 1
            else: matrix[top+r][left+c] = 0
    for r in range(-1, 8):
        for c in range(-1, 8):
            nr, nc = top + r, left + c
            if 0 <= nr < len(matrix) and 0 <= nc < len(matrix) and matrix[nr][nc] is None: matrix[nr][nc] = 0

def _draw_alignment(matrix, cr, cc):
    for r in range(-2, 3):
        for c in range(-2, 3):
            matrix[cr+r][cc+c] = 1 if max(abs(r), abs(c)) in (0, 2) else 0

_GF_EXP, _GF_LOG = [0]*512, [0]*256
_x = 1
for _i in range(255):
    _GF_EXP[_i] = _x; _GF_EXP[_i + 255] = _x; _GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100: _x ^= 0x11D

def _gf_mul(x, y):
    if x == 0 or y == 0: return 0
    return _GF_EXP[_GF_LOG[x] + _GF_LOG[y]]

def _rs_compute(data, ec_cnt):
    gen = [1]
    for i in range(ec_cnt):
        term = [1, _GF_EXP[i]]
        new_gen = [0] * (len(gen) + 1)
        for j, g in enumerate(gen):
            new_gen[j] ^= g
            new_gen[j + 1] ^= _gf_mul(g, term[1])
        gen = new_gen
    rem = data + [0] * ec_cnt
    for i in range(len(data)):
        lead = rem[i]
        if lead != 0:
            for j in range(len(gen)): rem[i + j] ^= _gf_mul(gen[j], lead)
    return rem[len(data):]

def generate_qr_base64(data: str, box_size: int = 8, border: int = 2) -> str:
    matrix = _get_qr_matrix(data)
    n = len(matrix)
    img_size = (n + border * 2) * box_size
    img = Image.new('RGB', (img_size, img_size), '#FFFFFF')
    pixels = img.load()
    for r in range(n):
        for c in range(n):
            if matrix[r][c]:
                for y in range((r + border) * box_size, (r + border + 1) * box_size):
                    for x in range((c + border) * box_size, (c + border + 1) * box_size):
                        pixels[x, y] = (15, 23, 42)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    encoded = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{encoded}"
