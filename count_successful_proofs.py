from pathlib import Path
import json
from initPrompt import initPrompt

def is_proof_successful(file_path: Path) -> bool:
    """Check if the proof in the file was successful"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Look for the last message
            for msg in reversed(data):
                if msg.get("role") == "user":
                    return "证明完全正确" in msg.get("content", ""), len(data), "连续3次生成重复代码" in msg.get("content", ""), "上一题你证明正确。请听下一题(请注意回答的code字段代码要保持原题目不变，不要忽略小于号）" in msg.get("content", "")
        return False, 0
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False, 0

def main():
    # Get the directory containing the JSON files
    root_dir = Path(__file__).parent / "TestQianwenPlus"
    
    # Count files and successful proofs
    total_files = 0
    successful_proofs = 0
    success_length = 0
    base_length = len(initPrompt)
    success_count_zero_shot = 0
    repeat_times = 0
    
    # Process each JSON file
    for file in root_dir.glob("*.json"):
        success, length, is_repeat, invalid = is_proof_successful(file)
        total_files += 0 if invalid else 1
        if success:
            successful_proofs += 1
            success_length += (length - base_length)
            if length - base_length == 2:
                success_count_zero_shot += 1
            print(f"✓ {file.name}")
        else:
            if is_repeat:
                repeat_times += 1
            print(f"✗ {file.name}")
    
    # Calculate and display statistics
    success_rate = (successful_proofs / total_files * 100) if total_files > 0 else 0
    print("\nStatistics:")
    print(f"Total files: {total_files}")
    print(f"Successful proofs: {successful_proofs}")
    print(f"Success rate: {success_rate:.2f}%")
    print(f"Average length: {success_length / successful_proofs:.2f}")
    print(f"Zero-shot successes: {success_count_zero_shot}")
    print(f"Repeat times: {repeat_times}")

if __name__ == "__main__":
    main()