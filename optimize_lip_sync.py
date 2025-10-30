#!/usr/bin/env python3
"""
数字人唇形同步优化脚本
自动应用最佳配置以改善唇形同步效果
"""

import os
import sys
from pathlib import Path

def detect_hardware():
    """检测硬件性能"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB

            if "RTX 3090" in gpu_name or "RTX 4090" in gpu_name or gpu_memory >= 20:
                return "high"
            elif "RTX 3080" in gpu_name or "RTX 3070" in gpu_name or gpu_memory >= 10:
                return "medium"
            else:
                return "low"
        else:
            return "cpu_only"
    except:
        return "unknown"

def generate_env_config(performance_level):
    """根据硬件性能生成配置"""

    configs = {
        "high": """
# 高性能GPU配置 - 最佳同步效果
ANY4DH_FPS=25
ANY4DH_BATCH_SIZE=6
ANY4DH_TTS=indextts
INDEX_TTS_FAST_ENABLED=true
INDEX_TTS_FAST_MAX_TOKENS=50
INDEX_TTS_FAST_BATCH_SIZE=6
""",
        "medium": """
# 中等性能GPU配置 - 平衡性能和同步
ANY4DH_FPS=20
ANY4DH_BATCH_SIZE=4
ANY4DH_TTS=indextts
INDEX_TTS_FAST_ENABLED=true
INDEX_TTS_FAST_MAX_TOKENS=30
INDEX_TTS_FAST_BATCH_SIZE=4
""",
        "low": """
# 低性能GPU配置 - 优先稳定性
ANY4DH_FPS=15
ANY4DH_BATCH_SIZE=2
ANY4DH_TTS=edgetts
INDEX_TTS_FAST_ENABLED=false
""",
        "cpu_only": """
# 仅CPU配置 - 基础功能
ANY4DH_FPS=10
ANY4DH_BATCH_SIZE=1
ANY4DH_TTS=edgetts
INDEX_TTS_FAST_ENABLED=false
"""
    }

    return configs.get(performance_level, configs["medium"])

def backup_env_file():
    """备份现有.env文件"""
    env_file = Path(".env")
    backup_file = Path(".env.backup")

    if env_file.exists():
        content = env_file.read_text(encoding='utf-8')
        backup_file.write_text(content, encoding='utf-8')
        print(f"✅ 已备份现有配置到 {backup_file}")
        return True
    return False

def update_env_config(config_content):
    """更新.env文件"""
    env_file = Path(".env")

    # 读取现有内容
    if env_file.exists():
        content = env_file.read_text(encoding='utf-8')
    else:
        content = ""

    # 移除相关的旧配置
    lines_to_remove = [
        "ANY4DH_FPS=", "ANY4DH_BATCH_SIZE=", "INDEX_TTS_FAST_ENABLED=",
        "INDEX_TTS_FAST_MAX_TOKENS=", "INDEX_TTS_FAST_BATCH_SIZE="
    ]

    existing_lines = content.split('\n')
    filtered_lines = []

    for line in existing_lines:
        should_remove = False
        for pattern in lines_to_remove:
            if line.strip().startswith(pattern):
                should_remove = True
                break
        if not should_remove:
            filtered_lines.append(line)

    # 添加新配置
    new_content = '\n'.join(filtered_lines).rstrip() + '\n' + config_content

    # 写入文件
    env_file.write_text(new_content, encoding='utf-8')
    print(f"✅ 已更新配置文件 {env_file}")

def main():
    print("🎭 数字人唇形同步优化工具")
    print("=" * 50)

    # 检测硬件
    print("🔍 正在检测硬件性能...")
    performance = detect_hardware()

    performance_names = {
        "high": "高性能 (RTX 3080+)",
        "medium": "中等性能 (GTX 1660+)",
        "low": "低性能 (GTX 1050+)",
        "cpu_only": "仅CPU",
        "unknown": "未知硬件"
    }

    print(f"📊 检测到硬件级别: {performance_names.get(performance, '未知')}")

    # 生成配置
    config = generate_env_config(performance)

    print("\n📝 将应用以下优化配置:")
    print("-" * 30)
    print(config.strip())
    print("-" * 30)

    # 询问用户
    response = input("\n是否应用此配置? (y/n): ").lower().strip()

    if response == 'y' or response == 'yes':
        print("\n💾 正在更新配置...")

        # 备份现有配置
        backup_env_file()

        # 更新配置
        update_env_config(config)

        print("\n✨ 优化完成!")
        print("\n📋 后续步骤:")
        print("1. 重启 any4any 服务")
        print("2. 测试语音聊天功能")
        print("3. 观察唇形同步效果")
        print("\n💡 提示: 如果效果不理想，可以尝试手动调整 .env 文件中的参数")

    else:
        print("\n❌ 已取消优化配置")

if __name__ == "__main__":
    main()