import chess

HIGH_VALUE = {chess.QUEEN, chess.ROOK, chess.KING}


def detect_themes(fen: str, move_san: str) -> list[str]:
    """Return a list of simple tactical themes for the given move."""
    board = chess.Board(fen)
    themes = []
    try:
        move = board.parse_san(move_san)
    except Exception:
        return themes
    piece = board.piece_at(move.from_square)
    if piece and piece.piece_type == chess.PAWN:
        themes.append("pawn_push")
    board.push(move)
    opp_color = board.turn
    for sq in board.pieces(chess.KNIGHT, opp_color):
        attacks = board.attacks(sq)
        count = sum(
            1
            for target in attacks
            if board.piece_at(target)
            and board.piece_at(target).color != opp_color
            and board.piece_at(target).piece_type in HIGH_VALUE
        )
        if count >= 2:
            themes.append("knight_fork")
            break
    return themes
