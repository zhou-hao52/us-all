import argparse
import asyncio
import json
import os
import re
import ssl
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


PROMPT_FILES = {
    "us": "US_prompt.md",
    "scenario": "Scenarios_prompt.md",
    "acceptance": "Acceptance Criteria_prompt.md",
    "relationship": "relationship_prompt.md",
}

PROMPT_ORDER = ["us", "scenario", "acceptance", "relationship"]
DEFAULT_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen3.5-plus-2026-02-15"
DEFAULT_API_KEYS: list[str] = ["sk-ac7b4452847b45cc8cb12fd97deab63f"]
REQUIREMENTS_FILE = "requirements.json"


@dataclass
class RunnerConfig:
    model: str
    api_base: str
    timeout_sec: int
    max_retries: int
    max_concurrent: int
    request_interval_seconds: float
    rate_limit_retry_delay: float
    server_retry_delay: float
    network_retry_delay: float
    force: bool


class ApiKeyPool:
    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        self.invalid_keys = set()
        self.index = 0
        self.lock = threading.Lock()

    def next_key(self) -> str:
        with self.lock:
            # 跳过无效的密钥
            for _ in range(len(self.keys)):
                key = self.keys[self.index]
                self.index = (self.index + 1) % len(self.keys)
                if key not in self.invalid_keys:
                    return key
            # 如果所有密钥都无效，返回第一个密钥（会失败，但至少不会无限循环）
            return self.keys[0]

    def mark_invalid(self, key: str) -> None:
        with self.lock:
            self.invalid_keys.add(key)


class AsyncRateLimiter:
    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = max(interval_seconds, 0.0)
        self.last_request_time = 0.0
        self.lock = asyncio.Lock()

    async def wait(self) -> None:
        if self.interval_seconds <= 0:
            return
        async with self.lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_request_time
            if elapsed < self.interval_seconds:
                await asyncio.sleep(self.interval_seconds - elapsed)
            self.last_request_time = asyncio.get_event_loop().time()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def to_json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=4)


def safe_name(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]", "_", name).strip()


def extract_json_text(text: str) -> str:
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return text.strip()


def load_requirements(requirements_path: Path) -> list[dict[str, Any]]:
    requirements_json = read_json(requirements_path)
    items = requirements_json.get("iotUserStoryRequirements", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def get_api_keys() -> list[str]:
    code_keys = [k.strip() for k in DEFAULT_API_KEYS if k.strip()]
    if code_keys:
        return code_keys
    env_keys = os.getenv("LLM_API_KEYS", "").strip()
    if env_keys:
        keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        if keys:
            return keys
    single_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if single_key:
        return [single_key]
    return []


def call_chat_completion_once(
    api_key: str,
    model: str,
    prompt: str,
    api_base: str,
    timeout_sec: int,
) -> str:
    url = api_base
    if "/chat/completions" not in url:
        url = f"{url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = request.Request(url=url, data=data, headers=headers, method="POST")
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    no_proxy_handler = request.ProxyHandler({})
    https_handler = request.HTTPSHandler(context=ssl_context)
    opener = request.build_opener(no_proxy_handler, https_handler)
    
    with opener.open(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8")
        parsed = json.loads(raw)
        return parsed["choices"][0]["message"]["content"]


def classify_error(exc: Exception) -> str:
    if isinstance(exc, error.HTTPError):
        if exc.code == 429:
            return "rate"
        if 500 <= exc.code < 600:
            return "server"
        return "fatal"
    if isinstance(exc, (error.URLError, TimeoutError)):
        return "network"
    if isinstance(exc, (KeyError, json.JSONDecodeError)):
        return "parse"
    return "fatal"


def delay_for_error(kind: str, attempt: int, config: RunnerConfig) -> float:
    if kind == "rate":
        return config.rate_limit_retry_delay * (attempt + 1)
    if kind == "server":
        return config.server_retry_delay * (attempt + 1)
    if kind == "network":
        return min(config.network_retry_delay * (attempt + 1), 30.0)
    if kind == "parse":
        return min(1.0 + attempt, 5.0)
    return 0.0


async def call_chat_completion_with_retry(
    prompt: str,
    config: RunnerConfig,
    key_pool: ApiKeyPool,
    rate_limiter: AsyncRateLimiter,
) -> str:
    last_error: Exception | None = None
    for attempt in range(config.max_retries + 1):
        await rate_limiter.wait()
        api_key = key_pool.next_key()
        try:
            return await asyncio.to_thread(
                call_chat_completion_once,
                api_key,
                config.model,
                prompt,
                config.api_base,
                config.timeout_sec,
            )
        except Exception as exc:
            last_error = exc
            kind = classify_error(exc)
            # 标记 401 错误的密钥为无效
            if isinstance(exc, error.HTTPError) and exc.code == 401:
                key_pool.mark_invalid(api_key)
            if kind == "fatal" or attempt == config.max_retries:
                break
            await asyncio.sleep(delay_for_error(kind, attempt, config))
    raise RuntimeError(f"LLM 调用失败: {last_error}") from last_error


def build_request_input(requirement_item: dict[str, Any]) -> dict[str, Any]:
    initial_demand = str(requirement_item.get("initialDemand", "")).strip()
    detailed_demand = str(requirement_item.get("detailedDemand", "")).strip()
    return {
        "initialDemand": initial_demand,
        "detailedDemand": detailed_demand or initial_demand,
    }


def render_prompt(
    template: str,
    request_input: dict[str, Any],
    user_story_json: dict[str, Any],
    ground_truth: dict[str, Any] | None,
) -> str:
    rendered = template
    rendered = rendered.replace("{request_input}", to_json_text(request_input))
    rendered = rendered.replace("{user_story_json}", to_json_text(user_story_json))
    rendered = rendered.replace("{ground_truth}", to_json_text(ground_truth or {}))
    return rendered


def project_output_done(output_dir: Path, project_name: str) -> bool:
    safe_project = safe_name(project_name)
    project_dir = output_dir / safe_project
    txt_file = output_dir / f"{safe_project}.txt"
    if not txt_file.exists():
        return False
    return all((project_dir / f"{key}.json").exists() for key in PROMPT_ORDER)


def write_result_files(output_dir: Path, project_name: str, outputs: dict[str, str]) -> None:
    project_dir = output_dir / safe_name(project_name)
    project_dir.mkdir(parents=True, exist_ok=True)
    for key, content in outputs.items():
        write_text(project_dir / f"{key}.json", content)
    txt_path = output_dir / f"{safe_name(project_name)}.txt"
    blocks = [f"[{key}]\n{outputs[key]}" for key in PROMPT_ORDER]
    write_text(txt_path, "\n\n".join(blocks))


@dataclass
class FileRunResult:
    file_name: str
    status: str
    error: str = ""


@dataclass
class RequirementTask:
    project_name: str
    data_file: Path
    ground_truth_file: Path
    request_input: dict[str, Any]


def build_requirement_tasks(
    requirements: list[dict[str, Any]],
    data_dir: Path,
    ground_truth_dir: Path,
) -> list[RequirementTask]:
    tasks: list[RequirementTask] = []
    for item in requirements:
        request_input = build_request_input(item)
        project_name = request_input.get("initialDemand", "").strip()
        if not project_name:
            continue
        file_name = f"{project_name}.json"
        tasks.append(
            RequirementTask(
                project_name=project_name,
                data_file=data_dir / file_name,
                ground_truth_file=ground_truth_dir / file_name,
                request_input=request_input,
            )
        )
    return tasks


async def evaluate_one_file(
    task: RequirementTask,
    prompts: dict[str, str],
    output_dir: Path,
    raw_dir: Path,
    config: RunnerConfig,
    key_pool: ApiKeyPool,
    rate_limiter: AsyncRateLimiter,
) -> FileRunResult:
    project_name = task.project_name
    if not config.force and project_output_done(output_dir, project_name):
        return FileRunResult(file_name=task.data_file.name, status="skipped")
    try:
        if not task.data_file.exists():
            print(f"[SKIPPED] 未找到 data 同名文件: {task.data_file}")
            return FileRunResult(file_name=task.data_file.name, status="skipped")
        if not task.ground_truth_file.exists():
            print(f"[SKIPPED] 未找到 ground_truth 同名文件: {task.ground_truth_file}")
            return FileRunResult(file_name=task.data_file.name, status="skipped")
        data_json = read_json(task.data_file)
        gt_json = read_json(task.ground_truth_file)
        request_input = task.request_input
        outputs: dict[str, str] = {}
        project_raw_dir = raw_dir / safe_name(project_name)
        for key in PROMPT_ORDER:
            prompt = render_prompt(prompts[key], request_input, data_json, gt_json)
            write_text(project_raw_dir / f"{key}_request.txt", prompt)
            response_text = await call_chat_completion_with_retry(
                prompt=prompt,
                config=config,
                key_pool=key_pool,
                rate_limiter=rate_limiter,
            )
            write_text(project_raw_dir / f"{key}_response.txt", response_text)
            outputs[key] = extract_json_text(response_text)
        write_result_files(output_dir=output_dir, project_name=project_name, outputs=outputs)
        return FileRunResult(file_name=task.data_file.name, status="success")
    except Exception as exc:
        error_text = str(exc)
        write_text(raw_dir / safe_name(project_name) / "error.txt", error_text)
        return FileRunResult(file_name=task.data_file.name if task.data_file.name else f"{project_name}.json", status="failed", error=error_text)


async def run_all_files(
    tasks: list[RequirementTask],
    prompts: dict[str, str],
    output_dir: Path,
    raw_dir: Path,
    config: RunnerConfig,
    key_pool: ApiKeyPool,
) -> list[FileRunResult]:
    semaphore = asyncio.Semaphore(max(config.max_concurrent, 1))
    rate_limiter = AsyncRateLimiter(config.request_interval_seconds)

    async def bounded_eval(task: RequirementTask) -> FileRunResult:
        async with semaphore:
            return await evaluate_one_file(
                task=task,
                prompts=prompts,
                output_dir=output_dir,
                raw_dir=raw_dir,
                config=config,
                key_pool=key_pool,
                rate_limiter=rate_limiter,
            )

    task_futures = [bounded_eval(task) for task in tasks]
    return await asyncio.gather(*task_futures)


def run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 个文件，0 表示全部")
    parser.add_argument("--max-concurrent", type=int, default=int(os.getenv("LLM_MAX_CONCURRENT", "10")))
    parser.add_argument("--request-interval-seconds", type=float, default=float(os.getenv("LLM_REQUEST_INTERVAL_SECONDS", "1.2")))
    parser.add_argument("--rate-limit-retry-delay", type=float, default=float(os.getenv("LLM_RATE_LIMIT_RETRY_DELAY", "10")))
    parser.add_argument("--server-retry-delay", type=float, default=float(os.getenv("LLM_SERVER_RETRY_DELAY", "5")))
    parser.add_argument("--network-retry-delay", type=float, default=float(os.getenv("LLM_NETWORK_RETRY_DELAY", "2")))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    data_dir = root / "data"
    ground_truth_dir = root / "ground_truth"
    requirements_path = root / REQUIREMENTS_FILE
    output_dir = root / "output"
    raw_dir = output_dir / "_raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    if not requirements_path.exists():
        raise RuntimeError(f"未找到原始需求文件: {requirements_path}")

    api_keys = get_api_keys()
    if not api_keys:
        raise RuntimeError("未找到 API Key，请在代码中的 DEFAULT_API_KEYS 填入，或设置 OPENAI_API_KEY / LLM_API_KEY / LLM_API_KEYS")

    requirements = load_requirements(requirements_path)
    prompts: dict[str, str] = {key: read_text(root / file_name) for key, file_name in PROMPT_FILES.items()}
    tasks = build_requirement_tasks(requirements, data_dir, ground_truth_dir)
    if args.limit > 0:
        tasks = tasks[: args.limit]
    if not tasks:
        raise RuntimeError(f"未在 {requirements_path} 中找到可处理需求")

    config = RunnerConfig(
        model=args.model,
        api_base=args.api_base,
        timeout_sec=args.timeout_sec,
        max_retries=args.max_retries,
        max_concurrent=args.max_concurrent,
        request_interval_seconds=args.request_interval_seconds,
        rate_limit_retry_delay=args.rate_limit_retry_delay,
        server_retry_delay=args.server_retry_delay,
        network_retry_delay=args.network_retry_delay,
        force=args.force,
    )

    key_pool = ApiKeyPool(api_keys)
    print(f"待处理文件数: {len(tasks)}")
    print(f"并发数: {max(config.max_concurrent, 1)}")
    print(f"请求最小间隔: {config.request_interval_seconds} 秒")
    results = asyncio.run(
        run_all_files(
            tasks=tasks,
            prompts=prompts,
            output_dir=output_dir,
            raw_dir=raw_dir,
            config=config,
            key_pool=key_pool,
        )
    )

    success_count = sum(1 for r in results if r.status == "success")
    failed_results = [r for r in results if r.status == "failed"]
    failed_count = len(failed_results)
    skipped_count = sum(1 for r in results if r.status == "skipped")

    for r in results:
        if r.status == "success":
            print(f"[SUCCESS] {r.file_name}")
        elif r.status == "skipped":
            print(f"[SKIPPED] {r.file_name}")
        else:
            print(f"[FAILED] {r.file_name} -> {r.error}")

    print(f"完成统计: 成功 {success_count}，失败 {failed_count}，跳过 {skipped_count}")
    print(f"结果目录: {output_dir}")
    if failed_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
