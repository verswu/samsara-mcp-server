#!/usr/bin/env python3
"""
Codegen script: generate samsara_client method, server tool registration, and test stub
from an OpenAPI endpoint spec (JSON from stdin or file).

Usage:
  # From file
  uv run python scripts/add_endpoint.py --spec endpoint_spec.json --tool-name get_drivers

  # From stdin (interactive)
  uv run python scripts/add_endpoint.py --tool-name get_drivers
  # Then paste JSON

  # Legacy usage (backwards compatible)
  uv run python scripts/add_endpoint.py path/to/spec.json

Input JSON format (OpenAPI-style, one operation):
  Option A - path + method key:
    { "path": "/fleet/drivers", "get": { "operationId": "listDrivers", "summary": "...", "parameters": [...] } }
    { "path": "/fleet/drivers", "post": { "operationId": "createDriver", "requestBody": {...}, ... } }
    { "path": "/fleet/drivers/{id}", "patch": { "operationId": "updateDriver", "requestBody": {...}, ... } }
  Option B - path as key:
    { "/fleet/drivers": { "get": { "operationId": "listDrivers", ... } } }

Outputs four sections to stdout for copy-paste into:
  - samsara_client.py
  - server.py (list_tools and call_tool)
  - tests/test_samsara_client.py
  - README.md snippet
"""

import argparse
import json
import re
import sys
from typing import Any


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return s.replace("__", "_")


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = name.split("_")
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def parse_spec(data: dict, tool_name_override: str | None = None) -> tuple[str, str, str, str, list[dict], dict | None]:
    """
    Parse OpenAPI-style spec. Returns:
    (path, method, operation_id, method_name, parameters, request_body_schema)
    """
    path = ""
    method = ""
    op = None

    # Option B: path as key, e.g. { "/fleet/drivers": { "get": { ... } } }
    for key, value in data.items():
        if key.startswith("/") and isinstance(value, dict):
            path = key
            # Priority order: get, post, patch, put, delete
            for m in ["get", "post", "patch", "put", "delete"]:
                if m in value:
                    method = m
                    op = value[m]
                    break
            break

    # Option A: explicit path and get/post/patch
    if not op:
        path = data.get("path", "")
        for m in ["get", "post", "patch", "put", "delete"]:
            if m in data:
                method = m
                op = data[m]
                break

    if not path or not method or not op:
        raise SystemExit(
            "Invalid spec: need path and get/post/patch with operationId.\n"
            'Example: {"path": "/me", "get": {"operationId": "getOrganizationInfo", "summary": "..."}}'
        )

    operation_id = op.get("operationId") or camel_to_snake(path.strip("/").replace("/", "_"))
    method_name = tool_name_override or camel_to_snake(operation_id)

    # Query and path parameters (path params are substituted in URL, not sent as query)
    parameters = []
    for p in op.get("parameters") or []:
        if p.get("in") in ("query", "path"):
            name = p.get("name")
            schema = p.get("schema") or {}
            param_type = schema.get("type", "string")
            # Handle array items
            if param_type == "array" and "items" in schema:
                param_type = "array"  # Keep as array for proper handling
            parameters.append({
                "name": name,
                "in": p.get("in", "query"),
                "type": param_type,
                "enum": schema.get("enum"),
                "description": p.get("description") or schema.get("description") or "",
                "required": p.get("required", False),
                "default": schema.get("default"),
            })

    request_body_schema = None
    if method in ("post", "patch", "put") and op.get("requestBody"):
        rb = op["requestBody"]
        content = (rb.get("content") or {}).get("application/json") or {}
        request_body_schema = content.get("schema")

    return path, method, operation_id, method_name, parameters, request_body_schema


def py_type(schema_type: str, enum: list | None, required: bool = False) -> str:
    """Return Python type hint for a parameter."""
    base_type = "str"
    if schema_type == "integer":
        base_type = "int"
    elif schema_type == "boolean":
        base_type = "bool"
    elif schema_type == "array":
        base_type = "List[str]"

    if required:
        return base_type
    return f"Optional[{base_type}]"


def gen_client_method(path: str, method: str, method_name: str, parameters: list[dict], request_body_schema: dict | None) -> str:
    """Generate the async method for samsara_client.py."""
    path_params = [p for p in parameters if p.get("in") == "path"]
    query_params = [p for p in parameters if p.get("in") != "path"]

    if method == "get":
        params = []
        param_docs = []
        param_assigns = []
        # Path params: required (no Optional)
        for p in path_params:
            name_camel = p["name"]
            name_snake = camel_to_snake(name_camel)
            typ = "str" if p["type"] == "string" else p["type"]
            params.append(f"        {name_snake}: {typ},")
            desc = (p.get("description") or "").replace("\n", " ").strip()[:80]
            param_docs.append(f"            {name_snake}: {desc}")
        # Query params: optional (unless required)
        for p in query_params:
            name_camel = p["name"]
            name_snake = camel_to_snake(name_camel)
            is_required = p.get("required", False)
            typ = py_type(p["type"], p.get("enum"), required=is_required)
            if is_required:
                params.append(f"        {name_snake}: {typ},")
            else:
                params.append(f"        {name_snake}: {typ} = None,")
            desc = (p.get("description") or "").replace("\n", " ").strip()[:80]
            param_docs.append(f"            {name_snake}: {desc}")
            param_assigns.append(f"        if {name_snake} is not None:\n            params[\"{name_camel}\"] = {name_snake}")

        params_str = "\n".join(params) if params else ""
        doc_args = "\n".join(param_docs) if param_docs else "            (none)"
        assigns_str = "\n".join(param_assigns) if param_assigns else ""

        # Build url_path: substitute path params in the path template
        if path_params:
            url_build_lines = [f"        url_path = \"{path}\""]
            for p in path_params:
                name_camel = p["name"]
                name_snake = camel_to_snake(name_camel)
                url_build_lines.append(f"        url_path = url_path.replace(\"{{{name_camel}}}\", str({name_snake}))")
            url_build_str = "\n".join(url_build_lines)
            request_line = "            response = await self.client.get(url_path, params=params)"
        else:
            url_build_str = ""
            request_line = "            response = await self.client.get(\"" + path + "\", params=params)"

        return f'''    async def {method_name}(
        self,{chr(10) + params_str if params_str else ""}
    ) -> Dict[str, Any]:
        """
        (Add docstring from OpenAPI summary/description.)

        Args:
{doc_args}

        Returns:
            Response data from the Samsara API.
        """
        params: Dict[str, Any] = {{}}
{assigns_str}
{chr(10) + url_build_str + chr(10) if url_build_str else ""}

        try:
{request_line}

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {{retry_after}} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {{response.status_code}}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {{error_body['message']}}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {{error_body['error']}}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({{response.status_code}}): {{error_text[:200]}}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except (SamsaraAPIError, SamsaraRateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {{e.response.status_code}}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {{str(e)}}") from e
'''
    elif method == "patch":
        # PATCH with path param + body
        path_params = [p for p in parameters if p.get("in") == "path"]
        params = []
        param_docs = []
        for p in path_params:
            name_camel = p["name"]
            name_snake = camel_to_snake(name_camel)
            params.append(f"        {name_snake}: str,")
            desc = (p.get("description") or "").replace("\n", " ").strip()[:80]
            param_docs.append(f"            {name_snake}: {desc}")
        params.append("        body: Dict[str, Any],")
        param_docs.append("            body: Fields to update (only include fields to patch).")

        params_str = "\n".join(params)
        doc_args = "\n".join(param_docs)

        # Build url_path
        url_build_lines = [f"        url_path = \"{path}\""]
        for p in path_params:
            name_camel = p["name"]
            name_snake = camel_to_snake(name_camel)
            url_build_lines.append(f"        url_path = url_path.replace(\"{{{name_camel}}}\", str({name_snake}))")
        url_build_str = "\n".join(url_build_lines)

        return f'''    async def {method_name}(
        self,
{params_str}
    ) -> Dict[str, Any]:
        """
        (Add docstring from OpenAPI summary/description.)

        Args:
{doc_args}

        Returns:
            Response data from the Samsara API.
        """
{url_build_str}

        try:
            response = await self.client.patch(url_path, json=body)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {{retry_after}} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {{response.status_code}}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {{error_body['message']}}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {{error_body['error']}}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({{response.status_code}}): {{error_text[:200]}}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except (SamsaraAPIError, SamsaraRateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {{e.response.status_code}}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {{str(e)}}") from e
'''
    else:
        # POST with body
        return f'''    async def {method_name}(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        (Add docstring from OpenAPI summary/description.)

        Args:
            body: Request body (add required/optional fields from OpenAPI schema).

        Returns:
            Response data from the Samsara API.
        """
        try:
            response = await self.client.post("{path}", json=body)

            if response.status_code == 429:
                retry_after = None
                if "Retry-After" in response.headers:
                    try:
                        retry_after = int(response.headers["Retry-After"])
                    except ValueError:
                        pass
                error_message = (
                    "Rate limit exceeded. Samsara API allows 25 requests per second. "
                    "Please wait before retrying."
                )
                if retry_after:
                    error_message += f" Retry after {{retry_after}} seconds."
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict) and "message" in error_body:
                        error_message = error_body["message"]
                except Exception:
                    pass
                raise SamsaraRateLimitError(error_message, retry_after=retry_after)

            if response.status_code >= 400:
                error_message = f"Samsara API error: {{response.status_code}}"
                error_body = None
                try:
                    error_body = response.json()
                    if isinstance(error_body, dict):
                        if "message" in error_body:
                            error_message = f"Samsara API error: {{error_body['message']}}"
                        elif "error" in error_body:
                            error_message = f"Samsara API error: {{error_body['error']}}"
                except Exception:
                    try:
                        error_text = response.text
                        if error_text:
                            error_message = f"Samsara API error ({{response.status_code}}): {{error_text[:200]}}"
                    except Exception:
                        pass
                raise SamsaraAPIError(
                    error_message,
                    status_code=response.status_code,
                    response_body=error_body,
                )

            return response.json()

        except (SamsaraAPIError, SamsaraRateLimitError):
            raise
        except httpx.HTTPStatusError as e:
            raise SamsaraAPIError(
                f"HTTP error: {{e.response.status_code}}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise SamsaraError(f"Network error connecting to Samsara API: {{str(e)}}") from e
'''


def gen_tool_registration(method_name: str, path: str, method: str, parameters: list[dict], summary: str, description: str) -> str:
    """Generate Tool(...) for server.py list_tools."""
    summary_clean = (summary or description or "").replace("\n", " ").strip()[:200]
    desc_repr = repr(summary_clean) if summary_clean else repr("(Add description.)")
    path_params = [p for p in parameters if p.get("in") == "path"]
    query_params = [p for p in parameters if p.get("in") != "path"]

    if method == "get" and parameters:
        props = []
        required_params = []
        for p in parameters:
            name_camel = p["name"]
            typ = p["type"]
            desc_param = (p.get("description") or "").replace("\n", " ").strip()[:120].replace('"', '\\"')
            if p.get("in") == "path" or p.get("required"):
                required_params.append(name_camel)
            if typ == "integer":
                props.append(f'''                    "{name_camel}": {{
                        "type": "integer",
                        "description": "{desc_param}",
                    }},''')
            elif typ == "boolean":
                props.append(f'''                    "{name_camel}": {{
                        "type": "boolean",
                        "description": "{desc_param}",
                    }},''')
            elif typ == "array":
                props.append(f'''                    "{name_camel}": {{
                        "type": "array",
                        "items": {{"type": "string"}},
                        "description": "{desc_param}",
                    }},''')
            elif p.get("enum"):
                enum_vals = ", ".join(f'"{v}"' for v in p["enum"])
                props.append(f'''                    "{name_camel}": {{
                        "type": "string",
                        "enum": [{enum_vals}],
                        "description": "{desc_param}",
                    }},''')
            else:
                props.append(f'''                    "{name_camel}": {{
                        "type": "string",
                        "description": "{desc_param}",
                    }},''')
        props_str = "\n".join(props)
        required_block = ""
        if required_params:
            required_list = ", ".join(f'"{p}"' for p in required_params)
            required_block = f'''
                "required": [{required_list}],'''
        schema_block = f'''            inputSchema={{
                "type": "object",
                "properties": {{
{props_str}
                }},{required_block}
            }},'''
    elif method == "patch":
        # PATCH: id (path param) + body
        path_params = [p for p in parameters if p.get("in") == "path"]
        props = []
        required_params = []
        for p in path_params:
            name_camel = p["name"]
            desc_param = (p.get("description") or "").replace("\n", " ").strip()[:120].replace('"', '\\"')
            props.append(f'''                    "{name_camel}": {{
                        "type": "string",
                        "description": "{desc_param}",
                    }},''')
            required_params.append(name_camel)
        props.append('''                    "body": {
                        "type": "object",
                        "description": "Fields to update (only include fields to patch).",
                    },''')
        required_params.append("body")
        props_str = "\n".join(props)
        required_list = ", ".join(f'"{p}"' for p in required_params)
        schema_block = f'''            inputSchema={{
                "type": "object",
                "properties": {{
{props_str}
                }},
                "required": [{required_list}],
            }},'''
    elif method == "post":
        schema_block = '''            inputSchema={
                "type": "object",
                "properties": {
                    "body": {
                        "type": "object",
                        "description": "Request body (add schema properties from OpenAPI).",
                    },
                },
                "required": ["body"],
            },'''
    else:
        schema_block = '''            inputSchema={
                "type": "object",
                "properties": {},
            },'''

    return f'''        Tool(
            name="{method_name}",
            description=(
                {desc_repr}
            ),
{schema_block}
        ),'''


def gen_call_tool_handler(method_name: str, method: str, parameters: list[dict]) -> str:
    """Generate elif block for server.py call_tool."""
    if method == "get":
        path_params = [p for p in parameters if p.get("in") == "path"]
        required_query_params = [p for p in parameters if p.get("in") != "path" and p.get("required")]
        all_required = path_params + required_query_params
        arg_gets = []
        client_args = []
        for p in parameters:
            name_camel = p["name"]
            name_snake = camel_to_snake(name_camel)
            arg_gets.append(f"            {name_snake} = arguments.get(\"{name_camel}\")")
            client_args.append(f"                {name_snake}={name_snake},")
        arg_gets_str = "\n".join(arg_gets)
        client_args_str = "\n".join(client_args)
        # Validate required params
        validation_block = ""
        if all_required:
            required_check = " or ".join(f"not {camel_to_snake(p['name'])}" for p in all_required)
            param_list = ", ".join(f"'{p['name']}'" for p in all_required)
            validation_block = f'''
            if {required_check}:
                return [TextContent(
                    type="text",
                    text="Error: {method_name} requires {param_list}."
                )]
'''
        if parameters:
            call_block = f'''{arg_gets_str}
{validation_block}
            result = await client.{method_name}(
{client_args_str}
            )

            import json'''
        else:
            call_block = f'''            result = await client.{method_name}()

            import json'''
        return f'''    elif name == "{method_name}":
        try:
{call_block}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\\n\\nPlease wait {{e.retry_after}} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {{error_message}}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\\n\\nResponse details: {{json.dumps(e.response_body, indent=2)}}"
            return [TextContent(type="text", text=f"Error: {{error_message}}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {{str(e)}}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {{type(e).__name__}}: {{str(e)}}"
            )]'''
    elif method == "patch":
        # PATCH: extract id (path param) and body
        path_params = [p for p in parameters if p.get("in") == "path"]
        arg_gets = []
        client_args = []
        for p in path_params:
            name_camel = p["name"]
            name_snake = camel_to_snake(name_camel)
            arg_gets.append(f"            {name_snake} = arguments.get(\"{name_camel}\")")
            client_args.append(f"                {name_snake}={name_snake},")
        arg_gets.append("            body = arguments.get(\"body\") or {}")
        client_args.append("                body=body,")
        arg_gets_str = "\n".join(arg_gets)
        client_args_str = "\n".join(client_args)
        # Validate required params
        required_check = " or ".join([f"not {camel_to_snake(p['name'])}" for p in path_params] + ["not body"])
        param_list = ", ".join([f"'{p['name']}'" for p in path_params] + ["'body'"])
        return f'''    elif name == "{method_name}":
        try:
{arg_gets_str}

            if {required_check}:
                return [TextContent(
                    type="text",
                    text="Error: {method_name} requires {param_list}."
                )]

            result = await client.{method_name}(
{client_args_str}
            )

            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\\n\\nPlease wait {{e.retry_after}} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {{error_message}}")]

        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\\n\\nResponse details: {{json.dumps(e.response_body, indent=2)}}"
            return [TextContent(type="text", text=f"Error: {{error_message}}")]

        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {{str(e)}}")]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {{type(e).__name__}}: {{str(e)}}"
            )]'''
    else:
        return f'''    elif name == "{method_name}":
        try:
            body = arguments.get("body") or {{}}
            result = await client.{method_name}(body)
            import json
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except SamsaraRateLimitError as e:
            error_message = str(e)
            if e.retry_after:
                error_message += f"\\n\\nPlease wait {{e.retry_after}} seconds before retrying."
            return [TextContent(type="text", text=f"Error: {{error_message}}")]
        except SamsaraAPIError as e:
            error_message = str(e)
            if e.response_body:
                import json
                error_message += f"\\n\\nResponse details: {{json.dumps(e.response_body, indent=2)}}"
            return [TextContent(type="text", text=f"Error: {{error_message}}")]
        except SamsaraError as e:
            return [TextContent(type="text", text=f"Error: {{str(e)}}")]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Unexpected error: {{type(e).__name__}}: {{str(e)}}"
            )]'''


def gen_test_stub(method_name: str, path: str, method: str, parameters: list[dict]) -> str:
    """Generate test stubs for tests/test_samsara_client.py."""
    sample_var = "SAMPLE_" + method_name.upper().replace("-", "_") + "_RESPONSE"
    path_params = [p for p in parameters if p.get("in") == "path"]
    query_params = [p for p in parameters if p.get("in") != "path"]

    if method == "get":
        if parameters:
            # Path params: required in call; URL has substituted path
            # Query params: go in params dict
            params_call = []
            path_substitutions = []  # (name, value) for building expected path
            params_expected = []
            for p in parameters[:5]:
                name_camel = p["name"]
                name_snake = camel_to_snake(name_camel)
                if p.get("in") == "path":
                    params_call.append(f"        {name_snake}=\"test-123\",")
                    path_substitutions.append((name_camel, "test-123"))
                else:
                    if p["type"] == "integer":
                        params_call.append(f"        {name_snake}=10,")
                        params_expected.append(f'            "{name_camel}": 10,')
                    elif p["type"] == "array":
                        params_call.append(f"        {name_snake}=[\"val1\", \"val2\"],")
                        params_expected.append(f'            "{name_camel}": ["val1", "val2"],')
                    elif p["type"] == "boolean":
                        params_call.append(f"        {name_snake}=True,")
                        params_expected.append(f'            "{name_camel}": True,')
                    else:
                        params_call.append(f"        {name_snake}=\"value\",")
                        params_expected.append(f'            "{name_camel}": "value",')
            expected_path = path
            for name_camel, val in path_substitutions:
                expected_path = expected_path.replace("{" + name_camel + "}", val)
            params_call_str = "\n".join(params_call)
            params_expected_str = "\n".join(params_expected)
            if query_params:
                params_assert = f'''        params={{
{params_expected_str}
        }},
    )'''
            else:
                params_assert = "        params={},\n    )"
            default_test = ""
            if not path_params and not any(p.get("required") for p in query_params):
                default_test = f'''

async def test_{method_name}_default_values(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, {sample_var})
    result = await client.{method_name}()
    assert result == {sample_var}
    mock_httpx_client.get.assert_called_once_with("{path}", params={{}})
'''
            # Generate path param call for 401 test
            path_param_401_call = ", ".join(
                f'{camel_to_snake(p["name"])}="test"' for p in path_params
            ) if path_params else ""
            return f'''
# ---------------------------------------------------------------------------
# {method_name} — path/query params
# ---------------------------------------------------------------------------

async def test_{method_name}_builds_correct_request(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, {sample_var})
    await client.{method_name}(
{params_call_str}
    )
    mock_httpx_client.get.assert_called_once_with(
        "{expected_path}",
{params_assert}
{default_test}

async def test_{method_name}_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(401, {{"message": "Unauthorized"}})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.{method_name}({path_param_401_call})
    assert exc_info.value.status_code == 401
'''
        else:
            return f'''
# ---------------------------------------------------------------------------
# {method_name} — GET (no params)
# ---------------------------------------------------------------------------

async def test_{method_name}_calls_endpoint(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(200, {sample_var})
    result = await client.{method_name}()
    assert result == {sample_var}
    mock_httpx_client.get.assert_called_once_with("{path}")

async def test_{method_name}_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.get.return_value = _make_response(401, {{"message": "Unauthorized"}})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.{method_name}()
    assert exc_info.value.status_code == 401
'''
    elif method == "patch":
        # PATCH: path param + body
        path_param_calls = []
        path_substitutions = []
        for p in path_params:
            name_camel = p["name"]
            name_snake = camel_to_snake(name_camel)
            path_param_calls.append(f'{name_snake}="test-123"')
            path_substitutions.append((name_camel, "test-123"))
        expected_path = path
        for name_camel, val in path_substitutions:
            expected_path = expected_path.replace("{" + name_camel + "}", val)
        path_args_str = ", ".join(path_param_calls)
        return f'''
# ---------------------------------------------------------------------------
# {method_name} — PATCH path + body
# ---------------------------------------------------------------------------

async def test_{method_name}_sends_correct_request(client, mock_httpx_client):
    mock_httpx_client.patch.return_value = _make_response(200, {sample_var})
    body = {{"name": "Updated Name"}}
    result = await client.{method_name}({path_args_str}, body=body)
    assert result == {sample_var}
    mock_httpx_client.patch.assert_called_once_with(
        "{expected_path}",
        json=body,
    )

async def test_{method_name}_401_raises_samsara_api_error(client, mock_httpx_client):
    mock_httpx_client.patch.return_value = _make_response(401, {{"message": "Unauthorized"}})
    with pytest.raises(SamsaraAPIError) as exc_info:
        await client.{method_name}({path_args_str}, body={{}})
    assert exc_info.value.status_code == 401
'''
    else:
        return f'''
# ---------------------------------------------------------------------------
# {method_name} — POST body
# ---------------------------------------------------------------------------

async def test_{method_name}_sends_correct_body(client, mock_httpx_client):
    mock_httpx_client.post.return_value = _make_response(200, {sample_var})
    body = {{"key": "value"}}
    result = await client.{method_name}(body)
    assert result == {sample_var}
    mock_httpx_client.post.assert_called_once_with("{path}", json=body)

async def test_{method_name}_429_raises_rate_limit_error(client, mock_httpx_client):
    mock_httpx_client.post.return_value = _make_response(
        429,
        {{"message": "Too many requests"}},
        headers={{"Retry-After": "30"}},
    )
    with pytest.raises(SamsaraRateLimitError) as exc_info:
        await client.{method_name}({{"key": "value"}})
    assert exc_info.value.retry_after == 30
'''


def gen_readme_snippet(method_name: str, summary: str, parameters: list[dict], method: str) -> str:
    """Generate README.md table row or section for the tool."""
    summary_clean = (summary or "").replace("\n", " ").strip()[:100]
    # Features bullet
    feature_bullet = f"- **{method_name}** - {summary_clean}"

    # Detailed section
    params_list = []
    for p in parameters[:8]:
        name_camel = p["name"]
        desc = (p.get("description") or "").replace("\n", " ").strip()[:60]
        req = " **Required.**" if p.get("required") or p.get("in") == "path" else ""
        params_list.append(f"- `{name_camel}` -{req} {desc}")
    if method in ("post", "patch"):
        params_list.append("- `body` - **Required.** Request body with fields to create/update.")
    params_str = "\n".join(params_list) if params_list else "- (none)"

    return f'''
### README.md Features bullet:
{feature_bullet}

### README.md Available Tools section:
### {method_name}

{summary_clean}

**Parameters:**
{params_str}
'''


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate MCP server code from an OpenAPI endpoint spec.",
        epilog="""
Examples:
  # From file with tool name
  uv run python scripts/add_endpoint.py --spec endpoint.json --tool-name get_drivers

  # From stdin (interactive)
  uv run python scripts/add_endpoint.py --tool-name get_drivers
  # Then paste JSON

  # Legacy usage (backwards compatible)
  uv run python scripts/add_endpoint.py endpoint.json
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--spec", "-s", type=str, help="Path to OpenAPI spec JSON file")
    parser.add_argument("--tool-name", "-n", type=str, help="Override the tool/method name (e.g., get_drivers)")
    parser.add_argument("positional_spec", nargs="?", type=str, help="Path to spec file (legacy, use --spec instead)")

    args = parser.parse_args()

    # Determine spec source: --spec, positional arg, or stdin
    spec_file = args.spec or args.positional_spec
    if spec_file and spec_file != "-":
        with open(spec_file) as f:
            data = json.load(f)
    else:
        print("Paste OpenAPI spec JSON (Ctrl+D when done):", file=sys.stderr)
        data = json.load(sys.stdin)

    path, method, operation_id, method_name, parameters, request_body_schema = parse_spec(
        data, tool_name_override=args.tool_name
    )

    # Get summary/description from the operation
    op = None
    if path in data and isinstance(data[path], dict):
        op = data[path].get(method) or {}
    else:
        op = data.get(method) or {}
    summary = op.get("summary") or ""
    description = op.get("description") or ""

    client_code = gen_client_method(path, method, method_name, parameters, request_body_schema)
    tool_code = gen_tool_registration(method_name, path, method, parameters, summary, description)
    handler_code = gen_call_tool_handler(method_name, method, parameters)
    test_code = gen_test_stub(method_name, path, method, parameters)
    readme_code = gen_readme_snippet(method_name, summary, parameters, method)

    print("=" * 60)
    print(f"GENERATED CODE FOR: {method_name} ({method.upper()} {path})")
    print("=" * 60)

    print("\n" + "=" * 60)
    print("1. samsara_client.py — add this async method (before async def close)")
    print("=" * 60)
    print(client_code)

    print("=" * 60)
    print("2. server.py list_tools() — add this Tool(...) to the return list")
    print("=" * 60)
    print(tool_code)

    print("\n" + "=" * 60)
    print("3. server.py call_tool() — add this elif block (before 'else: raise ValueError')")
    print("=" * 60)
    print(handler_code)

    print("\n" + "=" * 60)
    print("4. tests/test_samsara_client.py — add test stub(s)")
    print("   (Also add SAMPLE_" + method_name.upper() + "_RESPONSE to conftest.py)")
    print("=" * 60)
    print(test_code)

    print("\n" + "=" * 60)
    print("5. README.md — add to Features and Available Tools sections")
    print("=" * 60)
    print(readme_code)


if __name__ == "__main__":
    main()
