"""Test LLMService (Peran 2) — guard context window.

Anthropic selalu di-mock: test ini tidak boleh menyentuh jaringan, API key, atau
kuota. Yang diuji di sini bukan kualitas dokumen (itu tugas scripts/validation/),
tapi apakah repo yang kebesaran ditolak SEBELUM panggilan berbayar terjadi.
"""

from unittest.mock import MagicMock, Mock

import pytest
from pydantic import ValidationError

from app.domain.exceptions import ContextWindowExceededError, DocumentTruncatedError
from app.services import llm_service
from app.services.llm_service import LLMService

_CONTEXT_A = {"project_name": "x", "repositories": []}


def _fake_stream(final_message=None, error=None, stop_reason="end_turn"):
    """Tiru context manager client.messages.stream(...).

    MagicMock, bukan Mock: `with ... as stream` butuh protokol context manager.
    """
    stream = MagicMock()
    if error is not None:
        stream.get_final_message.side_effect = error
    else:
        stream.get_final_message.return_value = final_message
    stream.current_message_snapshot = Mock(stop_reason=stop_reason)

    manager = MagicMock()
    manager.__enter__.return_value = stream
    manager.__exit__.return_value = False
    return manager, stream


@pytest.fixture(autouse=True)
def clear_context_window_cache():
    """Cache-nya module-level, jadi tanpa ini test saling mencemari."""
    llm_service._CONTEXT_WINDOW_CACHE.clear()
    yield
    llm_service._CONTEXT_WINDOW_CACHE.clear()


def _service(window: int | None, counted: int) -> LLMService:
    """LLMService dengan client yang sepenuhnya palsu.

    window=None meniru Models API tidak bisa dihubungi.
    """
    service = LLMService()
    client = Mock()
    if window is None:
        client.models.retrieve.side_effect = RuntimeError("Models API tidak terjangkau")
    else:
        client.models.retrieve.return_value = Mock(max_input_tokens=window)
    client.messages.count_tokens.return_value = Mock(input_tokens=counted)
    final = Mock(
        parsed_output=Mock(model_dump=Mock(return_value={"document_type": "SDD"})),
        usage=Mock(
            input_tokens=1,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
            output_tokens=1,
        ),
    )
    client.messages.stream.return_value, _ = _fake_stream(final_message=final)
    service.client = client
    return service


def test_oversized_context_fails_before_paying(clear_context_window_cache):
    """Inti perbaikannya: repo yang tidak muat harus ditolak SEBELUM messages.parse.

    Diukur pada repo nyata: Contract A saleor = 1.224.476 token = 122% dari
    context window 1M. Tanpa guard ini, panggilan berbayar tetap dikirim hanya
    untuk ditolak API.
    """
    service = _service(window=1_000_000, counted=1_224_476)

    with pytest.raises(ContextWindowExceededError):
        service.generate_document_content(parsed_repo_context=_CONTEXT_A, target_doc_type="SDD")

    service.client.messages.stream.assert_not_called()


def test_error_message_names_the_real_numbers_and_forbids_retry():
    """Setengah bug-nya ada di pesannya. Sebelumnya semua kegagalan LLM diratakan
    jadi 502 'coba lagi beberapa saat' — saran yang tidak akan pernah menolong
    untuk kegagalan yang permanen. Pesannya harus menyebut angka aslinya dan
    menawarkan jalan keluar yang benar-benar ada."""
    service = _service(window=1_000_000, counted=1_224_476)

    with pytest.raises(ContextWindowExceededError) as excinfo:
        service.generate_document_content(parsed_repo_context=_CONTEXT_A, target_doc_type="SDD")

    message = str(excinfo.value)
    assert "1,224,476" in message and "1,000,000" in message
    assert "LLM_MODEL" in message  # jalan keluar yang bisa ditindaklanjuti


def test_context_that_fits_is_generated_normally():
    """Guard tidak boleh menghalangi repo yang sebenarnya muat."""
    service = _service(window=1_000_000, counted=60_907)  # ukuran fastapi sesudah manifest

    result = service.generate_document_content(
        parsed_repo_context=_CONTEXT_A, target_doc_type="SDD"
    )

    service.client.messages.stream.assert_called_once()
    assert result == {"document_type": "SDD"}


def test_guard_fails_open_when_models_api_unreachable():
    """Sengaja gagal-membuka: pemeriksaan yang gagal tidak boleh menghalangi
    generation yang mungkin baik-baik saja. Pelajaran yang sama dengan manifest.py
    — filter rakus jauh lebih berbahaya daripada filter yang kelewatan."""
    service = _service(window=None, counted=999_999_999)

    result = service.generate_document_content(
        parsed_repo_context=_CONTEXT_A, target_doc_type="SDD"
    )

    service.client.messages.stream.assert_called_once()
    assert result == {"document_type": "SDD"}


def _truncation_error() -> ValidationError:
    """ValidationError persis seperti yang dilempar Pydantic saat JSON terpotong."""
    from pydantic import BaseModel

    class _M(BaseModel):
        x: int

    try:
        _M.model_validate_json('{"x": 1')  # JSON sengaja dipotong
    except ValidationError as e:
        return e
    raise AssertionError("harusnya melempar")


def test_truncated_document_blames_max_tokens_not_the_model():
    """Terjadi sungguhan pada esteler-app: Pydantic melapor 'Invalid JSON: EOF
    while parsing a string', yang terbaca seperti LLM mengeluarkan sampah —
    padahal jatah keluaran KITA yang kurang. Kelas kesalahan yang sama dengan 502
    yang dulu menelan 414 mermaid.ink: sebab asli tertelan gejala."""
    service = _service(window=1_000_000, counted=100)
    service.client.messages.stream.return_value, _ = _fake_stream(
        error=_truncation_error(), stop_reason="max_tokens"
    )

    with pytest.raises(DocumentTruncatedError) as excinfo:
        service.generate_document_content(parsed_repo_context=_CONTEXT_A, target_doc_type="SDD")

    message = str(excinfo.value)
    assert "max_tokens" in message
    assert "MAX_OUTPUT_TOKENS" in message  # tempat memperbaikinya disebut


def test_json_error_not_caused_by_truncation_is_not_disguised():
    """Kebalikannya sama pentingnya: JSON rusak karena sebab LAIN tidak boleh
    dilabeli 'kepotong'. Guard yang terlalu bersemangat cuma memindahkan
    penyamaran ke arah sebaliknya."""
    service = _service(window=1_000_000, counted=100)
    service.client.messages.stream.return_value, _ = _fake_stream(
        error=_truncation_error(), stop_reason="end_turn"  # selesai normal
    )

    with pytest.raises(ValidationError):
        service.generate_document_content(parsed_repo_context=_CONTEXT_A, target_doc_type="SDD")


def test_context_window_asked_once_then_cached():
    """Context window tidak berubah selama proses hidup; menanyakannya tiap
    generation cuma menambah panggilan jaringan dan titik gagal."""
    service = _service(window=1_000_000, counted=100)

    for _ in range(3):
        service.generate_document_content(parsed_repo_context=_CONTEXT_A, target_doc_type="SDD")

    service.client.models.retrieve.assert_called_once()
