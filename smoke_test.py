"""Manual smoke test: run the real transcribe->route->cleanup pipeline against
recorded WAV files, without the live hotkey/mic/paste (those need a live desktop
session). Prints raw vs. cleaned output for review; skips the clipboard paste
step so it never disturbs whatever window currently has focus. Logs to history/
like the real app would, so 30-day retention can be inspected too.
"""

import sys
from pathlib import Path

import command_router
import config
import groq_client
import history
import mistral_cleanup

FILES = [
    "t1_grammar_and_hedge.wav",
    "t2_repetition_and_number.wav",
    "t3_mishearing.wav",
    "n1_topic_interleave.wav",
    "n2_verbatim_casual.wav",
    "n3_long_no_drop.wav",
]


def run_one(path: Path, groq_key: str, mistral_client, out) -> None:
    header = f"\n{'=' * 70}\n{path.name}\n{'=' * 70}"
    print(header)
    out.write(header + "\n")
    wav_bytes = path.read_bytes()

    raw_transcript = groq_client.transcribe(wav_bytes, api_key=groq_key)
    section = f"\n[Groq raw transcript]\n{raw_transcript}"
    print(section)
    out.write(section + "\n")

    mode, transcript = command_router.route(raw_transcript)
    section = f"\n[Router] mode={mode!r}"
    print(section)
    out.write(section + "\n")

    output = mistral_cleanup.clean(mistral_client, mode, transcript)
    section = f"\n[Mistral cleaned output]\n{output}"
    print(section)
    out.write(section + "\n")

    if mistral_cleanup.has_unclear_segment(output):
        section = "\n[WARNING] output contains an [UNCLEAR] marker — review it"
        print(section)
        out.write(section + "\n")

    record_path = history.record_dictation(mode, raw_transcript, output)
    section = f"\n[History] saved to {record_path}"
    print(section)
    out.write(section + "\n")


def main() -> None:
    credentials = config.load_config()
    if credentials is None:
        print("No cached credentials found. Run: python -c \"import config; config.get_credentials()\"")
        sys.exit(1)

    mistral_client = mistral_cleanup.make_client(credentials["MISTRAL_API_KEY"])
    project_dir = Path(__file__).parent

    with open(project_dir / "_smoke_test_output.txt", "w", encoding="utf-8") as out:
        for filename in FILES:
            path = project_dir / filename
            if not path.exists():
                print(f"Skipping missing file: {filename}")
                continue
            run_one(path, credentials["GROQ_API_KEY"], mistral_client, out)


if __name__ == "__main__":
    main()
