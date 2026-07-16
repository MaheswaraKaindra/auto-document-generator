import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

import tree_sitter_language_pack as tslp
from dotenv import load_dotenv

# Load environment variables dari file .env
load_dotenv()

def generate_file_metadata_prompt(file_name: str, file_content: str) -> str:
    prompt = f"""
    Anda adalah asisten AI khusus rekayasa perangkat lunak. Tugas Anda adalah mengekstrak
    struktur dan metadata dari source code secara objektif.

    ATURAN KETAT:
    1. JANGAN menjelaskan alur logika kode.
    2. JANGAN menambahkan teks pembuka atau penutup.
    3. Output HARUS berupa JSON murni yang bisa langsung di-parse oleh sistem.

    Informasi Target:
    - Nama File: {file_name}

    Source Code:
    ```
    {file_content}
    ```

    Ekstrak data tersebut ke dalam skema JSON berikut:
    {{
        "file_name": "{file_name}",
        "type": "controller|service|repository|ui_component|model|other",
        "dependencies": ["daftar_import_atau_library_yang_dipakai"],
        "classes": [
            {{
                "class_name": "NamaClass",
                "methods": [
                    {{
                        "method_name": "namaFungsi",
                        "parameters": ["param1", "param2"],
                        "return_type": "tipe_data",
                        "description": "Ringkasan 1 kalimat apa yang dilakukan fungsi ini"
                    }}
                ]
            }}
        ],
        "api_endpoints": [
            // ISI HANYA JIKA FILE INI ADALAH CONTROLLER/ROUTER
            {{
                "method": "GET/POST/PUT/DELETE",
                "path": "/api/v1/contoh",
                "payload": "Keterangan data yang diterima (jika ada)"
            }}
        ]
    }}
    """
    return prompt

# ==========================================================================
# STRUCTURAL EXTRACTION (Tree-sitter) - deterministic, no LLM call.
# Produces the per-file entries of Contract A (ParsedRepoContext.json).
# ==========================================================================

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
}

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@dataclass
class MethodInfo:
    method_name: str
    parameters: list[str] = field(default_factory=list)
    return_type: Optional[str] = None
    description: str = ""


@dataclass
class ClassInfo:
    class_name: str
    methods: list[MethodInfo] = field(default_factory=list)


@dataclass
class FunctionInfo:
    function_name: str
    parameters: list[str] = field(default_factory=list)
    return_type: Optional[str] = None
    description: str = ""


@dataclass
class EndpointInfo:
    method: str
    path: str
    payload: Optional[str] = None


@dataclass
class FileMetadata:
    file_name: str
    file_path: str
    type: str
    dependencies: list[str] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    api_endpoints: list[EndpointInfo] = field(default_factory=list)


def detect_language(file_name: str) -> Optional[str]:
    _, ext = os.path.splitext(file_name)
    return EXTENSION_TO_LANGUAGE.get(ext)


def _string_literal_value(node) -> Optional[str]:
    # Java menamai node-nya `string_literal`, Python/TS `string`. Isinya sama-sama
    # dibungkus `string_fragment`/`string_content`, jadi yang perlu dilonggarkan
    # cuma nama pembungkusnya.
    if node is None or node.type not in ("string", "string_literal"):
        return None
    for child in node.children:
        if child.type in ("string_content", "string_fragment"):
            return child.text.decode()
    return node.text.decode().strip("'\"")


def _docstring_from_body(body_node) -> str:
    if body_node is None or not body_node.named_children:
        return ""
    first = body_node.named_children[0]
    if first.type == "string":
        value = _string_literal_value(first)
    elif first.type == "expression_statement" and first.named_children:
        value = _string_literal_value(first.named_children[0])
    else:
        value = None
    return value.strip() if value else ""


def _guess_file_type(file_name: str, has_endpoints: bool) -> str:
    lower = file_name.lower()
    if has_endpoints or "controller" in lower or "router" in lower or "route" in lower:
        return "controller"
    if "service" in lower:
        return "service"
    if "repository" in lower:
        return "repository"
    if "model" in lower or "schema" in lower or "entity" in lower:
        return "model"
    if lower.endswith((".tsx", ".jsx")) or "component" in lower or "page" in lower:
        return "ui_component"
    return "other"


# --- Python -----------------------------------------------------------------

def _python_param_name(node) -> str:
    if node.type == "identifier":
        return node.text.decode()
    name_field = node.child_by_field_name("name")
    if name_field is not None:
        return name_field.text.decode()
    for child in node.named_children:
        if child.type == "identifier":
            return child.text.decode()
    return node.text.decode()


def _python_parameters(params_node) -> list[str]:
    if params_node is None:
        return []
    return [
        _python_param_name(p)
        for p in params_node.named_children
        if _python_param_name(p) not in ("self", "cls")
    ]


def _python_keyword_argument(args, name: str):
    """Ambil node nilai dari keyword argument tertentu, mis. methods=[...]."""
    if args is None:
        return None
    for child in args.named_children:
        if child.type != "keyword_argument":
            continue
        key = child.child_by_field_name("name")
        if key is not None and key.text.decode() == name:
            return child.child_by_field_name("value")
    return None


def _string_list_values(node) -> list[str]:
    """Isi list/tuple literal berisi string: ["GET", "POST"] -> ["GET", "POST"]."""
    if node is None or node.type not in ("list", "tuple"):
        return []
    return [value for value in (_string_literal_value(c) for c in node.named_children) if value]


def _python_endpoints_from_decorator(decorator_node) -> list[EndpointInfo]:
    """Endpoint dari satu decorator Python.

    Mengembalikan LIST, bukan satu: `@bp.route("/x", methods=["GET", "POST"])`
    itu DUA endpoint. Versi sebelumnya mengembalikan satu, dan itu memang cukup
    selama yang dikenali cuma FastAPI (satu decorator = satu method).

    Dua bentuk dikenali, keduanya `<apa_saja>.<attr>("path")`:
      FastAPI  @app.get("/x") / @router.post("/x")  -> attr adalah HTTP method-nya
      Flask    @app.route("/x", methods=["POST"])   -> attr == "route", method
               @auth_bp.route("/logout")               dibaca dari methods=

    Flask sebelumnya menghasilkan NOL endpoint karena "route" bukan anggota
    HTTP_METHODS — terukur pada esteler-app: routes/ berisi 32 view, terdeteksi 0.
    Untuk aplikasi bisnis itu fatal: endpoint adalah bahan baku pemetaan FE<->BE.

    CATATAN KETIDAKTEPATAN: path yang dikembalikan adalah path yang DITULIS di
    decorator. Blueprint biasanya didaftarkan dengan url_prefix di file lain
    (`app.register_blueprint(auth_bp, url_prefix="/auth")`), jadi URL sebenarnya
    bisa `/auth/login` sementara di sini tercatat `/login`. Menyelesaikannya butuh
    analisis lintas-file; belum dilakukan.
    """
    call = next((c for c in decorator_node.named_children if c.type == "call"), None)
    if call is None:
        return []
    fn = call.child_by_field_name("function")
    if fn is None or fn.type != "attribute":
        return []
    attr_node = fn.child_by_field_name("attribute")
    if attr_node is None:
        return []
    attr = attr_node.text.decode().lower()

    args = call.child_by_field_name("arguments")
    path = _string_literal_value(args.named_children[0]) if args and args.named_children else None
    if not path:
        return []

    if attr in HTTP_METHODS:
        return [EndpointInfo(method=attr.upper(), path=path)]

    if attr == "route":
        # methods= dihilangkan berarti GET saja. Ini bukan tebakan — itu default
        # Flask, dan bentuk paling umum (@bp.route("/menu") tanpa methods).
        declared = _string_list_values(_python_keyword_argument(args, "methods"))
        return [
            EndpointInfo(method=method.upper(), path=path)
            for method in (declared or ["GET"])
            # HEAD/OPTIONS ditambahkan Flask sendiri secara otomatis dan bukan
            # fitur yang perlu didokumentasikan — buang, jangan jadi noise.
            if method.lower() in HTTP_METHODS
        ]

    return []


def _python_function_info(fn_node, decorators: list) -> tuple[FunctionInfo, list[EndpointInfo]]:
    name_node = fn_node.child_by_field_name("name")
    return_type_node = fn_node.child_by_field_name("return_type")
    info = FunctionInfo(
        function_name=name_node.text.decode() if name_node else "",
        parameters=_python_parameters(fn_node.child_by_field_name("parameters")),
        return_type=return_type_node.text.decode() if return_type_node else None,
        description=_docstring_from_body(fn_node.child_by_field_name("body")),
    )
    # Semua decorator diperiksa, tidak berhenti di yang pertama: menumpuk route
    # pada satu view itu lazim di Flask (@app.route("/") + @app.route("/home")).
    endpoints = [ep for dec in decorators for ep in _python_endpoints_from_decorator(dec)]
    if info.parameters:
        for endpoint in endpoints:
            endpoint.payload = ", ".join(info.parameters)
    return info, endpoints


def _parse_python(root) -> tuple[list[str], list[ClassInfo], list[FunctionInfo], list[EndpointInfo]]:
    dependencies: list[str] = []
    classes: list[ClassInfo] = []
    functions: list[FunctionInfo] = []
    endpoints: list[EndpointInfo] = []

    def collect_import_names(node):
        for name_node in node.children_by_field_name("name"):
            if name_node.type == "aliased_import":
                alias = name_node.child_by_field_name("alias")
                original = name_node.child_by_field_name("name")
                dependencies.append(alias.text.decode() if alias else original.text.decode())
            else:
                dependencies.append(name_node.text.decode())

    def visit_class(class_node):
        name_node = class_node.child_by_field_name("name")
        class_info = ClassInfo(class_name=name_node.text.decode() if name_node else "")
        body = class_node.child_by_field_name("body")
        if body is None:
            classes.append(class_info)
            return
        for member in body.named_children:
            decorators: list = []
            fn_node = member
            if member.type == "decorated_definition":
                decorators = [c for c in member.children if c.type == "decorator"]
                fn_node = member.child_by_field_name("definition")
            if fn_node is not None and fn_node.type == "function_definition":
                method_info, found = _python_function_info(fn_node, decorators)
                class_info.methods.append(
                    MethodInfo(
                        method_name=method_info.function_name,
                        parameters=method_info.parameters,
                        return_type=method_info.return_type,
                        description=method_info.description,
                    )
                )
                endpoints.extend(found)
        classes.append(class_info)

    def visit(node):
        for child in node.named_children:
            if child.type == "import_statement":
                collect_import_names(child)
            elif child.type == "import_from_statement":
                collect_import_names(child)
            elif child.type == "class_definition":
                visit_class(child)
            elif child.type == "decorated_definition":
                decorators = [c for c in child.children if c.type == "decorator"]
                inner = child.child_by_field_name("definition")
                if inner is not None and inner.type == "function_definition":
                    fn_info, found = _python_function_info(inner, decorators)
                    functions.append(fn_info)
                    endpoints.extend(found)
                elif inner is not None and inner.type == "class_definition":
                    visit_class(inner)
            elif child.type == "function_definition":
                fn_info, endpoint = _python_function_info(child, [])
                functions.append(fn_info)
                if endpoint:
                    endpoints.append(endpoint)
            else:
                visit(child)

    visit(root)
    return dependencies, classes, functions, endpoints


# --- TypeScript / JavaScript --------------------------------------------------

def _ts_param_name(node) -> str:
    name_field = node.child_by_field_name("pattern") or node.child_by_field_name("name")
    if name_field is not None:
        return name_field.text.decode()
    for child in node.children:
        if child.type == "identifier":
            return child.text.decode()
    return node.text.decode().split(":")[0].strip()


def _ts_parameters(params_node) -> list[str]:
    if params_node is None:
        return []
    return [_ts_param_name(p) for p in params_node.named_children if p.type not in ("(", ")")]


def _ts_return_type(node) -> Optional[str]:
    rt = node.child_by_field_name("return_type")
    if rt is None:
        return None
    return rt.text.decode().lstrip(":").strip()


def _ts_endpoint_from_call(call_node) -> Optional[EndpointInfo]:
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return None
    method_name = None
    if fn.type == "member_expression":
        prop = fn.child_by_field_name("property")
        method_name = prop.text.decode().lower() if prop else None
    elif fn.type == "identifier":
        method_name = fn.text.decode().lower()
    if method_name not in HTTP_METHODS:
        return None
    args = call_node.child_by_field_name("arguments")
    path = _string_literal_value(args.named_children[0]) if args and args.named_children else None
    if not path:
        return None
    return EndpointInfo(method=method_name.upper(), path=path)


def _parse_ts_js(root) -> tuple[list[str], list[ClassInfo], list[FunctionInfo], list[EndpointInfo]]:
    dependencies: list[str] = []
    classes: list[ClassInfo] = []
    functions: list[FunctionInfo] = []
    endpoints: list[EndpointInfo] = []

    def collect_identifiers(node) -> list[str]:
        names = []
        if node.type == "identifier":
            names.append(node.text.decode())
        for child in node.children:
            names.extend(collect_identifiers(child))
        return names

    def visit_class(class_node):
        name_node = class_node.child_by_field_name("name")
        class_info = ClassInfo(class_name=name_node.text.decode() if name_node else "")
        body = class_node.child_by_field_name("body")
        if body is None:
            classes.append(class_info)
            return
        pending_decorators: list = []
        for member in body.named_children:
            if member.type == "decorator":
                pending_decorators.append(member)
                continue
            if member.type == "method_definition":
                name_node = member.child_by_field_name("name")
                class_info.methods.append(
                    MethodInfo(
                        method_name=name_node.text.decode() if name_node else "",
                        parameters=_ts_parameters(member.child_by_field_name("parameters")),
                        return_type=_ts_return_type(member),
                    )
                )
                for dec in pending_decorators:
                    call = next((c for c in dec.children if c.type == "call_expression"), None)
                    if call is not None:
                        endpoint = _ts_endpoint_from_call(call)
                        if endpoint:
                            endpoints.append(endpoint)
            pending_decorators = []
        classes.append(class_info)

    def visit(node):
        for child in node.named_children:
            if child.type == "import_statement":
                clause = child.child_by_field_name("source")
                source_str = _string_literal_value(clause) if clause else None
                clause_node = next((c for c in child.children if c.type == "import_clause"), None)
                names = collect_identifiers(clause_node) if clause_node else []
                dependencies.extend(names if names else ([source_str] if source_str else []))
            elif child.type in ("class_declaration",):
                visit_class(child)
            elif child.type == "function_declaration":
                name_node = child.child_by_field_name("name")
                functions.append(
                    FunctionInfo(
                        function_name=name_node.text.decode() if name_node else "",
                        parameters=_ts_parameters(child.child_by_field_name("parameters")),
                        return_type=_ts_return_type(child),
                    )
                )
            elif child.type == "call_expression":
                endpoint = _ts_endpoint_from_call(child)
                if endpoint:
                    endpoints.append(endpoint)
                visit(child)
            elif child.type == "export_statement":
                visit(child)
            else:
                visit(child)

    visit(root)
    return dependencies, classes, functions, endpoints


# --- Java ---------------------------------------------------------------------

# Spring MVC. @RequestMapping ditangani terpisah: methodnya dibaca dari `method=`,
# dan di level class dia bukan endpoint melainkan prefix.
SPRING_METHOD_ANNOTATIONS = {
    "getmapping": "GET",
    "postmapping": "POST",
    "putmapping": "PUT",
    "deletemapping": "DELETE",
    "patchmapping": "PATCH",
}

# Java tidak menaruh apa pun di top level: semua method ada di dalam salah satu
# dari keempat ini. `interface` bukan pelengkap — Spring Data menulis SELURUH
# repository sebagai interface (OwnerRepository, VetRepository, PetTypeRepository
# di petclinic), jadi menangani class saja membuat lapisan data hilang total.
JAVA_TYPE_DECLARATIONS = (
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
)


def _java_modifiers(node):
    """`modifiers` BUKAN field di grammar Java — `child_by_field_name("modifiers")`
    selalu None, beda dari `name`/`body`/`parameters` yang memang field. Menyalin
    pola Python apa adanya di sini menghasilkan NOL endpoint tanpa error apa pun:
    kelas kegagalan yang sama dengan `route` yang dulu bukan anggota HTTP_METHODS.
    """
    return next((c for c in node.named_children if c.type == "modifiers"), None)


def _java_annotations(node) -> list:
    mods = _java_modifiers(node)
    if mods is None:
        return []
    # `marker_annotation` = tanpa argumen (@PostMapping), `annotation` = dengan
    # argumen (@GetMapping("/list")). Dua node type berbeda untuk satu konsep.
    return [c for c in mods.named_children if c.type in ("annotation", "marker_annotation")]


def _java_annotation_name(ann) -> str:
    name = ann.child_by_field_name("name")
    if name is None:
        name = next((c for c in ann.named_children if c.type in ("identifier", "scoped_identifier")), None)
    return name.text.decode().rsplit(".", 1)[-1].lower() if name else ""


def _java_annotation_args(ann):
    return next((c for c in ann.named_children if c.type == "annotation_argument_list"), None)


def _java_path_value(node) -> Optional[str]:
    """String literal, atau elemen pertamanya kalau path ditulis sebagai array.

    `@GetMapping("/vets")` dan `@GetMapping({"/vets"})` adalah satu handler yang
    sama; kurung kurawal cuma sintaks. Mencatat semua elemen array akan membuat
    satu method tampak seperti beberapa fitur berbeda di dokumen, jadi ambil yang
    pertama.
    """
    if node is None:
        return None
    if node.type == "element_value_array_initializer":
        node = next((c for c in node.named_children), None)
    return _string_literal_value(node)


def _java_annotation_path(ann) -> Optional[str]:
    """Path dari anotasi. Empat bentuk, semuanya diambil dari petclinic sungguhan:
        @GetMapping("/list")                     -> string_literal posisional
        @GetMapping({"/vets"})                   -> array posisional (VetController)
        @RequestMapping(value = "/find", ...)    -> element_value_pair `value`
        @RequestMapping(path = "/p", ...)        -> element_value_pair `path`

    Bentuk array posisional sempat terlewat, dan gagalnya SUNYI: path jatuh ke None
    lalu keluar sebagai "/", sehingga VetController dan WelcomeController sama-sama
    melaporkan `GET /` — pola yang sama persis dengan url_prefix Blueprint Flask.
    """
    args = _java_annotation_args(ann)
    if args is None:
        return None
    for child in args.named_children:
        if child.type in ("string_literal", "element_value_array_initializer"):
            return _java_path_value(child)
        if child.type == "element_value_pair":
            key = child.child_by_field_name("key")
            if key is not None and key.text.decode() in ("value", "path"):
                return _java_path_value(child.child_by_field_name("value"))
    return None


def _java_request_methods(value) -> list[str]:
    """`method = RequestMethod.POST` -> ["POST"]
    `method = {RequestMethod.GET, RequestMethod.PUT}` -> ["GET", "PUT"]"""
    if value is None:
        return []
    if value.type == "element_value_array_initializer":
        return [m for c in value.named_children for m in _java_request_methods(c)]
    if value.type == "field_access":
        field = value.child_by_field_name("field")
        name = field.text.decode().lower() if field else ""
        return [name.upper()] if name in HTTP_METHODS else []
    if value.type == "identifier":
        # `import static ...RequestMethod.GET` membuat RequestMethod. hilang.
        name = value.text.decode().lower()
        return [name.upper()] if name in HTTP_METHODS else []
    return []


def _java_annotation_methods(ann) -> list[str]:
    args = _java_annotation_args(ann)
    if args is None:
        return []
    for child in args.named_children:
        if child.type != "element_value_pair":
            continue
        key = child.child_by_field_name("key")
        if key is not None and key.text.decode() == "method":
            return _java_request_methods(child.child_by_field_name("value"))
    return []


def _java_join_path(prefix: str, path: Optional[str]) -> str:
    """@RequestMapping("/owners") di class + @GetMapping("/new") di method = /owners/new.

    Ini masalah yang sama dengan url_prefix Blueprint Flask (path tercatat /login
    padahal aslinya /auth/login) — bedanya di Java kedua bagiannya ada di FILE YANG
    SAMA, jadi bisa disambung deterministik tanpa analisis lintas-file.
    """
    prefix = (prefix or "").strip()
    path = (path or "").strip()
    if not prefix:
        return path or "/"
    if not path:
        return prefix
    return prefix.rstrip("/") + "/" + path.lstrip("/")


def _java_class_path_prefix(annotations: list) -> str:
    """@RequestMapping di level class adalah PREFIX, bukan endpoint. Memperlakukannya
    sebagai endpoint akan memunculkan `/owners` hantu yang tidak punya handler."""
    for ann in annotations:
        if _java_annotation_name(ann) == "requestmapping":
            return _java_annotation_path(ann) or ""
    return ""


def _java_endpoints_from_annotations(annotations: list, prefix: str) -> list[EndpointInfo]:
    endpoints: list[EndpointInfo] = []
    for ann in annotations:
        name = _java_annotation_name(ann)
        if name in SPRING_METHOD_ANNOTATIONS:
            endpoints.append(
                EndpointInfo(
                    method=SPRING_METHOD_ANNOTATIONS[name],
                    path=_java_join_path(prefix, _java_annotation_path(ann)),
                )
            )
        elif name == "requestmapping":
            # APROKSIMASI YANG DISENGAJA: @RequestMapping tanpa `method=` sebenarnya
            # menerima SEMUA method. Beda dari Flask, di mana GET memang default
            # framework-nya — di sini GET adalah tebakan, bukan aturan. Dipilih
            # karena mencatat 5 baris untuk satu handler adalah noise yang pasti
            # salah, sementara mencatat 0 membuang handler yang nyata.
            # BELUM TERUJI DI REPO NYATA: petclinic memakai @GetMapping/@PostMapping
            # eksplisit di semua handler-nya, dan @RequestMapping-nya cuma di level
            # class (prefix). Butuh repo Spring bergaya lama untuk membuktikan ini.
            declared = _java_annotation_methods(ann) or ["GET"]
            endpoints.extend(
                EndpointInfo(method=method, path=_java_join_path(prefix, _java_annotation_path(ann)))
                for method in declared
            )
    return endpoints


def _java_javadoc(node) -> str:
    """Javadoc adalah block_comment SIBLING sebelum deklarasi — bukan di dalam body
    seperti docstring Python, jadi _docstring_from_body tidak akan menemukannya.

    Ini bukan detail kosmetik: `description` membawa docstring ke Contract A, dan
    LLM terbukti membacanya (PostgreSQL/Neon di dokumen esteler datang dari sana,
    bukan dari `dependencies`)."""
    prev = node.prev_named_sibling
    if prev is None or prev.type != "block_comment":
        return ""
    text = prev.text.decode().strip()
    if not text.startswith("/**"):
        return ""  # komentar biasa /* ... */, bukan Javadoc
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("/**"):
            line = line[3:]
        if line.endswith("*/"):
            line = line[:-2]
        line = line.lstrip("*").strip()
        if line.startswith("@"):
            break  # @param/@return dst: metadata tag, bukan kalimat deskripsi
        if line:
            lines.append(line)
    return " ".join(lines).strip()


def _java_parameters(params_node) -> list[str]:
    if params_node is None:
        return []
    names = []
    for p in params_node.named_children:
        if p.type not in ("formal_parameter", "spread_parameter"):
            continue
        name = p.child_by_field_name("name")
        names.append(name.text.decode() if name else p.text.decode())
    return names


def _java_import_name(node) -> Optional[str]:
    """import java.util.List;                        -> List
    import java.util.*;                              -> java.util
    import static org.junit.Assert.assertEquals;     -> assertEquals

    Diselaraskan dengan Python (`from x import y` -> `y`): yang dicatat adalah nama
    yang dipakai di kode, bukan path paket penuh."""
    target = next(
        (c for c in node.named_children if c.type in ("scoped_identifier", "identifier")), None
    )
    if target is None:
        return None
    if any(c.type == "asterisk" for c in node.children):
        return target.text.decode()  # wildcard: nama yang bermakna cuma paketnya
    if target.type == "identifier":
        return target.text.decode()
    name = target.child_by_field_name("name")
    return name.text.decode() if name else target.text.decode()


def _parse_java(root) -> tuple[list[str], list[ClassInfo], list[FunctionInfo], list[EndpointInfo]]:
    dependencies: list[str] = []
    classes: list[ClassInfo] = []
    endpoints: list[EndpointInfo] = []

    def visit_type(type_node):
        name_node = type_node.child_by_field_name("name")
        class_info = ClassInfo(class_name=name_node.text.decode() if name_node else "")
        prefix = _java_class_path_prefix(_java_annotations(type_node))
        body = type_node.child_by_field_name("body")
        if body is None:
            classes.append(class_info)
            return
        for member in body.named_children:
            if member.type == "method_declaration":
                method_name = member.child_by_field_name("name")
                return_type = member.child_by_field_name("type")
                parameters = _java_parameters(member.child_by_field_name("parameters"))
                class_info.methods.append(
                    MethodInfo(
                        method_name=method_name.text.decode() if method_name else "",
                        parameters=parameters,
                        return_type=return_type.text.decode() if return_type else None,
                        description=_java_javadoc(member),
                    )
                )
                found = _java_endpoints_from_annotations(_java_annotations(member), prefix)
                for endpoint in found:
                    if parameters:
                        endpoint.payload = ", ".join(parameters)
                endpoints.extend(found)
            elif member.type in JAVA_TYPE_DECLARATIONS:
                visit_type(member)  # nested/inner class
        classes.append(class_info)

    def visit(node):
        for child in node.named_children:
            if child.type == "import_declaration":
                name = _java_import_name(child)
                if name:
                    dependencies.append(name)
            elif child.type in JAVA_TYPE_DECLARATIONS:
                visit_type(child)
            else:
                visit(child)

    visit(root)
    # functions[] sengaja selalu kosong: Java tidak punya top-level function, semua
    # method hidup di dalam class. Kosong di sini adalah fakta, bukan lubang.
    return dependencies, classes, [], endpoints


# --- Public API ---------------------------------------------------------------

def parse_file(file_name: str, file_path: str, content: str) -> Optional[FileMetadata]:
    """Ekstraksi struktural deterministik (tanpa LLM) untuk satu file. Return None jika
    bahasanya belum didukung oleh parser (caller bisa fallback ke generate_file_metadata_prompt)."""
    language = detect_language(file_name)
    if language is None:
        return None

    parser = tslp.get_parser(language)
    tree = parser.parse(content.encode("utf-8"))

    if language == "python":
        dependencies, classes, functions, endpoints = _parse_python(tree.root_node)
    elif language in ("javascript", "typescript", "tsx"):
        dependencies, classes, functions, endpoints = _parse_ts_js(tree.root_node)
    elif language == "java":
        dependencies, classes, functions, endpoints = _parse_java(tree.root_node)
    else:
        return None

    return FileMetadata(
        file_name=file_name,
        file_path=file_path,
        type=_guess_file_type(file_name, bool(endpoints)),
        dependencies=dependencies,
        classes=classes,
        functions=functions,
        api_endpoints=endpoints,
    )


def build_parsed_repo_context(project_name: str, workspaces: list) -> dict:
    """workspaces: list of app.domain.models.Workspace, regardless of which SourceProvider
    produced them (GitHub OAuth/PAT, ZIP upload, ...). Output cocok dengan Contract A
    (ParsedRepoContext.json) yang dikonsumsi Peran 2. Parser tidak tahu dan tidak peduli
    dari mana Workspace ini berasal."""
    repositories = []
    for workspace in workspaces:
        files = []
        for workspace_file in workspace.files:
            metadata = parse_file(workspace_file.file_name, workspace_file.file_path, workspace_file.content)
            if metadata is None:
                metadata = FileMetadata(
                    file_name=workspace_file.file_name,
                    file_path=workspace_file.file_path,
                    type="other",
                )
            files.append(asdict(metadata))
        repositories.append({"repo_tag": workspace.repo_tag, "files": files})
    return {"project_name": project_name, "repositories": repositories}


if __name__ == "__main__":
    from app.domain.models import GithubIngestRequest, SourceType
    from app.services.ingestion_service import IngestionService

    workspaces = IngestionService().ingest(
        SourceType.GITHUB,
        [
            GithubIngestRequest(
                repo_tag="Backend",
                repo_url="https://github.com/MaheswaraKaindra/auto-document-generator",
                branch="develop",
            )
        ],
    )
    result = build_parsed_repo_context("auto-document-generator", workspaces)
    print(json.dumps(result, indent=2, ensure_ascii=False))
