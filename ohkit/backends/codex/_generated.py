# Generated from OpenAI Codex rust-v0.162.0 (Apache-2.0).
# Do not edit; run make codex-generate. See THIRD_PARTY_NOTICES.md.

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, RootModel

from ohkit.backends.codex._wire import WireModel


class CodexProtocol(WireModel):
    pass


class ActivePermissionProfile(WireModel):
    extends: Annotated[
        str | None,
        Field(
            description="Parent profile identifier from the selected permissions profile's `extends` setting, when present."
        ),
    ] = None
    id: Annotated[
        str,
        Field(
            description="Identifier from `default_permissions` or the implicit built-in default, such as `:workspace` or a user-defined `[permissions.<id>]` profile."
        ),
    ]


class AdditionalNetworkPermissions(WireModel):
    enabled: bool | None = None


class AgentMessageDeltaNotification(WireModel):
    delta: str
    item_id: Annotated[str, Field(alias="itemId")]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class InputTextAgentMessageInputContent(WireModel):
    text: str
    type: Annotated[Literal["input_text"], Field(title="InputTextAgentMessageInputContentType")]


class EncryptedContentAgentMessageInputContent(WireModel):
    encrypted_content: str
    type: Annotated[
        Literal["encrypted_content"],
        Field(title="EncryptedContentAgentMessageInputContentType"),
    ]


class Granular(WireModel):
    mcp_elicitations: bool
    request_permissions: bool = False
    rules: bool
    sandbox_approval: bool
    skill_approval: bool = False


class GranularAskForApproval(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    granular: Granular


class AsyncUserInputQuestion(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    options: list[str] | None = None
    title: str


class ByteRange(WireModel):
    end: Annotated[int, Field(ge=0)]
    start: Annotated[int, Field(ge=0)]


class EnvironmentCapabilityRootLocation(WireModel):
    environment_id: Annotated[str, Field(alias="environmentId")]
    path: Annotated[
        str,
        Field(description="Absolute path for the root in the selected environment."),
    ]
    type: Annotated[Literal["environment"], Field(title="EnvironmentCapabilityRootLocationType")]


class CapabilityRootLocation(RootModel[EnvironmentCapabilityRootLocation]):
    root: Annotated[
        EnvironmentCapabilityRootLocation,
        Field(description="Location used to resolve a selected capability root."),
    ]


class ClientInfo(WireModel):
    name: str
    title: str | None = None
    version: str


class HttpConnectionFailed(WireModel):
    http_status_code: Annotated[int | None, Field(alias="httpStatusCode", ge=0)] = None


class HttpConnectionFailedCodexErrorInfo(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    http_connection_failed: Annotated[HttpConnectionFailed, Field(alias="httpConnectionFailed")]


class ResponseStreamConnectionFailed(WireModel):
    http_status_code: Annotated[int | None, Field(alias="httpStatusCode", ge=0)] = None


class ResponseStreamConnectionFailedCodexErrorInfo(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    response_stream_connection_failed: Annotated[
        ResponseStreamConnectionFailed, Field(alias="responseStreamConnectionFailed")
    ]


class ResponseStreamDisconnected(WireModel):
    http_status_code: Annotated[int | None, Field(alias="httpStatusCode", ge=0)] = None


class ResponseStreamDisconnectedCodexErrorInfo(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    response_stream_disconnected: Annotated[ResponseStreamDisconnected, Field(alias="responseStreamDisconnected")]


class ResponseTooManyFailedAttempts(WireModel):
    http_status_code: Annotated[int | None, Field(alias="httpStatusCode", ge=0)] = None


class ResponseTooManyFailedAttemptsCodexErrorInfo(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    response_too_many_failed_attempts: Annotated[
        ResponseTooManyFailedAttempts, Field(alias="responseTooManyFailedAttempts")
    ]


class ListFilesCommandAction(WireModel):
    command: str
    path: str | None = None
    type: Annotated[Literal["listFiles"], Field(title="ListFilesCommandActionType")]


class SearchCommandAction(WireModel):
    command: str
    path: str | None = None
    query: str | None = None
    type: Annotated[Literal["search"], Field(title="SearchCommandActionType")]


class UnknownCommandAction(WireModel):
    command: str
    type: Annotated[Literal["unknown"], Field(title="UnknownCommandActionType")]


class AcceptWithExecpolicyAmendment(WireModel):
    execpolicy_amendment: list[str]


class AcceptWithExecpolicyAmendmentCommandExecutionApprovalDecision(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    accept_with_execpolicy_amendment: Annotated[
        AcceptWithExecpolicyAmendment, Field(alias="acceptWithExecpolicyAmendment")
    ]


class CommandExecutionOutputDeltaNotification(WireModel):
    delta: str
    item_id: Annotated[str, Field(alias="itemId")]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class InputTextContentItem(WireModel):
    text: str
    type: Annotated[Literal["input_text"], Field(title="InputTextContentItemType")]


class InputAudioContentItem(WireModel):
    audio_url: str
    type: Annotated[Literal["input_audio"], Field(title="InputAudioContentItemType")]


class OutputTextContentItem(WireModel):
    text: str
    type: Annotated[Literal["output_text"], Field(title="OutputTextContentItemType")]


class InputTextDynamicToolCallOutputContentItem(WireModel):
    text: str
    type: Annotated[
        Literal["inputText"],
        Field(title="InputTextDynamicToolCallOutputContentItemType"),
    ]


class InputImageDynamicToolCallOutputContentItem(WireModel):
    image_url: Annotated[str, Field(alias="imageUrl")]
    type: Annotated[
        Literal["inputImage"],
        Field(title="InputImageDynamicToolCallOutputContentItemType"),
    ]


class InputAudioDynamicToolCallOutputContentItem(WireModel):
    audio_url: Annotated[str, Field(alias="audioUrl")]
    type: Annotated[
        Literal["inputAudio"],
        Field(title="InputAudioDynamicToolCallOutputContentItemType"),
    ]


class FunctionDynamicToolNamespaceTool(WireModel):
    defer_loading: Annotated[bool | None, Field(alias="deferLoading")] = None
    description: str
    input_schema: Annotated[Any, Field(alias="inputSchema")]
    name: str
    type: Annotated[Literal["function"], Field(title="FunctionDynamicToolNamespaceToolType")]


class DynamicToolNamespaceTool(RootModel[FunctionDynamicToolNamespaceTool]):
    root: FunctionDynamicToolNamespaceTool


class FunctionDynamicToolSpec(WireModel):
    defer_loading: Annotated[bool | None, Field(alias="deferLoading")] = None
    description: str
    input_schema: Annotated[Any, Field(alias="inputSchema")]
    name: str
    type: Annotated[Literal["function"], Field(title="FunctionDynamicToolSpecType")]


class NamespaceDynamicToolSpec(WireModel):
    description: str
    name: str
    tools: list[DynamicToolNamespaceTool]
    type: Annotated[Literal["namespace"], Field(title="NamespaceDynamicToolSpecType")]


class EnvironmentAddResponse(WireModel):
    pass


class EnvironmentSkillsParams(WireModel):
    required: Annotated[
        list[str] | None,
        Field(description="Exact catalog names that must be available from this environment."),
    ] = None


class EnvironmentStatusParams(WireModel):
    environment_id: Annotated[str, Field(alias="environmentId", description="Environment id to inspect.")]


class EnvironmentStatusResponse(WireModel):
    error: Annotated[
        str | None,
        Field(description="Human-readable detail for `disconnected` and `unknown`; omitted for other statuses."),
    ] = None
    status: Annotated[
        Literal["ready", "pending", "disconnected", "unknown"],
        Field(description="Current status observed without starting or recovering the environment."),
    ]


class FileChangeRequestApprovalParams(WireModel):
    grant_root: Annotated[
        str | None,
        Field(
            alias="grantRoot",
            description="[UNSTABLE] When set, the agent is asking the user to allow writes under this root for the remainder of the session (unclear if this is honored today).",
        ),
    ] = None
    item_id: Annotated[str, Field(alias="itemId")]
    reason: Annotated[
        str | None,
        Field(description="Optional explanatory reason (e.g. request for extra write access)."),
    ] = None
    started_at_ms: Annotated[
        int,
        Field(
            alias="startedAtMs",
            description="Unix timestamp (in milliseconds) when this approval request started.",
        ),
    ]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class FileChangeRequestApprovalResponse(WireModel):
    decision: Literal["accept", "acceptForSession", "decline", "cancel"]


class GlobPatternFileSystemPath(WireModel):
    pattern: str
    type: Annotated[Literal["glob_pattern"], Field(title="GlobPatternFileSystemPathType")]


class RootFileSystemSpecialPath(WireModel):
    kind: Literal["root"]


class MinimalFileSystemSpecialPath(WireModel):
    kind: Literal["minimal"]


class TmpdirFileSystemSpecialPath(WireModel):
    kind: Literal["tmpdir"]


class SlashTmpFileSystemSpecialPath(WireModel):
    kind: Literal["slash_tmp"]


class InputTextFunctionCallOutputContentItem(WireModel):
    text: str
    type: Annotated[Literal["input_text"], Field(title="InputTextFunctionCallOutputContentItemType")]


class InputAudioFunctionCallOutputContentItem(WireModel):
    audio_url: str
    type: Annotated[
        Literal["input_audio"],
        Field(title="InputAudioFunctionCallOutputContentItemType"),
    ]


class EncryptedContentFunctionCallOutputContentItem(WireModel):
    encrypted_content: str
    type: Annotated[
        Literal["encrypted_content"],
        Field(title="EncryptedContentFunctionCallOutputContentItemType"),
    ]


class GitInfo(WireModel):
    branch: str | None = None
    origin_url: Annotated[str | None, Field(alias="originUrl")] = None
    sha: str | None = None


class HookPromptFragment(WireModel):
    hook_run_id: Annotated[str, Field(alias="hookRunId")]
    text: str


class UsageLimitExceededImageGenerationFailure(WireModel):
    limit_id: Annotated[str, Field(alias="limitId")]
    resets_at: Annotated[int | None, Field(alias="resetsAt")] = None
    type: Annotated[
        Literal["usageLimitExceeded"],
        Field(title="UsageLimitExceededImageGenerationFailureType"),
    ]


class ImageGenerationFailure(RootModel[UsageLimitExceededImageGenerationFailure]):
    root: UsageLimitExceededImageGenerationFailure


class InitializeCapabilities(WireModel):
    experimental_api: Annotated[
        bool,
        Field(
            alias="experimentalApi",
            description="Opt into receiving experimental API methods and fields.",
        ),
    ] = False
    explicit_gateway_oauth: Annotated[
        bool | None,
        Field(
            alias="explicitGatewayOauth",
            description="Use explicit gateway OAuth login instead of automatic browser authorization. Applies to this app-server's gateway runtime; later connections cannot undo it.",
        ),
    ] = None
    extensions: Annotated[
        dict[str, Any] | None,
        Field(description="MCP extension settings declared by the app-server client."),
    ] = None
    mcp_server_openai_form_elicitation: Annotated[
        bool | None,
        Field(
            alias="mcpServerOpenaiFormElicitation",
            description="Legacy opt-in for the `openai/form` MCP extension.\n\nNew clients should declare `openai/form` in [`Self::extensions`].",
        ),
    ] = None
    opt_out_notification_methods: Annotated[
        list[str] | None,
        Field(
            alias="optOutNotificationMethods",
            description="Exact notification method names that should be suppressed for this connection (for example `thread/started`).",
        ),
    ] = None
    request_attestation: Annotated[
        bool,
        Field(
            alias="requestAttestation",
            description="Opt into `attestation/generate` requests for upstream `x-oai-attestation`.",
        ),
    ] = False


class InitializeParams(WireModel):
    capabilities: InitializeCapabilities | None = None
    client_info: Annotated[ClientInfo, Field(alias="clientInfo")]


class InitializeResponse(WireModel):
    codex_home: Annotated[
        str,
        Field(
            alias="codexHome",
            description="Absolute path to the server's $CODEX_HOME directory.",
        ),
    ]
    platform_family: Annotated[
        str,
        Field(
            alias="platformFamily",
            description='Platform family for the running app-server target, for example `"unix"` or `"windows"`.',
        ),
    ]
    platform_os: Annotated[
        str,
        Field(
            alias="platformOs",
            description='Operating system for the running app-server target, for example `"macos"`, `"linux"`, or `"windows"`.',
        ),
    ]
    user_agent: Annotated[str, Field(alias="userAgent")]


class InternalChatMessageMetadataPassthrough(WireModel):
    turn_id: str | None = None


class ExecLocalShellAction(WireModel):
    command: list[str]
    env: dict[str, Any] | None = None
    timeout_ms: Annotated[int | None, Field(ge=0)] = None
    type: Annotated[Literal["exec"], Field(title="ExecLocalShellActionType")]
    user: str | None = None
    working_directory: str | None = None


class LocalShellAction(RootModel[ExecLocalShellAction]):
    root: ExecLocalShellAction


class McpAppUi(WireModel):
    preferred_model_display_mode: Annotated[Literal["inline", "fullscreen"], Field(alias="preferredModelDisplayMode")]
    resource_uri: Annotated[str, Field(alias="resourceUri")]


class McpToolCallAppContext(WireModel):
    action_name: Annotated[str | None, Field(alias="actionName")] = None
    app_name: Annotated[str | None, Field(alias="appName")] = None
    connector_id: Annotated[str, Field(alias="connectorId")]
    link_id: Annotated[str | None, Field(alias="linkId")] = None
    resource_uri: Annotated[str | None, Field(alias="resourceUri")] = None


class McpToolCallError(WireModel):
    message: str


class McpToolCallResult(WireModel):
    field_meta: Annotated[Any | None, Field(alias="_meta")] = None
    content: list[Any]
    structured_content: Annotated[Any | None, Field(alias="structuredContent")] = None


class MemoryCitationEntry(WireModel):
    line_end: Annotated[int, Field(alias="lineEnd", ge=0)]
    line_start: Annotated[int, Field(alias="lineStart", ge=0)]
    note: str
    path: str


class MisalignmentSteer(WireModel):
    message: str


class CustomMultiAgentMode(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    custom: str


class AddPatchChangeKind(WireModel):
    type: Annotated[Literal["add"], Field(title="AddPatchChangeKindType")]


class DeletePatchChangeKind(WireModel):
    type: Annotated[Literal["delete"], Field(title="DeletePatchChangeKindType")]


class UpdatePatchChangeKind(WireModel):
    move_path: str | None = None
    type: Annotated[Literal["update"], Field(title="UpdatePatchChangeKindType")]


class ReasoningEffort(RootModel[str]):
    root: Annotated[
        str,
        Field(
            description="A non-empty reasoning effort value advertised by the model.",
            min_length=1,
        ),
    ]


class ReasoningTextReasoningItemContent(WireModel):
    text: str
    type: Annotated[Literal["reasoning_text"], Field(title="ReasoningTextReasoningItemContentType")]


class TextReasoningItemContent(WireModel):
    text: str
    type: Annotated[Literal["text"], Field(title="TextReasoningItemContentType")]


class SummaryTextReasoningItemReasoningSummary(WireModel):
    text: str
    type: Annotated[
        Literal["summary_text"],
        Field(title="SummaryTextReasoningItemReasoningSummaryType"),
    ]


class ReasoningItemReasoningSummary(RootModel[SummaryTextReasoningItemReasoningSummary]):
    root: SummaryTextReasoningItemReasoningSummary


class ReasoningSummaryTextDeltaNotification(WireModel):
    delta: str
    item_id: Annotated[str, Field(alias="itemId")]
    summary_index: Annotated[int, Field(alias="summaryIndex")]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class ReasoningTextDeltaNotification(WireModel):
    content_index: Annotated[int, Field(alias="contentIndex")]
    delta: str
    item_id: Annotated[str, Field(alias="itemId")]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class AdditionalToolsResponseItem(WireModel):
    id: str | None = None
    role: str
    tools: list[Any]
    type: Annotated[Literal["additional_tools"], Field(title="AdditionalToolsResponseItemType")]


class AgentMessageResponseItem(WireModel):
    author: str
    content: list[InputTextAgentMessageInputContent | EncryptedContentAgentMessageInputContent]
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    recipient: str
    type: Annotated[Literal["agent_message"], Field(title="AgentMessageResponseItemType")]


class ReasoningResponseItem(WireModel):
    content: list[ReasoningTextReasoningItemContent | TextReasoningItemContent] | None = None
    encrypted_content: str | None = None
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    summary: list[ReasoningItemReasoningSummary]
    type: Annotated[Literal["reasoning"], Field(title="ReasoningResponseItemType")]


class LocalShellCallResponseItem(WireModel):
    action: LocalShellAction
    call_id: Annotated[str | None, Field(description="Set when using the Responses API.")] = None
    id: Annotated[
        str | None,
        Field(description="Legacy id field retained for compatibility with older payloads."),
    ] = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    status: Literal["completed", "in_progress", "incomplete"]
    type: Annotated[Literal["local_shell_call"], Field(title="LocalShellCallResponseItemType")]


class FunctionCallResponseItem(WireModel):
    arguments: str
    call_id: str
    encrypted_function_args: list[str] | None = None
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    name: str
    namespace: str | None = None
    type: Annotated[Literal["function_call"], Field(title="FunctionCallResponseItemType")]


class ToolSearchCallResponseItem(WireModel):
    arguments: Any
    call_id: str | None = None
    execution: str
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    status: str | None = None
    type: Annotated[Literal["tool_search_call"], Field(title="ToolSearchCallResponseItemType")]


class CustomToolCallResponseItem(WireModel):
    call_id: str
    id: str | None = None
    input: str
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    name: str
    namespace: str | None = None
    status: str | None = None
    type: Annotated[Literal["custom_tool_call"], Field(title="CustomToolCallResponseItemType")]


class ToolSearchOutputResponseItem(WireModel):
    call_id: str | None = None
    execution: str
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    status: str
    tools: list[Any]
    type: Annotated[Literal["tool_search_output"], Field(title="ToolSearchOutputResponseItemType")]


class ImageGenerationCallResponseItem(WireModel):
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    result: str
    revised_prompt: str | None = None
    status: str
    type: Annotated[
        Literal["image_generation_call"],
        Field(title="ImageGenerationCallResponseItemType"),
    ]


class CompactionResponseItem(WireModel):
    encrypted_content: str
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    type: Annotated[Literal["compaction"], Field(title="CompactionResponseItemType")]


class CompactionTriggerResponseItem(WireModel):
    type: Annotated[Literal["compaction_trigger"], Field(title="CompactionTriggerResponseItemType")]


class ContextCompactionResponseItem(WireModel):
    encrypted_content: str | None = None
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    type: Annotated[Literal["context_compaction"], Field(title="ContextCompactionResponseItemType")]


class OtherResponseItem(WireModel):
    type: Annotated[Literal["other"], Field(title="OtherResponseItemType")]


class SearchResponsesApiWebSearchAction(WireModel):
    queries: list[str] | None = None
    query: str | None = None
    type: Annotated[Literal["search"], Field(title="SearchResponsesApiWebSearchActionType")]


class OpenPageResponsesApiWebSearchAction(WireModel):
    type: Annotated[Literal["open_page"], Field(title="OpenPageResponsesApiWebSearchActionType")]
    url: str | None = None


class FindInPageResponsesApiWebSearchAction(WireModel):
    pattern: str | None = None
    type: Annotated[
        Literal["find_in_page"],
        Field(title="FindInPageResponsesApiWebSearchActionType"),
    ]
    url: str | None = None


class OtherResponsesApiWebSearchAction(WireModel):
    type: Annotated[Literal["other"], Field(title="OtherResponsesApiWebSearchActionType")]


class DangerFullAccessSandboxPolicy(WireModel):
    type: Annotated[Literal["dangerFullAccess"], Field(title="DangerFullAccessSandboxPolicyType")]


class ReadOnlySandboxPolicy(WireModel):
    network_access: Annotated[bool, Field(alias="networkAccess")] = False
    type: Annotated[Literal["readOnly"], Field(title="ReadOnlySandboxPolicyType")]


class ExternalSandboxSandboxPolicy(WireModel):
    network_access: Annotated[Literal["restricted", "enabled"], Field(alias="networkAccess")] = "restricted"
    type: Annotated[Literal["externalSandbox"], Field(title="ExternalSandboxSandboxPolicyType")]


class WorkspaceWriteSandboxPolicy(WireModel):
    exclude_slash_tmp: Annotated[bool, Field(alias="excludeSlashTmp")] = False
    exclude_tmpdir_env_var: Annotated[bool, Field(alias="excludeTmpdirEnvVar")] = False
    network_access: Annotated[bool, Field(alias="networkAccess")] = False
    type: Annotated[Literal["workspaceWrite"], Field(title="WorkspaceWriteSandboxPolicyType")]
    writable_roots: Annotated[list[str], Field(alias="writableRoots")] = []


class SelectedCapabilityRoot(WireModel):
    id: Annotated[
        str,
        Field(description="Stable identifier supplied by the capability selection platform."),
    ]
    location: Annotated[
        CapabilityRootLocation,
        Field(description="Where the selected root can be resolved."),
    ]


class ServerRequestResolvedNotification(WireModel):
    request_id: Annotated[str | int, Field(alias="requestId")]
    thread_id: Annotated[str, Field(alias="threadId")]


class CustomSessionSource(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    custom: str


class Settings(WireModel):
    developer_instructions: str | None = None
    model: str
    reasoning_effort: ReasoningEffort | None = None


class OtherSubAgentSource(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    other: str


class TextElement(WireModel):
    byte_range: Annotated[
        ByteRange,
        Field(
            alias="byteRange",
            description="Byte range in the parent `text` buffer that this element occupies.",
        ),
    ]
    placeholder: Annotated[
        str | None,
        Field(description="Optional human-readable placeholder for the element, displayed in the UI."),
    ] = None


class ThreadEnvironment(WireModel):
    cwd: str
    environment_id: Annotated[str, Field(alias="environmentId")]
    runtime_workspace_roots: Annotated[list[str], Field(alias="runtimeWorkspaceRoots")]


class ThreadExtra(WireModel):
    pass


class HookPromptThreadItem(WireModel):
    fragments: list[HookPromptFragment]
    id: str
    type: Annotated[Literal["hookPrompt"], Field(title="HookPromptThreadItemType")]


class PlanThreadItem(WireModel):
    id: str
    text: str
    type: Annotated[Literal["plan"], Field(title="PlanThreadItemType")]


class ReasoningThreadItem(WireModel):
    content: list[str] = []
    id: str
    summary: list[str] = []
    type: Annotated[Literal["reasoning"], Field(title="ReasoningThreadItemType")]


class McpToolCallThreadItem(WireModel):
    app_context: Annotated[McpToolCallAppContext | None, Field(alias="appContext")] = None
    arguments: Any
    duration_ms: Annotated[
        int | None,
        Field(
            alias="durationMs",
            description="The duration of the MCP tool call in milliseconds.",
        ),
    ] = None
    error: McpToolCallError | None = None
    id: str
    mcp_app_resource_uri: Annotated[
        str | None,
        Field(
            alias="mcpAppResourceUri",
            description="Legacy compatibility field; prefer `mcpAppUi.resourceUri` when available.",
        ),
    ] = None
    mcp_app_ui: Annotated[
        McpAppUi | None,
        Field(
            alias="mcpAppUi",
            description="Presentation captured from the invoked descriptor; absent in older history.",
        ),
    ] = None
    plugin_id: Annotated[str | None, Field(alias="pluginId")] = None
    read_only_hint: Annotated[bool | None, Field(alias="readOnlyHint")] = None
    result: McpToolCallResult | None = None
    server: str
    status: Literal["inProgress", "completed", "failed"]
    tool: str
    type: Annotated[Literal["mcpToolCall"], Field(title="McpToolCallThreadItemType")]


class DynamicToolCallThreadItem(WireModel):
    arguments: Any
    content_items: Annotated[
        list[
            InputTextDynamicToolCallOutputContentItem
            | InputImageDynamicToolCallOutputContentItem
            | InputAudioDynamicToolCallOutputContentItem
        ]
        | None,
        Field(alias="contentItems"),
    ] = None
    duration_ms: Annotated[
        int | None,
        Field(
            alias="durationMs",
            description="The duration of the dynamic tool call in milliseconds.",
        ),
    ] = None
    id: str
    namespace: str | None = None
    status: Literal["inProgress", "completed", "failed"]
    success: bool | None = None
    tool: str
    type: Annotated[Literal["dynamicToolCall"], Field(title="DynamicToolCallThreadItemType")]


class SubAgentActivityThreadItem(WireModel):
    agent_path: Annotated[str, Field(alias="agentPath")]
    agent_thread_id: Annotated[str, Field(alias="agentThreadId")]
    id: str
    kind: Literal["started", "interacted", "interrupted", "completed"]
    model: Annotated[
        str | None,
        Field(description="Resolved model at sub-agent creation; absent from older records and other activities."),
    ] = None
    reasoning_effort: Annotated[
        ReasoningEffort | None,
        Field(
            alias="reasoningEffort",
            description="Resolved reasoning effort at sub-agent creation, when known.",
        ),
    ] = None
    type: Annotated[Literal["subAgentActivity"], Field(title="SubAgentActivityThreadItemType")]


class ImageViewThreadItem(WireModel):
    id: str
    path: str
    type: Annotated[Literal["imageView"], Field(title="ImageViewThreadItemType")]


class SleepThreadItem(WireModel):
    duration_ms: Annotated[int, Field(alias="durationMs", ge=0)]
    id: str
    type: Annotated[Literal["sleep"], Field(title="SleepThreadItemType")]


class ImageGenerationThreadItem(WireModel):
    failure: ImageGenerationFailure | None = None
    id: str
    result: str
    revised_prompt: Annotated[str | None, Field(alias="revisedPrompt")] = None
    saved_path: Annotated[str | None, Field(alias="savedPath")] = None
    status: str
    transparent_background: Annotated[bool | None, Field(alias="transparentBackground")] = None
    type: Annotated[Literal["imageGeneration"], Field(title="ImageGenerationThreadItemType")]


class EnteredReviewModeThreadItem(WireModel):
    id: str
    review: str
    type: Annotated[Literal["enteredReviewMode"], Field(title="EnteredReviewModeThreadItemType")]


class ExitedReviewModeThreadItem(WireModel):
    id: str
    review: str
    type: Annotated[Literal["exitedReviewMode"], Field(title="ExitedReviewModeThreadItemType")]


class ContextCompactionThreadItem(WireModel):
    id: str
    type: Annotated[Literal["contextCompaction"], Field(title="ContextCompactionThreadItemType")]


class ThreadSectionAppearance(WireModel):
    color: str | None = None
    icon: str | None = None


class NotLoadedThreadStatus(WireModel):
    type: Annotated[Literal["notLoaded"], Field(title="NotLoadedThreadStatusType")]


class IdleThreadStatus(WireModel):
    type: Annotated[Literal["idle"], Field(title="IdleThreadStatusType")]


class SystemErrorThreadStatus(WireModel):
    type: Annotated[Literal["systemError"], Field(title="SystemErrorThreadStatusType")]


class ActiveThreadStatus(WireModel):
    active_flags: Annotated[
        list[Literal["waitingOnApproval", "waitingOnUserInput"]],
        Field(alias="activeFlags"),
    ]
    type: Annotated[Literal["active"], Field(title="ActiveThreadStatusType")]


class TokenUsageBreakdown(WireModel):
    cache_write_input_tokens: Annotated[int, Field(alias="cacheWriteInputTokens")] = 0
    cached_input_tokens: Annotated[int, Field(alias="cachedInputTokens")]
    input_tokens: Annotated[int, Field(alias="inputTokens")]
    output_tokens: Annotated[int, Field(alias="outputTokens")]
    reasoning_output_tokens: Annotated[int, Field(alias="reasoningOutputTokens")]
    total_tokens: Annotated[int, Field(alias="totalTokens")]


class ToolRequestUserInputAnswer(WireModel):
    answers: list[str]


class ToolRequestUserInputOption(WireModel):
    description: str
    label: str


class ToolRequestUserInputQuestion(WireModel):
    header: str
    id: str
    is_other: Annotated[bool, Field(alias="isOther")] = False
    is_secret: Annotated[bool, Field(alias="isSecret")] = False
    options: list[ToolRequestUserInputOption] | None = None
    question: str


class ToolRequestUserInputResponse(WireModel):
    answers: dict[str, ToolRequestUserInputAnswer]


class TurnEnvironmentParams(WireModel):
    cwd: str
    environment_id: Annotated[str, Field(alias="environmentId")]
    runtime_workspace_roots: Annotated[
        list[str] | None,
        Field(
            alias="runtimeWorkspaceRoots",
            description="Environment-native runtime workspace roots. Omitted defaults to `cwd`.",
        ),
    ] = None


class TurnInterruptParams(WireModel):
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class TurnInterruptResponse(WireModel):
    pass


class TurnSteerResponse(WireModel):
    turn_id: Annotated[str, Field(alias="turnId")]


class TextUserInput(WireModel):
    text: str
    text_elements: Annotated[
        list[TextElement],
        Field(
            description="UI-defined spans within `text` used to render or persist special elements.",
            validate_default=True,
        ),
    ] = []
    type: Annotated[Literal["text"], Field(title="TextUserInputType")]


class UrlUserInput(WireModel):
    detail: Literal["auto", "low", "high", "original"] | None = None
    type: Annotated[Literal["image"], Field(title="ImageUserInputType")]
    url: str


class FileIdUserInput(WireModel):
    detail: Literal["auto", "low", "high", "original"] | None = None
    type: Annotated[Literal["image"], Field(title="ImageUserInputType")]
    file_id: Annotated[str, Field(alias="fileId")]


class LocalImageUserInput(WireModel):
    detail: Literal["auto", "low", "high", "original"] | None = None
    path: str
    type: Annotated[Literal["localImage"], Field(title="LocalImageUserInputType")]


class AudioUserInput(WireModel):
    type: Annotated[Literal["audio"], Field(title="AudioUserInputType")]
    url: str


class LocalAudioUserInput(WireModel):
    path: str
    type: Annotated[Literal["localAudio"], Field(title="LocalAudioUserInputType")]


class SkillUserInput(WireModel):
    name: str
    path: str
    type: Annotated[Literal["skill"], Field(title="SkillUserInputType")]


class MentionUserInput(WireModel):
    name: str
    path: str
    type: Annotated[Literal["mention"], Field(title="MentionUserInputType")]


class SearchWebSearchAction(WireModel):
    queries: list[str] | None = None
    query: str | None = None
    type: Annotated[Literal["search"], Field(title="SearchWebSearchActionType")]


class OpenPageWebSearchAction(WireModel):
    type: Annotated[Literal["openPage"], Field(title="OpenPageWebSearchActionType")]
    url: str | None = None


class FindInPageWebSearchAction(WireModel):
    pattern: str | None = None
    type: Annotated[Literal["findInPage"], Field(title="FindInPageWebSearchActionType")]
    url: str | None = None


class OtherWebSearchAction(WireModel):
    type: Annotated[Literal["other"], Field(title="OtherWebSearchActionType")]


class AdditionalContextEntry(WireModel):
    kind: Literal["untrusted", "application"]
    value: str


class ActiveTurnNotSteerable(WireModel):
    turn_kind: Annotated[Literal["review", "compact"], Field(alias="turnKind")]


class ActiveTurnNotSteerableCodexErrorInfo(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    active_turn_not_steerable: Annotated[ActiveTurnNotSteerable, Field(alias="activeTurnNotSteerable")]


class CollabAgentState(WireModel):
    message: str | None = None
    status: Literal[
        "pendingInit",
        "running",
        "interrupted",
        "completed",
        "errored",
        "shutdown",
        "notFound",
    ]


class CollaborationMode(WireModel):
    mode: Annotated[
        Literal["plan", "default"],
        Field(description="Initial collaboration mode to use when the TUI starts."),
    ]
    settings: Settings


class ReadCommandAction(WireModel):
    command: str
    name: str
    path: str
    type: Annotated[Literal["read"], Field(title="ReadCommandActionType")]


class ConfigurationReasoning(WireModel):
    effort: Annotated[
        str,
        Field(
            description="A non-empty reasoning effort value advertised by the model.",
            min_length=1,
        ),
    ]


class ImageUrlContentItem(WireModel):
    detail: Literal["auto", "low", "high", "original"] | None = None
    type: Annotated[Literal["input_image"], Field(title="InputImageContentItemType")]
    image_url: str


class FileIdContentItem(WireModel):
    detail: Literal["auto", "low", "high", "original"] | None = None
    type: Annotated[Literal["input_image"], Field(title="InputImageContentItemType")]
    file_id: str


class EnvironmentAddParams(WireModel):
    auth_bearer_token: Annotated[
        str | None,
        Field(
            alias="authBearerToken",
            description="Optional raw bearer token for executor authentication, including reconnects. Requires a secure transport or a loopback destination.",
        ),
    ] = None
    connect_timeout_ms: Annotated[
        int | None,
        Field(
            alias="connectTimeoutMs",
            description="Optional WebSocket connection timeout. The server default applies when omitted.",
            ge=0,
        ),
    ] = None
    environment_id: Annotated[str, Field(alias="environmentId")]
    exec_server_url: Annotated[str, Field(alias="execServerUrl")]
    skills: Annotated[
        EnvironmentSkillsParams | None,
        Field(description="Required skills supplied by this environment, checked before model inference."),
    ] = None


class PathFileSystemPath(WireModel):
    path: str
    type: Annotated[Literal["path"], Field(title="PathFileSystemPathType")]


class KindFileSystemSpecialPath(WireModel):
    kind: Literal["project_roots"]
    subpath: str | None = None


class FileSystemSpecialPath1(WireModel):
    kind: Literal["unknown"]
    path: str
    subpath: str | None = None


class FileUpdateChange(WireModel):
    diff: str
    kind: AddPatchChangeKind | DeletePatchChangeKind | UpdatePatchChangeKind
    path: str


class ImageUrlFunctionCallOutputContentItem(WireModel):
    detail: Literal["auto", "low", "high", "original"] | None = None
    type: Annotated[
        Literal["input_image"],
        Field(title="InputImageFunctionCallOutputContentItemType"),
    ]
    image_url: str


class FileIdFunctionCallOutputContentItem(WireModel):
    detail: Literal["auto", "low", "high", "original"] | None = None
    type: Annotated[
        Literal["input_image"],
        Field(title="InputImageFunctionCallOutputContentItemType"),
    ]
    file_id: str


class MemoryCitation(WireModel):
    entries: list[MemoryCitationEntry]
    thread_ids: Annotated[list[str], Field(alias="threadIds")]


class MisalignmentErrorDetails(WireModel):
    detailed_explanation: Annotated[
        str | None,
        Field(
            alias="detailedExplanation",
            description="A substantive localized explanation is required before offering continuation.",
        ),
    ] = None
    error_type: Annotated[
        str | None,
        Field(
            alias="errorType",
            description="Open-ended classification; clients must accept categories added by Responses.",
        ),
    ] = None
    review_target: Annotated[
        str | None,
        Field(
            alias="reviewTarget",
            description="Opaque server-issued block target. Presence alone does not enable target-based continuation.",
        ),
    ] = None
    steer: Annotated[
        MisalignmentSteer | None,
        Field(description="Instruction to submit as the next turn's user input if continuation is confirmed."),
    ] = None


class NetworkApprovalContext(WireModel):
    host: str
    protocol: Literal["http", "https", "socks5Tcp", "socks5Udp"]


class NetworkPolicyAmendment(WireModel):
    action: Literal["allow", "deny"]
    host: str


class MessageResponseItem(WireModel):
    content: list[
        InputTextContentItem | InputAudioContentItem | OutputTextContentItem | ImageUrlContentItem | FileIdContentItem
    ]
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    phase: Literal["commentary", "partial_answer", "final_answer"] | None = None
    role: str
    type: Annotated[Literal["message"], Field(title="MessageResponseItemType")]


class WebSearchCallResponseItem(WireModel):
    action: (
        SearchResponsesApiWebSearchAction
        | OpenPageResponsesApiWebSearchAction
        | FindInPageResponsesApiWebSearchAction
        | OtherResponsesApiWebSearchAction
        | None
    ) = None
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    status: str | None = None
    type: Annotated[Literal["web_search_call"], Field(title="WebSearchCallResponseItemType")]


class ConfigurationUpdateResponseItem(WireModel):
    reasoning: ConfigurationReasoning
    type: Annotated[
        Literal["configuration_update"],
        Field(title="ConfigurationUpdateResponseItemType"),
    ]


class ThreadSpawn(WireModel):
    agent_nickname: str | None = None
    agent_path: str | None = None
    agent_role: str | None = None
    depth: int
    parent_thread_id: str


class ThreadSpawnSubAgentSource(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    thread_spawn: ThreadSpawn


class ThreadForkParams(WireModel):
    approval_policy: Annotated[
        Literal["untrusted", "on-request", "never"] | GranularAskForApproval | None,
        Field(alias="approvalPolicy"),
    ] = None
    approvals_reviewer: Annotated[
        Literal["user", "auto_review", "guardian_subagent"] | None,
        Field(
            alias="approvalsReviewer",
            description="Override where approval requests are routed for review on this thread and subsequent turns.",
        ),
    ] = None
    base_instructions: Annotated[str | None, Field(alias="baseInstructions")] = None
    before_turn_id: Annotated[
        str | None,
        Field(
            alias="beforeTurnId",
            description="Optional turn id to fork before, excluding that turn and all later turns. Cannot be combined with `last_turn_id`.",
        ),
    ] = None
    config: dict[str, Any] | None = None
    cwd: str | None = None
    defer_goal_continuation: Annotated[
        bool | None,
        Field(
            alias="deferGoalContinuation",
            description="When true, carry the source thread's current goal into the fork without starting its initial automatic continuation. The next explicit turn owns the goal lifecycle, and normal automatic continuation resumes after it.",
        ),
    ] = None
    developer_instructions: Annotated[str | None, Field(alias="developerInstructions")] = None
    ephemeral: bool | None = None
    exclude_turns: Annotated[
        bool | None,
        Field(
            alias="excludeTurns",
            description="When true, return only thread metadata and live fork state without populating `thread.turns`. This is useful when the client plans to call `thread/turns/list` immediately after forking. Full-history hydration is deprecated for paginated threads; use this with `thread/turns/list` and `thread/items/list` instead.",
        ),
    ] = None
    last_turn_id: Annotated[
        str | None,
        Field(
            alias="lastTurnId",
            description="Optional last turn id to fork through, inclusive.\n\nWhen specified, turns after `last_turn_id` are omitted from the fork. The referenced turn cannot be in progress.",
        ),
    ] = None
    model: Annotated[
        str | None,
        Field(description="Configuration overrides for the forked thread, if any."),
    ] = None
    model_provider: Annotated[str | None, Field(alias="modelProvider")] = None
    path: Annotated[
        str | None,
        Field(
            description="[UNSTABLE] Specify the rollout path to fork from. If specified, the thread_id param will be ignored."
        ),
    ] = None
    permissions: Annotated[
        str | None,
        Field(description="Named profile id for the forked thread. Cannot be combined with `sandbox`."),
    ] = None
    runtime_workspace_roots: Annotated[
        list[str] | None,
        Field(
            alias="runtimeWorkspaceRoots",
            description="Replace the thread's runtime workspace roots. Paths must be absolute.",
        ),
    ] = None
    sandbox: Literal["read-only", "workspace-write", "danger-full-access"] | None = None
    service_tier: Annotated[str | None, Field(alias="serviceTier")] = None
    thread_id: Annotated[str, Field(alias="threadId")]
    thread_source: Annotated[
        str | None,
        Field(
            alias="threadSource",
            description="Optional client-supplied analytics source classification for this forked thread.",
        ),
    ] = None


class UserMessageThreadItem(WireModel):
    client_id: Annotated[str | None, Field(alias="clientId")] = None
    content: list[
        TextUserInput
        | LocalImageUserInput
        | AudioUserInput
        | LocalAudioUserInput
        | SkillUserInput
        | MentionUserInput
        | UrlUserInput
        | FileIdUserInput
    ]
    id: str
    type: Annotated[Literal["userMessage"], Field(title="UserMessageThreadItemType")]


class AgentMessageThreadItem(WireModel):
    delivery: Literal["async"] | None = None
    id: str
    memory_citation: Annotated[MemoryCitation | None, Field(alias="memoryCitation")] = None
    phase: Literal["commentary", "partial_answer", "final_answer"] | None = None
    questions: list[AsyncUserInputQuestion] | None = None
    text: str
    type: Annotated[Literal["agentMessage"], Field(title="AgentMessageThreadItemType")]


class CommandExecutionThreadItem(WireModel):
    aggregated_output: Annotated[
        str | None,
        Field(
            alias="aggregatedOutput",
            description="The command's output, aggregated from stdout and stderr.",
        ),
    ] = None
    command: Annotated[str, Field(description="The command to be executed.")]
    command_actions: Annotated[
        list[ReadCommandAction | ListFilesCommandAction | SearchCommandAction | UnknownCommandAction],
        Field(
            alias="commandActions",
            description="A best-effort parsing of the command to understand the action(s) it will perform. This returns a list of CommandAction objects because a single shell command may be composed of many commands piped together.",
        ),
    ]
    cwd: Annotated[str, Field(description="The command's working directory.")]
    duration_ms: Annotated[
        int | None,
        Field(
            alias="durationMs",
            description="The duration of the command execution in milliseconds.",
        ),
    ] = None
    exit_code: Annotated[int | None, Field(alias="exitCode", description="The command's exit code.")] = None
    id: str
    plugin_id: Annotated[
        str | None,
        Field(
            alias="pluginId",
            description="Trusted first-party plugin id when this command resolves to one plugin script.",
        ),
    ] = None
    process_id: Annotated[
        str | None,
        Field(
            alias="processId",
            description="Identifier for the underlying PTY process (when available).",
        ),
    ] = None
    script_path: Annotated[
        str | None,
        Field(
            alias="scriptPath",
            description="Safe plugin-relative path when this command resolves to one plugin script.",
        ),
    ] = None
    source: Literal["agent", "userShell", "unifiedExecStartup", "unifiedExecInteraction"] = "agent"
    status: Literal["inProgress", "completed", "failed", "declined"]
    type: Annotated[Literal["commandExecution"], Field(title="CommandExecutionThreadItemType")]


class FileChangeThreadItem(WireModel):
    changes: list[FileUpdateChange]
    id: str
    status: Literal["inProgress", "completed", "failed", "declined"]
    type: Annotated[Literal["fileChange"], Field(title="FileChangeThreadItemType")]


class CollabAgentToolCallThreadItem(WireModel):
    agents_states: Annotated[
        dict[str, CollabAgentState],
        Field(
            alias="agentsStates",
            description="Last known status of the target agents, when available.",
        ),
    ]
    id: Annotated[str, Field(description="Unique identifier for this collab tool call.")]
    model: Annotated[
        str | None,
        Field(description="Model requested for the spawned agent, when applicable."),
    ] = None
    prompt: Annotated[
        str | None,
        Field(description="Prompt text sent as part of the collab tool call, when available."),
    ] = None
    reasoning_effort: Annotated[
        ReasoningEffort | None,
        Field(
            alias="reasoningEffort",
            description="Reasoning effort requested for the spawned agent, when applicable.",
        ),
    ] = None
    receiver_thread_ids: Annotated[
        list[str],
        Field(
            alias="receiverThreadIds",
            description="Thread ID of the receiving agent, when applicable. In case of spawn operation, this corresponds to the newly spawned agent.",
        ),
    ]
    sender_thread_id: Annotated[
        str,
        Field(
            alias="senderThreadId",
            description="Thread ID of the agent issuing the collab request.",
        ),
    ]
    status: Annotated[
        Literal["inProgress", "completed", "failed", "interrupted"],
        Field(description="Current status of the collab tool call."),
    ]
    tool: Annotated[
        Literal[
            "spawnAgent",
            "sendInput",
            "resumeAgent",
            "wait",
            "closeAgent",
            "sendMessage",
            "followupTask",
            "interruptAgent",
            "listAgents",
        ],
        Field(description="Name of the collab tool that was invoked."),
    ]
    type: Annotated[Literal["collabAgentToolCall"], Field(title="CollabAgentToolCallThreadItemType")]


class WebSearchThreadItem(WireModel):
    action: (
        SearchWebSearchAction | OpenPageWebSearchAction | FindInPageWebSearchAction | OtherWebSearchAction | None
    ) = None
    id: str
    query: str
    results: Annotated[
        list[Any] | None,
        Field(
            description="Structured search results returned out-of-band by standalone web search.\n\nThese stay as opaque JSON at the extension/app-server boundary so new result fields and result types can pass through without a Codex release."
        ),
    ] = None
    type: Annotated[Literal["webSearch"], Field(title="WebSearchThreadItemType")]


class ThreadResumeInitialTurnsPageParams(WireModel):
    items_view: Annotated[
        Literal["notLoaded", "summary", "full"] | None,
        Field(
            alias="itemsView",
            description="How much item detail to include for each returned turn; defaults to summary.",
        ),
    ] = None
    limit: Annotated[int | None, Field(description="Optional turn page size.", ge=0)] = None
    sort_direction: Annotated[
        Literal["asc", "desc"] | None,
        Field(
            alias="sortDirection",
            description="Optional turn pagination direction; defaults to descending.",
        ),
    ] = None


class ThreadSection(WireModel):
    appearance: Annotated[
        ThreadSectionAppearance | None,
        Field(description="Optional appearance synchronized across clients."),
    ] = None
    id: Annotated[
        str,
        Field(description="Opaque UUIDv7 identity that remains stable when the section is renamed."),
    ]
    name: Annotated[str, Field(description="The current user-visible section name.")]


class ThreadStartParams(WireModel):
    allow_provider_model_fallback: Annotated[
        bool | None,
        Field(
            alias="allowProviderModelFallback",
            description="Allow a provider with an authoritative static model catalog to replace an unavailable requested model with its default.",
        ),
    ] = None
    approval_policy: Annotated[
        Literal["untrusted", "on-request", "never"] | GranularAskForApproval | None,
        Field(alias="approvalPolicy"),
    ] = None
    approvals_reviewer: Annotated[
        Literal["user", "auto_review", "guardian_subagent"] | None,
        Field(
            alias="approvalsReviewer",
            description="Override where approval requests are routed for review on this thread and subsequent turns.",
        ),
    ] = None
    base_instructions: Annotated[str | None, Field(alias="baseInstructions")] = None
    config: dict[str, Any] | None = None
    cwd: str | None = None
    daybreak_enabled: Annotated[
        bool | None,
        Field(
            alias="daybreakEnabled",
            description="Initial Daybreak choice for this persistent thread. Omitted or null leaves it unset. This does not select a turn's `cyberAccessProgram` or grant access. Not supported for ephemeral threads.",
        ),
    ] = None
    developer_instructions: Annotated[str | None, Field(alias="developerInstructions")] = None
    dynamic_tools: Annotated[
        list[FunctionDynamicToolSpec | NamespaceDynamicToolSpec] | None,
        Field(alias="dynamicTools"),
    ] = None
    environments: Annotated[
        list[TurnEnvironmentParams] | None,
        Field(
            description="Optional sticky environments for this thread.\n\nOmitted selects the default environment when environment access is enabled. Empty disables environment access for turns that do not provide a turn override. Non-empty selects the first environment as the current turn environment."
        ),
    ] = None
    ephemeral: bool | None = None
    experimental_raw_events: Annotated[
        bool | None,
        Field(
            alias="experimentalRawEvents",
            description="If true, opt into emitting raw Responses API items on the event stream. This is for internal use only (e.g. Codex Cloud).",
        ),
    ] = None
    history_mode: Annotated[
        Literal["legacy", "paginated"] | None,
        Field(
            alias="historyMode",
            description="Persisted thread history contract to use for this new thread.",
        ),
    ] = None
    mock_experimental_field: Annotated[
        str | None,
        Field(
            alias="mockExperimentalField",
            description="Test-only experimental field used to validate experimental gating and schema filtering behavior in a stable way.",
        ),
    ] = None
    model: str | None = None
    model_provider: Annotated[str | None, Field(alias="modelProvider")] = None
    multi_agent_mode: Annotated[
        Literal["explicitRequestOnly", "proactive"] | CustomMultiAgentMode | None,
        Field(
            alias="multiAgentMode",
            description="@deprecated Ignored. Use Ultra reasoning effort for proactive multi-agent behavior.",
        ),
    ] = None
    permissions: Annotated[
        str | None,
        Field(description="Named profile id for this thread. Cannot be combined with `sandbox`."),
    ] = None
    personality: Annotated[
        Literal["none", "friendly", "pragmatic"] | None,
        Field(description="@deprecated `friendly` and `pragmatic` no longer select a style."),
    ] = None
    project_id: Annotated[
        str | None,
        Field(
            alias="projectId",
            description="Optional project identity for this new thread. Durable threads persist the assignment; ephemeral threads expose it only in live responses.",
        ),
    ] = None
    runtime_workspace_roots: Annotated[
        list[str] | None,
        Field(
            alias="runtimeWorkspaceRoots",
            description="Replace the thread's runtime workspace roots. Paths must be absolute.",
        ),
    ] = None
    sandbox: Literal["read-only", "workspace-write", "danger-full-access"] | None = None
    selected_capability_roots: Annotated[
        list[SelectedCapabilityRoot] | None,
        Field(
            alias="selectedCapabilityRoots",
            description="Capability roots selected for this thread by the hosting platform.",
        ),
    ] = None
    service_name: Annotated[str | None, Field(alias="serviceName")] = None
    service_tier: Annotated[str | None, Field(alias="serviceTier")] = None
    session_start_source: Annotated[Literal["startup", "clear"] | None, Field(alias="sessionStartSource")] = None
    thread_source: Annotated[
        str | None,
        Field(
            alias="threadSource",
            description="Optional client-supplied analytics source classification for this thread.",
        ),
    ] = None


class ThreadTokenUsage(WireModel):
    last: TokenUsageBreakdown
    model_context_window: Annotated[int | None, Field(alias="modelContextWindow")] = None
    total: TokenUsageBreakdown


class ThreadTokenUsageUpdatedNotification(WireModel):
    thread_id: Annotated[str, Field(alias="threadId")]
    token_usage: Annotated[ThreadTokenUsage, Field(alias="tokenUsage")]
    turn_id: Annotated[str, Field(alias="turnId")]


class ToolRequestUserInputParams(WireModel):
    auto_resolution_ms: Annotated[
        int | None,
        Field(
            alias="autoResolutionMs",
            description="@deprecated Use `isBlocking` to decide whether the request should block.",
            ge=0,
        ),
    ] = None
    is_blocking: Annotated[bool, Field(alias="isBlocking")]
    item_id: Annotated[str, Field(alias="itemId")]
    questions: list[ToolRequestUserInputQuestion]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class TurnError(WireModel):
    additional_details: Annotated[str | None, Field(alias="additionalDetails")] = None
    codex_error_info: Annotated[
        Literal[
            "contextWindowExceeded",
            "sessionBudgetExceeded",
            "usageLimitExceeded",
            "rateLimitExceeded",
            "flexUnavailable",
            "serverOverloaded",
            "cyberPolicy",
            "misalignmentPolicyViolation",
            "tooManyDenials",
            "internalServerError",
            "unauthorized",
            "badRequest",
            "threadRollbackFailed",
            "sandboxError",
            "other",
        ]
        | HttpConnectionFailedCodexErrorInfo
        | ResponseStreamConnectionFailedCodexErrorInfo
        | ResponseStreamDisconnectedCodexErrorInfo
        | ResponseTooManyFailedAttemptsCodexErrorInfo
        | ActiveTurnNotSteerableCodexErrorInfo
        | str
        | dict[str, Any]
        | None,
        Field(alias="codexErrorInfo"),
    ] = None
    message: str
    misalignment: Annotated[
        MisalignmentErrorDetails | None,
        Field(description="Optional public explanation and continuation instruction for a misalignment block."),
    ] = None


class TurnSteerParams(WireModel):
    additional_context: Annotated[
        dict[str, Any] | None,
        Field(
            alias="additionalContext",
            description="Optional client-provided context fragments keyed by an opaque source identifier.",
        ),
    ] = None
    client_user_message_id: Annotated[str | None, Field(alias="clientUserMessageId")] = None
    expected_turn_id: Annotated[
        str,
        Field(
            alias="expectedTurnId",
            description="Required active turn id precondition. The request fails when it does not match the currently active turn.",
        ),
    ]
    input: list[
        TextUserInput
        | LocalImageUserInput
        | AudioUserInput
        | LocalAudioUserInput
        | SkillUserInput
        | MentionUserInput
        | UrlUserInput
        | FileIdUserInput
    ]
    responsesapi_client_metadata: Annotated[
        dict[str, Any] | None,
        Field(
            alias="responsesapiClientMetadata",
            description='Optional metadata to enrich Codex\'s ResponsesAPI turn metadata.\n\nEntries are flattened into the JSON string sent as `client_metadata["x-codex-turn-metadata"]` on ResponsesAPI HTTP and websocket requests.\n\nThey are not sent as top-level ResponsesAPI `client_metadata` keys, and reserved keys such as `session_id`, `thread_id`, `turn_id`, and `window_id` cannot be overridden.',
        ),
    ] = None
    thread_id: Annotated[str, Field(alias="threadId")]


class ApplyNetworkPolicyAmendment(WireModel):
    network_policy_amendment: NetworkPolicyAmendment


class ApplyNetworkPolicyAmendmentCommandExecutionApprovalDecision(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    apply_network_policy_amendment: Annotated[ApplyNetworkPolicyAmendment, Field(alias="applyNetworkPolicyAmendment")]


class CommandExecutionRequestApprovalResponse(WireModel):
    decision: (
        Literal["accept", "acceptForSession", "decline", "cancel"]
        | AcceptWithExecpolicyAmendmentCommandExecutionApprovalDecision
        | ApplyNetworkPolicyAmendmentCommandExecutionApprovalDecision
    )


class SpecialFileSystemPath(WireModel):
    type: Annotated[Literal["special"], Field(title="SpecialFileSystemPathType")]
    value: (
        RootFileSystemSpecialPath
        | MinimalFileSystemSpecialPath
        | KindFileSystemSpecialPath
        | TmpdirFileSystemSpecialPath
        | SlashTmpFileSystemSpecialPath
        | FileSystemSpecialPath1
    )


class FileSystemSandboxEntry(WireModel):
    access: Literal["read", "write", "deny"]
    path: PathFileSystemPath | GlobPatternFileSystemPath | SpecialFileSystemPath


class FunctionCallOutputResponseItem(WireModel):
    call_id: str | None = None
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    name: str | None = None
    namespace: str | None = None
    output: (
        str
        | list[
            InputTextFunctionCallOutputContentItem
            | InputAudioFunctionCallOutputContentItem
            | EncryptedContentFunctionCallOutputContentItem
            | ImageUrlFunctionCallOutputContentItem
            | FileIdFunctionCallOutputContentItem
        ]
    )
    type: Annotated[
        Literal["function_call_output"],
        Field(title="FunctionCallOutputResponseItemType"),
    ]


class CustomToolCallOutputResponseItem(WireModel):
    call_id: str
    id: str | None = None
    internal_chat_message_metadata_passthrough: InternalChatMessageMetadataPassthrough | None = None
    name: str | None = None
    output: (
        str
        | list[
            InputTextFunctionCallOutputContentItem
            | InputAudioFunctionCallOutputContentItem
            | EncryptedContentFunctionCallOutputContentItem
            | ImageUrlFunctionCallOutputContentItem
            | FileIdFunctionCallOutputContentItem
        ]
    )
    type: Annotated[
        Literal["custom_tool_call_output"],
        Field(title="CustomToolCallOutputResponseItemType"),
    ]


class SubAgentSessionSource(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    sub_agent: Annotated[
        Literal["review", "compact", "memory_consolidation"] | ThreadSpawnSubAgentSource | OtherSubAgentSource,
        Field(alias="subAgent"),
    ]


class FunctionCallOutputThreadItem(WireModel):
    id: str
    name: str
    namespace: str | None = None
    output: (
        str
        | list[
            InputTextFunctionCallOutputContentItem
            | InputAudioFunctionCallOutputContentItem
            | EncryptedContentFunctionCallOutputContentItem
            | ImageUrlFunctionCallOutputContentItem
            | FileIdFunctionCallOutputContentItem
        ]
    )
    type: Annotated[Literal["functionCallOutput"], Field(title="FunctionCallOutputThreadItemType")]


class ThreadResumeParams(WireModel):
    approval_policy: Annotated[
        Literal["untrusted", "on-request", "never"] | GranularAskForApproval | None,
        Field(alias="approvalPolicy"),
    ] = None
    approvals_reviewer: Annotated[
        Literal["user", "auto_review", "guardian_subagent"] | None,
        Field(
            alias="approvalsReviewer",
            description="Override where approval requests are routed for review on this thread and subsequent turns.",
        ),
    ] = None
    base_instructions: Annotated[str | None, Field(alias="baseInstructions")] = None
    config: dict[str, Any] | None = None
    cwd: str | None = None
    developer_instructions: Annotated[str | None, Field(alias="developerInstructions")] = None
    exclude_turns: Annotated[
        bool | None,
        Field(
            alias="excludeTurns",
            description="When true, return only thread metadata and live-resume state without populating `thread.turns`. This is useful when the client plans to call `thread/turns/list` immediately after resuming. Full-history hydration is deprecated for paginated threads; use this with `thread/turns/list` and `thread/items/list` instead.",
        ),
    ] = None
    history: Annotated[
        list[
            AdditionalToolsResponseItem
            | MessageResponseItem
            | AgentMessageResponseItem
            | ReasoningResponseItem
            | LocalShellCallResponseItem
            | FunctionCallResponseItem
            | ToolSearchCallResponseItem
            | FunctionCallOutputResponseItem
            | CustomToolCallResponseItem
            | CustomToolCallOutputResponseItem
            | ToolSearchOutputResponseItem
            | WebSearchCallResponseItem
            | ImageGenerationCallResponseItem
            | CompactionResponseItem
            | ConfigurationUpdateResponseItem
            | CompactionTriggerResponseItem
            | ContextCompactionResponseItem
            | OtherResponseItem
        ]
        | None,
        Field(
            description="[UNSTABLE] FOR CODEX CLOUD - DO NOT USE. If specified, the thread will be resumed with the provided history instead of loaded from disk."
        ),
    ] = None
    initial_turns_page: Annotated[
        ThreadResumeInitialTurnsPageParams | None,
        Field(
            alias="initialTurnsPage",
            description="When present, include a `thread/turns/list` page in the resume response so clients can bootstrap recent turns without a second request.",
        ),
    ] = None
    model: Annotated[
        str | None,
        Field(description="Configuration overrides for the resumed thread, if any."),
    ] = None
    model_provider: Annotated[str | None, Field(alias="modelProvider")] = None
    path: Annotated[
        str | None,
        Field(
            description="[UNSTABLE] Specify the rollout path to resume from. If specified for a non-running thread, the thread_id param will be ignored. If thread_id identifies a running thread, the path must match the active rollout path."
        ),
    ] = None
    permissions: Annotated[
        str | None,
        Field(description="Named profile id for the resumed thread. Cannot be combined with `sandbox`."),
    ] = None
    personality: Annotated[
        Literal["none", "friendly", "pragmatic"] | None,
        Field(
            description="@deprecated `friendly` and `pragmatic` no longer select a style. Changing this does not rewrite the thread's existing instructions."
        ),
    ] = None
    runtime_workspace_roots: Annotated[
        list[str] | None,
        Field(
            alias="runtimeWorkspaceRoots",
            description="Replace the thread's runtime workspace roots. Paths must be absolute.",
        ),
    ] = None
    sandbox: Literal["read-only", "workspace-write", "danger-full-access"] | None = None
    service_tier: Annotated[str | None, Field(alias="serviceTier")] = None
    thread_id: Annotated[str, Field(alias="threadId")]


class Turn(WireModel):
    completed_at: Annotated[
        int | None,
        Field(
            alias="completedAt",
            description="Unix timestamp (in seconds) when the turn completed.",
        ),
    ] = None
    duration_ms: Annotated[
        int | None,
        Field(
            alias="durationMs",
            description="Duration between turn start and completion in milliseconds, if known.",
        ),
    ] = None
    error: Annotated[
        TurnError | None,
        Field(description="Error associated with a failed or interrupted turn."),
    ] = None
    id: Annotated[
        str,
        Field(description="Identifier for this turn. Codex-generated turn IDs are UUIDv7."),
    ]
    items: Annotated[
        list[
            UserMessageThreadItem
            | HookPromptThreadItem
            | AgentMessageThreadItem
            | FunctionCallOutputThreadItem
            | PlanThreadItem
            | ReasoningThreadItem
            | CommandExecutionThreadItem
            | FileChangeThreadItem
            | McpToolCallThreadItem
            | DynamicToolCallThreadItem
            | CollabAgentToolCallThreadItem
            | SubAgentActivityThreadItem
            | WebSearchThreadItem
            | ImageViewThreadItem
            | SleepThreadItem
            | ImageGenerationThreadItem
            | EnteredReviewModeThreadItem
            | ExitedReviewModeThreadItem
            | ContextCompactionThreadItem
        ],
        Field(description="Thread items currently included in this turn payload."),
    ]
    items_view: Annotated[
        Literal["notLoaded", "summary", "full"],
        Field(
            alias="itemsView",
            description="Describes how much of `items` has been loaded for this turn.",
        ),
    ] = "full"
    root_turn_id: Annotated[
        str | None,
        Field(
            alias="rootTurnId",
            description="ID of the first turn in the chain of work that led to this turn. Pass this as `rootTurnId` when starting work on behalf of this turn. May be null in older history or a `review/start` response.",
        ),
    ] = None
    started_at: Annotated[
        int | None,
        Field(
            alias="startedAt",
            description="Unix timestamp (in seconds) when the turn started.",
        ),
    ] = None
    status: Literal["completed", "interrupted", "failed", "inProgress"]


class TurnCompletedNotification(WireModel):
    thread_id: Annotated[str, Field(alias="threadId")]
    turn: Turn


class TurnStartResponse(WireModel):
    turn: Turn


class TurnStartedNotification(WireModel):
    thread_id: Annotated[str, Field(alias="threadId")]
    turn: Turn


class TurnToolOutput(WireModel):
    name: str
    namespace: str | None = None
    output: (
        str
        | list[
            InputTextFunctionCallOutputContentItem
            | InputAudioFunctionCallOutputContentItem
            | EncryptedContentFunctionCallOutputContentItem
            | ImageUrlFunctionCallOutputContentItem
            | FileIdFunctionCallOutputContentItem
        ]
    )


class TurnsPage(WireModel):
    backwards_cursor: Annotated[str | None, Field(alias="backwardsCursor")] = None
    data: list[Turn]
    next_cursor: Annotated[str | None, Field(alias="nextCursor")] = None


class AdditionalFileSystemPermissions(WireModel):
    entries: list[FileSystemSandboxEntry] | None = None
    glob_scan_max_depth: Annotated[int | None, Field(alias="globScanMaxDepth", ge=1)] = None
    read: Annotated[
        list[str] | None,
        Field(description="This will be removed in favor of `entries`."),
    ] = None
    write: Annotated[
        list[str] | None,
        Field(description="This will be removed in favor of `entries`."),
    ] = None


class AdditionalPermissionProfile(WireModel):
    file_system: Annotated[AdditionalFileSystemPermissions | None, Field(alias="fileSystem")] = None
    network: Annotated[
        AdditionalNetworkPermissions | None,
        Field(description="Partial overlay used for per-command permission requests."),
    ] = None


class CommandExecutionRequestApprovalParams(WireModel):
    additional_permissions: Annotated[
        AdditionalPermissionProfile | None,
        Field(
            alias="additionalPermissions",
            description="Optional additional permissions requested for this command.",
        ),
    ] = None
    approval_id: Annotated[
        str | None,
        Field(
            alias="approvalId",
            description="Unique identifier for this specific approval callback.\n\nFor regular shell/unified_exec approvals, this is null.\n\nFor zsh-exec-bridge subcommand approvals, multiple callbacks can belong to one parent `itemId`, so `approvalId` is a distinct opaque callback id (a UUID) used to disambiguate routing. Stdin approvals also use a distinct callback id; inspect `kind` to distinguish them.",
        ),
    ] = None
    available_decisions: Annotated[
        list[
            Literal["accept", "acceptForSession", "decline", "cancel"]
            | AcceptWithExecpolicyAmendmentCommandExecutionApprovalDecision
            | ApplyNetworkPolicyAmendmentCommandExecutionApprovalDecision
        ]
        | None,
        Field(
            alias="availableDecisions",
            description="Ordered list of decisions the client may present for this prompt.",
        ),
    ] = None
    command: Annotated[str | None, Field(description="The command to be executed.")] = None
    command_actions: Annotated[
        list[ReadCommandAction | ListFilesCommandAction | SearchCommandAction | UnknownCommandAction] | None,
        Field(
            alias="commandActions",
            description="Best-effort parsed command actions for friendly display.",
        ),
    ] = None
    cwd: Annotated[str | None, Field(description="The command's working directory.")] = None
    environment_id: Annotated[
        str | None,
        Field(
            alias="environmentId",
            description="Environment in which the command will run.",
        ),
    ] = None
    item_id: Annotated[str, Field(alias="itemId")]
    kind: Annotated[
        Literal["command", "writeStdin"],
        Field(description="Kind of action under review. Defaults to `command` for older servers."),
    ] = "command"
    network_approval_context: Annotated[
        NetworkApprovalContext | None,
        Field(
            alias="networkApprovalContext",
            description="Optional context for a managed-network approval prompt.",
        ),
    ] = None
    proposed_execpolicy_amendment: Annotated[
        list[str] | None,
        Field(
            alias="proposedExecpolicyAmendment",
            description="Optional proposed execpolicy amendment to allow similar commands without prompting.",
        ),
    ] = None
    proposed_network_policy_amendments: Annotated[
        list[NetworkPolicyAmendment] | None,
        Field(
            alias="proposedNetworkPolicyAmendments",
            description="Optional proposed network policy amendments (allow/deny host) for future requests.",
        ),
    ] = None
    reason: Annotated[
        str | None,
        Field(description="Optional explanatory reason (e.g. request for network access)."),
    ] = None
    started_at_ms: Annotated[
        int,
        Field(
            alias="startedAtMs",
            description="Unix timestamp (in milliseconds) when this approval request started.",
        ),
    ]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class GrantedPermissionProfile(WireModel):
    file_system: Annotated[AdditionalFileSystemPermissions | None, Field(alias="fileSystem")] = None
    network: AdditionalNetworkPermissions | None = None


class ItemCompletedNotification(WireModel):
    completed_at_ms: Annotated[
        int,
        Field(
            alias="completedAtMs",
            description="Unix timestamp (in milliseconds) when this item lifecycle completed.",
        ),
    ]
    item: (
        UserMessageThreadItem
        | HookPromptThreadItem
        | AgentMessageThreadItem
        | FunctionCallOutputThreadItem
        | PlanThreadItem
        | ReasoningThreadItem
        | CommandExecutionThreadItem
        | FileChangeThreadItem
        | McpToolCallThreadItem
        | DynamicToolCallThreadItem
        | CollabAgentToolCallThreadItem
        | SubAgentActivityThreadItem
        | WebSearchThreadItem
        | ImageViewThreadItem
        | SleepThreadItem
        | ImageGenerationThreadItem
        | EnteredReviewModeThreadItem
        | ExitedReviewModeThreadItem
        | ContextCompactionThreadItem
    )
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class ItemStartedNotification(WireModel):
    item: (
        UserMessageThreadItem
        | HookPromptThreadItem
        | AgentMessageThreadItem
        | FunctionCallOutputThreadItem
        | PlanThreadItem
        | ReasoningThreadItem
        | CommandExecutionThreadItem
        | FileChangeThreadItem
        | McpToolCallThreadItem
        | DynamicToolCallThreadItem
        | CollabAgentToolCallThreadItem
        | SubAgentActivityThreadItem
        | WebSearchThreadItem
        | ImageViewThreadItem
        | SleepThreadItem
        | ImageGenerationThreadItem
        | EnteredReviewModeThreadItem
        | ExitedReviewModeThreadItem
        | ContextCompactionThreadItem
    )
    started_at_ms: Annotated[
        int,
        Field(
            alias="startedAtMs",
            description="Unix timestamp (in milliseconds) when this item lifecycle started.",
        ),
    ]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]


class PermissionsRequestApprovalResponse(WireModel):
    permissions: GrantedPermissionProfile
    scope: Literal["turn", "session"] = "turn"
    strict_auto_review: Annotated[
        bool | None,
        Field(
            alias="strictAutoReview",
            description="Review every subsequent command in this turn before normal sandboxed execution.",
        ),
    ] = None


class RequestPermissionProfile(WireModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    file_system: Annotated[AdditionalFileSystemPermissions | None, Field(alias="fileSystem")] = None
    network: AdditionalNetworkPermissions | None = None


class Thread(WireModel):
    agent_nickname: Annotated[
        str | None,
        Field(
            alias="agentNickname",
            description="Optional random unique nickname assigned to an AgentControl-spawned sub-agent.",
        ),
    ] = None
    agent_role: Annotated[
        str | None,
        Field(
            alias="agentRole",
            description="Optional role (agent_role) assigned to an AgentControl-spawned sub-agent.",
        ),
    ] = None
    can_accept_direct_input: Annotated[
        bool | None,
        Field(
            alias="canAcceptDirectInput",
            description="Whether the app server accepts direct turn input for this loaded thread. `None` means the capability is unavailable, such as for an unloaded stored thread.",
        ),
    ] = None
    cli_version: Annotated[
        str,
        Field(
            alias="cliVersion",
            description="Version of the CLI that created the thread.",
        ),
    ]
    created_at: Annotated[
        int,
        Field(
            alias="createdAt",
            description="Unix timestamp (in seconds) when the thread was created.",
        ),
    ]
    cwd: Annotated[str, Field(description="Working directory captured for the thread.")]
    daybreak_enabled: Annotated[
        bool | None,
        Field(
            alias="daybreakEnabled",
            description="Saved Daybreak choice, independent of turn execution. Null if unset.",
        ),
    ] = None
    environments: Annotated[
        list[ThreadEnvironment] | None,
        Field(
            description="Current environments for a loaded thread, in priority order, primary first. `null` means the thread is not loaded or the server does not expose its selection. An empty list means no environments are selected. This does not report connection status."
        ),
    ] = None
    ephemeral: Annotated[
        bool,
        Field(description="Whether the thread is ephemeral and should not be materialized on disk."),
    ]
    extra: Annotated[
        ThreadExtra | None,
        Field(description="Optional implementation-specific thread data."),
    ] = None
    forked_from_id: Annotated[
        str | None,
        Field(
            alias="forkedFromId",
            description="Source thread id when this thread was created by forking another thread.",
        ),
    ] = None
    git_info: Annotated[
        GitInfo | None,
        Field(
            alias="gitInfo",
            description="Optional Git metadata captured when the thread was created.",
        ),
    ] = None
    history_mode: Annotated[
        Literal["legacy", "paginated"],
        Field(
            alias="historyMode",
            description="Persisted thread history contract selected when this thread was created.",
        ),
    ] = "legacy"
    id: Annotated[
        str,
        Field(description="Identifier for this thread. Codex-generated thread IDs are UUIDv7."),
    ]
    model: Annotated[
        str | None,
        Field(
            description="Current configured model when loaded, otherwise the latest persisted model. Null when unavailable. This is not per-turn execution telemetry."
        ),
    ] = None
    model_provider: Annotated[
        str,
        Field(
            alias="modelProvider",
            description="Model provider used for this thread (for example, 'openai').",
        ),
    ]
    name: Annotated[str | None, Field(description="Optional user-facing thread title.")] = None
    originator: Annotated[
        str | None,
        Field(
            description="Originator recorded when the thread was created, independent of its current client or executor. Null when the recorded originator is unavailable."
        ),
    ] = None
    parent_thread_id: Annotated[
        str | None,
        Field(
            alias="parentThreadId",
            description="The ID of the parent thread. This will only be set if this thread is a subagent.",
        ),
    ] = None
    path: Annotated[str | None, Field(description="[UNSTABLE] Path to the thread on disk.")] = None
    preview: Annotated[
        str,
        Field(description="Usually the first user message in the thread, if available."),
    ]
    project_id: Annotated[
        str | None,
        Field(
            alias="projectId",
            description="Canonical project assignment owned by app-server, if any.",
        ),
    ]
    reasoning_effort: Annotated[
        ReasoningEffort | None,
        Field(
            alias="reasoningEffort",
            description="Current configured reasoning effort when loaded, otherwise the latest persisted effort. Null when unset or unavailable. This is not per-turn execution telemetry.",
        ),
    ] = None
    recency_at: Annotated[
        int | None,
        Field(
            alias="recencyAt",
            description="Unix timestamp (in seconds) used for thread recency ordering.",
        ),
    ] = None
    section: Annotated[
        ThreadSection | None,
        Field(description="The independently persisted section selected for this thread, if any."),
    ] = None
    section_entered_at: Annotated[
        int | None,
        Field(
            alias="sectionEnteredAt",
            description="Unix timestamp in seconds when the thread entered its current section.",
        ),
    ] = None
    session_id: Annotated[
        str,
        Field(
            alias="sessionId",
            description="Session id shared by threads that belong to the same session tree.",
        ),
    ]
    source: Annotated[
        Literal["cli", "vscode", "exec", "appServer", "unknown"] | CustomSessionSource | SubAgentSessionSource,
        Field(description="Origin of the thread (CLI, VSCode, codex exec, codex app-server, etc.)."),
    ]
    status: Annotated[
        NotLoadedThreadStatus | IdleThreadStatus | SystemErrorThreadStatus | ActiveThreadStatus,
        Field(description="Current runtime status for the thread."),
    ]
    thread_source: Annotated[
        str | None,
        Field(
            alias="threadSource",
            description="Optional analytics source classification for this thread.",
        ),
    ] = None
    turns: Annotated[
        list[Turn],
        Field(
            description="Only populated on `thread/resume`, `thread/fork`, and `thread/read` (when `includeTurns` is true) responses. For all other responses and notifications returning a Thread, the turns field will be an empty list."
        ),
    ]
    updated_at: Annotated[
        int,
        Field(
            alias="updatedAt",
            description="Unix timestamp (in seconds) when the thread was last updated.",
        ),
    ]


class ThreadForkResponse(WireModel):
    active_permission_profile: Annotated[
        ActivePermissionProfile | None,
        Field(
            alias="activePermissionProfile",
            description="Named or implicit built-in profile that produced the active permissions, when known.",
        ),
    ] = None
    approval_policy: Annotated[
        Literal["untrusted", "on-request", "never"] | GranularAskForApproval,
        Field(alias="approvalPolicy"),
    ]
    approvals_reviewer: Annotated[
        Literal["user", "auto_review", "guardian_subagent"],
        Field(
            alias="approvalsReviewer",
            description="Reviewer currently used for approval requests on this thread.",
        ),
    ]
    cwd: Annotated[
        str,
        Field(
            description="A path that is guaranteed to be absolute and normalized (though it is not guaranteed to be canonicalized or exist on the filesystem).\n\nIMPORTANT: When deserializing an `AbsolutePathBuf`, a base path must be set using [AbsolutePathBufGuard::new]. If no base path is set, the deserialization will fail unless the path being deserialized is already absolute."
        ),
    ]
    disabled_plugin_ids: Annotated[
        list[str],
        Field(
            alias="disabledPluginIds",
            description="Saved list of disabled plugin IDs. Does not yet filter plugin capabilities.",
        ),
    ] = []
    instruction_sources: Annotated[
        list[str],
        Field(
            alias="instructionSources",
            description="Environment-native paths to instruction source files currently loaded for this thread.",
        ),
    ] = []
    model: str
    model_provider: Annotated[str, Field(alias="modelProvider")]
    multi_agent_mode: Annotated[
        Literal["explicitRequestOnly", "proactive"] | CustomMultiAgentMode,
        Field(
            alias="multiAgentMode",
            description="@deprecated Always `explicitRequestOnly`. Use `reasoningEffort` for Ultra behavior.",
            validate_default=True,
        ),
    ] = "explicitRequestOnly"
    reasoning_effort: Annotated[ReasoningEffort | None, Field(alias="reasoningEffort")] = None
    runtime_workspace_roots: Annotated[
        list[str],
        Field(
            alias="runtimeWorkspaceRoots",
            description="Thread-scoped runtime workspace roots used to materialize `:workspace_roots`.",
        ),
    ] = []
    sandbox: Annotated[
        DangerFullAccessSandboxPolicy
        | ReadOnlySandboxPolicy
        | ExternalSandboxSandboxPolicy
        | WorkspaceWriteSandboxPolicy,
        Field(
            description="Legacy sandbox policy retained for compatibility. Experimental clients should prefer `activePermissionProfile` for profile provenance."
        ),
    ]
    service_tier: Annotated[str | None, Field(alias="serviceTier")] = None
    thread: Thread


class ThreadResumeResponse(WireModel):
    active_permission_profile: Annotated[
        ActivePermissionProfile | None,
        Field(
            alias="activePermissionProfile",
            description="Named or implicit built-in profile that produced the active permissions, when known.",
        ),
    ] = None
    approval_policy: Annotated[
        Literal["untrusted", "on-request", "never"] | GranularAskForApproval,
        Field(alias="approvalPolicy"),
    ]
    approvals_reviewer: Annotated[
        Literal["user", "auto_review", "guardian_subagent"],
        Field(
            alias="approvalsReviewer",
            description="Reviewer currently used for approval requests on this thread.",
        ),
    ]
    collaboration_mode: Annotated[
        CollaborationMode | None,
        Field(
            alias="collaborationMode",
            description="Effective collaboration mode. Absent when resuming from an older server.",
        ),
    ] = None
    cwd: Annotated[
        str,
        Field(
            description="A path that is guaranteed to be absolute and normalized (though it is not guaranteed to be canonicalized or exist on the filesystem).\n\nIMPORTANT: When deserializing an `AbsolutePathBuf`, a base path must be set using [AbsolutePathBufGuard::new]. If no base path is set, the deserialization will fail unless the path being deserialized is already absolute."
        ),
    ]
    disabled_plugin_ids: Annotated[
        list[str],
        Field(
            alias="disabledPluginIds",
            description="Saved list of disabled plugin IDs. Does not yet filter plugin capabilities.",
        ),
    ] = []
    initial_turns_page: Annotated[
        TurnsPage | None,
        Field(
            alias="initialTurnsPage",
            description="`thread/turns/list` page returned when requested by `initialTurnsPage`.",
        ),
    ] = None
    instruction_sources: Annotated[
        list[str],
        Field(
            alias="instructionSources",
            description="Environment-native paths to instruction source files currently loaded for this thread.",
        ),
    ] = []
    items_backwards_cursor: Annotated[
        str | None,
        Field(
            alias="itemsBackwardsCursor",
            description='Opaque cursor for hydrating paginated items backwards.\n\nPass this as `cursor` to `thread/items/list` with `sortDirection: "desc"`. The first page includes the item identified by the cursor.',
        ),
    ] = None
    model: str
    model_provider: Annotated[str, Field(alias="modelProvider")]
    multi_agent_mode: Annotated[
        Literal["explicitRequestOnly", "proactive"] | CustomMultiAgentMode,
        Field(
            alias="multiAgentMode",
            description="@deprecated Always `explicitRequestOnly`. Use `reasoningEffort` for Ultra behavior.",
            validate_default=True,
        ),
    ] = "explicitRequestOnly"
    reasoning_effort: Annotated[ReasoningEffort | None, Field(alias="reasoningEffort")] = None
    runtime_workspace_roots: Annotated[
        list[str],
        Field(
            alias="runtimeWorkspaceRoots",
            description="Thread-scoped runtime workspace roots used to materialize `:workspace_roots`.",
        ),
    ] = []
    sandbox: Annotated[
        DangerFullAccessSandboxPolicy
        | ReadOnlySandboxPolicy
        | ExternalSandboxSandboxPolicy
        | WorkspaceWriteSandboxPolicy,
        Field(
            description="Legacy sandbox policy retained for compatibility. Experimental clients should prefer `activePermissionProfile` for profile provenance."
        ),
    ]
    service_tier: Annotated[str | None, Field(alias="serviceTier")] = None
    thread: Thread
    turns_backwards_cursor: Annotated[
        str | None,
        Field(
            alias="turnsBackwardsCursor",
            description='Opaque cursor for hydrating paginated turns backwards.\n\nPass this as `cursor` to `thread/turns/list` with `sortDirection: "desc"`. The first page includes the turn identified by the cursor.',
        ),
    ] = None


class ThreadStartResponse(WireModel):
    active_permission_profile: Annotated[
        ActivePermissionProfile | None,
        Field(
            alias="activePermissionProfile",
            description="Named or implicit built-in profile that produced the active permissions, when known.",
        ),
    ] = None
    approval_policy: Annotated[
        Literal["untrusted", "on-request", "never"] | GranularAskForApproval,
        Field(alias="approvalPolicy"),
    ]
    approvals_reviewer: Annotated[
        Literal["user", "auto_review", "guardian_subagent"],
        Field(
            alias="approvalsReviewer",
            description="Reviewer currently used for approval requests on this thread.",
        ),
    ]
    cwd: Annotated[
        str,
        Field(
            description="A path that is guaranteed to be absolute and normalized (though it is not guaranteed to be canonicalized or exist on the filesystem).\n\nIMPORTANT: When deserializing an `AbsolutePathBuf`, a base path must be set using [AbsolutePathBufGuard::new]. If no base path is set, the deserialization will fail unless the path being deserialized is already absolute."
        ),
    ]
    disabled_plugin_ids: Annotated[
        list[str],
        Field(
            alias="disabledPluginIds",
            description="Saved list of disabled plugin IDs. Does not yet filter plugin capabilities.",
        ),
    ] = []
    instruction_sources: Annotated[
        list[str],
        Field(
            alias="instructionSources",
            description="Environment-native paths to instruction source files currently loaded for this thread.",
        ),
    ] = []
    model: str
    model_provider: Annotated[str, Field(alias="modelProvider")]
    multi_agent_mode: Annotated[
        Literal["explicitRequestOnly", "proactive"] | CustomMultiAgentMode,
        Field(
            alias="multiAgentMode",
            description="@deprecated Always `explicitRequestOnly`. Use `reasoningEffort` for Ultra behavior.",
            validate_default=True,
        ),
    ] = "explicitRequestOnly"
    reasoning_effort: Annotated[ReasoningEffort | None, Field(alias="reasoningEffort")] = None
    runtime_workspace_roots: Annotated[
        list[str],
        Field(
            alias="runtimeWorkspaceRoots",
            description="Thread-scoped runtime workspace roots used to materialize `:workspace_roots`.",
        ),
    ] = []
    sandbox: Annotated[
        DangerFullAccessSandboxPolicy
        | ReadOnlySandboxPolicy
        | ExternalSandboxSandboxPolicy
        | WorkspaceWriteSandboxPolicy,
        Field(
            description="Legacy sandbox policy retained for compatibility. Experimental clients should prefer `activePermissionProfile` for profile provenance."
        ),
    ]
    service_tier: Annotated[str | None, Field(alias="serviceTier")] = None
    thread: Thread


class TurnStartParams(WireModel):
    additional_context: Annotated[
        dict[str, Any] | None,
        Field(
            alias="additionalContext",
            description="Optional client-provided context fragments keyed by an opaque source identifier.",
        ),
    ] = None
    approval_policy: Annotated[
        Literal["untrusted", "on-request", "never"] | GranularAskForApproval | None,
        Field(
            alias="approvalPolicy",
            description="Override the approval policy for this turn and subsequent turns.",
        ),
    ] = None
    approvals_reviewer: Annotated[
        Literal["user", "auto_review", "guardian_subagent"] | None,
        Field(
            alias="approvalsReviewer",
            description="Override where approval requests are routed for review on this turn and subsequent turns.",
        ),
    ] = None
    client_user_message_id: Annotated[str | None, Field(alias="clientUserMessageId")] = None
    collaboration_mode: Annotated[
        CollaborationMode | None,
        Field(
            alias="collaborationMode",
            description='EXPERIMENTAL - Set a pre-set collaboration mode. Takes precedence over model, reasoning_effort, and developer instructions if set.\n\nFor `collaboration_mode.settings.developer_instructions`, `null` means "use the built-in instructions for the selected mode".',
        ),
    ] = None
    cwd: Annotated[
        str | None,
        Field(description="Override the working directory for this turn and subsequent turns."),
    ] = None
    cyber_access_program: Annotated[
        Literal["standard", "daybreakBlue", "daybreakRed"] | None,
        Field(
            alias="cyberAccessProgram",
            description="EXPERIMENTAL - Request an authorized cyber program for this turn. Omission preserves automatic behavior. This does not grant access.",
        ),
    ] = None
    disabled_plugin_ids: Annotated[
        list[str] | None,
        Field(
            alias="disabledPluginIds",
            description="Replace this thread's disabled plugin IDs. Omitted/null preserves the list; [] clears it.",
        ),
    ] = None
    effort: Annotated[
        ReasoningEffort | None,
        Field(description="Override the reasoning effort for this turn and subsequent turns."),
    ] = None
    environments: Annotated[
        list[TurnEnvironmentParams] | None,
        Field(
            description="Optional environments for this turn and subsequent turns.\n\nOmitted uses the thread sticky environments. Empty disables environment access for this turn. Non-empty selects the first environment as the current turn environment for this turn."
        ),
    ] = None
    input: list[
        TextUserInput
        | LocalImageUserInput
        | AudioUserInput
        | LocalAudioUserInput
        | SkillUserInput
        | MentionUserInput
        | UrlUserInput
        | FileIdUserInput
    ]
    model: Annotated[
        str | None,
        Field(description="Override the model for this turn and subsequent turns."),
    ] = None
    multi_agent_mode: Annotated[
        Literal["explicitRequestOnly", "proactive"] | CustomMultiAgentMode | None,
        Field(
            alias="multiAgentMode",
            description='@deprecated Ignored. Use `effort: "ultra"` for proactive multi-agent behavior.',
        ),
    ] = None
    output_schema: Annotated[
        Any | None,
        Field(
            alias="outputSchema",
            description="Optional JSON Schema used to constrain the final assistant message for this turn.",
        ),
    ] = None
    parent_turn_id: Annotated[
        str | None,
        Field(
            alias="parentTurnId",
            description="ID of the turn that caused this new turn to start.\n\nSet this when starting work on behalf of another turn, such as delegated work in a different thread. Leave unset for work started directly by the user. Ignored when this request adds input to an active turn.",
        ),
    ] = None
    permissions: Annotated[
        str | None,
        Field(
            description="Select a named permissions profile id for this turn and subsequent turns. Cannot be combined with `sandboxPolicy`."
        ),
    ] = None
    personality: Annotated[
        Literal["none", "friendly", "pragmatic"] | None,
        Field(
            description="@deprecated `friendly` and `pragmatic` no longer select a style. Changing this does not rewrite the thread's existing instructions."
        ),
    ] = None
    responsesapi_client_metadata: Annotated[
        dict[str, Any] | None,
        Field(
            alias="responsesapiClientMetadata",
            description='Optional metadata to enrich Codex\'s ResponsesAPI turn metadata.\n\nEntries are flattened into the JSON string sent as `client_metadata["x-codex-turn-metadata"]` on ResponsesAPI HTTP and websocket requests.\n\nThey are not sent as top-level ResponsesAPI `client_metadata` keys, and reserved keys such as `session_id`, `thread_id`, `turn_id`, and `window_id` cannot be overridden.',
        ),
    ] = None
    root_turn_id: Annotated[
        str | None,
        Field(
            alias="rootTurnId",
            description="ID of the first turn in the chain of work that led to this new turn.\n\nWhen setting `parentTurnId`, set this to the parent turn's `rootTurnId` when known. This keeps descendant work attributed to the original turn. If omitted, the new turn becomes its own root. Ignored when this request adds input to an active turn.",
        ),
    ] = None
    runtime_workspace_roots: Annotated[
        list[str] | None,
        Field(
            alias="runtimeWorkspaceRoots",
            description="Replace the thread's runtime workspace roots for this turn and subsequent turns. Paths must be absolute.",
        ),
    ] = None
    sandbox_policy: Annotated[
        DangerFullAccessSandboxPolicy
        | ReadOnlySandboxPolicy
        | ExternalSandboxSandboxPolicy
        | WorkspaceWriteSandboxPolicy
        | None,
        Field(
            alias="sandboxPolicy",
            description="Override the sandbox policy for this turn and subsequent turns.",
        ),
    ] = None
    service_tier: Annotated[
        str | None,
        Field(
            alias="serviceTier",
            description="Override the service tier for this turn and subsequent turns.",
        ),
    ] = None
    service_tier_for_turn: Annotated[
        str | None,
        Field(
            alias="serviceTierForTurn",
            description="Override the service tier only when this request starts a new turn. Use \"default\" for standard speed. Omitted or null inherits the thread's tier. Does not change the thread's tier or a turn being steered.",
        ),
    ] = None
    summary: Annotated[
        Literal["auto", "concise", "detailed", "none"] | None,
        Field(description="Override the reasoning summary for this turn and subsequent turns."),
    ] = None
    thread_id: Annotated[str, Field(alias="threadId")]
    tool_output: Annotated[TurnToolOutput | None, Field(alias="toolOutput")] = None
    turn_trigger: Annotated[
        str | None,
        Field(
            alias="turnTrigger",
            description="Optional source classification for the caller that starts this turn. Ignored when this request steers an already-active turn.",
        ),
    ] = None


class PermissionsRequestApprovalParams(WireModel):
    cwd: str
    environment_id: Annotated[str | None, Field(alias="environmentId")] = None
    item_id: Annotated[str, Field(alias="itemId")]
    permissions: RequestPermissionProfile
    reason: str | None = None
    started_at_ms: Annotated[
        int,
        Field(
            alias="startedAtMs",
            description="Unix timestamp (in milliseconds) when this approval request started.",
        ),
    ]
    thread_id: Annotated[str, Field(alias="threadId")]
    turn_id: Annotated[str, Field(alias="turnId")]
