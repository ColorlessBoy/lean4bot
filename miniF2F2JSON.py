import re


def extract_theorem_name(theorem_line: str) -> str:
    """从定理行中提取定理名称"""
    match = re.match(r"theorem\s+([^\s(]+)", theorem_line)
    if match:
        return match.group(1)
    return None


def main():
    # 读取Test.lean文件
    with open("miniF2F-lean4/MiniF2F/Test.lean", "r") as f:
        content = f.readlines()

    theorems = []
    preTheorem = ""
    preTheoremName = ""
    for line in content:
        line = line.strip()
        if line.startswith("theorem"):
            preTheorem = line
            preTheoremName = extract_theorem_name(line)
        else:
            preTheorem += line
        if line.endswith("by sorry"):
            theorems.append({"name": preTheoremName, "code": preTheorem[:-5]})
            preTheorem = ""

    # 保存为JSON文件
    import json

    with open("theorems.json", "w", encoding="utf-8") as f:
        json.dump(theorems, f, ensure_ascii=False, indent=2)

    print(f"Successfully extracted {len(theorems)} theorems")


if __name__ == "__main__":
    main()
