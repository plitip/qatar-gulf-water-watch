"""
One-off diagnostic: find the current Copernicus Marine dataset ID for
daily, gap-free, global chlorophyll-a (used to locate Qatar's coastal
waters). Writes only the matching dataset IDs to chl_dataset_ids.txt
so we don't have to scroll through the full catalogue dump.
"""

import copernicusmarine

catalogue = copernicusmarine.describe(contains=["CHL"], disable_progress_bar=True)

matches = []
for product in catalogue.products:
    for dataset in product.datasets:
        id_lower = dataset.dataset_id.lower()
        if "plankton" in id_lower or "chl" in id_lower:
            matches.append(f"{dataset.dataset_id}    (product: {product.product_id})")

with open("chl_dataset_ids.txt", "w") as f:
    if matches:
        f.write("\n".join(sorted(set(matches))))
    else:
        f.write("No matches found.")

print(f"Wrote {len(matches)} matching dataset id(s) to chl_dataset_ids.txt")
