"""Client-side params models for daemon RPCs.

Validate request payloads before send to catch empty ids and bad shapes early.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    # Loop RPC params
    "LoopGetParams",
    "LoopListParams",
    "LoopTreeParams",
    "LoopPruneParams",
    "LoopDeleteParams",
    "LoopNewParams",
    "LoopReattachParams",
    "LoopInputParams",
    "LoopMessagesParams",
    "LoopStateGetParams",
    "LoopStateUpdateParams",
    "LoopCardsFetchParams",
    "LoopDetachParams",
    # Subscription params
    "SubscribeParams",
    "AutopilotSubscribeParams",
    "AutopilotStatusParams",
    "AutopilotSubmitParams",
    "AutopilotListGoalsParams",
    "AutopilotGetGoalParams",
    "AutopilotCancelGoalParams",
    "AutopilotCancelAllParams",
    "AutopilotWakeParams",
    "AutopilotDreamParams",
    "AutopilotResumeParams",
    "AutopilotListJobsParams",
    "AutopilotGetJobParams",
    # Job RPC params
    "JobCreateParams",
    "JobStatusParams",
    "JobPauseParams",
    "JobResumeParams",
    "JobCancelParams",
    "JobDagParams",
    "JobGuidanceParams",
    # Cron RPC params
    "CronAddParams",
    "CronListParams",
    "CronShowParams",
    "CronCancelParams",
    # Daemon & config params
    "DaemonStatusParams",
    "DaemonShutdownParams",
    "ConfigGetParams",
    "ConfigReloadParams",
    # Skills & models params
    "SkillsListParams",
    "ModelsListParams",
    "InvokeSkillParams",
    "McpStatusParams",
    # Auth params
    "AuthParams",
    "AuthRefreshParams",
    # Command params
    "SlashCommandParams",
    "RpcCommandParams",
    # Connection params
    "ConnectionInitParams",  # re-exported from wire.py
    "DisconnectParams",
]


class ParamsBase(BaseModel):
    """Base for all client-side param models — allows extra fields for forward compat.

    The protocol envelope carries ``proto``, ``type``, ``method``, and ``id``
    alongside the operation-specific fields. All models validate against the
    ``params`` dict so extra keys must be tolerated.
    """

    model_config = {"extra": "allow"}


class EmptyParams(ParamsBase):
    """Params model for methods that carry no required fields."""


# ---------------------------------------------------------------------------
# Loop RPC params
# ---------------------------------------------------------------------------


class LoopGetParams(ParamsBase):
    """Params for ``method=loop_get``.

    Attributes:
        loop_id: Loop identifier (required, non-empty).
        verbose: Include verbose details.
        tree: Include checkpoint tree.
    """

    loop_id: str = Field(..., min_length=1, description="Loop identifier")
    verbose: bool = Field(default=False, description="Include verbose details")
    tree: bool = Field(default=False, description="Include checkpoint tree")


class LoopListParams(ParamsBase):
    """Params for ``method=loop_list``.

    Attributes:
        status: Optional status filter.
        limit: Maximum number of results.
    """

    status: str | None = Field(default=None, description="Filter by loop status")
    limit: int | None = Field(default=None, ge=1, description="Maximum results")


class LoopTreeParams(ParamsBase):
    """Params for ``method=loop_tree``.

    Attributes:
        loop_id: Loop identifier (required).
    """

    loop_id: str = Field(..., min_length=1, description="Loop identifier")


class LoopPruneParams(ParamsBase):
    """Params for ``method=loop_prune``.

    Attributes:
        loop_id: Loop identifier (required).
        keep_latest: Number of recent branches to keep (default 1).
    """

    loop_id: str = Field(..., min_length=1)
    keep_latest: int = Field(default=1, ge=1)


class LoopDeleteParams(ParamsBase):
    """Params for ``method=loop_delete``.

    Attributes:
        loop_id: Loop identifier (required).
    """

    loop_id: str = Field(..., min_length=1)


class LoopNewParams(ParamsBase):
    """Params for ``method=loop_new``.

    Attributes:
        workspace: Optional client workspace path.
        user_id: Optional user identifier.
        client_workspace_id: Optional stable workspace scope.
        is_ephemeral: Create ephemeral loop.
    """

    workspace: str | None = None
    user_id: str | None = None
    client_workspace_id: str | None = None
    is_ephemeral: bool = False


class LoopReattachParams(ParamsBase):
    """Params for ``method=loop_reattach``.

    Attributes:
        loop_id: Loop to reattach (required).
    """

    loop_id: str = Field(..., min_length=1)


class LoopDetachParams(ParamsBase):
    """Params for ``method=loop_detach``.

    Attributes:
        loop_id: Loop to detach from (required).
    """

    loop_id: str = Field(..., min_length=1)


class LoopInputParams(ParamsBase):
    """Params for ``method=loop_input``.

    Attributes:
        loop_id: Loop identifier (required).
        content: User input text or structured content (required).
        autonomous: Enable autonomous mode.
        max_iterations: Max iterations for autonomous mode.
        preferred_subagent: Routing hint.
        model: Provider:model override.
        model_params: Additional model parameters.
        router_profile: Named ``router_profiles`` overlay for chat roles this turn.
        attachments: Image attachments.
        intent_hint: Daemon direct-model hint (text_completion, image_to_text, ocr, embed).
        response_schema: Structured output schema.
        response_schema_name: Schema name for logging.
        response_schema_strict: Enable strict schema validation.
        clarification_mode: clarification relay mode.
        clarification_answer: Mark as answer to pending clarification.
        clarification_answers: Per-question answers for multi-question clarification.
    """

    loop_id: str = Field(..., min_length=1)
    content: str | dict[str, Any] = Field(..., description="User input text or structured content")
    autonomous: bool = False
    max_iterations: int | None = Field(default=None, gt=0)
    preferred_subagent: str | None = None
    model: str | None = None
    model_params: dict[str, Any] | None = None
    router_profile: str | None = None
    attachments: list[dict[str, str]] | None = None
    intent_hint: str | None = None
    response_schema: dict[str, Any] | None = None
    response_schema_name: str | None = None
    response_schema_strict: bool | None = None
    clarification_mode: str | None = Field(default=None, pattern=r"^(auto|manual)$")
    clarification_answer: bool = False
    clarification_answers: list[str] | None = None


class LoopMessagesParams(ParamsBase):
    """Params for ``method=loop_messages``.

    Attributes:
        loop_id: Loop identifier (required).
        limit: Maximum messages (default 100).
        offset: Pagination offset.
        include_events: Include tool events.
    """

    loop_id: str = Field(..., min_length=1)
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)
    include_events: bool = False


class LoopStateGetParams(ParamsBase):
    """Params for ``method=loop_state_get``.

    Attributes:
        loop_id: Loop identifier (required).
        keys: Specific channel keys to fetch.
    """

    loop_id: str = Field(..., min_length=1)
    keys: list[str] | None = None


class LoopStateUpdateParams(ParamsBase):
    """Params for ``method=loop_state_update``.

    Attributes:
        loop_id: Loop identifier (required).
        values: Channel values to apply (required).
        as_node: Node to apply update as.
    """

    loop_id: str = Field(..., min_length=1)
    values: dict[str, Any]
    as_node: str | None = None


class LoopCardsFetchParams(ParamsBase):
    """Params for ``method=loop_cards_fetch``.

    Attributes:
        loop_id: Loop identifier (required).
        since: Fetch cards after this sequence.
    """

    loop_id: str = Field(..., min_length=1)
    since: str | None = None


class LoopHistoryFetchParams(ParamsBase):
    """Params for ``method=loop_history_fetch``.

    Attributes:
        loop_id: Loop identifier (required).
    """

    loop_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Subscription params
# ---------------------------------------------------------------------------


class SubscribeParams(ParamsBase):
    """Params for ``method=loop_events`` subscription.

    Attributes:
        loop_id: Loop to subscribe to (required).
        stream_delivery: Delivery mode (batch/adaptive/streaming).
        wire_tier: Wire filter tier (full/compact).
    """

    loop_id: str = Field(..., min_length=1)
    stream_delivery: Literal["batch", "adaptive", "streaming"] = "adaptive"
    wire_tier: Literal["full", "compact"] = "full"


class AutopilotSubscribeParams(ParamsBase):
    """Params for ``method=autopilot_events`` subscription.

    Attributes:
        job_id: Optional job filter.
        filters: Event filter criteria.
    """

    job_id: str | None = None
    filters: dict[str, Any] | None = None


class AutopilotStatusParams(EmptyParams):
    """Params for ``method=autopilot_status`` — no required fields."""


class AutopilotSubmitParams(ParamsBase):
    """Params for ``method=autopilot_submit``.

    Attributes:
        description: Task description (required).
        priority: Task priority (default 50).
        workspace: Optional workspace path.
    """

    description: str = Field(..., min_length=1)
    priority: int = 50
    workspace: str | None = None


class AutopilotListGoalsParams(EmptyParams):
    """Params for ``method=autopilot_list_goals`` — no required fields."""


class AutopilotGetGoalParams(ParamsBase):
    """Params for ``method=autopilot_get_goal``.

    Attributes:
        goal_id: Goal identifier (required).
    """

    goal_id: str = Field(..., min_length=1)


class AutopilotCancelGoalParams(ParamsBase):
    """Params for ``method=autopilot_cancel_goal``.

    Attributes:
        goal_id: Goal to cancel (required).
    """

    goal_id: str = Field(..., min_length=1)


class AutopilotCancelAllParams(EmptyParams):
    """Params for ``method=autopilot_cancel_all`` — no required fields."""


class AutopilotWakeParams(EmptyParams):
    """Params for ``method=autopilot_wake`` — no required fields."""


class AutopilotDreamParams(EmptyParams):
    """Params for ``method=autopilot_dream`` — no required fields."""


class AutopilotResumeParams(ParamsBase):
    """Params for ``method=autopilot_resume``.

    Attributes:
        goal_id: Goal to resume (required).
    """

    goal_id: str = Field(..., min_length=1)


class AutopilotListJobsParams(EmptyParams):
    """Params for ``method=autopilot_list_jobs`` — no required fields."""


class AutopilotGetJobParams(ParamsBase):
    """Params for ``method=autopilot_get_job``.

    Attributes:
        job_id: Root goal (job) identifier (required).
    """

    job_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Job RPC params
# ---------------------------------------------------------------------------


class JobCreateParams(ParamsBase):
    """Params for ``method=job_create``.

    Attributes:
        goal: Root goal description (required).
        workspace: Optional workspace path.
        user_id: Optional user identifier.
        autonomous: Enable autonomous mode.
        max_iterations: Max iterations.
        guidance: Initial guidance.
        intent_hint: Daemon direct-model hint (text_completion, image_to_text, ocr, embed).
    """

    goal: str = Field(..., min_length=1, description="Root goal text")
    workspace: str | None = None
    user_id: str | None = None
    autonomous: bool = False
    max_iterations: int | None = Field(default=None, gt=0)
    guidance: str | None = None
    intent_hint: str | None = None


class JobStatusParams(ParamsBase):
    """Params for ``method=job_status``.

    Attributes:
        job_id: Job identifier (required).
    """

    job_id: str = Field(..., min_length=1)


class JobPauseParams(ParamsBase):
    """Params for ``method=job_pause``.

    Attributes:
        job_id: Job to pause (required).
    """

    job_id: str = Field(..., min_length=1)


class JobResumeParams(ParamsBase):
    """Params for ``method=job_resume``.

    Attributes:
        job_id: Job to resume (required).
    """

    job_id: str = Field(..., min_length=1)


class JobCancelParams(ParamsBase):
    """Params for ``method=job_cancel``.

    Attributes:
        job_id: Job to cancel (required).
    """

    job_id: str = Field(..., min_length=1)


class JobDagParams(ParamsBase):
    """Params for ``method=job_dag``.

    Attributes:
        job_id: Job identifier (required).
    """

    job_id: str = Field(..., min_length=1)


class JobGuidanceParams(ParamsBase):
    """Params for ``method=job_guidance``.

    Attributes:
        job_id: Target job (required).
        content: Guidance text (canonical, required).
        goal_id: Optional specific goal target.
    """

    job_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1, description="Guidance text (canonical)")
    goal_id: str | None = None


# ---------------------------------------------------------------------------
# Cron RPC params
# ---------------------------------------------------------------------------


class CronAddParams(ParamsBase):
    """Params for ``method=cron_add``.

    Attributes:
        text: Natural language scheduling request (required).
        priority: Optional job priority (1-100).
    """

    text: str = Field(..., min_length=1, description="Natural language scheduling request")
    priority: int | None = Field(default=None, ge=1, le=100)


class CronListParams(ParamsBase):
    """Params for ``method=cron_list``.

    Attributes:
        status: Optional status filter.
    """

    status: str | None = None


class CronShowParams(ParamsBase):
    """Params for ``method=cron_show``.

    Attributes:
        job_id: Cron job identifier (required).
    """

    job_id: str = Field(..., min_length=1)


class CronCancelParams(ParamsBase):
    """Params for ``method=cron_cancel``.

    Attributes:
        job_id: Cron job to cancel (required).
    """

    job_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Daemon & config params
# ---------------------------------------------------------------------------


class DaemonStatusParams(EmptyParams):
    """Params for ``method=daemon_status`` — no required fields."""


class DaemonShutdownParams(EmptyParams):
    """Params for ``method=daemon_shutdown`` — no required fields."""


class ConfigGetParams(ParamsBase):
    """Params for ``method=config_get``.

    Attributes:
        section: Config section to fetch.
    """

    section: str | None = None


class ConfigReloadParams(EmptyParams):
    """Params for ``method=config_reload`` — no required fields."""


# ---------------------------------------------------------------------------
# Skills & models params
# ---------------------------------------------------------------------------


class SkillsListParams(EmptyParams):
    """Params for ``method=skills_list`` — no required fields."""


class ModelsListParams(EmptyParams):
    """Params for ``method=models_list`` — no required fields."""


class InvokeSkillParams(ParamsBase):
    """Params for ``method=invoke_skill``.

    Attributes:
        skill: Skill name (required).
        args: Skill arguments.
        clarification_mode: clarification relay mode.
    """

    skill: str = Field(..., min_length=1)
    args: str = ""
    clarification_mode: str | None = Field(default=None, pattern=r"^(auto|manual)$")


class McpStatusParams(EmptyParams):
    """Params for ``method=mcp_status`` — no required fields."""


# ---------------------------------------------------------------------------
# Auth params
# ---------------------------------------------------------------------------


class AuthParams(ParamsBase):
    """Params for ``method=auth``.

    Attributes:
        access_key: Access key credential.
        secret_key: Secret key credential.
    """

    access_key: str = ""
    secret_key: str = ""


class AuthRefreshParams(ParamsBase):
    """Params for ``method=auth_refresh``.

    Attributes:
        refresh_token: Token to refresh.
    """

    refresh_token: str = ""


# ---------------------------------------------------------------------------
# Command params
# ---------------------------------------------------------------------------


class SlashCommandParams(ParamsBase):
    """Params for ``method=slash_command`` notification.

    Attributes:
        cmd: Slash command string (e.g. ``/exit``, ``/cancel``).
    """

    cmd: str = Field(..., min_length=1)


class RpcCommandParams(ParamsBase):
    """Params for ``method=rpc_command`` request.

    Attributes:
        command: RPC command name.
        payload: Command payload.
    """

    command: str | None = None
    payload: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Connection params
# ---------------------------------------------------------------------------


# Re-export ConnectionInitParams from wire.py so callers have one import path.
# The wire.py version carries the full handshake structure (client_version,
# client_name, accept_proto, capabilities) and is used by the actual
# connection_init envelope — see WireEnvelope/ConnectionInitEnvelope there.
from soothe_sdk.wire.codec import ConnectionInitParams  # noqa: E402,F401


class DisconnectParams(EmptyParams):
    """Params for ``method=disconnect`` notification — no required fields."""


class DeliveryAckParams(ParamsBase):
    """Params for ``method=delivery_ack`` notification (stream termination drain)."""

    loop_id: str = Field(..., min_length=1)
    seq: int = Field(..., ge=0)
