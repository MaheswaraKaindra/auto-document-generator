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
    if node is None or node.type != "string":
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


def _python_endpoint_from_decorator(decorator_node) -> Optional[EndpointInfo]:
    call = next((c for c in decorator_node.named_children if c.type == "call"), None)
    if call is None:
        return None
    fn = call.child_by_field_name("function")
    if fn is None or fn.type != "attribute":
        return None
    attr = fn.child_by_field_name("attribute")
    if attr is None or attr.text.decode().lower() not in HTTP_METHODS:
        return None
    args = call.child_by_field_name("arguments")
    path = _string_literal_value(args.named_children[0]) if args and args.named_children else None
    if not path:
        return None
    return EndpointInfo(method=attr.text.decode().upper(), path=path)


def _python_function_info(fn_node, decorators: list) -> tuple[FunctionInfo, Optional[EndpointInfo]]:
    name_node = fn_node.child_by_field_name("name")
    return_type_node = fn_node.child_by_field_name("return_type")
    info = FunctionInfo(
        function_name=name_node.text.decode() if name_node else "",
        parameters=_python_parameters(fn_node.child_by_field_name("parameters")),
        return_type=return_type_node.text.decode() if return_type_node else None,
        description=_docstring_from_body(fn_node.child_by_field_name("body")),
    )
    endpoint = None
    for dec in decorators:
        endpoint = _python_endpoint_from_decorator(dec)
        if endpoint:
            if info.parameters:
                endpoint.payload = ", ".join(info.parameters)
            break
    return info, endpoint


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
                method_info, endpoint = _python_function_info(fn_node, decorators)
                class_info.methods.append(
                    MethodInfo(
                        method_name=method_info.function_name,
                        parameters=method_info.parameters,
                        return_type=method_info.return_type,
                        description=method_info.description,
                    )
                )
                if endpoint:
                    endpoints.append(endpoint)
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
                    fn_info, endpoint = _python_function_info(inner, decorators)
                    functions.append(fn_info)
                    if endpoint:
                        endpoints.append(endpoint)
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
