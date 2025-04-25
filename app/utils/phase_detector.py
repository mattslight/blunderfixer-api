import chess

def is_studyable_endgame(board: chess.Board) -> bool:
    """
    Studyable endgame = 3 or fewer non-pawn pieces per side, and 6 or fewer total.
    """
    piece_map = board.piece_map()
    non_pawn_counts = {'white': 0, 'black': 0}
    total_non_pawn = 0

    for square, piece in piece_map.items():
        if piece.piece_type not in [chess.PAWN, chess.KING]:
            total_non_pawn += 1
            color = 'white' if piece.color == chess.WHITE else 'black'
            non_pawn_counts[color] += 1

    return (
        non_pawn_counts['white'] <= 3 and
        non_pawn_counts['black'] <= 3 and
        total_non_pawn <= 6
    )

def is_endgame(board: chess.Board) -> bool:
    """
    Alias for clarity.
    """
    return is_studyable_endgame(board)

def is_middlegame(board: chess.Board, move_number: int, move_stack: list) -> bool:
    """
    Middlegame begins if:
    - not in endgame
    - an irreversible move has happened after move 10, or it's past move 12
    - there are still 7+ non-pawn pieces
    - at least 1 queen or 2 rooks remain
    """
    if is_endgame(board):
        return False

    def is_irreversible(move, board_state):
        return (
            board_state.is_capture(move) or
            board_state.piece_type_at(move.from_square) == chess.PAWN
        )

    irreversible_found = False
    if move_number > 10:
        for move in move_stack[20:]:  # skip first 10 full moves (20 ply)
            temp_board = board.copy(stack=False)
            temp_board.set_board_fen(board.board_fen())
            temp_board.push(move)
            if is_irreversible(move, temp_board):
                irreversible_found = True
                break

    total_non_pawn = sum(
        1 for p in board.piece_map().values()
        if p.piece_type not in [chess.PAWN, chess.KING]
    )
    has_queen_or_two_rooks = (
        len(board.pieces(chess.QUEEN, chess.WHITE)) +
        len(board.pieces(chess.QUEEN, chess.BLACK)) >= 1 or
        len(board.pieces(chess.ROOK, chess.WHITE)) +
        len(board.pieces(chess.ROOK, chess.BLACK)) >= 2
    )

    return (
        (move_number >= 12 or irreversible_found) and
        total_non_pawn > 6 and
        has_queen_or_two_rooks
    )

def get_game_phase(board: chess.Board, move_number: int, move_stack: list) -> str:
    """
    Returns 'opening', 'middlegame', or 'endgame' based on deterministic rules.
    """
    if is_endgame(board):
        return 'endgame'
    if is_middlegame(board, move_number, move_stack):
        return 'middlegame'
    return 'opening'
