"""Test filters.py (Peran 1) — penentu file mana yang masuk Workspace.

Filter ini menentukan APA yang dilihat LLM. Kalau kode test lolos ke sini,
dokumen akan menggambarkan fixture test sebagai fitur produk — dan terbaca
meyakinkan, jadi tidak ada yang tahu harus mengeceknya.
"""

import pytest

from app.ingestion.filters import is_relevant_path


@pytest.mark.parametrize(
    "path",
    [
        "app/main.py",
        "lib/express.js",
        "src/components/Button.tsx",
        "internal/server/handler.go",
        "package.json",
        "requirements.txt",
        "go.mod",
        "Dockerfile",
    ],
)
def test_source_and_essential_files_are_kept(path):
    assert is_relevant_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "logo.png",
        "node_modules/lodash/index.js",
        "venv/lib/site-packages/x.py",
        "dist/bundle.js",
        "vendor/github.com/pkg/errors.go",
    ],
)
def test_noise_is_dropped(path):
    assert is_relevant_path(path) is False


@pytest.mark.parametrize(
    "path",
    [
        "test/app.js",
        "tests/test_parser.py",
        "spec/models_spec.rb",
        "__tests__/Button.tsx",
        "src/__mocks__/api.ts",
        "e2e/login.ts",
        "cypress/integration/auth.js",
        "testdata/sample.go",
    ],
)
def test_test_directories_are_dropped(path):
    """Diukur pada repo express: 1169 dari 1265 'endpoint' berasal dari test/."""
    assert is_relevant_path(path) is False


@pytest.mark.parametrize(
    "path",
    [
        "examples/auth/index.js",
        "example/basic/main.py",
        "demo/app.js",
        "samples/quickstart.py",
        "benchmarks/run.py",
    ],
)
def test_top_level_example_directories_are_dropped(path):
    """Kode contoh menggambarkan aplikasi demo, bukan sistem yang didokumentasikan."""
    assert is_relevant_path(path) is False


@pytest.mark.parametrize(
    "path",
    [
        # Kasus nyata: seluruh kode produksi spring-petclinic ada di bawah sini.
        "src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java",
        "src/main/java/org/springframework/samples/petclinic/owner/Owner.java",
        "internal/app/demo/handler.go",
        "src/lib/example/parser.py",
    ],
)
def test_example_words_deep_in_path_are_kept(path):
    """'samples'/'demo'/'example' lazim jadi bagian sah nama package — beda dengan
    folder demo di root. Aturan any-depth sempat membuang SELURUH 48 file Java
    spring-petclinic karena package-nya bernama org.springframework.samples.
    Filter yang terlalu rakus membuang kode produksi diam-diam: kegagalan yang
    jauh lebih sulit dilihat daripada kebanyakan noise."""
    assert is_relevant_path(path) is True


def test_maven_test_directory_is_dropped_even_when_nested():
    """Kebalikan dari kasus di atas: 'test' JUSTRU harus tertangkap jauh di dalam,
    karena Maven/Gradle menaruh test di src/test/java, bukan di root."""
    assert is_relevant_path("src/test/java/org/springframework/samples/petclinic/OwnerTest.java") is False


@pytest.mark.parametrize(
    "path",
    [
        "src/components/Button.test.tsx",
        "src/api/client.spec.ts",
        "lib/router.test.js",
        "app/test_parser.py",
        "internal/server/handler_test.go",
        "app/parser_test.py",
        "tests_helper/conftest.py",
    ],
)
def test_test_files_beside_source_are_dropped(path):
    """Blocklist folder tidak cukup: Go MEWAJIBKAN foo_test.go di sebelah foo.go,
    dan React lazim menaruh Button.test.tsx di sebelah Button.tsx. Tidak ada
    folder terpisah yang bisa disaring di kasus-kasus itu."""
    assert is_relevant_path(path) is False


@pytest.mark.parametrize(
    "path",
    [
        "app/latest_test_results.py",  # 'test' cuma bagian dari kata
        "src/contest.py",             # mengandung 'test' tapi bukan test
        "app/testing_utils.py",       # utilitas produksi, bukan file test
        "src/protest/views.py",       # folder mengandung 'test' tapi bukan 'test'
    ],
)
def test_pattern_does_not_over_match_ordinary_names(path):
    """Filter yang terlalu rakus diam-diam membuang kode produksi — kegagalan yang
    jauh lebih sulit dilihat daripada kebanyakan noise."""
    assert is_relevant_path(path) is True
