from steps.step1_extractor import extract_all_users, load_dataset
from steps.step2_timeline import run_step2
from steps.step3_candidates import run_step3
from steps.step4_reasoner import run_step4

if __name__ == "__main__":
    print("=== Step 1: Extracting events ===")
    dataset = load_dataset("data/askfirst_synthetic_dataset.json")
    extract_all_users(dataset)

    print("\n=== Step 2: Building timelines ===")
    run_step2()

    print("\n=== Step 3: Generating candidates ===")
    run_step3()

    print("\n=== Step 4: Reasoning patterns ===")
    run_step4()

    print("\nDone. Run: streamlit run steps/step5_ui.py")