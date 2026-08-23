import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.llm.llm_chain import query_llm_chain, PROVIDER_STATUS, reset_provider_cooldown
from backend.pipeline import build_batch_enrichment_prompt, extract_balanced_json_array

def run_verification():
    print("==================================================")
    print("STARTING VERIFICATION FOR ISSUES 1 & 2 (36 PRODUCTS)")
    print("==================================================")

    reset_provider_cooldown()

    # Generate 36 sample products (12 batches of 3)
    sample_products = []
    for i in range(1, 37):
        sample_products.append({
            "id": i,
            "mfg_part_num": f"PART-{2000+i}",
            "part_manuf": "Whirlpool Corporation" if i % 2 == 0 else "3M Company",
            "e1_brand": "Whirlpool" if i % 2 == 0 else "3M",
            "part_desc": f"Industrial Heavy Duty Assembly Part #{i} 240V 30A"
        })

    batch_size = 3
    batches = [sample_products[i:i + batch_size] for i in range(0, len(sample_products), batch_size)]
    print(f"Created {len(batches)} batches from {len(sample_products)} products.\n")

    raw_responses = []
    json_parse_success_count = 0
    json_parse_fail_count = 0

    for b_idx, batch in enumerate(batches, 1):
        print(f"--- Processing Batch #{b_idx}/12 ---")
        prompt = build_batch_enrichment_prompt(batch)
        
        result_text = query_llm_chain(prompt, reason=f"Verification Batch {b_idx}")
        
        if result_text:
            if len(raw_responses) < 5:
                raw_responses.append(result_text)
            
            # Check JSON parsing
            json_arr = extract_balanced_json_array(result_text)
            if json_arr:
                try:
                    parsed = json.loads(json_arr)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        json_parse_success_count += 1
                        print(f"Batch #{b_idx} JSON Parse: SUCCESS ({len(parsed)} items extracted)")
                    else:
                        json_parse_fail_count += 1
                        print(f"Batch #{b_idx} JSON Parse: FAILED (Empty array)")
                except Exception as pe:
                    json_parse_fail_count += 1
                    print(f"Batch #{b_idx} JSON Parse: FAILED ({pe})")
            else:
                json_parse_fail_count += 1
                print(f"Batch #{b_idx} JSON Parse: FAILED (No balanced JSON array found)")
        else:
            json_parse_fail_count += 1
            print(f"Batch #{b_idx} FAILED: All providers in chain failed")
        print()

    print("==================================================")
    print("VERIFICATION RESULTS SUMMARY")
    print("==================================================")
    print(f"Total Batches Processed: {len(batches)}")
    print(f"JSON Parsing Success Rate: {json_parse_success_count}/{len(batches)} ({json_parse_success_count/len(batches)*100:.1f}%)")
    print(f"JSON Parsing Failure Count: {json_parse_fail_count}/{len(batches)}")
    
    print("\nProvider Cooldown & Quota Status:")
    for p, p_info in PROVIDER_STATUS.items():
        print(f"- {p.upper()}: disabled={p_info['is_disabled']}, reason='{p_info['disabled_reason']}'")

    print("\n--------------------------------------------------")
    print("RAW OPENROUTER / LLM RESPONSE SAMPLES (UP TO 5):")
    print("--------------------------------------------------")
    for idx, sample in enumerate(raw_responses, 1):
        print(f"--- SAMPLE #{idx} ---")
        print(sample)
        print("--------------------------------------------------")

if __name__ == "__main__":
    run_verification()
