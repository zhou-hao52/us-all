import os
import json
import time
import requests
from pathlib import Path

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re

BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
API_KEYS = ["sk-68207b5922064651adbf6b5e2baa7fbc"]
MODEL = "qwen3-coder-plus"

REQUEST_INTERVAL_SECONDS = 2
RATE_LIMIT_RETRY_DELAY = 10
RETRY_BACKOFF_FACTOR = 2

DISABLE_THINK_MODE = True

BASE_DIR = Path(__file__).resolve().parent
PROMPT_TEMPLATE_PATH = BASE_DIR / "US_prompt.md"
INPUT_JSON_PATH = BASE_DIR / "requirements.json"
OUTPUT_JSON_PATH = BASE_DIR / "requirements_with_llm.json"

REQUEST_DIR = BASE_DIR / "request" / "iot_tasks"
RESPONSE_DIR = BASE_DIR / "response" / "iot_tasks"

current_key_index = 0

def sanitize_filename(filename: str) -> str:
    illegal_chars = r'[\/:*?"<>|]'
    sanitized = re.sub(illegal_chars, '_', filename)
    max_length = 100
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    sanitized = sanitized.strip().strip('_')
    return sanitized if sanitized else "unnamed_demand"

def extract_json_from_code_block(content: str) -> str:
    if not content:
        return "{}"
    json_pattern = r'```(?:json)?\s*(.*?)\s*```'
    matches = re.search(json_pattern, content, re.DOTALL)
    json_str = matches.group(1).strip() if matches else content.strip()
    try:
        json_data = json.loads(json_str)
        return json.dumps(json_data, ensure_ascii=False, indent=4)
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {str(e)}，使用原始内容")
        return json_str

def get_model_type() -> str:
    if not MODEL:
        raise ValueError("MODEL配置不能为空")
    model_lower = MODEL.lower()
    if "qwen3-coder" in model_lower:
        return "qwen3-coder"
    elif "deepseek-chat" in model_lower:
        return "deepseek-chat"
    elif "gpt-5-2025-08-07" in model_lower:
        return "gpt-5-2025-08-07"
    elif "gemini-2.5-pro" in model_lower:
        return "gemini-2.5-pro"
    elif "kimi" in model_lower:
        return "kimi"
    elif "glm4.7" in model_lower:
        return "glm4.7"
    elif "claude" in model_lower:
        return "claude"
    else:
        raise ValueError(f"不支持的模型：{MODEL}")

def process_prompt_for_think_mode(prompt: str) -> str:
    model_type = get_model_type()
    if not DISABLE_THINK_MODE:
        return prompt
    if model_type == "qwen3-coder":
        return prompt + "\n/no_think"
    return prompt

def adapt_payload_for_model(payload: Dict, prompt: str) -> Dict:
    model_type = get_model_type()
    if DISABLE_THINK_MODE:
        if model_type == "deepseek-chat":
            payload["extra_body"] = payload.get("extra_body", {})
            payload["extra_body"]["thinking"] = {"type": "disabled"}
        elif model_type == "glm4.7":
            payload["thinking"] = {"type": "disabled"}
        elif model_type == "gpt-5-2025-08-07":
            payload["temperature"] = 0
        elif model_type == "gemini-2.5-pro":
            payload["temperature"] = 0
    return payload

@dataclass
class IoTRequirementItem:
    id: int
    initialDemand: str
    detailedDemand: str
    prompt_template: str

    @property
    def prompt(self) -> str:
        user_requirements = f"## Initial Demand: {self.initialDemand}\n## Detailed Demand: {self.detailedDemand}"
        base_prompt = self.prompt_template.replace("{user_requirements}", user_requirements)
        return process_prompt_for_think_mode(base_prompt)

    @property
    def response_filename(self) -> str:
        sanitized_name = sanitize_filename(self.initialDemand)
        return f"{sanitized_name}.json"

    @property
    def request_filename(self) -> str:
        sanitized_name = sanitize_filename(self.initialDemand)
        return f"{sanitized_name}_prompt.txt"

def load_file_safely(file_path: Path, mode: str = "r", encoding: str = "utf-8", data: Any = None) -> Optional[Any]:
    try:
        if mode == "r":
            with open(file_path, mode, encoding=encoding) as f:
                if file_path.suffix == ".json":
                    return json.load(f)
                return f.read().strip()
        elif mode == "w":
            with open(file_path, mode, encoding=encoding) as f:
                if isinstance(data, str) and file_path.suffix == ".json":
                    f.write(data)
                elif isinstance(data, (dict, list)):
                    json.dump(data, f, ensure_ascii=False, indent=4)
                else:
                    f.write(data if data else "")
            return None
    except Exception as e:
        print(f"文件操作失败 {file_path}: {str(e)}")
        return None

def load_prompt_template() -> str:
    if not PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Prompt模板文件不存在: {PROMPT_TEMPLATE_PATH}")
    content = load_file_safely(PROMPT_TEMPLATE_PATH)
    if not content:
        raise ValueError(f"Prompt模板文件为空: {PROMPT_TEMPLATE_PATH}")
    return content

def load_iot_requirements() -> List[Dict[str, Any]]:
    if not INPUT_JSON_PATH.exists():
        raise FileNotFoundError(f"输入需求JSON不存在: {INPUT_JSON_PATH}")
    content = load_file_safely(INPUT_JSON_PATH)
    if not content:
        raise ValueError(f"输入JSON文件为空: {INPUT_JSON_PATH}")
    try:
        data = json.loads(content) if isinstance(content, str) else content
    except json.JSONDecodeError as e:
        raise ValueError(f"输入JSON格式错误: {str(e)}")
    if "iotUserStoryRequirements" not in data:
        raise ValueError("输入JSON缺少核心字段：iotUserStoryRequirements")
    return data["iotUserStoryRequirements"]

def save_llm_results_to_json(requirements: List[Dict[str, Any]], results: Dict[int, str]):
    output_data = {
        "iotUserStoryRequirements": [
            {**item, "llmResponse": results.get(item["id"], f"Error: 无响应 for id {item['id']}")}
            for item in requirements
        ]
    }
    try:
        with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
        print(f"汇总结果已保存至: {OUTPUT_JSON_PATH}")
    except Exception as e:
        print(f"保存汇总结果失败: {str(e)}")

def get_request_file_path(item: IoTRequirementItem) -> Path:
    return REQUEST_DIR / item.request_filename

def get_response_file_path(item: IoTRequirementItem) -> Path:
    return RESPONSE_DIR / item.response_filename

def request_exists(item: IoTRequirementItem) -> bool:
    return get_request_file_path(item).exists()

def response_exists(item: IoTRequirementItem) -> bool:
    return get_response_file_path(item).exists()

def save_request(item: IoTRequirementItem, prompt: str):
    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    load_file_safely(get_request_file_path(item), mode="w", encoding="utf-8", data=prompt)

def save_response(item: IoTRequirementItem, llm_response: str):
    RESPONSE_DIR.mkdir(parents=True, exist_ok=True)
    clean_json_content = extract_json_from_code_block(llm_response)
    load_file_safely(
        get_response_file_path(item),
        mode="w",
        encoding="utf-8",
        data=clean_json_content
    )
    print(f"单个响应已保存至: {get_response_file_path(item)}")

def get_next_api_key() -> tuple:
    global current_key_index
    if not API_KEYS:
        return None, -1
    if current_key_index >= len(API_KEYS):
        current_key_index = 0
    key = API_KEYS[current_key_index]
    index = current_key_index
    current_key_index += 1
    return key, index

def call_llm_with_retry(prompt: str) -> tuple:
    if not API_KEYS:
        return False, "错误：API_KEYS配置为空"

    tried_keys = set()
    retry_count = 0

    while len(tried_keys) < len(API_KEYS):
        api_key, key_index = get_next_api_key()
        if not api_key or key_index in tried_keys:
            continue
        tried_keys.add(key_index)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        base_payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "stream": False,
            "max_tokens": 8192
        }

        payload = adapt_payload_for_model(base_payload, prompt)
        time.sleep(REQUEST_INTERVAL_SECONDS)

        retry_delay = RATE_LIMIT_RETRY_DELAY * (RETRY_BACKOFF_FACTOR ** retry_count)
        retry_count += 1

        try:
            response = requests.post(
                BASE_URL,
                headers=headers,
                json=payload,
                timeout=600
            )
            
            print(f"API Key {key_index + 1} 响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and result['choices']:
                    content = result["choices"][0].get("message", {}).get("content", "")
                    return True, content
                else:
                    return False, f"响应无choices字段: {response.text[:500]}"
            elif response.status_code == 429:
                print(f"API Key {key_index + 1} 限流，等待 {retry_delay} 秒重试...")
                time.sleep(retry_delay)
                continue
            elif response.status_code >= 500:
                print(f"API Key {key_index + 1} 服务器错误（{response.status_code}），等待 {retry_delay} 秒重试...")
                time.sleep(retry_delay)
                continue
            else:
                print(f"API Key {key_index + 1} 失败: HTTP {response.status_code}")
                print(f"错误详情: {response.text}")
                continue
        except requests.exceptions.Timeout:
            print(f"API Key {key_index + 1} 调用超时，跳过该密钥")
            continue
        except Exception as e:
            print(f"API Key {key_index + 1} 调用异常: {str(e)}")
            continue

    return False, f"所有 {len(API_KEYS)} 个API密钥调用均失败"

def process_requirement(item: IoTRequirementItem) -> tuple:
    if response_exists(item):
        response_content = load_file_safely(get_response_file_path(item))
        if response_content:
            print(f"[跳过] {item.response_filename}（响应已存在）")
            return (item.id, json.dumps(response_content, ensure_ascii=False), True)
        else:
            print(f"[警告] {item.response_filename} 响应文件损坏，重新处理")

    if request_exists(item):
        prompt = load_file_safely(get_request_file_path(item))
        if not prompt:
            prompt = item.prompt
            save_request(item, prompt)
        print(f"[加载缓存] {item.request_filename} 的请求prompt")
    else:
        prompt = item.prompt
        save_request(item, prompt)
        print(f"[生成请求] {item.request_filename}，已保存至缓存")

    print(f"[开始处理] ID:{item.id} - {item.initialDemand[:50]}...")
    success, response = call_llm_with_retry(prompt)

    if success:
        save_response(item, response)
        print(f"[处理完成] ID:{item.id} - {item.response_filename}")
    else:
        print(f"[处理失败] ID:{item.id} - {item.initialDemand[:50]}...: {response}")
    return (item.id, response, success)

def run_all_requirements(requirements: List[IoTRequirementItem]):
    llm_results = {}
    success_count = failed_count = skipped_count = 0
    
    for item in requirements:
        req_id, response, success = process_requirement(item)
        if success:
            llm_results[req_id] = response
            if response_exists(item):
                skipped_count += 1
            else:
                success_count += 1
        else:
            llm_results[req_id] = f"处理失败: {response}"
            failed_count += 1

    print(f"\n===== 批量处理完成统计 =====")
    print(f"总需求数：{len(requirements)}")
    print(f"成功：{success_count} | 失败：{failed_count} | 跳过（断点续跑）：{skipped_count}")
    print(f"单个响应文件保存路径：{RESPONSE_DIR}")
    print(f"汇总结果文件路径：{OUTPUT_JSON_PATH}")
    print(f"============================")

    original_requirements = load_iot_requirements()
    save_llm_results_to_json(original_requirements, llm_results)

def validate_config():
    if not BASE_URL:
        raise ValueError("配置错误：BASE_URL不能为空")
    if not API_KEYS or all(not key.strip() for key in API_KEYS):
        raise ValueError("配置错误：API_KEYS不能为空")
    if not MODEL:
        raise ValueError("配置错误：MODEL不能为空")
    if not PROMPT_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Prompt模板文件不存在: {PROMPT_TEMPLATE_PATH}")
    if not INPUT_JSON_PATH.exists():
        raise FileNotFoundError(f"输入JSON文件不存在: {INPUT_JSON_PATH}")

def main():
    print("=" * 80)
    print("IoT需求LLM批量处理工具 (requests版本)")
    print("=" * 80)

    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        validate_config()
        model_type = get_model_type()
        print(f"模型：{MODEL}（{model_type}）| Think模式：{'已关闭' if DISABLE_THINK_MODE else '已开启'}")
        print(f"Temperature：0 | API密钥数量：{len([k for k in API_KEYS if k.strip()])}")
        print(f"API地址：{BASE_URL}")
        print(f"Prompt模板：{PROMPT_TEMPLATE_PATH}")
        print(f"输入文件：{INPUT_JSON_PATH}")
        print(f"单个响应保存路径：{RESPONSE_DIR}")
        print("=" * 80)

        prompt_template = load_prompt_template()
        raw_requirements = load_iot_requirements()
        print(f"\n成功加载 {len(raw_requirements)} 个IoT需求项")

        requirement_items = [
            IoTRequirementItem(
                id=item["id"],
                initialDemand=item["initialDemand"],
                detailedDemand=item["detailedDemand"],
                prompt_template=prompt_template
            ) for item in raw_requirements
        ]

        if not requirement_items:
            print("无需求项可处理，程序退出")
            return

        print(f"\n开始批量处理...\n")
        run_all_requirements(requirement_items)

    except Exception as e:
        print(f"\n程序执行异常：{str(e)}")
        return

    print(f"\n" + "=" * 80)
    print("所有任务处理完成！")
    print(f"单个响应文件（纯JSON）：{RESPONSE_DIR}")
    print(f"汇总结果文件：{OUTPUT_JSON_PATH}")
    print("=" * 80)

if __name__ == "__main__":
    main()
