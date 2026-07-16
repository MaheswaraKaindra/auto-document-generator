"""Test parser Java + deteksi endpoint Spring MVC (Peran 1).

Java adalah bahasa ketiga yang didukung parser, dan yang paling mungkin dipakai
calon pengguna SDD/UAT (repo enterprise). Sebelum ini seluruh file .java jatuh ke
entry `type: "other"` kosong: terukur pada spring-petclinic, 33 file menghasilkan
NOL class, NOL dependency, NOL endpoint.

Tiap test di bawah mengunci satu bentuk yang DIAMBIL DARI PETCLINIC SUNGGUHAN,
bukan dikarang dari ingatan tentang Spring — beberapa di antaranya sempat salah
justru karena ditebak.
"""

from app.domain.models import Workspace, WorkspaceFile
from app.services.parser_service import build_parsed_repo_context


def _parse(source: str, file_path: str = "src/main/java/OwnerController.java") -> dict:
    workspace = Workspace(repo_tag="Backend", source_ref="test")
    workspace.files.append(
        WorkspaceFile(
            file_name=file_path.split("/")[-1], file_path=file_path, content=source
        )
    )
    context = build_parsed_repo_context(project_name="t", workspaces=[workspace])
    return context["repositories"][0]["files"][0]


def _endpoints(source: str, file_path: str = "src/main/java/OwnerController.java") -> set:
    return {(e["method"], e["path"]) for e in _parse(source, file_path)["api_endpoints"]}


# --- Endpoint Spring MVC ------------------------------------------------------

def test_spring_shortcut_annotations_detected():
    """@GetMapping/@PostMapping dst — bentuk yang dipakai SELURUH handler petclinic."""
    endpoints = _endpoints(
        "class C {\n"
        '  @GetMapping("/owners/find") public String find() { return "x"; }\n'
        '  @PostMapping("/owners/new") public String create() { return "x"; }\n'
        '  @DeleteMapping("/owners/1") public String del() { return "x"; }\n'
        "}\n"
    )

    assert endpoints == {
        ("GET", "/owners/find"),
        ("POST", "/owners/new"),
        ("DELETE", "/owners/1"),
    }


def test_path_written_as_positional_array():
    """@GetMapping({"/vets"}) — kurung kurawal cuma sintaks, tetap satu handler.

    Bentuk ini sempat terlewat dan gagalnya SUNYI: path jatuh ke None lalu keluar
    sebagai "/", sehingga VetController dan WelcomeController sama-sama melaporkan
    `GET /`. Diambil langsung dari VetController petclinic.
    """
    assert _endpoints('class C { @GetMapping({"/vets"}) String v() { return "x"; } }') == {
        ("GET", "/vets")
    }


def test_class_level_request_mapping_is_prefix_not_endpoint():
    """@RequestMapping di level class adalah PREFIX. Memperlakukannya sebagai
    endpoint memunculkan `/owners/{ownerId}` hantu yang tidak punya handler."""
    endpoints = _endpoints(
        '@RequestMapping("/owners/{ownerId}")\n'
        "class PetController {\n"
        '  @GetMapping("/pets/new") public String init() { return "x"; }\n'
        "}\n"
    )

    assert endpoints == {("GET", "/owners/{ownerId}/pets/new")}


def test_class_prefix_joined_without_double_slash():
    """Prefix berakhiran "/" + path berawalan "/" tidak boleh jadi "//"."""
    endpoints = _endpoints(
        '@RequestMapping("/owners/")\n'
        'class C { @GetMapping("/new") String n() { return "x"; } }\n'
    )

    assert endpoints == {("GET", "/owners/new")}


def test_method_annotation_without_path_falls_back_to_class_prefix():
    """@PostMapping tanpa argumen (marker_annotation) = POST ke prefix class-nya."""
    endpoints = _endpoints(
        '@RequestMapping("/owners")\n'
        "class C { @PostMapping public String c() { return \"x\"; } }\n"
    )

    assert endpoints == {("POST", "/owners")}


def test_request_mapping_reads_method_attribute():
    """@RequestMapping(value=..., method=RequestMethod.POST) — bentuk Spring lama."""
    endpoints = _endpoints(
        "class C {\n"
        '  @RequestMapping(value = "/find", method = RequestMethod.POST)\n'
        '  public String find() { return "x"; }\n'
        "}\n"
    )

    assert endpoints == {("POST", "/find")}


def test_request_mapping_method_array_is_several_endpoints():
    """method = {RequestMethod.GET, RequestMethod.PUT} itu DUA endpoint —
    analog dengan methods=["GET","POST"] di Flask."""
    endpoints = _endpoints(
        "class C {\n"
        '  @RequestMapping(path = "/p", method = {RequestMethod.GET, RequestMethod.PUT})\n'
        '  public String p() { return "x"; }\n'
        "}\n"
    )

    assert endpoints == {("GET", "/p"), ("PUT", "/p")}


def test_request_mapping_without_method_approximated_as_get():
    """APROKSIMASI YANG DISENGAJA, dikunci supaya perubahannya tidak diam-diam:
    Spring sebenarnya menerima SEMUA method di sini. GET dipilih karena mencatat
    5 baris untuk satu handler pasti salah, dan mencatat 0 membuang handler nyata.
    Beda dari Flask, di mana GET memang default framework-nya."""
    endpoints = _endpoints('class C { @RequestMapping("/oups") String c() { return "x"; } }')

    assert endpoints == {("GET", "/oups")}


def test_non_mapping_annotations_are_not_endpoints():
    """@Controller/@Autowired/@Override tidak boleh diseret jadi endpoint."""
    endpoints = _endpoints(
        "@Controller\n"
        "class C {\n"
        "  @Autowired private OwnerRepository owners;\n"
        '  @Override public String toString() { return "x"; }\n'
        "}\n"
    )

    assert endpoints == set()


def test_payload_carries_handler_parameters():
    endpoints = _parse(
        'class C { @PostMapping("/new") String c(Owner owner, BindingResult r) { return "x"; } }'
    )["api_endpoints"]

    assert endpoints[0]["payload"] == "owner, r"


# --- Struktur: class, interface, Javadoc, import ------------------------------

def test_interface_methods_extracted():
    """Spring Data menulis SELURUH repository sebagai interface. Menangani
    `class` saja membuat lapisan data hilang total — di petclinic itu
    OwnerRepository, VetRepository, dan PetTypeRepository sekaligus."""
    parsed = _parse(
        "public interface OwnerRepository extends JpaRepository<Owner, Integer> {\n"
        "  Page<Owner> findByLastName(String lastName, Pageable pageable);\n"
        "}\n",
        file_path="src/main/java/OwnerRepository.java",
    )

    assert parsed["type"] == "repository"
    assert parsed["classes"][0]["class_name"] == "OwnerRepository"
    method = parsed["classes"][0]["methods"][0]
    assert method["method_name"] == "findByLastName"
    assert method["parameters"] == ["lastName", "pageable"]
    assert method["return_type"] == "Page<Owner>"


def test_javadoc_becomes_description():
    """Javadoc adalah block_comment SIBLING sebelum deklarasi, bukan di dalam body
    seperti docstring Python. `description` ini bukan hiasan: LLM terbukti membaca
    docstring dari Contract A (PostgreSQL/Neon di dokumen esteler datang dari sana,
    bukan dari `dependencies`)."""
    parsed = _parse(
        "class C {\n"
        "  /**\n"
        "   * Return the Pet with the given name.\n"
        "   */\n"
        "  public Pet getPet(String name) { return null; }\n"
        "}\n"
    )

    assert parsed["classes"][0]["methods"][0]["description"] == "Return the Pet with the given name."


def test_javadoc_tags_are_dropped():
    """@param/@return itu metadata tag, bukan kalimat deskripsi."""
    parsed = _parse(
        "class C {\n"
        "  /**\n"
        "   * Adds a visit.\n"
        "   * @param petId the pet identifier\n"
        "   * @return nothing\n"
        "   */\n"
        "  public void addVisit(int petId) {}\n"
        "}\n"
    )

    assert parsed["classes"][0]["methods"][0]["description"] == "Adds a visit."


def test_plain_block_comment_is_not_javadoc():
    """/* ... */ biasa (mis. header lisensi) bukan dokumentasi method."""
    parsed = _parse(
        "class C {\n"
        "  /* internal note, not javadoc */\n"
        "  public void x() {}\n"
        "}\n"
    )

    assert parsed["classes"][0]["methods"][0]["description"] == ""


def test_imports_become_dependencies():
    """Diselaraskan dengan Python (`from x import y` -> `y`): yang dicatat nama
    yang dipakai di kode. Wildcard tidak punya nama, jadi paketnya yang dicatat."""
    parsed = _parse(
        "import java.util.List;\n"
        "import java.util.*;\n"
        "import static org.junit.Assert.assertEquals;\n"
        "class C {}\n"
    )

    assert parsed["dependencies"] == ["List", "java.util", "assertEquals"]


def test_java_reports_no_top_level_functions():
    """Java tidak punya top-level function — semua method hidup di dalam class.
    functions[] kosong di sini adalah fakta bahasa, bukan lubang parser."""
    parsed = _parse("class C { public void a() {} }")

    assert parsed["functions"] == []
    assert [m["method_name"] for m in parsed["classes"][0]["methods"]] == ["a"]


def test_enum_and_record_are_captured():
    """Keduanya deklarasi tipe tersendiri di grammar Java; petclinic memakai enum
    untuk model, dan record lazim di Java modern."""
    parsed = _parse(
        "enum Status { ACTIVE, INACTIVE }\n"
        "record Point(int x, int y) {}\n",
        file_path="src/main/java/Status.java",
    )

    assert {c["class_name"] for c in parsed["classes"]} == {"Status", "Point"}


def test_nested_class_is_captured():
    parsed = _parse("class Outer { static class Inner { void a() {} } }")

    assert {c["class_name"] for c in parsed["classes"]} == {"Outer", "Inner"}


def test_java_file_no_longer_falls_back_to_other():
    """Penjaga regresi utama: sebelum dukungan Java, build_parsed_repo_context
    meng-hardcode type="other" di jalur fallback dan tidak pernah memanggil
    _guess_file_type — jadi OwnerController.java pun berlabel "other"."""
    parsed = _parse('class C { @GetMapping("/x") String x() { return "y"; } }')

    assert parsed["type"] == "controller"
