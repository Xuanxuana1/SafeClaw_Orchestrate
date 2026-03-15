from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import tempfile
from typing import Any, List, Optional

# Ensure evaluation/ is on sys.path so run_eval can be imported
# regardless of the working directory the script is invoked from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ontoplan_mvp.engine import OntoPlanEngine
from ontoplan_mvp.executor.node_executor import NodeExecutor
from ontoplan_mvp.executor.workflow_executor import WorkflowExecutor
from ontoplan_mvp.llm_client import LLMConfig as OntoPlanLLMConfig
from ontoplan_mvp.seed_patterns import build_full_ontology
from run_eval import (
    BrowserOutputObservation,
    CmdOutputObservation,
    CmdRunAction,
    LLMConfig,
    OpenHandsConfig,
    Runtime,
    call_async_from_sync,
    create_runtime,
    get_config,
    get_llm_config_arg,
    get_parser,
    init_task_env,
    load_dependencies,
    logger,
    pre_login,
    run_evaluator,
    run_solver,
)


def _run_single_agent_fallback(
    runtime: Runtime,
    task_name: str,
    config: OpenHandsConfig,
    dependencies: List[str],
    output_dir: str,
    save_screenshots: bool,
    screenshots_dir: str,
):
    """Reuse the original single-agent runner as a fallback path."""
    return run_solver(
        runtime,
        task_name,
        config,
        dependencies,
        save_final_state=True,
        state_dir=output_dir,
        save_screenshots=save_screenshots,
        screenshots_dir=screenshots_dir,
    )


def _secret_to_str(secret: object) -> Optional[str]:
    """Return a plain string from OpenHands secret-like objects."""
    if secret is None:
        return None
    getter = getattr(secret, "get_secret_value", None)
    if callable(getter):
        return getter()
    return str(secret)


def _to_ontoplan_llm_config(config: OpenHandsConfig) -> OntoPlanLLMConfig:
    """Map the OpenHands LLM config to the OntoPlan local LLM config shape."""
    llm_config = None

    getter = getattr(config, "get_llm_config", None)
    if callable(getter):
        try:
            llm_config = getter()
        except Exception:
            llm_config = None

    if llm_config is None:
        llm_config = getattr(config, "llm", None) or getattr(config, "llm_config", None)

    if llm_config is None:
        return OntoPlanLLMConfig()

    return OntoPlanLLMConfig(
        model=getattr(llm_config, "model", "") or "",
        api_key=_secret_to_str(getattr(llm_config, "api_key", None)),
        base_url=getattr(llm_config, "base_url", None),
    )


def _read_task_query(runtime: Runtime) -> str:
    """Read the full task instruction from the task container."""
    action = CmdRunAction(command="cat /instruction/task.md")
    logger.info(action, extra={"msg_type": "ACTION"})
    obs: CmdOutputObservation = runtime.run_action(action)
    logger.info(obs, extra={"msg_type": "OBSERVATION"})
    assert obs.exit_code == 0
    return obs.content


def _save_workflow_screenshots(task_name: str, screenshots_dir: str, result: Any) -> None:
    """Persist screenshots from all executed node histories."""
    target_dir = os.path.join(screenshots_dir, task_name)
    os.makedirs(target_dir, exist_ok=True)

    image_id = 0
    for node_index, node_result in enumerate(result.node_results):
        history = getattr(node_result.state, "history", []) or []
        for obs in history:
            if isinstance(obs, BrowserOutputObservation):
                image_data = base64.b64decode(
                    obs.screenshot.replace("data:image/png;base64,", "")
                )
                file_name = f"{node_index}_{image_id}.png"
                with open(os.path.join(target_dir, file_name), "wb") as file:
                    file.write(image_data)
                image_id += 1


def _save_final_state(task_name: str, output_dir: str, state: Any) -> None:
    """Persist the final state for parity with the original runner."""
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, f"state_{task_name}.json"), "w") as file:
        json.dump(str(state), file, indent=4)


def run_orchestrated_solver(
    runtime: Runtime,
    task_name: str,
    task_query: str,
    config: OpenHandsConfig,
    dependencies: List[str],
    output_dir: str,
    save_screenshots: bool,
    screenshots_dir: str,
    fallback_to_single_agent: bool = True,
) -> Any:
    """Run OntoPlan planning plus DAG execution, with single-agent fallback."""
    try:
        engine = OntoPlanEngine(
            build_full_ontology(),
            use_llm=True,
            llm_config=_to_ontoplan_llm_config(config),
        )
        plan = engine.plan(task_query)
    except Exception as exc:
        logger.warning("OntoPlan planning failed (%s)", exc)
        if fallback_to_single_agent:
            return _run_single_agent_fallback(
                runtime=runtime,
                task_name=task_name,
                config=config,
                dependencies=dependencies,
                output_dir=output_dir,
                save_screenshots=save_screenshots,
                screenshots_dir=screenshots_dir,
            )
        raise

    executable_nodes = plan.workflow.non_system_nodes()
    if plan.validation_errors:
        logger.warning("OntoPlan validation failed: %s", plan.validation_errors)
        if fallback_to_single_agent:
            return _run_single_agent_fallback(
                runtime=runtime,
                task_name=task_name,
                config=config,
                dependencies=dependencies,
                output_dir=output_dir,
                save_screenshots=save_screenshots,
                screenshots_dir=screenshots_dir,
            )
    if len(executable_nodes) <= 1:
        logger.warning("OntoPlan produced %s executable node(s), falling back", len(executable_nodes))
        if fallback_to_single_agent:
            return _run_single_agent_fallback(
                runtime=runtime,
                task_name=task_name,
                config=config,
                dependencies=dependencies,
                output_dir=output_dir,
                save_screenshots=save_screenshots,
                screenshots_dir=screenshots_dir,
            )

    executor = WorkflowExecutor(NodeExecutor(max_iterations=50, budget_per_node=1.0))
    try:
        result = executor.execute(
            plan=plan,
            original_query=task_query,
            runtime=runtime,
            config=config,
            task_name=task_name,
            output_dir=output_dir,
        )
    except Exception as exc:
        logger.warning("Workflow execution failed (%s)", exc)
        if fallback_to_single_agent:
            return _run_single_agent_fallback(
                runtime=runtime,
                task_name=task_name,
                config=config,
                dependencies=dependencies,
                output_dir=output_dir,
                save_screenshots=save_screenshots,
                screenshots_dir=screenshots_dir,
            )
        raise

    if not result.node_results:
        logger.warning("Workflow execution produced no node results")
        if fallback_to_single_agent:
            return _run_single_agent_fallback(
                runtime=runtime,
                task_name=task_name,
                config=config,
                dependencies=dependencies,
                output_dir=output_dir,
                save_screenshots=save_screenshots,
                screenshots_dir=screenshots_dir,
            )
        raise RuntimeError("workflow execution produced no node results")

    final_state = result.node_results[-1].state

    if save_screenshots:
        _save_workflow_screenshots(task_name, screenshots_dir, result)
    _save_final_state(task_name, output_dir, final_state)

    return final_state


if __name__ == "__main__":
    parser = get_parser()
    parser.add_argument(
        "--task-image-name",
        type=str,
        default="ghcr.io/theagentcompany/example-image:1.0.0",
        help="Task image name",
    )
    parser.add_argument(
        "--outputs-path",
        type=str,
        default="./outputs",
        help="Folder path to save trajectories and evaluation results",
    )
    parser.add_argument(
        "--server-hostname",
        type=str,
        default="localhost",
        help="Server hostname, e.g. localhost to access the host machine from the container, "
        "assuming the task docker container is run with `--network host` flag",
    )
    parser.add_argument(
        "--agent-llm-config",
        type=str,
        default=None,
        help="LLM config for agent",
    )
    parser.add_argument(
        "--env-llm-config",
        type=str,
        default=None,
        help="LLM config for evaluation environment (NPC & llm-based evaluator)",
    )
    parser.add_argument(
        "--build-image-only",
        type=bool,
        default=False,
        help="Just build an OpenHands runtime image for the given task and then exit",
    )
    args, _ = parser.parse_known_args()

    if not args.task_image_name or not args.task_image_name.strip():
        raise ValueError("Task image name is invalid")
    task_short_name = args.task_image_name.split("/")[-1].split(":")[0]
    logger.info("Task image name is %s, short name is %s", args.task_image_name, task_short_name)

    if os.getenv("TMPDIR") and os.path.exists(os.getenv("TMPDIR")):
        temp_dir = os.path.abspath(os.getenv("TMPDIR"))
    else:
        temp_dir = tempfile.mkdtemp()

    if args.build_image_only:
        logger.info("build-image-only mode, will build a runtime image and then exit")
        config: OpenHandsConfig = get_config(args.task_image_name, task_short_name, temp_dir, LLMConfig())
        runtime: Runtime = create_runtime(config)
        call_async_from_sync(runtime.connect)
        logger.info(
            "Finished building runtime image %s from base task image %s",
            runtime.runtime_container_image,
            runtime.base_container_image,
        )
        sys.exit()

    agent_llm_config = get_llm_config_arg(args.agent_llm_config) if args.agent_llm_config else None
    if agent_llm_config is None:
        raise ValueError(
            f"Could not find LLM config for agent: --agent-llm-config {args.agent_llm_config}"
        )
    if agent_llm_config.api_key is None:
        raise ValueError("LLM API key is not set for agent")

    env_llm_config = get_llm_config_arg(args.env_llm_config) if args.env_llm_config else None
    if env_llm_config is None:
        raise ValueError(
            "Could not find LLM config for evaluation environment: "
            f"--env-llm-config {args.env_llm_config}"
        )
    if env_llm_config.api_key is None:
        raise ValueError("LLM API key is not set for evaluation environment")

    config = get_config(args.task_image_name, task_short_name, temp_dir, agent_llm_config)
    runtime = create_runtime(config)
    call_async_from_sync(runtime.connect)

    init_task_env(runtime, args.server_hostname, env_llm_config)

    dependencies = load_dependencies(runtime)
    logger.info("Service dependencies: %s", dependencies)

    screenshots_dir = os.path.join(os.path.abspath(args.outputs_path), "screenshots")
    try:
        pre_login(runtime, dependencies, save_screenshots=True, screenshots_dir=screenshots_dir)
    except Exception as exc:
        logger.error("Failed to pre-login: %s", exc)
        init_task_env(runtime, args.server_hostname, env_llm_config)
        pre_login(runtime, dependencies, save_screenshots=True, screenshots_dir=screenshots_dir)

    task_query = _read_task_query(runtime)
    run_orchestrated_solver(
        runtime=runtime,
        task_name=task_short_name,
        task_query=task_query,
        config=config,
        dependencies=dependencies,
        output_dir=temp_dir,
        save_screenshots=True,
        screenshots_dir=screenshots_dir,
    )

    trajectory_path = f"/outputs/traj_{task_short_name}.json"
    result_path = f"/outputs/eval_{task_short_name}.json"

    run_evaluator(runtime, env_llm_config, trajectory_path, result_path)

    shutil.move(
        os.path.join(temp_dir, f"traj_{task_short_name}.json"),
        os.path.join(os.path.abspath(args.outputs_path), f"traj_{task_short_name}.json"),
    )
    shutil.move(
        os.path.join(temp_dir, f"eval_{task_short_name}.json"),
        os.path.join(os.path.abspath(args.outputs_path), f"eval_{task_short_name}.json"),
    )
