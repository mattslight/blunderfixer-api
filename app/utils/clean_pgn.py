import re

def clean_pgn(pgn_text: str) -> str:
    """
    Cleans PGN input for compatibility with python-chess parser.
    Removes:
    - Clock annotations {[%clk ...]}
    - Non-standard tags like [CurrentPosition ...]
    - Duplicate move numbers (e.g. 1... c6)
    """
    
    # Remove all {...} comments
    pgn_text = re.sub(r'\{.*?\}', '', pgn_text)

    # Remove Chess.com clock info and other tags
    pgn_text = re.sub(r'\[%.*?\]', '', pgn_text)
    pgn_text = re.sub(r'\[CurrentPosition .*?\]', '', pgn_text)

    # Replace "1... c6" with just "c6" (removes extra black move labels)
    pgn_text = re.sub(r'\d+\.\.\.\s*', '', pgn_text)

    # Strip repeated white move numbers (e.g. "1. e4 1... c6" → "1. e4 c6")
    pgn_text = re.sub(r'(\d+)\.\s+', r'\1. ', pgn_text)

    print("--- CLEANED PGN ---")
    print(pgn_text)

    return pgn_text.strip()
