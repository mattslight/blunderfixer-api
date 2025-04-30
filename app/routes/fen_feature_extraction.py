# fen_feature_extraction.py
from fastapi import APIRouter
from pydantic import BaseModel
from collections import Counter
import chess

router = APIRouter()

class FeatureExtractionRequest(BaseModel):
    fen: str

PIECE_NAME = {
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
}

@router.post("/extract-features", summary="Extract position features from a FEN for LLM coaching")
def extract_features(req: FeatureExtractionRequest):
    board = chess.Board(req.fen)
    
    # Phase-1 & Phase-2 core features
    material        = get_material_balance(board)
    center          = get_center_control(board)
    king            = get_king_safety(board)
    open_files      = get_open_files(board)
    semi_open_files = get_semi_open_files(board)
    doubled         = get_doubled_pawns(board)
    pawn_struct     = get_pawn_structure(board)
    attacked        = get_attacked_pieces(board)
    activity        = get_piece_activity(board)
    mobility        = get_mobility(board)
    space           = get_space_advantage(board)
    loose_hanging   = get_loose_and_hanging_pieces(board)

    # New strategic/tactical features
    diagonals    = get_diagonals(board)
    has_bishop_pair = get_bishop_pair(board)
    weak_squares = get_weak_squares(board)
    passed_pawns = get_passed_pawns(board)
    outposts     = get_outposts(board)
    rook_place   = get_rook_placement(board, open_files, semi_open_files)

    # Grouped output
    features = {
        "material": material,
        "safety": {
            "king": king,
            "weak_squares": weak_squares
        },
        "structure": {
            "pawn_structure": pawn_struct,
            "doubled_pawns": doubled,
            "has_bishop_pair": has_bishop_pair,
            "passed_pawns": passed_pawns,
            "outposts": outposts
        },
        "center_control": center,
        "mobility": {
            "total": mobility,
            "per_piece": activity
        },
        "tactics": {
            "attacked_pieces": attacked,
            "loose_and_hanging_pieces": loose_hanging
        },
        "lines": {
            "open_files": open_files,
            "semi_open_files": semi_open_files,
            "diagonals": {
                "open": [d for d, status in diagonals.items() if status == "open"],
                "semi_open_white": [d for d, status in diagonals.items() if status == "semi_open_white"],
                "semi_open_black": [d for d, status in diagonals.items() if status == "semi_open_black"]
            },
            "rook_placement": rook_place
        },
        "space_advantage": space
    }

    return features

def get_material_balance(board):
    """
    Returns a dict with:
      - 'balance': (white_material – black_material) in pawn units
      - 'advantage': 'white', 'black', or 'equal'
    """
    piece_values = {
        chess.PAWN:   1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK:   5,
        chess.QUEEN:  9,
    }

    balance = 0
    for piece in board.piece_map().values():
        value = piece_values.get(piece.piece_type, 0)
        balance += value if piece.color == chess.WHITE else -value

    if balance > 0:
        adv = "white"
    elif balance < 0:
        adv = "black"
    else:
        adv = "equal"

    return {
        "balance": balance,
        "advantage": adv
    }

def get_center_control(board):
    center_squares = [chess.D4, chess.E4, chess.D5, chess.E5]
    white = sum(board.is_attacked_by(chess.WHITE, sq) for sq in center_squares)
    black = sum(board.is_attacked_by(chess.BLACK, sq) for sq in center_squares)
    return {"white": white, "black": black}

def get_king_safety(board):
    def analyze(color):
        king_sq = board.king(color)
        if king_sq is None:
            return {"status": "king missing"}

        info = {}
        opp = not color

        # 1. Castled status by current king square
        if color == chess.WHITE:
            if king_sq == chess.G1:
                info["status"] = "castled kingside"
            elif king_sq == chess.C1:
                info["status"] = "castled queenside"
        else:
            if king_sq == chess.G8:
                info["status"] = "castled kingside"
            elif king_sq == chess.C8:
                info["status"] = "castled queenside"

        # 2. Castling availability (legal right now)
        kingside_move  = chess.Move.from_uci("e1g1") if color == chess.WHITE else chess.Move.from_uci("e8g8")
        queenside_move = chess.Move.from_uci("e1c1") if color == chess.WHITE else chess.Move.from_uci("e8c8")
        legal_moves    = set(board.legal_moves)
        info["can_castle_kingside"]  = (kingside_move in legal_moves)
        info["can_castle_queenside"] = (queenside_move in legal_moves)

        # 3. In-check status by counting attackers on king square
        info["in_check"] = (len(board.attackers(opp, king_sq)) > 0)

        # 4. Number of enemy attackers on the king
        info["attackers"] = len(board.attackers(opp, king_sq))

        # 5. Pawn-shield quality: count friendly pawns on 3 shield squares
        file = chess.square_file(king_sq)
        rank = chess.square_rank(king_sq)
        forward = 1 if color == chess.WHITE else -1

        shield_count = 0
        for df in (-1, 0, 1):
            f = file + df
            r = rank + forward
            if 0 <= f <= 7 and 0 <= r <= 7:
                sq = chess.square(f, r)
                p = board.piece_at(sq)
                if p and p.piece_type == chess.PAWN and p.color == color:
                    shield_count += 1
        info["pawn_shield"] = shield_count

        # Default status if not castled
        info.setdefault("status", "uncastled or blocked")
        return info

    return {
        "white": analyze(chess.WHITE),
        "black": analyze(chess.BLACK),
    }


def get_open_files(board):
    open_files = []
    for file in range(8):
        if all(board.piece_at(chess.square(file, rank)) is None or board.piece_at(chess.square(file, rank)).piece_type != chess.PAWN for rank in range(8)):
            open_files.append(chr(file + ord('a')))
    return open_files

def get_semi_open_files(board):
    semi_open = {"white": [], "black": []}
    for file in range(8):
        file_squares = [chess.square(file, rank) for rank in range(8)]
        white_pawns = any(board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN and board.piece_at(sq).color == chess.WHITE for sq in file_squares)
        black_pawns = any(board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN and board.piece_at(sq).color == chess.BLACK for sq in file_squares)
        if not white_pawns and black_pawns:
            semi_open["white"].append(chr(file + ord('a')))
        if not black_pawns and white_pawns:
            semi_open["black"].append(chr(file + ord('a')))
    return semi_open

def get_doubled_pawns(board):
    doubled = {"white": [], "black": []}

    for color, side in ((chess.WHITE, "white"), (chess.BLACK, "black")):
        # Gather all pawn squares for that color
        pawn_sqs = board.pieces(chess.PAWN, color)
        # Count how many pawns appear on each file index (0=a … 7=h)
        file_counts = Counter(chess.square_file(sq) for sq in pawn_sqs)

        # Any file with count > 1 is doubled
        for file_idx, cnt in file_counts.items():
            if cnt > 1:
                file_letter = chr(file_idx + ord('a'))
                doubled[side].append(f"{file_letter}-file")

    return doubled


def get_attacked_pieces(board):
    """
    Returns a structured dict for each non-pawn, non-king piece under attack:
      {
        "white": [
          {
            "piece": "Knight",
            "square": "e5",
            "attackers": [
              {"piece": "Queen", "square": "c7"},
              {"piece": "Knight", "square": "d5"}
            ]
          },
          ...
        ],
        "black": [ ... ]
      }
    """
    attacked = {"white": [], "black": []}

    for square, piece in board.piece_map().items():
        # Only consider knight, bishop, rook, queen
        if piece.piece_type not in PIECE_NAME:
            continue

        attackers = board.attackers(not piece.color, square)
        if not attackers:
            continue

        side = "white" if piece.color == chess.WHITE else "black"
        entry = {
            "piece": PIECE_NAME[piece.piece_type],
            "square": chess.square_name(square),
            "attackers": []
        }

        # List each attacker by full name and square
        for a_sq in sorted(attackers):
            attacker = board.piece_at(a_sq)
            if attacker and attacker.piece_type in PIECE_NAME:
                entry["attackers"].append({
                    "piece": PIECE_NAME[attacker.piece_type],
                    "square": chess.square_name(a_sq)
                })

        attacked[side].append(entry)

    return attacked

def get_piece_activity(board):
    """
    Returns piece activity as:
    {
      "white": [
        { "piece": "Knight", "square": "f3", "move_count": 5, "moves": ["f3e5","f3g5",...] },
        ...
      ],
      "black": [ ... ]
    }
    """
    result = {"white": [], "black": []}

    def collect(color, side):
        b = board.copy()
        b.turn = color
        seen = {}
        for move in b.legal_moves:
            p = b.piece_at(move.from_square)
            if not p or p.piece_type not in PIECE_NAME:
                continue
            key = (p.piece_type, move.from_square)
            seen.setdefault(key, []).append(move.uci())
        # build list  
        for (ptype, sq), mvlist in seen.items():
            result[side].append({
                "piece": PIECE_NAME[ptype],
                "square": chess.square_name(sq),
                "move_count": len(mvlist),
                "moves": mvlist
            })

    collect(chess.WHITE, "white")
    collect(chess.BLACK, "black")
    return result



def get_pawn_structure(board):
    pawn_structure = {"white": [], "black": []}

    # First, compute open and semi-open files for each side
    open_files = []
    semi_open = {"white": [], "black": []}
    for f in range(8):
        squares = [chess.square(f, r) for r in range(8)]
        has_wp = any(board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN and board.piece_at(sq).color == chess.WHITE for sq in squares)
        has_bp = any(board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN and board.piece_at(sq).color == chess.BLACK for sq in squares)
        if not has_wp and not has_bp:
            open_files.append(f)
        if not has_wp and has_bp:
            semi_open["white"].append(f)
        if has_wp and not has_bp:
            semi_open["black"].append(f)

    for color in [chess.WHITE, chess.BLACK]:
        side = "white" if color == chess.WHITE else "black"
        pawns = board.pieces(chess.PAWN, color)

        for pawn_sq in pawns:
            file = chess.square_file(pawn_sq)
            rank = chess.square_rank(pawn_sq)

            # 1) Isolated pawn?
            adj_files = [file - 1, file + 1]
            is_isolated = True
            for af in adj_files:
                if 0 <= af <= 7 and any(chess.square_file(p) == af for p in pawns):
                    is_isolated = False
                    break
            if is_isolated:
                pawn_structure[side].append(f"isolated pawn on {chess.square_name(pawn_sq)}")
                continue

            # 2) Only consider backward on open/semi-open
            if file not in open_files and file not in semi_open[side]:
                continue

            # 3) If the square in front is empty…
            forward = 1 if color == chess.WHITE else -1
            front_rank = rank + forward
            if not (0 <= front_rank <= 7):
                continue
            front_sq = chess.square(file, front_rank)
            if board.piece_at(front_sq) is not None:
                continue

            # 4) Count attackers vs defenders on that front square
            attackers = len(board.attackers(not color, front_sq))
            defenders = len(board.attackers(color, front_sq))

            # 5) Ensure no adjacent pawn can ever defend the front square
            can_defend = False
            for af in adj_files:
                if 0 <= af <= 7:
                    for r in (rank, front_rank):
                        sq = chess.square(af, r)
                        p = board.piece_at(sq)
                        if p and p.piece_type == chess.PAWN and p.color == color:
                            can_defend = True
                            break
                    if can_defend:
                        break

            # 6) If front square is under-defended and undefendable → backward pawn
            if not can_defend and attackers > defenders:
                pawn_structure[side].append(f"backward pawn on {chess.square_name(pawn_sq)}")

    return pawn_structure



def get_mobility(board):
    """
    Returns how many legal moves each side could make,
    regardless of whose turn it currently is.
    """
    # White’s mobility
    wb = board.copy()
    wb.turn = chess.WHITE
    white_moves = len(list(wb.legal_moves))

    # Black’s mobility
    bb = board.copy()
    bb.turn = chess.BLACK
    black_moves = len(list(bb.legal_moves))

    return {"white_moves": white_moves, "black_moves": black_moves}



def get_space_advantage(board):
    white_count = 0
    black_count = 0

    for square, piece in board.piece_map().items():
        rank = chess.square_rank(square)
        if piece.color == chess.WHITE and rank >= 4:
            white_count += 1
        elif piece.color == chess.BLACK and rank <= 3:
            black_count += 1

    if white_count > black_count:
        winner = "white"
    elif black_count > white_count:
        winner = "black"
    else:
        winner = "equal"

    return {
        "white_space": white_count,
        "black_space": black_count,
        "advantage": winner
    }


def get_loose_and_hanging_pieces(board):
    """
    Identify non-pawn, non-king pieces that are:
      - 'hanging': attacked by more enemies than defenders
      - 'loose': attacked by exactly as many enemies as defenders (and at least once)
    Also reports how many attackers and their piece types.
    """
    pieces = {"white": {"loose": [], "hanging": []}, "black": {"loose": [], "hanging": []}}

    for square, piece in board.piece_map().items():
        # Skip pawns and kings
        if piece.piece_type in (chess.PAWN, chess.KING):
            continue

        # Gather attackers and defenders sets
        attackers_sqs = board.attackers(not piece.color, square)
        defenders_sqs = board.attackers(piece.color, square)
        attackers = len(attackers_sqs)
        defenders = len(defenders_sqs)

        # Nothing to do if not attacked
        if attackers == 0:
            continue

        side = "white" if piece.color == chess.WHITE else "black"
        sq_name = chess.square_name(square)

        # Normalize attacker piece types to uppercase symbols
        attacker_types = sorted({board.piece_at(a).symbol().upper() for a in attackers_sqs})
        types_str = ", ".join(attacker_types)

        # Classify hanging vs loose
        if attackers > defenders:
            desc = f"{piece.symbol()} on {sq_name} is hanging (attacked by {attackers}: {types_str})"
            pieces[side]["hanging"].append(desc)
        elif attackers == defenders:
            desc = f"{piece.symbol()} on {sq_name} is loose (attacked by {attackers}: {types_str})"
            pieces[side]["loose"].append(desc)

    return pieces

def get_diagonals(board):
    diagonals = {}
    # a1–h8 direction
    for d in range(-7, 8):
        sqs = [sq for sq in chess.SQUARES
               if chess.square_file(sq) - chess.square_rank(sq) == d]
        if len(sqs) < 4:                      # ← only keep len ≥ 4
            continue
        sqs.sort(key=lambda sq: (chess.square_rank(sq), chess.square_file(sq)))
        name = f"{chess.square_name(sqs[0])}-{chess.square_name(sqs[-1])}"
        pawns = [sq for sq in sqs
                 if (p := board.piece_at(sq)) and p.piece_type == chess.PAWN]
        if not pawns:
            diagonals[name] = "open"
        else:
            wp = any(board.piece_at(sq).color == chess.WHITE for sq in pawns)
            bp = any(board.piece_at(sq).color == chess.BLACK for sq in pawns)
            if wp and not bp:
                diagonals[name] = "semi_open_white"
            elif bp and not wp:
                diagonals[name] = "semi_open_black"
            else:
                diagonals[name] = "blocked"

    # h1–a8 direction
    for s in range(1, 15):
        sqs = [sq for sq in chess.SQUARES
               if chess.square_file(sq) + chess.square_rank(sq) == s]
        if len(sqs) < 4:                      # ← only keep len ≥ 4
            continue
        sqs.sort(key=lambda sq: (chess.square_rank(sq), -chess.square_file(sq)))
        name = f"{chess.square_name(sqs[0])}-{chess.square_name(sqs[-1])}"
        pawns = [sq for sq in sqs
                 if (p := board.piece_at(sq)) and p.piece_type == chess.PAWN]
        if not pawns:
            diagonals[name] = "open"
        else:
            wp = any(board.piece_at(sq).color == chess.WHITE for sq in pawns)
            bp = any(board.piece_at(sq).color == chess.BLACK for sq in pawns)
            if wp and not bp:
                diagonals[name] = "semi_open_white"
            elif bp and not wp:
                diagonals[name] = "semi_open_black"
            else:
                diagonals[name] = "blocked"

    return diagonals



def get_bishop_pair(board):
    """
    True for each side if they have two or more bishops.
    """
    return {
        "white": len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2,
        "black": len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2,
    }


def get_weak_squares(board):
    """
    Squares adjacent to each king that:
      - share the king-square color complex (light vs dark)
      - are attacked by the opponent
      - are NOT defended by a friendly pawn
    """
    weak = {"white": [], "black": []}

    for color in (chess.WHITE, chess.BLACK):
        king_sq = board.king(color)
        if king_sq is None:
            continue

        # Determine the king-square’s color complex: 0=dark, 1=light
        file_k = chess.square_file(king_sq)
        rank_k = chess.square_rank(king_sq)
        complex_color = (file_k + rank_k) % 2

        opp = not color
        side = "white" if color == chess.WHITE else "black"

        # Check eight neighboring squares
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                f = file_k + df
                r = rank_k + dr
                if not (0 <= f <= 7 and 0 <= r <= 7):
                    continue

                sq = chess.square(f, r)
                # Skip if not same color complex
                if (f + r) % 2 != complex_color:
                    continue
                # Must be attacked by the opponent
                if not board.attackers(opp, sq):
                    continue
                # Must NOT be defended by a friendly pawn
                defenders = board.attackers(color, sq)
                if any(board.piece_at(a).piece_type == chess.PAWN for a in defenders):
                    continue

                weak[side].append(chess.square_name(sq))

    return weak



def get_passed_pawns(board):
    """
    Pawns for which there is NO enemy pawn on the same file or adjacent files
    in the direction of promotion.
    """
    passed = {"white": [], "black": []}

    for color, side in ((chess.WHITE, "white"), (chess.BLACK, "black")):
        direction = 1 if color == chess.WHITE else -1
        enemy = not color

        for sq in board.pieces(chess.PAWN, color):
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            is_passed = True

            # check same + adjacent files ahead
            for af in (file - 1, file, file + 1):
                if 0 <= af <= 7:
                    # ranks in front of the pawn
                    ranks = range(rank + direction, 8) if color == chess.WHITE else range(rank + direction, -1, -1)
                    for rr in ranks:
                        target = chess.square(af, rr)
                        p = board.piece_at(target)
                        if p and p.piece_type == chess.PAWN and p.color == enemy:
                            is_passed = False
                            break
                    if not is_passed:
                        break

            if is_passed:
                passed[side].append(chess.square_name(sq))

    return passed


def is_dislodgeable(board: chess.Board, sq: int, enemy: bool) -> bool:
    """
    True if an enemy pawn on an adjacent file can push (eventually) to attack sq.
    """
    file, rank = chess.square_file(sq), chess.square_rank(sq)
    for df in (-1, 1):
        f = file + df
        if not 0 <= f < 8:
            continue
        # WHITE pawns push up from ranks < rank; BLACK pawns push down from ranks > rank
        ranks = range(rank) if enemy == chess.WHITE else range(rank + 1, 8)
        for r in ranks:
            p_sq = chess.square(f, r)
            p = board.piece_at(p_sq)
            if p and p.piece_type == chess.PAWN and board.color_at(p_sq) == enemy:
                return True
    return False


def get_outposts(board: chess.Board) -> dict:
    """
    Loose outpost for knight or bishop on 4th–7th rank (idx 3–6):
     - pawn-protected
     - no direct pawn-attacks
     - not is_dislodgeable (no pawn can push to attack)
    Returns lists like “Knight on d5” or “Bishop on e6”.
    """
    outposts = {"white": [], "black": []}

    for color, side in ((chess.WHITE, "white"), (chess.BLACK, "black")):
        enemy = not color
        for piece_type in (chess.KNIGHT, chess.BISHOP):
            name = chess.piece_name(piece_type).capitalize()  # “Knight” or “Bishop”
            for sq in board.pieces(piece_type, color):
                r = chess.square_rank(sq)
                if not (3 <= r <= 6):
                    continue
                # 1) pawn-protected?
                if not any(
                    board.piece_at(a)
                    and board.piece_at(a).piece_type == chess.PAWN
                    and board.color_at(a) == color
                    for a in board.attackers(color, sq)
                ):
                    continue
                # 2) no direct pawn attacks
                if any(
                    board.piece_at(a)
                    and board.piece_at(a).piece_type == chess.PAWN
                    for a in board.attackers(enemy, sq)
                ):
                    continue
                # 3) no pawn pushes
                if is_dislodgeable(board, sq, enemy):
                    continue

                square = chess.square_name(sq)
                outposts[side].append(f"{name} on {square}")

    return outposts



def get_rook_placement(board, open_files, semi_open_files):
    """
    For each rook, note if it sits on an open or semi-open file.
    `open_files` is a list like ['a','d'], `semi_open_files` a dict with 'white'/'black' lists.
    """
    placement = {"white": {"open": [], "semi_open": []}, "black": {"open": [], "semi_open": []}}

    for color, side in ((chess.WHITE, "white"), (chess.BLACK, "black")):
        for sq in board.pieces(chess.ROOK, color):
            file_letter = chr(chess.square_file(sq) + ord("a"))
            sq_name = chess.square_name(sq)
            if file_letter in open_files:
                placement[side]["open"].append(sq_name)
            elif file_letter in semi_open_files[side]:
                placement[side]["semi_open"].append(sq_name)

    return placement
