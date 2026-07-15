"""Helper + catalog RPC integration tests."""

from __future__ import annotations

import pytest

from soothe_client import (
    WebSocketClient,
    check_daemon_status,
    fetch_config_section,
    fetch_skills_catalog,
    is_daemon_live,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_is_daemon_live(daemon_url: str, require_daemon: str) -> None:
    assert await is_daemon_live(daemon_url, timeout=5.0, wait_for_ready=True, ready_timeout=10.0)


@pytest.mark.asyncio
async def test_check_daemon_status_helper(client: WebSocketClient) -> None:
    status = await check_daemon_status(client, timeout=10.0)
    assert isinstance(status, dict)
    assert status.get("running") is True or status.get("readiness_state") == "ready"


@pytest.mark.asyncio
async def test_skills_list(
    client: WebSocketClient,
    bootstrapped_loop: str,
) -> None:
    # skills_list resolves workspace from the subscribed loop; without a
    # subscription the daemon may fall back to a missing process cwd.
    assert bootstrapped_loop
    resp = await client.list_skills(timeout=20.0)
    assert isinstance(resp, dict)
    skills = resp.get("skills")
    assert isinstance(skills, list)


@pytest.mark.asyncio
async def test_fetch_skills_catalog_helper(
    client: WebSocketClient,
    bootstrapped_loop: str,
) -> None:
    assert bootstrapped_loop
    skills = await fetch_skills_catalog(client, timeout=20.0)
    assert isinstance(skills, list)


@pytest.mark.asyncio
async def test_models_list(client: WebSocketClient) -> None:
    resp = await client.list_models(timeout=20.0)
    assert isinstance(resp, dict)
    models = resp.get("models")
    assert isinstance(models, list)


@pytest.mark.asyncio
async def test_mcp_status(client: WebSocketClient) -> None:
    resp = await client.get_mcp_status(timeout=20.0)
    assert isinstance(resp, dict)


@pytest.mark.asyncio
async def test_config_get_providers(client: WebSocketClient) -> None:
    section = await fetch_config_section(client, "providers", timeout=15.0)
    assert section is not None
