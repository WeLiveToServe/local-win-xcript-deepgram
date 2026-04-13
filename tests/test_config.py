from local_wispr_transcript.config import load_settings


def test_default_settings_load() -> None:
    settings = load_settings()
    assert settings.app.hotkey
    assert settings.audio.sample_rate == 16000
