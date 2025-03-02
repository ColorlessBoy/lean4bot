from pathlib import Path
import json

def is_proof_successful(file_path: Path) -> bool:
    """Check if the proof in the file was successful"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for msg in reversed(data):
                if msg.get("role") == "user":
                    return "证明完全正确" in msg.get("content", "")
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    # Get the directory containing the JSON files
    root_dir = Path(__file__).parent / "TestDeepseekV3"
    
    # Count files and successful proofs
    total_files = 0
    successful_proofs = 0
    
    # Process each JSON file
    for file in root_dir.glob("*.json"):
        total_files += 1
        if is_proof_successful(file):
            successful_proofs += 1
            print(f"✓ {file.name}")
        else:
            print(f"✗ {file.name}")
    
    # Calculate and display statistics
    success_rate = (successful_proofs / total_files * 100) if total_files > 0 else 0
    print("\nStatistics:")
    print(f"Total files: {total_files}")
    print(f"Successful proofs: {successful_proofs}")
    print(f"Success rate: {success_rate:.2f}%")

if __name__ == "__main__":
    main()