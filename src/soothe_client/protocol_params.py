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
    "LoopDeleteParams",
    "LoopNewParams",
    "LoopReattachParams",
    "LoopInputParams",
    "LoopMessagesParams",
    "LoopStateGetParams",
    "LoopStateUpdateParams",
    "LoopExecutionStateFetchParams",
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
    "AutopilotTopParams",
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
    """Base for all client-side param models — allows extra fields for forward compat."""

    model_config = {"extra": "allow"}


class EmptyParams(ParamsBase):
    """Params model for methods that carry no required fields."""


# ---------------------------------------------------------------------------
# Loop RPC params
# ---------------------------------------------------------------------------


class LoopGetParams(ParamsBase):
    """Params for `method=loop_get`."""

    loop_id: str = Field(..., min_length=1, description="Loop identifier")
    verbose: bool = Field(default=False, description="Include verbose details")
    tree: bool = Field(default=False, description="Include checkpoint tree")


class LoopListParams(ParamsBase):
    """Params for `method=loop_list`."""

    status: str | None = Field(default=None, description="Filter by loop status")
    limit: int | None = Field(default=None, ge=1, description="Maximum results")


class LoopDeleteParams(ParamsBase):
    """Params for `method=loop_delete`."""

    loop_id: str = Field(..., min_length=1)


class LoopNewParams(ParamsBase):
    """Params for `method=loop_new`."""

    workspace: str | None = None
    user_id: str | None = None
    client_workspace_id: str | None = None
    is_ephemeral: bool = False


class LoopReattachParams(ParamsBase):
    """Params for `method=loop_reattach`."""

    loop_id: str = Field(..., min_length=1)


class LoopDetachParams(ParamsBase):
    """Params for `method=loop_detach`."""

    loop_id: str = Field(..., min_length=1)


class LoopInputParams(ParamsBase):
    """Params for `method=loop_input`."""

    loop_id: str = Field(..., min_length=1)
    content: str | dict[str, Any] = Field(..., description="User input text or structured content")
    preferred_subagent: str | None = None
    intake_scope: str | None = None
    model: str | None = None
    model_params: dict[str, Any] | None = None
    router_profile: str | None = None
    attachments: list[dict[str, str]] | None = None
    intent_hint: str | None = None
    response_schema: dict[str, Any] | None = None
    response_schema_name: str | None = None
    response_schema_strict: bool | None = None
    clarification_mode: str | None = Field(default=None, pattern=r"^(auto|manual)$")
    interaction_mode: str | None = Field(default=None, pattern=r"^(agent|ask|plan|bypass)$")
    clarification_answer: bool = False
    clarification_answers: list[str] | None = None


class LoopMessagesParams(ParamsBase):
    """Params for `method=loop_messages`."""

    loop_id: str = Field(..., min_length=1)
    limit: int = Field(default=100, ge=1)
    offset: int = Field(default=0, ge=0)
    include_events: bool = False


class LoopStateGetParams(ParamsBase):
    """Params for `method=loop_state_get`."""

    loop_id: str = Field(..., min_length=1)
    keys: list[str] | None = None


class LoopStateUpdateParams(ParamsBase):
    """Params for `method=loop_state_update`."""

    loop_id: str = Field(..., min_length=1)
    values: dict[str, Any]
    as_node: str | None = None


class LoopExecutionStateFetchParams(ParamsBase):
    """Params for `method=loop_execution_state_fetch`."""

    loop_id: str = Field(..., min_length=1)


class LoopHistoryFetchParams(ParamsBase):
    """Params for `method=loop_history_fetch`."""

    loop_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Subscription params
# ---------------------------------------------------------------------------


class SubscribeParams(ParamsBase):
    """Params for `method=loop_events` subscription."""

    loop_id: str = Field(..., min_length=1)
    stream_delivery: Literal["batch", "adaptive", "streaming"] = "adaptive"
    wire_tier: Literal["full", "compact"] = "full"


class AutopilotSubscribeParams(ParamsBase):
    """Params for `method=autopilot_events` subscription."""

    job_id: str | None = None
    filters: dict[str, Any] | None = None


class AutopilotStatusParams(EmptyParams):
    """Params for `method=autopilot_status` — no required fields."""


class AutopilotSubmitParams(ParamsBase):
    """Params for `method=autopilot_submit`."""

    description: str = Field(..., min_length=1)
    priority: int = 50
    workspace: str | None = None


class AutopilotListGoalsParams(EmptyParams):
    """Params for `method=autopilot_list_goals` — no required fields."""


class AutopilotGetGoalParams(ParamsBase):
    """Params for `method=autopilot_get_goal`."""

    goal_id: str = Field(..., min_length=1)


class AutopilotCancelGoalParams(ParamsBase):
    """Params for `method=autopilot_cancel_goal`."""

    goal_id: str = Field(..., min_length=1)


class AutopilotCancelAllParams(EmptyParams):
    """Params for `method=autopilot_cancel_all` — no required fields."""


class AutopilotWakeParams(EmptyParams):
    """Params for `method=autopilot_wake` — no required fields."""


class AutopilotDreamParams(EmptyParams):
    """Params for `method=autopilot_dream` — no required fields."""


class AutopilotResumeParams(ParamsBase):
    """Params for `method=autopilot_resume`."""

    goal_id: str = Field(..., min_length=1)


class AutopilotListJobsParams(EmptyParams):
    """Params for `method=autopilot_list_jobs` — no required fields."""


class AutopilotGetJobParams(ParamsBase):
    """Params for `method=autopilot_get_job`."""

    job_id: str = Field(..., min_length=1)


class AutopilotTopParams(ParamsBase):
    """Params for `method=autopilot_top` (IG-679 / IG-688)."""

    include_terminal: bool = False


# ---------------------------------------------------------------------------
# Job RPC params
# ---------------------------------------------------------------------------


class JobCreateParams(ParamsBase):
    """Params for `method=job_create`."""

    goal: str = Field(..., min_length=1, description="Root goal text")
    workspace: str | None = None
    user_id: str | None = None
    guidance: str | None = None
    intent_hint: str | None = None


class JobStatusParams(ParamsBase):
    """Params for `method=job_status`."""

    job_id: str = Field(..., min_length=1)


class JobPauseParams(ParamsBase):
    """Params for `method=job_pause`."""

    job_id: str = Field(..., min_length=1)


class JobResumeParams(ParamsBase):
    """Params for `method=job_resume`."""

    job_id: str = Field(..., min_length=1)


class JobCancelParams(ParamsBase):
    """Params for `method=job_cancel`."""

    job_id: str = Field(..., min_length=1)


class JobDagParams(ParamsBase):
    """Params for `method=job_dag`."""

    job_id: str = Field(..., min_length=1)


class JobGuidanceParams(ParamsBase):
    """Params for `method=job_guidance`."""

    job_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1, description="Guidance text (canonical)")
    goal_id: str | None = None


# ---------------------------------------------------------------------------
# Cron RPC params
# ---------------------------------------------------------------------------


class CronAddParams(ParamsBase):
    """Params for `method=cron_add`."""

    text: str = Field(..., min_length=1, description="Natural language scheduling request")
    priority: int | None = Field(default=None, ge=1, le=100)


class CronListParams(ParamsBase):
    """Params for `method=cron_list`."""

    status: str | None = None


class CronShowParams(ParamsBase):
    """Params for `method=cron_show`."""

    job_id: str = Field(..., min_length=1)


class CronCancelParams(ParamsBase):
    """Params for `method=cron_cancel`."""

    job_id: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Daemon & config params
# ---------------------------------------------------------------------------


class DaemonStatusParams(EmptyParams):
    """Params for `method=daemon_status` — no required fields."""


class DaemonShutdownParams(EmptyParams):
    """Params for `method=daemon_shutdown` — no required fields."""


class ConfigGetParams(ParamsBase):
    """Params for `method=config_get`."""

    section: str | None = None


class ConfigReloadParams(EmptyParams):
    """Params for `method=config_reload` — no required fields."""


# ---------------------------------------------------------------------------
# Skills & models params
# ---------------------------------------------------------------------------


class SkillsListParams(EmptyParams):
    """Params for `method=skills_list` — no required fields."""


class ModelsListParams(EmptyParams):
    """Params for `method=models_list` — no required fields."""


class InvokeSkillParams(ParamsBase):
    """Params for `method=invoke_skill`."""

    skill: str = Field(..., min_length=1)
    args: str = ""
    clarification_mode: str | None = Field(default=None, pattern=r"^(auto|manual)$")
    interaction_mode: str | None = Field(default=None, pattern=r"^(agent|ask|plan|bypass)$")


class McpStatusParams(EmptyParams):
    """Params for `method=mcp_status` — no required fields."""


# ---------------------------------------------------------------------------
# Auth params
# ---------------------------------------------------------------------------


class AuthParams(ParamsBase):
    """Params for `method=auth`."""

    access_key: str = ""
    secret_key: str = ""


class AuthRefreshParams(ParamsBase):
    """Params for `method=auth_refresh`."""

    refresh_token: str = ""


# ---------------------------------------------------------------------------
# Command params
# ---------------------------------------------------------------------------


class SlashCommandParams(ParamsBase):
    """Params for `method=slash_command` notification."""

    cmd: str = Field(..., min_length=1)


class RpcCommandParams(ParamsBase):
    """Params for `method=rpc_command` request."""

    command: str | None = None
    payload: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Connection params
# ---------------------------------------------------------------------------


# Re-export ConnectionInitParams from wire.py so callers have one import path.
# The wire.py version carries the full handshake structure (client_version,
# client_name, accept_proto, capabilities) and is used by the actual
# connection_init envelope — see WireEnvelope/ConnectionInitEnvelope there.
from soothe_client.wire.codec import ConnectionInitParams  # noqa: E402,F401


class DisconnectParams(EmptyParams):
    """Params for `method=disconnect` notification — no required fields."""


class DeliveryAckParams(ParamsBase):
    """Params for `method=delivery_ack` notification (stream termination drain)."""

    loop_id: str = Field(..., min_length=1)
    seq: int = Field(..., ge=0)
