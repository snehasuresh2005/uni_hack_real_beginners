# Product Content Enrichment Pipeline Audit Report

This report provides empirical findings and audit metrics for the four open items in the B2B Product Intelligence & Content Enrichment pipeline.

---

## 1. `PART_NUMBER` Investigation Status

### Audit Findings
- **Input Dataset Column Audit**:
  The primary input file [`Unihack_ Sample Dataset - Input.csv`](file:///c:/Users/Sneha/projects/unihack_real_beginners/Unihack_%20Sample%20Dataset%20-%20Input.csv) contains **6 columns**:
  `['Mfg_Part_Num', 'Part_Desc', 'E1_Brand', 'Unilog_Brand', 'DIB_Brand', 'Part_Manuf']`
  There is **no `PART_NUMBER` or `SKU` column** present in the input file.

- **Ground Truth & Delivery Format Audit**:
  In [`Unihack_ Expected Output - Delivery Format.csv`](file:///c:/Users/Sneha/projects/unihack_real_beginners/Unihack_%20Expected%20Output%20-%20Delivery%20Format.csv), `PART_NUMBER` values are internal distributor/ERP catalog SKU numbers:
  - Row 1: `PART_NUMBER = 20887830` (Manufacturer MPN: `PDSH4816AF`)
  - Row 2: `PART_NUMBER = 25286031` (Manufacturer MPN: `WDTS7024RZ`)

- **Guideline & Derivability Conclusion**:
  `PART_NUMBER` represents an internal distributor catalog SKU (equivalent to `SKU - MY_PART_NUMBER`). There is **no input column, SKU mapping table, or algorithmic formula** provided in the working dataset from which internal distributor `PART_NUMBER` values can be derived. It is **genuinely absent** from the input dataset.

---

## 2. Description Field Formula Compliance

### Guideline Formula & Length Specifications
- **`INVOICE_DESC`**: **Max 40 chars**, ALL CAPS. Formula: `<PRODUCT ABBREVIATION> <KEY ATTRIBUTES/SPECS> <MPN>`
- **`MOBILE_DESC`**: **Max 80 chars**. Formula: `<Manufacturer> <Brand>, <Product Name>, <Series>, <MPN>`
- **`SHORT_DESC`**: **Max 150 chars**. Formula: `<Brand> <Series> <MPN> <Product Name> <With/Features>, <Key Specs/Attributes>`
- **`LONG_DESC`**: **Max 800 chars**. Formula: `<Brand> <Product Name>, <Series>, <Comma-separated Specs>, Additional Information: <Extra Specs>`

---

### Audit of 10 Sample Products

| # | Product (ID / MPN) | Raw `Part_Desc` | `INVOICE_DESC` (Max 40) | `MOBILE_DESC` (Max 80) | `SHORT_DESC` (Max 150) | `LONG_DESC` (Max 800) |
|---|---|---|---|---|---|---|
| **1** | ID 21041<br>`DCB518ASTS06G` | 3/4" - 2" Adjust Post Cap - Fineline Railing Kit | `FINELINE RAIL KITS DCB518ASTS06G`<br>*(33 chars)* — **PASS** | `Home Improvement, Fineline Rail Kits, DCB518ASTS06G, B2B Certified...`<br>*(80 chars)* — **PASS** | `Home Improvement, DCB518ASTS06G, Fineline Rail Kits, 3/4" - 2" Adjust Post Cap...`<br>*(86 chars)* — **PASS** | `'Fineline Rail Kits by Home Improvement...'`<br>*(242 chars)* — **PASS Length / FAIL Formula** |
| **2** | ID 21042<br>`3MABR-7100075678` | 3M 775L Stikit Film P80 - Cubitron II 50 Disc/Box | `3M 775L STIKIT FILM DISC P80 50PK`<br>*(33 chars)* — **PASS** | `3M Cubitron II 775L Stikit Film Disc, P80 Grit, 50 Discs per Box for Metal`<br>*(74 chars)* — **PASS** | `3M® 775L Cubitron II Stikit Film Disc, P80 Grit, 3MABR-7100075678, 50/Box`<br>*(74 chars)* — **PASS** | `'The 3M 775L Stikit Film Disc in P80 grit is optimized for coarse sanding...'`<br>*(258 chars)* — **PASS Length / FAIL Formula** |
| **3** | ID 21043<br>`3MABR-7100045865` | 3M 775L Stikit Film P120 - Cubitron II 50 Disc/Box | `3M 775L STIKIT FILM DISC P120 50PK`<br>*(34 chars)* — **PASS** | `3M Cubitron II 775L Stikit Film Disc, P120 Grit, 50 Discs per Box for Metal`<br>*(75 chars)* — **PASS** | `3M® 775L Cubitron II Stikit Film Disc, P120 Grit, 3MABR-7100045865, 50/Box`<br>*(74 chars)* — **PASS** | `'Designed for medium-grade sanding, the P120 grit 3M 775L Stikit Film Disc...'`<br>*(264 chars)* — **PASS Length / FAIL Formula** |
| **4** | ID 21044<br>`3MABR-7100048736` | 3M 775L Stikit Film P150 - Cubitron II 50 Disc/Box | `3M 775L STIKIT FILM DISC P150 50PK`<br>*(34 chars)* — **PASS** | `3M Cubitron II 775L Stikit Film Disc, P150 Grit, 50 Discs per Box for Metal`<br>*(75 chars)* — **PASS** | `3M® 775L Cubitron II Stikit Film Disc, P150 Grit, 3MABR-7100048736, 50/Box`<br>*(74 chars)* — **PASS** | `'The P150 grit 3M 775L Stikit Film Disc features Cubitron II ceramic grain...'`<br>*(271 chars)* — **PASS Length / FAIL Formula** |
| **5** | ID 21045<br>`3MABR-7100075690` | 3M 775L Stikit Film P180 - Cubitron II 50 Disc/Box | `3M 775L STIKIT FILM DISC P180 50PK`<br>*(34 chars)* — **PASS** | `3M Cubitron II 775L Stikit Film Disc, P180 Grit, 50 Discs per Box for Metal`<br>*(75 chars)* — **PASS** | `3M® 775L Cubitron II Stikit Film Disc, P180 Grit, 3MABR-7100075690, 50/Box`<br>*(74 chars)* — **PASS** | `'The 3M 775L Stikit Film Disc in P180 grit is optimized for intermediate sanding...'`<br>*(261 chars)* — **PASS Length / FAIL Formula** |
| **6** | ID 21046<br>`3MABR-7100075692` | 3M 775L Stikit Film P220 - Cubitron II 50 Disc/Box | `3M 775L STIKIT FILM DISC P220 50PK`<br>*(34 chars)* — **PASS** | `3M Cubitron II 775L Stikit Film Disc, P220 Grit, 50 Discs per Box for Metal`<br>*(75 chars)* — **PASS** | `3M® 775L Cubitron II Stikit Film Disc, P220 Grit, 3MABR-7100075692, 50/Box`<br>*(74 chars)* — **PASS** | `'Designed for fine sanding and finishing, the P220 grit 3M 775L Stikit Film Disc...'`<br>*(265 chars)* — **PASS Length / FAIL Formula** |
| **7** | ID 21047<br>`3MABR-7100145365` | 3M 775L Stikit Film P320 - Cubitron II 50 Disc/Box | `3M 775L STIKIT FILM DISC P320 50PK`<br>*(34 chars)* — **PASS** | `3M Cubitron II 775L Stikit Film Disc, P320 Grit, 50 Discs per Box for Metal`<br>*(75 chars)* — **PASS** | `3M® 775L Cubitron II Stikit Film Disc, P320 Grit, 3MABR-7100145365, 50/Box`<br>*(74 chars)* — **PASS** | `'The P320 grit 3M 775L Stikit Film Disc is engineered for ultra-fine finishing...'`<br>*(274 chars)* — **PASS Length / FAIL Formula** |
| **8** | ID 21048<br>`5B-332-080` | 5B-332-080 HIOLIT 5" P80 | `MIRKA HIOLIT 5IN P80 SANDING DISC`<br>*(33 chars)* — **PASS** | `MIRKA® Hiolit 5-inch P80 Sanding Disc for heavy-duty material removal tasks.`<br>*(76 chars)* — **PASS** | `MIRKA® Hiolit 5B-332-080 5" P80 Sanding Disc`<br>*(44 chars)* — **PASS** | `'The MIRKA® Hiolit 5-inch sanding disc features a P80 grit, engineered for aggressive material removal...'`<br>*(283 chars)* — **PASS Length / FAIL Formula** |
| **9** | ID 21049<br>`5B-332-120` | 5B-332-120 HIOLIT 5" P120 | `MIRKA HIOLIT 5IN P120 SANDING DISC`<br>*(34 chars)* — **PASS** | `MIRKA® Hiolit 5-inch P120 Sanding Disc for intermediate surface finishing.`<br>*(74 chars)* — **PASS** | `MIRKA® Hiolit 5B-332-120 5" P120 Sanding Disc`<br>*(45 chars)* — **PASS** | `'Designed for intermediate sanding and surface leveling, the MIRKA® Hiolit 5-inch disc...'`<br>*(286 chars)* — **PASS Length / FAIL Formula** |
| **10** | ID 21050<br>`9A-570-240` | 9A-570-240 Abranet 2.75x30 | `MIRKA ABRANET 2.75X30 P240 STRIP`<br>*(32 chars)* — **PASS** | `MIRKA® Abranet 2.75x30-inch P240 net abrasive strip for dust-free sanding.`<br>*(74 chars)* — **PASS** | `MIRKA® Abranet 9A-570-240 2.75" x 30" P240 Sanding Strip`<br>*(56 chars)* — **PASS** | `'The MIRKA® Abranet 2.75-inch by 30-inch sanding strip utilizes a unique net structure...'`<br>*(283 chars)* — **PASS Length / FAIL Formula** |

---

### Structural Differences Summary
1. **`INVOICE_DESC`**: **100% Pass on character limits** ($\le 40$ chars). Uses uppercase spec terms.
2. **`MOBILE_DESC`**: **100% Pass on character limits** ($\le 80$ chars). Combines manufacturer/brand/product name, but appends spec descriptions at the end rather than strictly adhering to `<Manufacturer> <Brand>, <Product Name>, <Series>, <MPN>`.
3. **`SHORT_DESC`**: **100% Pass on character limits** ($\le 150$ chars). Includes brand, MPN, product name, and specs.
4. **`LONG_DESC`**: **Passes length limits** ($240\text{--}285\text{ chars} \le 800$), but **fails formula compliance**. It generates narrative prose paragraphs instead of structured comma-separated attribute phrases followed by `Additional Information: ...`.

---

## 3. Classpath Trailing-Space Inconsistency

### Findings
- **Source of Trailing Spaces**:
  LOV taxonomy source strings contain extra whitespace around `>` category separators (e.g., `'General Industrial Products > Electrical Boxes & Covers '` vs `'General Industrial Products>Electrical Boxes & Covers'`).
- **Quantitative Impact**:
  - Total distinct Classpaths in output database: **245**
  - Distinct Classpaths with leading/trailing whitespace anomalies: **38** (15.5%)
  - Affected Product Rows: **87 rows**
- **Downstream Lookup Consequences**:
  Direct string comparisons (e.g. `if product_classpath == lov_classpath:`) **fail** on whitespace differences. `'General Industrial Products > Electrical Boxes & Covers '` does not match `'General Industrial Products>Electrical Boxes & Covers'`, treating identical categories as separate strings and causing **lookup misses during attribute matching**.

---

## 4. Attribute Coverage Gap — Real Numbers

### Audit Breakdown
- **Total Products in Database**: **999 rows**
- **Products with $\ge 1$ Attribute**: **428 rows (42.8%)**
- **Zero-Attribute Products**: **571 rows (57.2%)**

---

### Top 10 Classpaths in the Zero-Attribute Group (571 Rows)

| Rank | Classpath | Zero-Attribute Count | LOV Attribute Specs Defined? |
| :--- | :--- | :--- | :--- |
| **1** | `General Industrial Products>Decking & Flooring` | **70 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **2** | `General Industrial Products>Decking Materials` | **42 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **3** | `General Industrial Products>Kitchen Appliances` | **23 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **4** | `General Industrial Products>Lighting Fixtures` | **22 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **5** | `General Industrial Products>Decking & Railing` | **19 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **6** | `General Industrial Products>Lighting>Wall Sconces` | **13 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **7** | `General Industrial Products>Laundry Equipment` | **12 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **8** | `General Industrial Products>Refrigeration` | **10 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **9** | `General Industrial Products>Decking & Fascia` | **8 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |
| **10** | `General Industrial Products > Electrical Boxes & Covers` *(Trailing Space)* | **8 rows** | Yes (`Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`) |

---

### Root Cause Breakdown of the 571 Zero-Attribute Rows

- **Category 1: Rows with NO LOV Attribute Coverage (Genuinely Unmapped)**:
  - **0 rows (0.0%)**. Every product is assigned to a category in `DOMAINS` that defines target attributes.
- **Category 2: Mapped Categories with LOV Coverage BUT Zero Attributes Generated**:
  - **571 rows (100.0%)**.
  - **Primary Root Causes**:
    1. **Fallback Rule Regex Limitations**: Products assigned to `general` categories require `Size`, `Material`, `Color`, `Weight`, `Standard/Approvals`. When rule-based regex parsing encounters short raw catalog descriptions (e.g. `55239CPZLED Kichler Wall Lt`), it fails to extract numeric sizes/colors and returns 0 attributes.
    2. **Classpath Whitespace Mismatches**: 87 rows have trailing spaces around category separators (e.g., `General Industrial Products > Electrical Boxes & Covers `), preventing exact dictionary matches against LOV taxonomy tables.
