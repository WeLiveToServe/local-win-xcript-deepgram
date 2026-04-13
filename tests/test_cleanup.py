from local_wispr_transcript.config import CleanupSettings
from local_wispr_transcript.postprocess.cleanup import LightCleanupProcessor


def test_cleanup_normalizes_spaces_and_capitalizes() -> None:
    processor = LightCleanupProcessor(CleanupSettings())
    assert processor.clean("  hello   world ! ") == "Hello world!"

