import chess

HIGH_VALUE = {chess.QUEEN, chess.ROOK, chess.KING}
SLIDERS = {chess.BISHOP, chess.ROOK, chess.QUEEN}
DIRECTIONS = [8, -8, 1, -1, 9, -9, 7, -7]  # rook + bishop deltas on 0–63


def detect_themes(fen: str, move_san: str) -> list[str]:
    board = chess.Board(fen)
    themes = []
    mover = board.turn

    # 1) PRE-MOVE checks
    try:
        move = board.parse_san(move_san)
    except ValueError:
        return themes

    if board.is_capture(move):
        themes.append("capture")
    if board.is_check():
        themes.append("check")

    piece = board.piece_at(move.from_square)
    if piece and piece.piece_type == chess.PAWN:
        themes.append("pawn_push")
        if board.is_en_passant(move):
            themes.append("en_passant")
        if chess.square_rank(move.to_square) in (0, 7):
            themes.append("promotion")
    if board.is_castling(move):
        themes.append("castling")

    # record “slider → target” pairs before move
    pre_attacks = {
        (src, tgt)
        for pt in SLIDERS
        for src in board.pieces(pt, mover)
        for tgt in board.attacks(src)
        if board.piece_at(tgt) and board.piece_at(tgt).color != mover
    }

    # 2) POST-MOVE checks
    board.push(move)
    opp = board.turn

    # knight-fork
    for sq in board.pieces(chess.KNIGHT, opp):
        cnt = sum(
            1
            for t in board.attacks(sq)
            if (p := board.piece_at(t))
            and p.color != opp
            and p.piece_type in HIGH_VALUE
        )
        if cnt >= 2:
            themes.append("knight_fork")
            break

    # discovered_check
    if board.is_check() and "check" not in themes:
        themes.append("discovered_check")

    # discovered_attack (any HIGH-VALUE target newly attacked)
    post_attacks = {
        (src, tgt)
        for pt in SLIDERS
        for src in board.pieces(pt, mover)
        for tgt in board.attacks(src)
        if board.piece_at(tgt) and board.piece_at(tgt).color != mover
    }
    if any(pair not in pre_attacks for pair in post_attacks):
        themes.append("discovered_attack")

    # pin (any opponent piece pinned to king)
    for sq in (
        board.pieces(chess.PAWN, opp)
        | board.pieces(chess.KNIGHT, opp)
        | board.pieces(chess.BISHOP, opp)
        | board.pieces(chess.ROOK, opp)
        | board.pieces(chess.QUEEN, opp)
    ):
        if board.is_pinned(opp, sq):
            themes.append("pin")
            break

    # skewer: look along rays for two enemy HIGH-VALUE men in line
    for attacker in {
        *board.pieces(chess.BISHOP, mover),
        *board.pieces(chess.ROOK, mover),
        *board.pieces(chess.QUEEN, mover),
    }:
        for d in DIRECTIONS:
            seen = []
            sq = attacker
            while True:
                sq += d
                if not (0 <= sq < 64):
                    break
                # file wrap?
                if abs((sq % 8) - ((sq - d) % 8)) > 1 and d in (1, -1, 9, -7, -9, 7):
                    break
                p = board.piece_at(sq)
                if p and p.color == opp:
                    seen.append(p.piece_type)
                    if len(seen) == 2:
                        # first & second are HIGH_VALUE → skewer
                        if seen[0] in HIGH_VALUE and seen[1] in HIGH_VALUE:
                            themes.append("skewer")
                        break
                elif p:
                    break
            if "skewer" in themes:
                break
        if "skewer" in themes:
            break

    return themes
