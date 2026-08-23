import sys
import os

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.llm.llm_chain import query_llm_chain, PROVIDER_STATUS, reset_provider_cooldown
from backend.pipeline import build_batch_enrichment_prompt

def run_verification_test():
    print("==================================================")
    print("STARTING FAILOVER CHAIN VERIFICATION TEST (25 PRODUCTS)")
    print("==================================================")
    
    # Reset any active cooldowns for fresh test
    reset_provider_cooldown()

    # Generate 25 sample products (8 batches of 3, plus 1 remaining)
    sample_products = []
    for i in range(1, 26):
        sample_products.append({
            "id": i,
            "mfg_part_num": f"PART-{1000+i}",
            "part_manuf": "Whirlpool Corporation" if i % 2 == 0 else "3M Company",
            "e1_brand": "Whirlpool" if i % 2 == 0 else "3M",
            "part_desc": f"Industrial Grade Assembly Part Item #{i} 120V 15A"
        })

    # Group into batches of 3
    batch_size = 3
    batches = [sample_products[i:i + batch_size] for i in range(0, len(sample_products), batch_size)]
    
    print(f"Created {len(batches)} batches from {len(sample_products)} products.")

    stats = {
        "gemini": {"attempts": 0, "success": 0, "fail": 0, "skipped": 0},
        "groq": {"attempts": 0, "success": 0, "fail": 0, "skipped": 0},
        "openrouter": {"attempts": 0, "success": 0, "fail": 0, "skipped": 0}
    }

    for b_idx, batch in enumerate(batches, 1):
        print(f"\n--- Processing Batch #{b_idx} ({len(batch)} items) ---")
        prompt = build_batch_enrichment_prompt(batch)
        
        # Track status before call
        gemini_was_disabled = PROVIDER_STATUS["gemini"]["is_disabled"]
        if gemini_was_disabled:
            stats["gemini"]["skipped"] += 1

        result = query_llm_chain(prompt, reason=f"Verification Test Batch {b_idx}")
        
        if result:
            print(f"Batch #{b_idx} SUCCESS: Received enriched payload ({len(result)} chars).")
        else:
            print(f"Batch #{b_idx} FAILED: All providers in chain failed.")

    print("\n==================================================")
    print("VERIFICATION RESULTS SUMMARY")
    print("==================================================")
    print(f"Gemini Skipped Count (after quota exhaustion): {stats['gemini']['skipped']}")
    print("Final Provider Cooldown Status:")
    for p, p_info in PROVIDER_STATUS.items():
        print(f"- {p}: disabled={p_info['is_disabled']}, reason='{p_info['disabled_reason']}'")
    print("==================================================")

if __name__ == "__main__":
    run_verification_test()
