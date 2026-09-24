from pathlib import Path

PROMPT_ROOT = (
    Path(__file__).parent
)

def load_prompt(name: str) -> str:
    path = (PROMPT_ROOT / name / "system.md")
    if not path.exists:
        raise FileExistsError(
            f"Prompt not found: {name}"
        )
        
    return path.read_text(encoding="utf-8").strip()